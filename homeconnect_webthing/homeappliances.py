import logging
import requests
import sseclient
import json
from time import sleep
from abc import ABC
from threading import Thread
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from homeconnect_webthing.auth import Auth




class EventListener(ABC):

    def on_keep_alive_event(self, event):
        pass

    def on_notify_event(self, event):
        pass

    def on_status_event(self, event):
        pass


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

    def _perform_get(self, path:str) -> Dict[str, Any]:
        uri = self._uri + path
        logging.info("query GET " + uri)
        response = requests.get(uri, headers={"Authorization": "Bearer " + self._auth.access_token})
        response.raise_for_status()
        data = response.json()
        return data

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
        self.date_refreshed = datetime.now()
        self.__power = ""
        self.__operation = ""
        self.__door = ""
        self.__program_selected = ""
        self.remote_start_allowed = False
        self.__program_start_in_relative_sec = ""
        self.__program_remaining_time = ""
        self.program_progress = 100
        self.__program_remote_control_active = ""
        self.program_extra_try = ""
        self.program_hygiene_plus = ""
        self.program_vario_speed_plus = ""
        self._value_changed_listeners = set()
        super().__init__(uri, auth, name, device_type, haid, brand, vib, enumber)
        self.__refresh()

    def is_dishwasher(self) -> bool:
        return True

    def register_value_changed_listener(self, value_changed_listener):
        self._value_changed_listeners.add(value_changed_listener)

    def on_notify_event(self, event):
        self.on__value_changed_event(event)

    def on_status_event(self, event):
        self.on__value_changed_event(event)

    def on__value_changed_event(self, event):
        if event.id == self.haid:
            try:
                logging.info("event received: " + str(event))
                logging.info("data: " + str(event.data))
                data = json.loads(event.data)
                self.__on_value_changes(data.get('items', []))
                for value_changed_listener in self._value_changed_listeners:
                    value_changed_listener()
            except Exception as e:
                logging.warning("error occurred by handling event " + str(event), e)

    def __on_value_changes(self, changes: List[Any]):
        for record in changes:
            if record['key'] == 'BSH.Common.Status.DoorState':
                self.__door = record['value']
            elif record['key'] == 'BSH.Common.Status.OperationState':
                self.__operation = record['value']
            elif record['key'] == 'BSH.Common.Status.RemoteControlStartAllowed':
                self.remote_start_allowed = record['value']
            elif record['key'] == 'BSH.Common.Setting.PowerState':
                self.__power = record['value']
            elif record['key'] == 'BSH.Common.Option.StartInRelative':
                self.__program_start_in_relative_sec = record['value']
            elif record['key'] == 'BSH.Common.Option.RemainingProgramTime':
                self.__program_remaining_time = record['value']
            elif record['key'] == 'BSH.Common.Option.ProgramProgress':
                self.program_progress = record['value']
            elif record['key'] == 'BSH.Common.Status.RemoteControlActive':
                self.__program_remote_control_active = record['value']
            elif record['key'] == 'Dishcare.Dishwasher.Option.ExtraDry':
                self.program_extra_try = record['value']
            elif record['key'] == 'Dishcare.Dishwasher.Option.HygienePlus':
                self.program_hygiene_plus = record['value']
            elif record['key'] == 'Dishcare.Dishwasher.Option.VarioSpeedPlus':
                self.program_vario_speed_plus = record['value']
            else:
                print(record)

    def on_keep_alive_event(self, event):
        if datetime.now() > (self.date_refreshed + timedelta(minutes=45)):
            logging.info("refresh state")
            self.__refresh()

    def __refresh(self):
        settings = self._perform_get('/settings')['data']['settings']
        self.__on_value_changes(settings)

        status = self._perform_get('/status')['data']['status']
        self.__on_value_changes(status)

        record = self._perform_get('/programs/selected')['data']
        self.__program_selected = record['key']
        self.__on_value_changes(record['options'])

        self.date_refreshed = datetime.now()

    @property
    def power(self):
        return self.__power[self.__power.rindex('.')+1:]

    @property
    def door(self):
        return self.__door[self.__door.rindex('.')+1:]

    @property
    def operation(self):
        return self.__operation[self.__operation.rindex('.')+1:]

    @property
    def program_selected(self):
        return self.__program_selected[self.__program_selected.rindex('.')+1:]

    @property
    def start_date(self) -> str:
        start_date = (datetime.now() + timedelta(seconds=self.__program_start_in_relative_sec))
        if start_date > datetime.now():
            return start_date.strftime("%Y-%m-%dT%H:%M")
        else:
            return ""

    def set_start_date(self, dt: str):
        if self.operation == "BSH.Common.EnumType.OperationState.Run":
            logging.info("dishwasher is already running")
        else:
            remaining_secs_to_wait = (datetime.fromisoformat(dt) - datetime.now()).seconds
            uri = self._uri + "/programs/active"
            data = {
                "data": {
                    "key": self.__program_selected,
                    "options": [ {
                                    "key": "BSH.Common.Option.StartInRelative",
                                    "value": remaining_secs_to_wait,
                                    "unit": "seconds"
                                } ]
                }
            }
            logging.info("query PUT " + uri)
            js = json.dumps(data)
            response = requests.put(uri, data=js, headers={"Content-Type": "application/json", "Authorization": "Bearer " + self._auth.access_token})
            response.raise_for_status()
            self.__refresh()

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

    def __init__(self, filename: str):
        self.notify_listeners: List[EventListener] = list()
        self.auth = Auth.load(filename)
        if self.auth == None:
            refresh_token = input("Please enter refresh token: ").strip()
            client_secret = input("Please enter client secret: ").strip()
            self.auth = Auth(refresh_token, client_secret)
            self.auth.store(filename)
        Thread(target=self.__listening_for_events, daemon=True).start()

    def __listening_for_events(self):
        sleep(3)
        uri = HomeConnect.API_URI + "/homeappliances/events"
        num_reconnect = 0
        while True:
            try:
                num_reconnect += 1
                logging.info("opening sse socket to " + uri)
                response = requests.get(uri, stream=True, headers={'Accept': 'text/event-stream', "Authorization": "Bearer " + self.auth.access_token})
                response.raise_for_status()
                client = sseclient.SSEClient(response)

                num_reconnect = 0
                logging.info("consuming event...")
                for event in client.events():
                    if event.event == "NOTIFY":
                        for notify_listener in self.notify_listeners:
                            notify_listener.on_notify_event(event)
                    elif event.event == "KEEP-ALIVE":
                        for notify_listener in self.notify_listeners:
                            notify_listener.on_keep_alive_event(event)
                    elif event.event == "STATUS":
                        for notify_listener in self.notify_listeners:
                            notify_listener.on_status_event(event)
                    else:
                        print(event)
            except Exception as e:
                logging.warning("Error occurred by opening sse socket to " + uri + " " + str(e))
                wait_time_sec = {0: 3, 1:5, 2: 30, 3: 2*60, 4: 5*60}.get(num_reconnect, 30*60)
                logging.info("try reconnect in " + str(wait_time_sec) + "sec")
                sleep(wait_time_sec)

    def devices(self) -> List[Device]:
        uri = HomeConnect.API_URI + "/homeappliances"
        logging.info("requesting " + uri)
        response = requests.get(uri, headers={"Authorization": "Bearer " + self.auth.access_token})
        response.raise_for_status()
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

    def dishwashers(self) -> List[Dishwasher]:
        return [device for device in self.devices() if isinstance(device, Dishwasher)]

    def dishwasher(self) -> Optional[Dishwasher]:
        dishwashers = self.dishwashers()
        if len(dishwashers) > 0:
            return dishwashers[0]
        else:
            return None

