import logging
import requests
import json
from time import sleep
from typing import List, Dict, Any
from datetime import datetime, timedelta
from redzoo.database.simple import SimpleDB
from homeconnect_webthing.auth import Auth
from homeconnect_webthing.eventstream import EventListener
from homeconnect_webthing.utils import print_duration, is_success



class OfflineException(Exception):
    pass


class Appliance(EventListener):

    ON = "On"
    OFF = "Off"

    STATE_READY = "READY"
    STATE_STARTABLE = "STARTABLE"
    STATE_DELAYED_STARTED = "DELAYED_STARTED"
    STATE_RUNNING = "RUNNING"
    STATE_FINISHED = "FINISHED"
    STATE_OFF = "OFF"
    VALID_STATES = [STATE_READY, STATE_STARTABLE, STATE_DELAYED_STARTED, STATE_RUNNING, STATE_FINISHED, STATE_OFF]

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
        self.__db = SimpleDB(haid + '_db')
        self._reload_status_and_settings()
        self._reload_selected_program(ignore_error=True)

    def id(self) -> str:
        return self.haid

    @property
    def power(self):
        if len(self._power) > 0:
            return self._power[self._power.rindex('.')+1:]
        else:
            return self.OFF

    @property
    def door(self):
        if len(self._door) > 0:
            return self._door[self._door.rindex('.')+1:]
        else:
            return ""

    @property
    def operation(self):
        if len(self._operation) > 0:
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

    @property
    def state(self) -> str:
        return self.__db.get("state", self.STATE_READY)

    @state.setter
    def state(self, new_state: str):
        if self.state != new_state:
            logging.info(self.name + " new state: " + new_state + " (previous: " + self.state + ")")
            self.__db.put("state", new_state)

    def __update_state(self):
        power = self.power.lower() == self.ON.lower()
        operation = self.operation.lower()

        if power and operation == 'delayedstart':
            self.state = self.STATE_DELAYED_STARTED
        elif power and operation == 'run':
            self.state = self.STATE_RUNNING
            self.__previous_run_completed = False
        elif power and operation == 'ready' and self.door.lower() == "closed" and self.remote_start_allowed and self.program_remote_control_active:
            self.state = self.STATE_STARTABLE
        elif power and operation == 'finished':
            self.state = self.STATE_FINISHED
        else:
            if power and self.door.lower() == 'closed':
                self.state = self.STATE_READY
            elif power:
                self.state = self.STATE_FINISHED
            else:
                self.state = self.OFF

    def _notify_listeners(self):
        self.__update_state()
        for value_changed_listener in self.__value_changed_listeners:
            value_changed_listener()

    def on_connected(self, event):
        logging.info(self.name + " has been connected (event stream). Reloading status/settings")
        self._reload_status_and_settings()

    def on_disconnected(self, event):
        logging.info(self.name + " has been disconnected (event stream)")

    def on_keep_alive_event(self, event):
        try:
            if (self.last_refresh + timedelta(minutes=30)) < datetime.now():
                self._reload_status_and_settings()
            self._notify_listeners()
        except Exception as e:
            logging.warning("error occurred processing keep alive event "+  str(e))

    def on_notify_event(self, event):
        self._on_value_changed_event(event)

    def on_status_event(self, event):
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
            status = self._perform_get('/status').get('data', {}).get('status', {})
            self._on_values_changed(status, "reload status", notify_listeners=False)

            settings = self._perform_get('/settings').get('data', {}).get('settings', {})
            self._on_values_changed(settings, "reload settings")
        except Exception as e:
            if isinstance(e, OfflineException):
                self._power = ""
                logging.info(self.name + " is offline. Could not query current status/settings")
            else:
                logging.warning(self.name + " error occurred on refreshing" + str(e))

    def _on_values_changed(self, changes: List[Dict[str, Any]], source: str, notify_listeners: bool = True):
        if len(changes) > 0:
            for change in changes:
                key = str(change.get('key', ""))
                try:
                    handled = self._on_value_changed(key, change, source)
                    if not handled:
                        logging.warning(self.name + " unhandled change " + str(change) + " (" + source + ")")
                except Exception as e:
                    logging.warning("error occurred by handling change with key " + key + " (" + source + ")" + " " + str(e) + "(" + source + ")")
        if notify_listeners:
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

    def _reload_selected_program(self, ignore_error: bool = False):
        # query the selected program
        try:
            selected_data = self._perform_get('/programs/selected').get('data', {})
            self._program_selected = selected_data.get('key', "")
            logging.info(self.name + " program selected: " + str(self._program_selected) + " (reload program)")
            selected_options = selected_data.get('options', "")
            self._on_values_changed(selected_options, "reload program")

            # query available options of the selected program
            if len(self._program_selected) > 0:
                try:
                    available_data = self._perform_get('/programs/available/' + self._program_selected).get('data', {})
                    available_options = available_data.get('options', "")
                    self._on_values_changed(available_options, "reload program")
                except Exception as e:
                    logging.warning("error occurred fetching program options of " + self._program_selected + " " + str(e))
            self._notify_listeners()
        except Exception as e:
            if ignore_error:
                return
            else:
                raise e


    def _perform_get(self, path:str) -> Dict[str, Any]:
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

    def _perform_put(self, path:str, data: str, max_trials: int = 3, current_trial: int = 1, verbose: bool = False):
        uri = self._device_uri + path
        if verbose:
            logging.info("PUT " + uri + "\r\n" + json.dumps(data, indent=2))
        response = requests.put(uri, data=data, headers={"Content-Type": "application/json", "Authorization": "Bearer " + self._auth.access_token}, timeout=5000)
        if verbose:
            logging.info(str(response.status_code) + "\r\n" + response.text)
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

        else:
            remaining_secs_to_wait = int((datetime.fromisoformat(start_date) - datetime.now()).total_seconds())
            if remaining_secs_to_wait < 0:
                remaining_secs_to_wait = 0
            if remaining_secs_to_wait >= self.__program_start_in_relative_sec_max:
                logging.warning("remaining seconds to wait " + print_duration(remaining_secs_to_wait) + " is larger than max supported value of " + print_duration(self.__program_start_in_relative_sec_max) + ". Ignore setting start date")

            # start in a delayed manner
            if self.state == self.STATE_STARTABLE:
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

            # update start time (already started in a delayed manner)
            elif self.state == self.STATE_DELAYED_STARTED:
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
                    logging.warning("error occurred by updating start time " + self.name + " " + str(e))

            else:
                logging.warning("ignoring start command. " + self.name + " is in state " + str(self.state))
            self._notify_listeners()


class FinishDate:

    def __init__(self, start_date: str, program_duration_sec: int, remaining_secs_to_finish: int):
        self.start_date = start_date
        self.program_duration_sec = program_duration_sec
        self.remaining_secs_to_finish = remaining_secs_to_finish

    @staticmethod
    def __compute_remaining_secs_to_finish(start_date: str, duration_sec: int, program_finish_in_relative_stepsize_sec: int) -> int:
        remaining_secs_to_finish = int((datetime.fromisoformat(start_date) - datetime.now()).total_seconds()) + duration_sec
        if remaining_secs_to_finish < 0:
            logging.info("remaining_secs_to_finish is < 0. set it with 0")
            remaining_secs_to_finish = 0
        if remaining_secs_to_finish > 0 and program_finish_in_relative_stepsize_sec > 0:
            remaining_secs_to_finish = int(remaining_secs_to_finish / program_finish_in_relative_stepsize_sec) * program_finish_in_relative_stepsize_sec
        return remaining_secs_to_finish

    @staticmethod
    def create(start_date: str, program_duration_sec: int, program_finish_in_relative_stepsize_sec: int, program_finish_in_relative_max_sec: int):
        remaining_secs_to_finish = FinishDate.__compute_remaining_secs_to_finish(start_date, program_duration_sec, program_finish_in_relative_stepsize_sec)
        return FinishDate(start_date, program_duration_sec, remaining_secs_to_finish)

    def __str__(self):
        return "remaining seconds to finished " + str(self.remaining_secs_to_finish) + " (" + print_duration(self.remaining_secs_to_finish) + "). End time " + (datetime.fromisoformat(self.start_date) + timedelta(seconds=self.program_duration_sec)).strftime("%H:%M") + " (= start time " + datetime.fromisoformat(self.start_date).strftime("%H:%M") + " + " + print_duration(self.program_duration_sec) + " program duration)"

    def __repr__(self):
        return self.__str__()


class FinishInAppliance(Appliance):

    def __init__(self, device_uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str):
        self._program_finish_in_relative_sec = 0
        self.__program_finish_in_relative_max_sec = 86000
        self.__program_finish_in_relative_stepsize_sec = 60
        self._durations = SimpleDB(haid + '_durations')
        super().__init__(device_uri, auth, name, device_type, haid, brand, vib, enumber)

    def _on_value_changed(self, key: str, change: Dict[str, Any], source: str) -> bool:
        if key == 'BSH.Common.Status.OperationState':
            operation = change.get('value', "undefined")
            if operation != self._operation:
                logging.info(self.name + " field 'operation state': " + str(operation) + ". previous state = " + str(self._operation) + " (" + source + ")")
                self._operation = operation
        elif key == 'BSH.Common.Option.FinishInRelative':  # supported by dryer & washer only
            if 'value' in change.keys():
                self._program_finish_in_relative_sec = int(change['value'])
            if 'constraints' in change.keys():
                constraints = change['constraints']
                if 'max' in constraints.keys():
                    self.__program_finish_in_relative_max_sec = constraints['max']
                    logging.info(self.name + " field 'program_finish_in_relative_max_sec: " + str(self.__program_finish_in_relative_max_sec) + " (" + source + ")")
                if 'stepsize' in constraints.keys():
                    self.__program_finish_in_relative_stepsize_sec = constraints['stepsize']
                    logging.info(self.name + " field 'program_finish_in_relative_stepsize_sec: " + str(self.__program_finish_in_relative_stepsize_sec) + " (" + source + ")")
        elif key == 'BSH.Common.Root.SelectedProgram':
            program_selected = change.get('value', None)
            if program_selected is not None and len(program_selected) > 0:
                self._program_selected = program_selected
                logging.info(self.name + " field 'selected program': " + str(self._program_selected) + " (" + source + ")")
        else:
            # unhandled
            return super()._on_value_changed(key, change, source)
        return True

    def read_start_date(self) -> str:
        if self.operation.lower() == 'delayedstart' and self._program_finish_in_relative_sec > 0:
            start_date = datetime.now() + timedelta(seconds=self._program_finish_in_relative_sec) - timedelta(seconds=self.__program_duration_sec())
            return start_date.strftime("%Y-%m-%dT%H:%M")
        else:
            return ""

    def _program_fingerprint(self) -> str:
        return self._program_selected

    @property
    def program_duration_hours(self) -> float:
        return round(self.__program_duration_sec() / (60*60), 1)

    def __program_duration_sec(self):
        # will update props, if duration is available
        program_fingerprint = self._program_fingerprint()
        if len(self.program_selected) > 0 and self._program_finish_in_relative_sec > 0 and self.state == self.STATE_READY:
            if self._durations.get(program_fingerprint, -1) != self._program_finish_in_relative_sec:   # duration changed?
                if self._program_finish_in_relative_sec < 5 * 60 * 60:
                    self._durations.put(program_fingerprint, self._program_finish_in_relative_sec)
                    logging.info("duration update for " + program_fingerprint + " with " + str(self._program_finish_in_relative_sec))
                else:
                    logging.info("duration update for " + program_fingerprint + " with " + str(self._program_finish_in_relative_sec) + " ignored. Value seems to high")

        # get duration
        duration_sec = self._durations.get(program_fingerprint, None)
        if duration_sec is None:
            logging.warning("no duration stored. Using default (key: " + program_fingerprint + " available values: " + ", ".join([key + ": " + str(self._durations.get(key)) for key in self._durations.keys()]) + ")")
            return 7222  # 2h
        else:
            return duration_sec

    def write_start_date(self, start_date: str):
        logging.info("starting device at " + start_date)

        # ensure that current settings and selected program is loaded
        self._reload_status_and_settings()
        self._reload_selected_program()

        # when startable
        if self.state == self.STATE_STARTABLE:
            program_duration_sec = self.__program_duration_sec()
            finish_date = FinishDate.create(start_date, program_duration_sec, self.__program_finish_in_relative_stepsize_sec, self.__program_finish_in_relative_max_sec)
            if finish_date.remaining_secs_to_finish >= self.__program_finish_in_relative_max_sec:
                logging.warning("remaining seconds to finished " + print_duration(finish_date.remaining_secs_to_finish) + " is larger than max supported value of " + print_duration(self.__program_finish_in_relative_max_sec) + ". Ignore setting start date")
            else:
                try:
                    data = {
                        "data": {
                            "key": self._program_selected,
                            "options": [{
                                "key": "BSH.Common.Option.FinishInRelative",
                                "value": finish_date.remaining_secs_to_finish,
                                "unit": "seconds"
                            }]
                        }
                    }
                    self._perform_put("/programs/active", json.dumps(data, indent=2), max_trials=3, verbose=True)
                    logging.info(self.name + " program " + self.program_selected + " starts at " + start_date + " -> " + str(finish_date))
                except Exception as e:
                    logging.warning("error occurred by starting " + self.name + " with program " + self.program_selected + " at " + start_date + " (duration: " + str(round(program_duration_sec/(60*60), 1)) + " h) " + str(e))

        # update end time
        elif self.state == self.STATE_DELAYED_STARTED:
            logging.warning("updating start time currently not supported")
        else:
            logging.warning(self.name + " is in state " + str(self.state) + " Ignoring start command.")



class Washer(FinishInAppliance):
    DeviceType = 'washer'

    def __init__(self, device_uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str):
        self.idos1_baselevel = 0
        self.idos1_active = False
        self.idos2_baselevel = 0
        self.idos2_active = False
        self.water_forecast = 0
        self.load_recommendation = 0
        self.rinse_hold = False
        self.__spin_speed = ""
        self.__temperature = ""
        self.energy_forecast = 0
        self.intensive_plus = False
        self.prewash = False
        self.rinse_plus1 = False
        self.speed_perfect = False
        super().__init__(device_uri, auth, name, device_type, haid, brand, vib, enumber)

    @property
    def spin_speed(self) -> str:
        if len(self.__spin_speed) > 0:
            return self.__spin_speed[self.__spin_speed.rindex('.') + 1:]
        else:
            return ""

    @property
    def temperature(self) -> str:
        if len(self.__temperature) > 0:
            return self.__temperature[self.__temperature.rindex('.') + 1:]
        else:
            return ""

    def _program_fingerprint(self) -> str:
        return self._program_selected + "#" + \
               str(self.speed_perfect) + "#" + \
               str(self.intensive_plus) + "#" + \
               str(self.prewash) + "#" + \
               str(self.rinse_plus1)

    def _on_value_changed(self, key: str, change: Dict[str, Any], source: str) -> bool:
        if key == 'LaundryCare.Washer.Setting.IDos1BaseLevel':
            self.idos1_baselevel = change.get('value', 0)
            logging.info(self.name + " field 'idos1 baselevel': " + str(self.idos1_baselevel) + " (" + source + ")")
        elif key == 'LaundryCare.Washer.Setting.IDos2BaseLevel':
            self.idos2_baselevel = change.get('value', 0)
            logging.info(self.name + " field 'idos2 baselevel': " + str(self.idos2_baselevel) + " (" + source + ")")
        elif key == 'BSH.Common.Option.WaterForecast':
            self.water_forecast = change.get('value', 0)
            logging.info(self.name + " field 'water forecast': " + str(self.water_forecast) + " (" + source + ")")
        elif key == 'LaundryCare.Common.Option.LoadRecommendation':
            self.load_recommendation = change.get('value', 0)
            logging.info(self.name + " field 'load recommendation': " + str(self.load_recommendation) + " (" + source + ")")
        elif key == 'LaundryCare.Washer.Option.IDos1.Active':
            self.idos1_active = change.get('value', False)
            logging.info(self.name + " field 'idos1 active': " + str(self.idos1_active) + " (" + source + ")")
        elif key == 'LaundryCare.Washer.Option.IDos2.Active':
            self.idos2_active = change.get('value', False)
            logging.info(self.name + " field 'idos2 active': " + str(self.idos2_active) + " (" + source + ")")
        elif key == 'LaundryCare.Washer.Option.RinseHold':
            self.rinse_hold = change.get('value', False)
            logging.info(self.name + " field 'rinse hold': " + str(self.rinse_hold) + " (" + source + ")")
        elif key == 'LaundryCare.Washer.Option.SpinSpeed':
            value = change.get('value', None)
            if value is not None:
                self.__spin_speed = value
                logging.info(self.name + " field 'spin speed': " + str(self.__spin_speed) + " (" + source + ")")
        elif key == 'LaundryCare.Washer.Option.Temperature':
            self.__temperature = change.get('value', '')
            logging.info(self.name + " field 'temperature': " + str(self.__temperature) + " (" + source + ")")
        elif key == 'BSH.Common.Option.EnergyForecast':
            self.energy_forecast = change.get('value', 0)
            logging.info(self.name + " field 'energy forecast': " + str(self.energy_forecast) + " (" + source + ")")
        elif key == 'LaundryCare.Washer.Option.IntensivePlus':
            self.intensive_plus = change.get('value', False)
            logging.info(self.name + " field 'intensive plus': " + str(self.intensive_plus) + " (" + source + ")")
        elif key == 'LaundryCare.Washer.Option.Prewash':
            self.prewash = change.get('value', False)
            logging.info(self.name + " field 'prewash': " + str(self.prewash) + " (" + source + ")")
        elif key == 'LaundryCare.Washer.Option.RinsePlus1':
            self.rinse_plus1 = change.get('value', False)
            logging.info(self.name + " field 'rinse plus 1': " + str(self.rinse_plus1) + " (" + source + ")")
        elif key == 'LaundryCare.Washer.Option.SpeedPerfect':
            self.speed_perfect = change.get('value', False)
            logging.info(self.name + " field 'speed perfect': " + str(self.speed_perfect) + " (" + source + ")")
        else:
            # unhandled
            return super()._on_value_changed(key, change, source)
        return True



class Dryer(FinishInAppliance):

    DeviceType = 'dryer'

    def __init__(self, device_uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str):
        self.program_gentle = False
        self.__program_drying_target = ""
        self.__program_drying_target_adjustment = ""
        self.__program_wrinkle_guard = ""
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

    def _program_fingerprint(self) -> str:
        return self._program_selected + "#" + \
               str(self.program_gentle) + "#" + \
               str(self.__program_drying_target) + "#" + \
               str(self.__program_drying_target_adjustment) + "#" + \
               str(self.__program_wrinkle_guard)

    def _on_value_changed(self, key: str, change: Dict[str, Any], source: str) -> bool:
        if key == 'LaundryCare.Dryer.Option.DryingTarget':
            self.__program_drying_target = change.get('value', "")
            logging.info(self.name + " field 'program drying target': " + str(self.__program_drying_target) + " (" + source + ")")
        elif key == 'LaundryCare.Dryer.Option.DryingTargetAdjustment':
            self.__program_drying_target_adjustment = change.get('value', "")
            logging.info(self.name + " field 'program_drying target adjustment': " + str(self.__program_drying_target_adjustment) + " (" + source + ")")
        elif key == 'LaundryCare.Dryer.Option.Gentle':
            self.program_gentle = change.get('value', False)
            logging.info(self.name + " field 'program gentle': " + str(self.program_gentle) + " (" + source + ")")
        elif key == 'LaundryCare.Dryer.Option.WrinkleGuard':
            self.__program_wrinkle_guard = change.get('value', "")
            logging.info(self.name + " field 'program wrinkle guard': " + str(self.__program_wrinkle_guard) + " (" + source + ")")
        else:
            # unhandled
            return super()._on_value_changed(key, change, source)
        return True
