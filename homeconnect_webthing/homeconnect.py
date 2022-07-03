import logging
import requests
import sseclient
import json
from time import sleep
from threading import Thread
from typing import List, Optional
from homeconnect_webthing.auth import Auth



class Device:

    def __init__(self, uri: str, auth: Auth, name: str, type: str, haid: str, brand: str, vib: str, enumber: str):
        self._uri = uri
        self._auth = auth
        self.name = name
        self.type = type
        self.haid = haid
        self.brand = brand
        self.vib = vib
        self.enumber = enumber

        self.listeners = set()

    def is_dishwasher(self) -> bool:
        return False

    def _query(self, path: str):
        uri = self._uri + path
        response = requests.get(uri, headers={"Authorization": "Bearer " + self._auth.access_token})
        response.raise_for_status()
        return response.json()['data']

    def _on_event(self, event):
        if event.id == self.haid:
            for listener in self.listeners:
                listener(event.data)

    def on_updates(self, listener):
        self.listeners.add(listener)

    def __str__(self):
        return self.name + " (" + self.haid + ")"

    def __repr__(self):
        return self.__str__()


class Dishwasher(Device):

    def is_dishwasher(self) -> bool:
        return True

    @property
    def power(self) -> str:
        return self._query('/settings/BSH.Common.Setting.PowerState')['value']

    @property
    def operation(self) -> str:
        return self._query("/status/BSH.Common.Status.OperationState")['value']

    @property
    def remote_start_allowed(self) -> str:
        return self._query("/status/BSH.Common.Status.RemoteControlStartAllowed")['value']

    @property
    def door(self) -> str:
        return self._query("/status/BSH.Common.Status.DoorState")['value']

    @property
    def program(self) -> str:
        return self._query("/programs/selected")['key']

    def start_program(self):
        if self.operation == "BSH.Common.EnumType.OperationState.Run":
            logging.info("dishwasher is already running")
        else:
            uri = self._uri + "/programs/active"

            data = {
                "data": {
                    "key": self.program,
                    "options": [ ]
                }
            }
            js = json.dumps(data, indent=2)
            response = requests.put(uri, data=js, headers={"Content-Type": "application/json", "Authorization": "Bearer " + self._auth.access_token})
            response.raise_for_status()

    def __str__(self):
        return "power=" + str(self.power) + \
               "operation=" + str(self.operation) + \
               "\ndoor=" + str(self.door) + \
               "\nremote_start_allowed=" + str(self.remote_start_allowed) + \
               "\nprogram=" + str(self.program)

    def __repr__(self):
        return self.__str__()


def create_device(uri: str, auth: Auth, name: str, type: str, haid: str, brand: str, vib: str, enumber: str) -> Device:
    if type.lower() == "dishwasher":
        return Dishwasher(uri, auth, name, type, haid, brand, vib, enumber)
    else:
        return Device(uri, auth, name, type, haid, brand, vib, enumber)


class HomeConnect:

    API_URI = "https://api.home-connect.com/api"

    def __init__(self):
        self.event_listeners = set()
        self.auth = Auth.load()
        if self.auth == None:
            refresh_token = input("Please enter refresh token: ").strip()
            client_secret = input("Please enter client secret: ").strip()
            self.auth = Auth(refresh_token, client_secret)
            self.auth.store()
        Thread(target=self.__listening_for_updates, daemon=True).start()

    def __listening_for_updates(self):
        uri = HomeConnect.API_URI + "/homeappliances/events"
        while True:
            try:
                logging.info("opening sse socket to " + uri)
                response = requests.get(uri, stream=True, headers={'Accept': 'text/event-stream', "Authorization": "Bearer " + self.auth.access_token})
                response.raise_for_status()
                client = sseclient.SSEClient(response)
                for event in client.events():
                    if event.event == "NOTIFY":
                        for listener in self.event_listeners:
                            listener(event)
            except Exception as e:
                logging.warning("Error occurred by opening sse socket to " + uri, e)
                sleep(5)

    def devices(self) -> List[Device]:
        response = requests.get(HomeConnect.API_URI + "/homeappliances", headers={"Authorization": "Bearer " + self.auth.access_token})
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
            self.event_listeners.add(device._on_event)
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

