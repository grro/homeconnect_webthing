import logging
import requests
import sseclient
from abc import ABC
from time import sleep
from threading import Thread
from datetime import datetime, timedelta
from homeconnect_webthing.auth import Auth


class EventListener(ABC):

    def on_connected(self):
        pass

    def on_disconnected(self):
        pass

    def on_keep_alive_event(self, event):
        pass

    def on_notify_event(self, event):
        pass

    def on_status_event(self, event):
        pass

    def on_event_event(self, event):
        pass


class ReconnectingEventStream:

    def __init__(self,
                 uri: str,
                 auth: Auth,
                 notify_listener,
                 read_timeout_sec: int,
                 max_lifetime_sec:int,
                 reconnect_delay_short_sec: int = 5,
                 reconnect_delay_long_sec: int = 5 * 60):
        self.uri = uri
        self.auth = auth
        self.read_timeout_sec = read_timeout_sec
        self.max_lifetime_sec = max_lifetime_sec
        self.reconnect_delay_short_sec = reconnect_delay_short_sec
        self.reconnect_delay_long_sec = reconnect_delay_long_sec
        self.notify_listener = notify_listener
        self.current_event_stream = None
        self.is_running = True

    def terminate(self, reason: str = ""):
        logging.info("terminating reconnecting event stream " + reason)
        self.is_running = False
        self.current_event_stream.terminate()

    def consume(self):
        while self.is_running:
            start_time = datetime.now()
            try:
                self.current_event_stream = EventStream(self.uri, self.auth, self.notify_listener, self.read_timeout_sec, self.max_lifetime_sec)
                EventStreamWatchDog(self.current_event_stream, int(self.max_lifetime_sec * 1.1)).start()
                self.current_event_stream.consume()
            except Exception as e:
                logging.warning("Event stream (" + self.uri + ") error: ", e)
                elapsed_min = (datetime.now() - start_time).total_seconds() / 60
                wait_time_sec = self.reconnect_delay_long_sec if (elapsed_min < 30) else self.reconnect_delay_short_sec
                logging.info("try reconnect in " + str(wait_time_sec) + " sec")
                sleep(wait_time_sec)
                logging.info("reconnecting")


class EventStream:

    def __init__(self, uri: str, auth: Auth, notify_listener, read_timeout_sec: int, max_lifetime_sec:int):
        self.uri = uri
        self.auth = auth
        self.read_timeout_sec = read_timeout_sec
        self.max_lifetime_sec = max_lifetime_sec
        self.notify_listener = notify_listener
        self.response = None
        self.is_running = True

    def terminate(self, reason: str = ""):
        if self.is_running:
            self.is_running = False
            logging.info("terminating event stream " + reason)
            try:
                if self.response is not None:
                    self.response.close()
                    self.response = None
            except Exception as e:
                pass

    def consume(self):
        connect_time = datetime.now()
        client = None
        try:
            logging.info("opening event stream connection " + self.uri + "(read timeout " + str(self.read_timeout_sec) + " sec, lifetimeout " + str(self.max_lifetime_sec) + " sec)")
            self.response = requests.get(self.uri,
                                         stream=True,
                                         timeout=self.read_timeout_sec,
                                         headers={'Accept': 'text/event-stream', "Authorization": "Bearer " + self.auth.access_token})

            if self.response.status_code >= 200 and self.response.status_code <= 299:
                client = sseclient.SSEClient(self.response)
                logging.info("notify event stream connected")
                self.notify_listener.on_connected()

                logging.info("consuming events...")
                for event in client.events():
                    if event.event == "NOTIFY":
                        self.notify_listener.on_notify_event(event)
                    elif event.event == "KEEP-ALIVE":
                        self.notify_listener.on_keep_alive_event(event)
                    elif event.event == "STATUS":
                        self.notify_listener.on_status_event(event)
                    elif event.event == "Event":
                        self.notify_listener.on_event_event(event)
                    else:
                        logging.info("unknown event type " + str(event.event))

                    if datetime.now() > (connect_time + timedelta(seconds=self.max_lifetime_sec)):
                        self.terminate("Max lifetime " + str(self.max_lifetime_sec) + " sec reached (periodic reconnect)")

                    if self.is_running is False:
                        return
            else:
                logging.warning("error occurred by opening event stream connection " + self.uri)
                logging.warning("got " + str(self.response.status_code) + " " + self.response.text)
        finally:
            self.notify_listener.on_disconnected()
            logging.info("event stream closed")
            if client is not None:
                client.close()


class EventStreamWatchDog:

    def __init__(self, event_stream: EventStream, max_lifetime_sec:int):
        self.event_stream = event_stream
        self.max_lifetime_sec = max_lifetime_sec

    def start(self):
        Thread(target=self.watch, daemon=True).start()

    def watch(self):
        sleep(self.max_lifetime_sec)
        self.event_stream.terminate("by watchdog")
