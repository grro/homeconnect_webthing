import logging
import requests
from time import sleep
from threading import Thread
from typing import List, Optional
from homeconnect_webthing.auth import Auth
from homeconnect_webthing.eventstream import EventListener, ReconnectingEventStream
from homeconnect_webthing.appliances import Appliance, Dishwasher, Dryer, Washer
from homeconnect_webthing.utils import is_success



def create_appliance(uri: str, auth: Auth, name: str, device_type: str, haid: str, brand: str, vib: str, enumber: str) -> Optional[Appliance]:
    if device_type.lower() == Dishwasher.DeviceType:
        return Dishwasher(uri, auth, name, device_type, haid, brand, vib, enumber)
    if device_type.lower() == Washer.DeviceType:
        return Washer(uri, auth, name, device_type, haid, brand, vib, enumber)
    elif device_type.lower() == Dryer.DeviceType:
        return Dryer(uri, auth, name, device_type, haid, brand, vib, enumber)
    else:
        logging.warning("unknown device type " + device_type + " ignoring it")
        return None



class HomeConnect:

    API_URI = "https://api.home-connect.com/api"

    def __init__(self, refresh_token: str, client_secret: str):
        self.notify_listeners: List[EventListener] = list()
        self.auth = Auth(refresh_token, client_secret)
        self.appliances: List[Appliance] = []
        self.refresh_devices()
        Thread(target=self.__start_consuming_events, daemon=True).start()

    def refresh_devices(self):
        uri = HomeConnect.API_URI + "/homeappliances"
        logging.info("requesting " + uri)
        response = requests.get(uri, headers={"Authorization": "Bearer " + self.auth.access_token}, timeout=5000)
        if is_success(response.status_code):
            data = response.json()
            fetch_appliances = list()
            for homeappliances in data['data']['homeappliances']:
                appliances = create_appliance(HomeConnect.API_URI + "/homeappliances/" + homeappliances['haId'],
                                              self.auth,
                                              homeappliances['name'],
                                              homeappliances['type'],
                                              homeappliances['haId'],
                                              homeappliances['brand'],
                                              homeappliances['vib'],
                                              homeappliances['enumber'])
                if appliances is None:
                    logging.warning("unsupported device type: " + homeappliances['type'] + " (" + homeappliances['haId'] + "). Ignoring it")
                else:
                    self.notify_listeners.append(appliances)
                    fetch_appliances.append(appliances)
            self.appliances = fetch_appliances
        else:
            logging.warning("error occurred by calling GET " + uri)
            logging.warning("got " + str(response.status_code) + " " + response.text)
            raise Exception("error occurred by calling GET " + uri + " Got " + str(response))

    # will be called by a background thread
    def __start_consuming_events(self):
        sleep(5)
        ReconnectingEventStream(HomeConnect.API_URI + "/homeappliances/events",
                                self.auth,
                                self,
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

    def dishwashers(self) -> List[Dishwasher]:
        return [device for device in self.appliances if isinstance(device, Dishwasher)]

    def dishwasher(self) -> Optional[Dishwasher]:
        dishwashers = self.dishwashers()
        if len(dishwashers) > 0:
            return dishwashers[0]
        else:
            return None

    def dryers(self) -> List[Dryer]:
        return [device for device in self.appliances if isinstance(device, Dryer)]

    def dryer(self) -> Optional[Dryer]:
        dryers = self.dryers()
        if len(dryers) > 0:
            return dryers[0]
        else:
            return None

    def washers(self) -> List[Washer]:
        return [device for device in self.appliances if isinstance(device, Washer)]

    def washer(self) -> Optional[Washer]:
        washers = self.washers()
        if len(washers) > 0:
            return washers[0]
        else:
            return None

