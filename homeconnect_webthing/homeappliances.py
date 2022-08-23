import logging
import requests
import json
from time import sleep
from threading import Thread
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from homeconnect_webthing.auth import Auth
from homeconnect_webthing.eventstream import EventListener, ReconnectingEventStream


def is_success(status_code: int) -> bool:
    return status_code >= 200 and status_code <= 299


class Device(EventListener):

    def __init__(self, uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str):
        self._uri = uri
        self._auth = auth
        self.name = name
        self.device_type = device_type
        self.haid = haid
        self.brand = brand
        self.vib = vib
        self.enumber = enumber

    def is_dishwasher(self) -> bool:
        return False

    def _perform_get(self, path:str, ignore_error: bool = False) -> Dict[str, Any]:
        uri = self._uri + path
        #logging.info("query GET " + uri)
        response = requests.get(uri, headers={"Authorization": "Bearer " + self._auth.access_token}, timeout=5000)
        if is_success(response.status_code):
            return response.json()
        else:
            if not ignore_error:
                logging.warning("error occurred by calling GET " + uri)
                logging.warning("got " + str(response.status_code) + " " + response.text)
                raise Exception("error occurred by calling GET " + uri + " Got " + str(response))
            else:
                return {}

    def _perform_put(self, path:str, data: str, max_trials: int = 3, current_trial: int = 1):
        uri = self._uri + path
        response = requests.put(uri, data=data, headers={"Content-Type": "application/json", "Authorization": "Bearer " + self._auth.access_token}, timeout=5000)
        if not is_success(response.status_code):
            logging.warning("error occurred by calling PUT " + uri + " " + data)
            logging.warning("got " + str(response.status_code) + " " + str(response.text))
            if current_trial <= max_trials:
                delay = 1 + current_trial
                logging.warning("waiting " + str(delay) + " sec for retry")
                sleep(delay)
                self._perform_put(path, data, max_trials, current_trial+1)

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
            return self.name + " (" + self.haid + ")"

    def __repr__(self):
        return self.__str__()



class Dishwasher(Device):

    def __init__(self, uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str):
        self.__power = ""
        self.__operation = ""
        self.__door = ""
        self.__program_selected = ""
        self.remote_start_allowed = False
        self.__program_start_in_relative_sec = 0
        self.__program_progress = 0
        self.__program_active = ""
        self.__program_remote_control_active = ""
        self.program_remaining_time_sec = 0
        self.program_extra_try = ""
        self.program_hygiene_plus = ""
        self.program_vario_speed_plus = ""
        self.program_energy_forecast_percent = 0
        self.program_water_forecast_percent = 0
        self._value_changed_listeners = set()
        self.last_refresh = datetime.now() - timedelta(hours=9)
        super().__init__(uri, auth, name, device_type, haid, brand, vib, enumber)
        self.__refresh(reason="dishwasher appliance initialized")

    def is_dishwasher(self) -> bool:
        return True

    def register_value_changed_listener(self, value_changed_listener):
        self._value_changed_listeners.add(value_changed_listener)
        logging.info("value_changed_listener " + str(value_changed_listener) + " registered")
        self.__notify_listeners()

    def __notify_listeners(self):
        for value_changed_listener in self._value_changed_listeners:
            value_changed_listener()

    def on_connected(self):
        logging.info("refresh state (new event stream connection)")
        self.__refresh(reason="on connected")

    def on_keep_alive_event(self, event):
        logging.debug("keep alive event")

    def on_notify_event(self, event):
        logging.debug("notify event: " + str(event.data))
        self.on__value_changed_event(event)

    def on_status_event(self, event):
        logging.debug("status event: " + str(event.data))
        self.on__value_changed_event(event)

    def on_event_event(self, event):
        logging.debug("event event: " + str(event.data))
        pass

    def on__value_changed_event(self, event):
        if event.id == self.haid:
            try:
                data = json.loads(event.data)
                self.__on_value_changes(data.get('items', []), "updated")
                self.__notify_listeners()
            except Exception as e:
                logging.warning("error occurred by handling event " + str(event), e)

    def __on_value_changes(self, changes: List[Any], ops: str = "updated"):
        for record in changes:
            key = record.get('key', "")
            if key == 'BSH.Common.Status.DoorState':
                self.__door = record['value']
                logging.info("door state " + ops + ": " + str(self.__door))
            elif key == 'BSH.Common.Status.OperationState':
                self.__operation = record['value']
                logging.info("operation state " + ops + ": " + str(self.__operation))
            elif key == 'BSH.Common.Status.RemoteControlStartAllowed':
                self.remote_start_allowed = record['value']
                logging.info("remote start allowed " + ops + ": " + str(self.remote_start_allowed))
            elif key == 'BSH.Common.Setting.PowerState':
                self.__power = record['value']
                logging.info("power state " + ops + ": " + str(self.__power))
            elif key == 'BSH.Common.Root.SelectedProgram':
                self.__program_selected = record['value']
            elif key ==  'BSH.Common.Root.ActiveProgram':
                self.__program_active = record['value']
            elif key == 'BSH.Common.Option.StartInRelative':
                self.__program_start_in_relative_sec = record['value']
            elif key == 'BSH.Common.Option.RemainingProgramTime':
                self.program_remaining_time_sec = record['value']
            elif key == 'BSH.Common.Option.ProgramProgress':
                self.__program_progress = record['value']
            elif key == 'BSH.Common.Status.RemoteControlActive':
                self.__program_remote_control_active = record['value']
            elif key == 'Dishcare.Dishwasher.Option.ExtraDry':
                self.program_extra_try = record['value']
            elif key == 'Dishcare.Dishwasher.Option.HygienePlus':
                self.program_hygiene_plus = record['value']
            elif key == 'Dishcare.Dishwasher.Option.VarioSpeedPlus':
                self.program_vario_speed_plus = record['value']
            elif key == 'BSH.Common.Option.EnergyForecast':
                self.program_energy_forecast_percent = record['value']
            elif key == 'BSH.Common.Option.WaterForecast':
                self.program_water_forecast_percent = record['value']
            else:
                print(record)
                #logging.info("unknown changed " + str(record))

    def __refresh(self, notify: bool = True, reason: str = None):
        self.last_refresh = datetime.now()
        try:
            logging.info("fetch settings, status and selection" + ("" if reason is None else " (" + reason +")"))
            settings = self._perform_get('/settings')['data']['settings']
            logging.info("settings, status and selection fetched")
            self.__on_value_changes(settings, "fetched")

            status = self._perform_get('/status')['data']['status']
            self.__on_value_changes(status, "fetched")

            record = self._perform_get('/programs/selected')['data']
            self.__program_selected = record['key']
            self.__on_value_changes(record.get('options', {}), "fetched")

            record = self._perform_get('/programs/active', ignore_error=True).get('data', {})
            self.__on_value_changes(record.get('options', {}), "fetched")

            if notify:
                self.__notify_listeners()
        except Exception as e:
            logging.warning("error occurred on refreshing", e)

    @property
    def power(self):
        if len(self.__power) > 0:
            return self.__power[self.__power.rindex('.')+1:]

    @property
    def door(self):
        if len(self.__door) > 0:
            return self.__door[self.__door.rindex('.')+1:]
        else:
            return ""

    @property
    def operation(self):
        if len(self.__operation)> 0:
            return self.__operation[self.__operation.rindex('.')+1:]
        else:
            return ""

    @property
    def program_progress(self):
        if self.operation.lower() == 'run':
            return self.__program_progress
        else:
            return 0

    @property
    def program_selected(self):
        if len(self.__program_selected) > 0:
            return self.__program_selected[self.__program_selected.rindex('.')+1:]
        else:
            return ""

    @property
    def start_date(self) -> str:
        start_date = (datetime.now() + timedelta(seconds=self.__program_start_in_relative_sec))
        if start_date > datetime.now():
            return start_date.strftime("%Y-%m-%dT%H:%M")
        else:
            return ""

    def set_start_date(self, dt: str):
        self.__refresh(notify=False, reason="startdate updated pre-refresh")
        if self.__operation == "BSH.Common.EnumType.OperationState.Ready":
            remaining_secs_to_wait = int((datetime.fromisoformat(dt) - datetime.now()).total_seconds())
            if remaining_secs_to_wait < 0:
                logging.warning("negative delay " + str(remaining_secs_to_wait) + " (start date: " + dt + ") delay set to 5 sec")
                remaining_secs_to_wait = 5
            if remaining_secs_to_wait > 86000:
                logging.warning("large delay " + str(remaining_secs_to_wait) + " (start date: " + dt + ") reduced to 86000")
                remaining_secs_to_wait = 86000

            data = {
                "data": {
                    "key": self.__program_selected,
                    "options": [{
                                    "key": "BSH.Common.Option.StartInRelative",
                                    "value": remaining_secs_to_wait,
                                    "unit": "seconds"
                                }]
                }
            }
            try:
                self._perform_put("/programs/active", json.dumps(data, indent=2), max_trials=3)
                logging.info("dishwasher program " + self.program_selected + " starts in " + str(remaining_secs_to_wait) + " secs")
            except Exception as e:
                logging.warning("error occurred by starting dishwasher", e)
        else:
            logging.info("ignoring start command. Dishwasher is in state " + self.__operation)
        self.__refresh(reason="startdate updated post-refresh")

    def __str__(self):
        return "power=" + str(self.power) + \
           "operation=" + str(self.operation) + \
           "\ndoor=" + str(self.door) + \
           "\nremote_start_allowed=" + str(self.remote_start_allowed) + \
           "\nprogram_selected=" + str(self.program_selected)

    def __repr__(self):
        return self.__str__()


def create_device(uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str) -> Device:
    if device_type.lower() == "dishwasher":
        return Dishwasher(uri, auth, name, device_type, haid, brand, vib, enumber)
    else:
        return Device(uri, auth, name, device_type, haid, brand, vib, enumber)



class HomeConnect:

    API_URI = "https://api.home-connect.com/api"

    def __init__(self, refresh_token: str, client_secret: str):
        self.notify_listeners: List[EventListener] = list()
        self.auth = Auth(refresh_token, client_secret)
        Thread(target=self.__start_consuming_events, daemon=True).start()

    def __start_consuming_events(self):
        sleep(5)
        ReconnectingEventStream(HomeConnect.API_URI + "/homeappliances/events",
                                self.auth,
                                self,
                                read_timeout_sec=15*60,
                                max_lifetime_sec=90*60).consume()

    def on_connected(self):
        for notify_listener in self.notify_listeners:
            notify_listener.on_connected()

    def on_disconnected(self):
        for notify_listener in self.notify_listeners:
            notify_listener.on_disconnected()

    def on_keep_alive_event(self, event):
        for notify_listener in self.notify_listeners:
            notify_listener.on_keep_alive_event(event)

    def on_notify_event(self, event):
        for notify_listener in self.notify_listeners:
            notify_listener.on_notify_event(event)

    def on_status_event(self, event):
        for notify_listener in self.notify_listeners:
            notify_listener.on_status_event(event)

    def on_event_event(self, event):
        for notify_listener in self.notify_listeners:
            notify_listener.on_event_event(event)

    def devices(self) -> List[Device]:
        uri = HomeConnect.API_URI + "/homeappliances"
        logging.info("requesting " + uri)
        response = requests.get(uri, headers={"Authorization": "Bearer " + self.auth.access_token}, timeout=5000)
        if is_success(response.status_code):
            data = response.json()
            devices = list()
            for homeappliances in data['data']['homeappliances']:
                device = create_device(HomeConnect.API_URI + "/homeappliances/" + homeappliances['haId'],
                                       self.auth,
                                       homeappliances['name'],
                                       homeappliances['type'],
                                       homeappliances['haId'],
                                       homeappliances['brand'],
                                       homeappliances['vib'],
                                       homeappliances['enumber'])
                self.notify_listeners.append(device)
                devices.append(device)
            return devices
        else:
            logging.warning("error occurred by calling GET " + uri)
            logging.warning("got " + str(response.status_code) + " " + response.text)
            raise Exception("error occurred by calling GET " + uri + " Got " + str(response))

    def dishwashers(self) -> List[Dishwasher]:
        return [device for device in self.devices() if isinstance(device, Dishwasher)]

    def dishwasher(self) -> Optional[Dishwasher]:
        dishwashers = self.dishwashers()
        if len(dishwashers) > 0:
            return dishwashers[0]
        else:
            return None

