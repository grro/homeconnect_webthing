import logging
import requests
import json
from time import sleep
from typing import List, Dict, Any
from datetime import datetime, timedelta
from homeconnect_webthing.auth import Auth
from homeconnect_webthing.eventstream import EventListener
from homeconnect_webthing.utils import print_duration, is_success



class OfflineException(Exception):
    pass


class Appliance(EventListener):

    def __init__(self, device_uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str):
        self._device_uri = device_uri
        self._auth = auth
        self.name = name
        self.device_type = device_type
        self.haid = haid
        self.brand = brand
        self.vib = vib
        self.enumber = enumber
        self.__value_changed_listeners = set()
        self.last_refresh = datetime.now() - timedelta(hours=9)
        self.remote_start_allowed = False
        self.startable = False
        self.started = False
        self.program_remote_control_active = False
        self._program_selected = ""
        self.program_remaining_time_sec = 0
        self.__program_progress = 0
        self.__program_local_control_active = ""
        self._power = ""
        self._door = ""
        self._operation = ""
        self.__program_active = ""
        self.child_lock = False
        self._reload_status_and_settings()

    def id(self) -> str:
        return self.haid

    @property
    def power(self):
        if len(self._power) > 0:
            return self._power[self._power.rindex('.')+1:]
        else:
            return "Off"

    @property
    def door(self):
        if len(self._door) > 0:
            return self._door[self._door.rindex('.')+1:]
        else:
            return ""

    @property
    def operation(self):
        if len(self._operation)> 0:
            return self._operation[self._operation.rindex('.')+1:]
        else:
            return ""

    @property
    def program_selected(self):
        if len(self._program_selected) > 0:
            return self._program_selected[self._program_selected.rindex('.') + 1:]
        else:
            return ""

    @property
    def program_progress(self):
        if self.operation.lower() == 'run':
            return self.__program_progress
        else:
            return 0

    def register_value_changed_listener(self, value_changed_listener):
        self.__value_changed_listeners.add(value_changed_listener)
        self._notify_listeners()

    def _notify_listeners(self):
        for value_changed_listener in self.__value_changed_listeners:
            value_changed_listener()

    def on_connected(self, event):
        logging.info(self.name + " device has been connected")
        self._reload_status_and_settings()

    def on_disconnected(self, event):
        logging.info(self.name + " device has been disconnected")

    def on_keep_alive_event(self, event):
        self._notify_listeners()

    def on_notify_event(self, event):
        logging.debug(self.name + " notify event: " + str(event.data))
        self._on_value_changed_event(event)

    def on_status_event(self, event):
        #logging.debug(self.name + " status event: " + str(event.data))
        self._on_value_changed_event(event)

    def _on_event_event(self, event):
        logging.debug(self.name + " unhandled event event: " + str(event.data))

    def _on_value_changed_event(self, event):
        try:
            data = json.loads(event.data)
            self._on_values_changed(data.get('items', []), "event received")
            self._notify_listeners()
        except Exception as e:
            logging.warning("error occurred by handling event " + str(event), e)

    def _reload_status_and_settings(self):
        self.last_refresh = datetime.now()
        try:
            settings = self.__perform_get('/settings').get('data', {}).get('settings', {})
            self._on_values_changed(settings, "reload settings")

            status = self.__perform_get('/status').get('data', {}).get('status', {})
            self._on_values_changed(status, "reload status")
        except Exception as e:
            if isinstance(e, OfflineException):
                logging.info(self.name + " is offline")
            else:
                logging.warning(self.name + " error occurred on refreshing" + str(e))

    def _on_values_changed(self, changes: List[Dict[str, Any]], source: str):
        if len(changes) > 0:
            for change in changes:
                key = str(change.get('key', ""))
                try:
                    handled = self._on_value_changed(key, change, source)
                    if not handled:
                        logging.warning(self.name + " unhandled change " + str(change) + " (" + source + ")")
                except Exception as e:
                    logging.warning("error occurred by handling change with key " + key + " (" + source + ")" + " " + str(e) + "(" + source + ")")
        self._notify_listeners()

    def _on_value_changed(self, key: str, change: Dict[str, Any], source: str) -> bool:
        if key == 'BSH.Common.Status.DoorState':
            self._door = change.get('value', "undefined")
            logging.info(self.name + " field 'door state': " + str(self._door) + " (" + source + ")")
        elif key == 'BSH.Common.Status.OperationState':
            self._operation = change.get('value', "undefined")
            logging.info(self.name + " field 'operation state': " + str(self._operation) + " (" + source + ")")
        elif key == 'BSH.Common.Status.RemoteControlStartAllowed':
            self.remote_start_allowed = change.get('value', False)
            logging.info(self.name + " field 'remote start allowed': " + str(self.remote_start_allowed) + " (" + source + ")")
        elif key == 'BSH.Common.Setting.PowerState':
            self._power = change.get('value', None)
            logging.info(self.name + " field 'power state': " + str(self._power) + " (" + source + ")")
        elif key == 'BSH.Common.Root.SelectedProgram':
            self._program_selected = change.get('value', None)
            logging.info(self.name + " field 'selected program': " + str(self._program_selected) + " (" + source + ")")
        elif key == 'BSH.Common.Option.ProgramProgress':
            self.__program_progress = change.get('value', None)
            logging.info(self.name + " field 'program progress': " + str(self.__program_progress) + " (" + source + ")")
        elif key == 'BSH.Common.Status.LocalControlActive':
            self.__program_local_control_active = change.get('value', None)
            logging.info(self.name + " field 'local control active': " + str(self.__program_local_control_active) + " (" + source + ")")
        elif key == 'BSH.Common.Status.RemoteControlActive':
            self.program_remote_control_active = change.get('value', False)
            logging.info(self.name + " field 'remote control active': " + str(self.program_remote_control_active) + " (" + source + ")")
        elif key == 'BSH.Common.Setting.ChildLock': # supported by dishwasher, washer, dryer, ..
            self.child_lock = change.get('value', False)
            logging.info(self.name + " field 'child lock': " + str(self.child_lock) + " (" + source + ")")
        elif key == 'BSH.Common.Root.ActiveProgram':
            self.__program_active = change.get('value', False)
            logging.info(self.name + " field 'active program': " + str(self.__program_active) + " (" + source + ")")
        elif key == 'BSH.Common.Option.RemainingProgramTime':   # supported by dishwasher, washer, dryer, ..
            self.program_remaining_time_sec = change.get('value', 0)
            logging.info(self.name + " field 'remaining program time': " + str(self.program_remaining_time_sec) + " (" + source + ")")
        else:
            # unhandled change
            return False
        return True

    def _reload_selected_program(self):
        # query the selected program
        selected_data = self.__perform_get('/programs/selected').get('data', {})
        self._program_selected = selected_data.get('key', "")
        logging.info(self.name + " program selected: " + str(self._program_selected) + " (reload program)")
        selected_options = selected_data.get('options', "")
        self._on_values_changed(selected_options, "reload program")

        # query available options of the selected program
        if len(self._program_selected) > 0:
            try:
                available_data = self.__perform_get('/programs/available/' + self._program_selected).get('data', {})
                available_options = available_data.get('options', "")
                self._on_values_changed(available_options, "reload program")
            except Exception as e:
                logging.warning("error occurred fetching program options of " + self._program_selected + " " + str(e))
        self._notify_listeners()

    def __perform_get(self, path:str) -> Dict[str, Any]:
        uri = self._device_uri + path
        response = requests.get(uri, headers={"Authorization": "Bearer " + self._auth.access_token}, timeout=5000)
        if is_success(response.status_code):
            return response.json()
        else:
            if response.status_code == 409:
                msg = response.json()
                if msg.get("error", {}).get('key', "") == "SDK.Error.HomeAppliance.Connection.Initialization.Failed":
                    raise OfflineException()
            raise Exception("error occurred by calling GET " + uri + " Got " + str(response.status_code) + " " + response.text)

    def _perform_put(self, path:str, data: str, max_trials: int = 3, current_trial: int = 1):
        uri = self._device_uri + path
        response = requests.put(uri, data=data, headers={"Content-Type": "application/json", "Authorization": "Bearer " + self._auth.access_token}, timeout=5000)
        if not is_success(response.status_code):
            logging.warning("error occurred by calling PUT (" + str(current_trial) + ". trial) " + uri + " " + data)
            logging.warning("got " + str(response.status_code) + " " + str(response.text))
            if current_trial <= max_trials:
                delay = 1 + current_trial
                logging.warning("waiting " + str(delay) + " sec for retry")
                sleep(delay)
                self._perform_put(path, data, max_trials, current_trial+1)
            else:
                response.raise_for_status()

    @property
    def __fingerprint(self) -> str:
        return self.device_type + ":" + self.brand + ":" + self.vib + ":" + self.enumber + ":" + self.haid

    def __hash__(self):
        return hash(self.__fingerprint)

    def __lt__(self, other):
        return self.__fingerprint < other.__fingerprint

    def __eq__(self, other):
        return self.__fingerprint == other.__fingerprint

    def __str__(self):
        return self.name + " (" + self.device_type + ", " + self.vib + ")"

    def __repr__(self):
        return self.__str__()


class Dishwasher(Appliance):
    DeviceType = 'dishwasher'

    def __init__(self, device_uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str):
        self.__program_start_in_relative_sec = 0
        self.__program_start_in_relative_sec_max = 86000
        self.program_extra_try = ""
        self.program_hygiene_plus = ""
        self.program_vario_speed_plus = ""
        self.program_energy_forecast_percent = 0
        self.program_water_forecast_percent = 0
        super().__init__(device_uri, auth, name, device_type, haid, brand, vib, enumber)

    def _on_value_changed(self, key: str, change: Dict[str, Any], source: str) -> bool:
        if key == 'BSH.Common.Option.StartInRelative':
            if 'value' in change.keys():
                self.__program_start_in_relative_sec = change['value']
                logging.info(self.name + " field 'start in relative': " + str(self.__program_start_in_relative_sec) + " (" + source + ")")
            if 'constraints' in change.keys():
                constraints = change['constraints']
                if 'max' in constraints.keys():
                    self.__program_start_in_relative_sec_max = constraints['max']
                    logging.info(self.name + " field 'start in relative max value': " + str(self.__program_start_in_relative_sec_max) + " (" + source + ")")
        elif key == 'Dishcare.Dishwasher.Option.ExtraDry':
            self.program_extra_try = change.get('value', False)
            logging.info(self.name + " field 'extra try': " + str(self.program_extra_try) + " (" + source + ")")
        elif key == 'Dishcare.Dishwasher.Option.HygienePlus':
            self.program_hygiene_plus = change.get('value', False)
            logging.info(self.name + " field 'hygiene plus': " + str(self.program_hygiene_plus) + " (" + source + ")")
        elif key == 'Dishcare.Dishwasher.Option.VarioSpeedPlus':
            self.program_vario_speed_plus = change.get('value', 0)
            logging.info(self.name + " field 'vario speed plus': " + str(self.program_vario_speed_plus) + " (" + source + ")")
        elif key == 'BSH.Common.Option.EnergyForecast':
            self.program_energy_forecast_percent = change.get('value', 0)
            logging.info(self.name + " field 'energy forecast': " + str(self.program_energy_forecast_percent) + " (" + source + ")")
        elif key == 'BSH.Common.Option.WaterForecast':
            self.program_water_forecast_percent = change.get('value', 0)
            logging.info(self.name + " field 'water forecast': " + str(self.program_water_forecast_percent) + " (" + source + ")")
        else:
            # unhandled
            return super()._on_value_changed(key, change, source)
        return True

    def _notify_listeners(self):
        self.startable = self.door.lower() == "closed" and \
                         self.power.lower() == "on" and \
                         self.remote_start_allowed and \
                         self.operation.lower() not in ['run', 'finished', 'inactive']
        self.started = self.power.lower() == "on" and \
                       self.door.lower() == "closed" and \
                       self.operation.lower() in ['delayedstart', 'run']
        super()._notify_listeners()

    def read_start_date(self) -> str:
        start_date = datetime.now() + timedelta(seconds=self.__program_start_in_relative_sec)
        if start_date > datetime.now():
            return start_date.strftime("%Y-%m-%dT%H:%M")
        else:
            return ""

    def write_start_date(self, start_date: str):
        self._reload_status_and_settings()
        self._reload_selected_program()  # ensure that selected program is loaded

        if len(self._program_selected) == 0:
            logging.warning("ignoring start command. No program selected")

        elif self.startable:
            remaining_secs_to_wait = int((datetime.fromisoformat(start_date) - datetime.now()).total_seconds())
            if remaining_secs_to_wait < 0:
                remaining_secs_to_wait = 0
            if remaining_secs_to_wait > self.__program_start_in_relative_sec_max:
                remaining_secs_to_wait = self.__program_start_in_relative_sec_max

            # already in delayed start? (update start time?)
            if self.operation.lower() in ['delayedstart']:
                try:
                    data = {
                        "data": {
                            "key": "BSH.Common.Option.StartInRelative",
                            "value": remaining_secs_to_wait,
                            "unit": "seconds"
                        }
                    }

                    self._perform_put("/programs/active/options/BSH.Common.Option.StartInRelative", json.dumps(data, indent=2), max_trials=3)
                    logging.info(self.name + " update start time: " + self.program_selected +
                                 " starts in " + print_duration(remaining_secs_to_wait) +
                                 " (duration " + print_duration(self.program_remaining_time_sec) + ")")
                except Exception as e:
                    logging.warning("error occurred by starting " + self.name + " " + str(e))

            # start delayed
            else:
                try:
                    data = {
                        "data": {
                            "key": self._program_selected,
                            "options": [{
                                "key": "BSH.Common.Option.StartInRelative",
                                "value": remaining_secs_to_wait,
                                "unit": "seconds"
                            }]
                        }
                    }

                    self._perform_put("/programs/active", json.dumps(data, indent=2), max_trials=3)
                    logging.info(self.name + " PROGRAMSTRART - program " + self.program_selected +
                                 " starts in " + print_duration(remaining_secs_to_wait) +
                                 " (duration " + print_duration(self.program_remaining_time_sec) + ")")
                except Exception as e:
                    logging.warning("error occurred by starting " + self.name + " " + str(e))
        else:
            logging.warning("ignoring start command. " + self.name + " is in state " + self._operation)


class Dryer(Appliance):
    DeviceType = 'dryer'

    def __init__(self, device_uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str):
        self.__program_finish_in_relative_sec = 0
        self.__program_finish_in_relative_max_sec = 86000
        self.__program_finish_in_relative_stepsize_sec = 60
        self.program_gentle = False
        self.__program_drying_target = ""
        self.__program_drying_target_adjustment = ""
        self.__program_wrinkle_guard = ""
        self.__start_date = ""
        super().__init__(device_uri, auth, name, device_type, haid, brand, vib, enumber)

    @property
    def program_wrinkle_guard(self) -> str:
        if len(self.__program_wrinkle_guard) > 0:
            return self.__program_wrinkle_guard[self.__program_wrinkle_guard.rindex('.') + 1:]
        else:
            return ""

    @property
    def program_drying_target(self) -> str:
        if len(self.__program_drying_target) > 0:
            return self.__program_drying_target[self.__program_drying_target.rindex('.') + 1:]
        else:
            return ""

    @property
    def program_drying_target_adjustment(self) -> str:
        if len(self.__program_drying_target_adjustment) > 0:
            return self.__program_drying_target_adjustment[self.__program_drying_target_adjustment.rindex('.') + 1:]
        else:
            return ""

    def _on_value_changed(self, key: str, change: Dict[str, Any], source: str) -> bool:
        if key == 'BSH.Common.Option.FinishInRelative':  # supported by dryer & washer only
            if 'value' in change.keys():
                self.__program_finish_in_relative_sec = int(change['value'])
                logging.info(self.name + " field 'finish in relative': " + str(self.__program_finish_in_relative_sec) + " (" + source + ")")
            if 'constraints' in change.keys():
                constraints = change['constraints']
                if 'max' in constraints.keys():
                    self.__program_finish_in_relative_max_sec = constraints['max']
                    logging.info(self.name + " field 'program_finish_in_relative_max_sec: " + str(self.__program_finish_in_relative_max_sec) + " (" + source + ")")
                if 'stepsize' in constraints.keys():
                    self.__program_finish_in_relative_stepsize_sec = constraints['stepsize']
                    logging.info(self.name + " field 'program_finish_in_relative_stepsize_sec: " + str(self.__program_finish_in_relative_stepsize_sec) + " (" + source + ")")
        elif key == 'LaundryCare.Dryer.Option.DryingTarget':
            self.__program_drying_target = change.get('value', "")
        elif key == 'LaundryCare.Dryer.Option.DryingTargetAdjustment':
            self.__program_drying_target_adjustment = change.get('value', "")
        elif key == 'LaundryCare.Dryer.Option.Gentle':
            self.program_gentle = change.get('value', False)
        elif key == 'LaundryCare.Dryer.Option.WrinkleGuard':
            self.__program_wrinkle_guard = change.get('value', "")
        else:
            # unhandled
            return super()._on_value_changed(key, change, source)
        return True

    def _notify_listeners(self):
        self.startable = self.door.lower() == "closed" and \
                         self.power.lower() == "on" and \
                         self.remote_start_allowed and \
                         self.program_remote_control_active and \
                         self.operation.lower() not in ['delayedstart','run', 'finished', 'inactive']
        self.started = self.power.lower() == "on" and \
                       self.door.lower() == "closed" and \
                       self.operation.lower() in ['delayedstart', 'run']
        super()._notify_listeners()

    def read_start_date(self) -> str:
        if self.operation.lower() == 'delayedstart':
            return self.__start_date
        else:
            return ""

    def write_start_date(self, start_date: str):
        self._reload_selected_program()  # refresh to ensure that current program is read
        if len(self._program_selected) == 0:
            logging.warning("ignoring start command. No program selected")
        elif self.startable:
            duration_sec = self.__program_finish_in_relative_sec
            remaining_secs_to_finish = int((datetime.fromisoformat(start_date) - datetime.now()).total_seconds()) + duration_sec
            logging.info("remaining_secs_to_finish " + str(remaining_secs_to_finish) + " (" + print_duration(remaining_secs_to_finish) + ") computed based on start date " + start_date + " and duration " + print_duration(duration_sec))
            if remaining_secs_to_finish < 0:
                logging.info("remaining_secs_to_finish is < 0. set it with 0")
                remaining_secs_to_finish = 0
            if remaining_secs_to_finish > 0 and self.__program_finish_in_relative_stepsize_sec > 0:
                remaining_secs_to_finish = int(remaining_secs_to_finish / self.__program_finish_in_relative_stepsize_sec) * self.__program_finish_in_relative_stepsize_sec
                logging.info("remaining_secs_to_finish " + str(remaining_secs_to_finish) + " (" + print_duration(remaining_secs_to_finish) + ") computed based on stepsize of " + str(self.__program_finish_in_relative_stepsize_sec) + " sec")
            data = {
                "data": {
                    "key": self._program_selected,
                    "options": [{
                        "key": "BSH.Common.Option.FinishInRelative",
                        "value": remaining_secs_to_finish,
                        "unit": "seconds"
                    }]
                }
            }
            try:
                self._perform_put("/programs/active", json.dumps(data, indent=2), max_trials=3)
                logging.info(self.name + " program " + self.program_selected + " starts at " + start_date)
                self.__start_date = start_date
            except Exception as e:
                logging.warning("error occurred by starting " + self.name + " " + str(e))
        else:
            logging.warning("ignoring start command. " + self.name + " is in state " + self._operation + " power: " + self.power)


class FinishInAppliance(Appliance):

    def __init__(self, device_uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str):
        self.__program_finish_in_relative_sec = 0
        self.__program_finish_in_relative_max_sec = 86000
        self.__program_finish_in_relative_stepsize_sec = 60
        self.__start_date = ""
        super().__init__(device_uri, auth, name, device_type, haid, brand, vib, enumber)

    def _on_value_changed(self, key: str, change: Dict[str, Any], source: str) -> bool:
        if key == 'BSH.Common.Option.FinishInRelative':  # supported by dryer & washer only
            if 'value' in change.keys():
                self.__program_finish_in_relative_sec = int(change['value'])
                logging.info(self.name + " field 'finish in relative': " + str(self.__program_finish_in_relative_sec) + " (" + source + ")")
            if 'constraints' in change.keys():
                constraints = change['constraints']
                if 'max' in constraints.keys():
                    self.__program_finish_in_relative_max_sec = constraints['max']
                    logging.info(self.name + " field 'program_finish_in_relative_max_sec: " + str(self.__program_finish_in_relative_max_sec) + " (" + source + ")")
                if 'stepsize' in constraints.keys():
                    self.__program_finish_in_relative_stepsize_sec = constraints['stepsize']
                    logging.info(self.name + " field 'program_finish_in_relative_stepsize_sec: " + str(self.__program_finish_in_relative_stepsize_sec) + " (" + source + ")")
        else:
            # unhandled
            return super()._on_value_changed(key, change, source)
        return True

    def _notify_listeners(self):
        self.startable = self.door.lower() == "closed" and \
                         self.power.lower() == "on" and \
                         self.remote_start_allowed and \
                         self.program_remote_control_active and \
                         self.operation.lower() not in ['delayedstart','run', 'finished', 'inactive']
        super()._notify_listeners()

    def read_start_date(self) -> str:
        if self.operation.lower() == 'delayedstart':
            return self.__start_date
        else:
            return ""

    def write_start_date(self, start_date: str):
        self._reload_selected_program()  # refresh to ensure that current program is read
        if len(self._program_selected) == 0:
            logging.warning("ignoring start command. No program selected")
        elif self.startable:
            duration_sec = self.__program_finish_in_relative_sec
            remaining_secs_to_finish = int((datetime.fromisoformat(start_date) - datetime.now()).total_seconds()) + duration_sec
            logging.info("remaining_secs_to_finish " + str(remaining_secs_to_finish) + " (" + print_duration(remaining_secs_to_finish) + ") computed based on start date " + start_date + " and duration " + print_duration(duration_sec))
            if remaining_secs_to_finish < 0:
                logging.info("remaining_secs_to_finish is < 0. set it with 0")
                remaining_secs_to_finish = 0
            if remaining_secs_to_finish > 0 and self.__program_finish_in_relative_stepsize_sec > 0:
                remaining_secs_to_finish = int(remaining_secs_to_finish / self.__program_finish_in_relative_stepsize_sec) * self.__program_finish_in_relative_stepsize_sec
                logging.info("remaining_secs_to_finish " + str(remaining_secs_to_finish) + " (" + print_duration(remaining_secs_to_finish) + ") computed based on stepsize of " + str(self.__program_finish_in_relative_stepsize_sec) + " sec")
            data = {
                "data": {
                    "key": self._program_selected,
                    "options": [{
                        "key": "BSH.Common.Option.FinishInRelative",
                        "value": remaining_secs_to_finish,
                        "unit": "seconds"
                    }]
                }
            }
            try:
                self._perform_put("/programs/active", json.dumps(data, indent=2), max_trials=3)
                logging.info(self.name + " program " + self.program_selected + " starts at " + start_date)
                self.__start_date = start_date
            except Exception as e:
                logging.warning("error occurred by starting " + self.name + " " + str(e))
        else:
            logging.warning("ignoring start command. " + self.name + " is in state " + self._operation + " power: " + self.power)


class Washer(FinishInAppliance):
    DeviceType = 'washer'

    def __init__(self, device_uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str):
        super().__init__(device_uri, auth, name, device_type, haid, brand, vib, enumber)

    def _on_value_changed(self, key: str, change: Dict[str, Any], source: str) -> bool:
        if key == 'BSH.Common.Option.TTTT':
            print("stop")
        else:
            # unhandled
            return super()._on_value_changed(key, change, source)
        return True


