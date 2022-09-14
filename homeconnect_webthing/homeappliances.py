import logging
import requests
import json
from time import sleep
from threading import Thread
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from homeconnect_webthing.auth import Auth
from homeconnect_webthing.eventstream import EventListener, ReconnectingEventStream
from homeconnect_webthing.utils import print_duration, DailyRequestCounter


DRYER = 'dryer'
DISHWASHER = 'dishwasher'



def is_success(status_code: int) -> bool:
    return status_code >= 200 and status_code <= 299


class Targetdate:

    def __init__(self, start_date: str):
        self.start_date = start_date
        self.unit = "seconds"
        self.max = 86000
        self.stepsize = 60

    def remaining_secs_to_start(self) -> int:
        remaining_secs_to_wait = int((datetime.fromisoformat(self.start_date) - datetime.now()).total_seconds())
        remaining_secs_to_start = int(remaining_secs_to_wait/self.stepsize) * self.stepsize
        if remaining_secs_to_start < 0:
            remaining_secs_to_start = 0
        if remaining_secs_to_start > self.max:
            remaining_secs_to_start = self.max
        return remaining_secs_to_start

    def remaining_secs_to_finish(self, program_duration_sec: int) -> int:
        remaining_secs_to_finish = self.remaining_secs_to_start() + program_duration_sec
        if remaining_secs_to_finish > self.max:
            remaining_secs_to_finish = self.max
        return remaining_secs_to_finish


class Appliance(EventListener):

    def __init__(self, device_uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str, request_counter: DailyRequestCounter):
        self._device_uri = device_uri
        self._auth = auth
        self.name = name
        self.device_type = device_type
        self.haid = haid
        self.brand = brand
        self.vib = vib
        self.enumber = enumber
        self.request_counter = request_counter
        self.__value_changed_listeners = set()
        self.last_refresh = datetime.now() - timedelta(hours=9)
        self.remote_start_allowed = False
        self._program_selected = ""
        self.__program_progress = 0
        self.__program_remote_control_active = ""
        self.__program_local_control_active = ""
        self._power = ""
        self._door = ""
        self._operation = ""
        self._refresh(reason=self.name + " appliance initialized")

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
        self._refresh(reason="on connected")

    def on_disconnected(self, event):
        logging.info(self.name + " device has been disconnected")

    def on_keep_alive_event(self, event):
        self._notify_listeners()

    def on_notify_event(self, event):
        logging.debug(self.name + " notify event: " + str(event.data))
        self._on_value_changed_event(event)

    def on_status_event(self, event):
        logging.debug(self.name + " status event: " + str(event.data))
        self._on_value_changed_event(event)

    def _on_event_event(self, event):
        logging.debug(self.name + " event event: " + str(event.data))

    def _on_value_changed_event(self, event):
        try:
            data = json.loads(event.data)
            self._on_values_changed(data.get('items', []), "updated")
            self._notify_listeners()
        except Exception as e:
            logging.warning("error occurred by handling event " + str(event), e)

    def _on_values_changed(self, changes: List[Any], ops: str = "updated"):
        for record in changes:
            key = str(record.get('key', ""))
            value = record.get('value', None)
            if value is None:
                logging.warning("key without value " + key)
            else:
                handled = self._on_value_changed(key, value, ops)
                if not handled:
                    logging.warning(self.name + " unhandled key " + key + " " + str(value))

    def _on_value_changed(self, key: str, value: str, ops: str) -> bool:
        if key == 'BSH.Common.Status.DoorState':
            self._door = value
            logging.info(self.name + " field 'door state' " + ops + ": " + str(value))
        elif key == 'BSH.Common.Status.OperationState':
            self._operation = value
            logging.info(self.name + " field 'operation state' " + ops + ": " + str(value))
        elif key == 'BSH.Common.Status.RemoteControlStartAllowed':
            self.remote_start_allowed = value
            logging.info(self.name + " field 'remote start allowed' " + ops + ": " + str(value))
        elif key == 'BSH.Common.Setting.PowerState':
            self._power = value
            logging.info(self.name + " field 'power state' " + ops + ": " + str(value))
        elif key == 'BSH.Common.Root.SelectedProgram':
            self._program_selected = value
            logging.info(self.name + " field 'selected program' " + ops + ": " + str(value))
        elif key == 'BSH.Common.Option.ProgramProgress':
            self.__program_progress = value
            logging.info(self.name + " field 'program progress' " + ops + ": " + str(value))
        elif key == 'BSH.Common.Status.LocalControlActive':
            self.__program_local_control_active = value
            logging.info(self.name + " field 'local control active' " + ops + ": " + str(value))
        elif key == 'BSH.Common.Status.RemoteControlActive':
            self.__program_remote_control_active = value
            logging.info(self.name + " field 'remote control active' " + ops + ": " + str(value))
        else:
            return False
        return True


    def _refresh(self, notify: bool = True, reason: str = None):
        self.last_refresh = datetime.now()
        try:
            self._do_refresh(reason)
            if notify:
                self._notify_listeners()
        except Exception as e:
            self._on_refresh_error(e)

    def _on_refresh_error(self, e):
        logging.warning("error occurred on refreshing", e)

    def _do_refresh(self, reason: str = None):
        settings = self._perform_get('/settings').get('data', {}).get('settings', {})
        logging.info("fetching settings, status and selection for " + self.name)
        self._on_values_changed(settings, "setting fetched")

        status = self._perform_get('/status').get('data', {}).get('status', {})
        self._on_values_changed(status, "status fetched")

    def _fresh_program_info(self):
        record = self._perform_get('/programs/selected', ignore_error_codes=[409]).get('data', {})
        self._on_program_selected(record.get('key', ""), record.get('options', {}))

    def _on_program_selected(self, selected_program, options):
        self._program_selected = selected_program
        logging.info(self.name + " program selected: " + str(self._program_selected))
        self._on_values_changed(options, "option fetched")

    def _perform_get(self, path:str, ignore_error_codes: List[int] = None) -> Dict[str, Any]:
        uri = self._device_uri + path
        self.request_counter.inc()
        response = requests.get(uri, headers={"Authorization": "Bearer " + self._auth.access_token}, timeout=5000)
        if is_success(response.status_code):
            return response.json()
        else:
            if ignore_error_codes is None or response.status_code not in ignore_error_codes:
                raise Exception("error occurred by calling GET " + uri + " Got " + str(response.status_code) + " " + response.text)
            return {}

    def _perform_put(self, path:str, data: str, max_trials: int = 3, current_trial: int = 1):
        uri = self._device_uri + path
        self.request_counter.inc()
        response = requests.put(uri, data=data, headers={"Content-Type": "application/json", "Authorization": "Bearer " + self._auth.access_token}, timeout=5000)
        if not is_success(response.status_code):
            logging.warning("error occurred by calling PUT " + uri + " " + data)
            logging.warning("got " + str(response.status_code) + " " + str(response.text))
            if current_trial <= max_trials:
                delay = 1 + current_trial
                logging.warning("waiting " + str(delay) + " sec for retry")
                sleep(delay)
                self._perform_put(path, data, max_trials, current_trial+1)
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



class Dishwasher(Appliance):

    def __init__(self, device_uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str, request_counter: DailyRequestCounter):
        self.__program_start_in_relative_sec = 0
        self.program_remaining_time_sec = 0
        self.__program_active = ""
        self.program_extra_try = ""
        self.program_hygiene_plus = ""
        self.program_vario_speed_plus = ""
        self.program_energy_forecast_percent = 0
        self.program_water_forecast_percent = 0
        super().__init__(device_uri, auth, name, device_type, haid, brand, vib, enumber, request_counter)

    def _on_value_changed(self, key: str, value: str, ops: str) -> bool:
        if key == 'BSH.Common.Root.ActiveProgram':
            self.__program_active = value
            logging.info(self.name + " field 'active program' " + ops + ": " + str(value))
        elif key == 'BSH.Common.Option.StartInRelative':
            self.__program_start_in_relative_sec = value
            logging.info(self.name + " field 'start in relative' " + ops + ": " + str(value))
        elif key == 'Dishcare.Dishwasher.Option.ExtraDry':
            self.program_extra_try = value
        elif key == 'Dishcare.Dishwasher.Option.HygienePlus':
            self.program_hygiene_plus = value
        elif key == 'Dishcare.Dishwasher.Option.VarioSpeedPlus':
            self.program_vario_speed_plus = value
        elif key == 'BSH.Common.Option.EnergyForecast':
            self.program_energy_forecast_percent = value
        elif key == 'BSH.Common.Option.WaterForecast':
            self.program_water_forecast_percent = value
        elif key == 'BSH.Common.Option.RemainingProgramTime':
            self.program_remaining_time_sec = value
            logging.info(self.name + " field 'remaining program time' " + ops + ": " + str(value))
        else:
            return super()._on_value_changed(key, value, ops)
        return True

    def _on_program_selected(self, selected_program, options):
        super()._on_program_selected(selected_program, options)

    def _do_refresh(self, reason: str = None):
        super()._do_refresh(reason)
        record = self._perform_get('/programs/active', ignore_error_codes=[404]).get('data', {})
        self._on_values_changed(record.get('options', {}), "fetched")

    def read_start_date(self) -> str:
        start_date = datetime.now() + timedelta(seconds=self.__program_start_in_relative_sec)
        if start_date > datetime.now():
            return start_date.strftime("%Y-%m-%dT%H:%M")
        else:
            return ""

    def write_start_date(self, start_date: str):
        self._refresh(notify=False, reason=self.name + " write start date pre-refresh")

        if self._operation in ["BSH.Common.EnumType.OperationState.Ready"]:
            remaining_secs_to_wait = Targetdate(start_date).remaining_secs_to_finish(self.program_remaining_time_sec)
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
            try:
                self._perform_put("/programs/active", json.dumps(data, indent=2), max_trials=3)
                logging.info(self.name + " program " + self.program_selected + " starts in " + print_duration(remaining_secs_to_wait) + " (program duration " + print_duration(self.program_remaining_time_sec) + ")")
            except Exception as e:
                logging.warning("error occurred by starting " + self.name + " " + str(e))
        else:
            logging.warning("ignoring start command. " + self.name + " is in state " + self._operation)



class Dryer(Appliance):

    def __init__(self, device_uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str, request_counter: DailyRequestCounter):
        self.__program_finish_in_relative_sec = 0
        self.child_lock = False
        self.program_gentle = False
        self.__program_drying_target = ""
        self.__program_drying_target_adjustment = ""
        self.__program_wrinkle_guard = ""
        self.__program_duration_sec = 0
        super().__init__(device_uri, auth, name, device_type, haid, brand, vib, enumber, request_counter)

    def _on_refresh_error(self, e):
        logging.warning("error occurred on refreshing " + str(e))
        logging.info(self.name + " seems to be offline")
        self._power = 'BSH.Common.EnumType.PowerState.Off'
        self._notify_listeners()

    @property
    def program_duration_sec(self) -> int:
        if self.__program_finish_in_relative_sec > 0:
            return self.__program_finish_in_relative_sec
        else:
            return 3 * 60 * 60

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

    def _on_value_changed(self, key: str, value: str, ops: str) -> bool:
        logging.debug(self.name + " " + key + "=" + str(value))
        if key == 'BSH.Common.Option.FinishInRelative':
            self.__program_finish_in_relative_sec = value
            logging.info(self.name + " field 'finish in relative' " + ops + ": " + str(value))
        elif key == 'BSH.Common.Setting.ChildLock':
            self.child_lock = value
            logging.info(self.name + " field 'child lock' " + ops + ": " + str(value))
        elif key == 'LaundryCare.Dryer.Option.DryingTarget':
            self.__program_drying_target = value
        elif key == 'LaundryCare.Dryer.Option.DryingTargetAdjustment':
            self.__program_drying_target_adjustment = value
        elif key == 'LaundryCare.Dryer.Option.Gentle':
            self.program_gentle = value
        elif key == 'LaundryCare.Dryer.Option.WrinkleGuard':
            self.__program_wrinkle_guard = value
        else:
            return super()._on_value_changed(key, value, ops)
        return True

    def read_end_date(self) -> str:
        end_date = datetime.now() + timedelta(seconds=self.__program_finish_in_relative_sec)
        if end_date > datetime.now():
            return end_date.strftime("%Y-%m-%dT%H:%M")
        else:
            return ""

    def read_start_date(self) -> str:
        end_date = datetime.now() + timedelta(seconds=self.__program_finish_in_relative_sec)
        start_date = end_date - timedelta(seconds=self.__program_duration_sec)
        if start_date > datetime.now():
            return start_date.strftime("%Y-%m-%dT%H:%M")
        else:
            return ""

    def __update_target_date_options(self, targetdate: Targetdate):
        if len(self._program_selected) > 0:
            d = self._perform_get('/programs/available/' + self._program_selected)
            print(d)
            for options in self._perform_get('/programs/available/' + self._program_selected).get('data', {}).get('options', []):
                if options.get('key', "") == 'BSH.Common.Option.FinishInRelative':
                    targetdate.unit = options.get("unit", targetdate.unit)
                    constrains = options.get("constraints", {})
                    targetdate.max = constrains.get("max", targetdate.max)
                    targetdate.stepsize = constrains.get("stepsize", targetdate.stepsize)

    def write_end_date(self, end_date: str):
        self._refresh(notify=False, reason=self.name + " write end date pre-refresh")
        if self._operation in ["BSH.Common.EnumType.OperationState.Ready", '']:
            start_date = datetime.fromisoformat(end_date) - timedelta(seconds=self.program_duration_sec)
            logging.info("WRITE_END_DATE end_date " + str(end_date))
            logging.info("WRITE_END_DATE program_duration_sec " + str(self.program_duration_sec))
            logging.info("WRITE_END_DATE computed start_date " + str(start_date.isoformat()))
            self.write_start_date(start_date.isoformat())

    def write_start_date(self, start_date: str):
        self._refresh(notify=False, reason=self.name + " write start date pre-refresh")
        self._fresh_program_info()
        if self._operation in ["BSH.Common.EnumType.OperationState.Ready", '']:
            targetdate = Targetdate(start_date)
            self.__update_target_date_options(targetdate)
            remaining_secs_to_finish = targetdate.remaining_secs_to_finish(self.program_duration_sec)
            logging.info("WRITE_START_DATE start_date " + str(start_date))
            logging.info("WRITE_START_DATE remaining secs to start " + str(targetdate.remaining_secs_to_start()))
            logging.info("WRITE_START_DATE program_duration_sec " + str(self.program_duration_sec))
            logging.info("WRITE_START_DATE remaining_secs_to_finish " + str(remaining_secs_to_finish))

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
                logging.info(self.name + " program " + "self.program_selected" + " starts in " + print_duration(targetdate.remaining_secs_to_start()) + " (duration: " + print_duration(self.program_duration_sec) + ")")
            except Exception as e:
                logging.warning("error occurred by starting " + self.name + " " + str(e))
        else:
            logging.warning("ignoring start command. " + self.name + " is in state " + self._operation)



def create_appliance(uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str, request_counter: DailyRequestCounter) -> Optional[Appliance]:
    if device_type.lower() == DISHWASHER:
        return Dishwasher(uri, auth, name, device_type, haid, brand, vib, enumber, request_counter)
    elif device_type.lower() == DRYER:
        return Dryer(uri, auth, name, device_type, haid, brand, vib, enumber, request_counter)
    else:
        return None



class HomeConnect:

    API_URI = "https://api.home-connect.com/api"

    def __init__(self, refresh_token: str, client_secret: str):
        self.notify_listeners: List[EventListener] = list()
        self.auth = Auth(refresh_token, client_secret)
        self.request_counter = DailyRequestCounter()
        Thread(target=self.__start_consuming_events, daemon=True).start()

    # will be called by a background thread
    def __start_consuming_events(self):
        sleep(5)
        ReconnectingEventStream(HomeConnect.API_URI + "/homeappliances/events",
                                self.auth,
                                self,
                                self.request_counter,
                                read_timeout_sec=3*60,
                                max_lifetime_sec=7*60*60).consume()

    def __is_assigned(self, notify_listener: EventListener, event):
        return event is None or event.id is None or event.id == notify_listener.id()

    def on_connected(self, event):
        for notify_listener in self.notify_listeners:
            if self.__is_assigned(notify_listener, event):
                notify_listener.on_connected(event)

    def on_disconnected(self, event):
        for notify_listener in self.notify_listeners:
            if self.__is_assigned(notify_listener, event):
                notify_listener.on_disconnected(event)

    def on_keep_alive_event(self, event):
        for notify_listener in self.notify_listeners:
            if self.__is_assigned(notify_listener, event):
                notify_listener.on_keep_alive_event(event)

    def on_notify_event(self, event):
        for notify_listener in self.notify_listeners:
            if self.__is_assigned(notify_listener, event):
                notify_listener.on_notify_event(event)

    def on_status_event(self, event):
        for notify_listener in self.notify_listeners:
            if self.__is_assigned(notify_listener, event):
                notify_listener.on_status_event(event)

    def on_event_event(self, event):
        for notify_listener in self.notify_listeners:
            if self.__is_assigned(notify_listener, event):
                notify_listener.on_event_event(event)

    def appliances(self) -> List[Appliance]:
        uri = HomeConnect.API_URI + "/homeappliances"
        logging.info("requesting " + uri)
        response = requests.get(uri, headers={"Authorization": "Bearer " + self.auth.access_token}, timeout=5000)
        if is_success(response.status_code):
            data = response.json()
            devices = list()
            for homeappliances in data['data']['homeappliances']:
                device = create_appliance(HomeConnect.API_URI + "/homeappliances/" + homeappliances['haId'],
                                          self.auth,
                                          homeappliances['name'],
                                          homeappliances['type'],
                                          homeappliances['haId'],
                                          homeappliances['brand'],
                                          homeappliances['vib'],
                                          homeappliances['enumber'],
                                          self.request_counter)
                if device is not None:
                    self.notify_listeners.append(device)
                    devices.append(device)
            return devices
        else:
            logging.warning("error occurred by calling GET " + uri)
            logging.warning("got " + str(response.status_code) + " " + response.text)
            raise Exception("error occurred by calling GET " + uri + " Got " + str(response))

    def dishwashers(self) -> List[Dishwasher]:
        return [device for device in self.appliances() if isinstance(device, Dishwasher)]

    def dishwasher(self) -> Optional[Dishwasher]:
        dishwashers = self.dishwashers()
        if len(dishwashers) > 0:
            return dishwashers[0]
        else:
            return None

    def dryers(self) -> List[Dryer]:
        return [device for device in self.appliances() if isinstance(device, Dryer)]

    def dryer(self) -> Optional[Dryer]:
        dryers = self.dryers()
        if len(dryers) > 0:
            return dryers[0]
        else:
            return None

