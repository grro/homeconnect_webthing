import logging
import requests
import sseclient
from abc import ABC
from time import sleep
from threading import Thread
from datetime import datetime, timedelta
from homeconnect_webthing.auth import Auth



def print_duration(time: int):
    if time > 60 * 60:
        return str(round(time/(60*60), 1)) + " hour"
    elif time > 60:
        return str(round(time/60, 1)) + " min"
    else:
        return str(time) + " sec"


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
        self.stream = None
        self.is_running = True

    def close(self, reason: str = None):
        if reason is not None:
            logging.info("terminating reconnecting event stream " + reason)
        self.is_running = False
        self.stream.close()

    def consume(self):
        while self.is_running:
            start_time = datetime.now()
            try:
                self.stream = EventStream(self.uri, self.auth, self.notify_listener, self.read_timeout_sec, self.max_lifetime_sec)
                EventStreamWatchDog(self.stream, int(self.max_lifetime_sec * 1.1)).start()
                self.stream.consume()
            except Exception as e:
                logging.warning("error occurred for Event stream " + self.uri, e)
                elapsed_min = (datetime.now() - start_time).total_seconds() / 60
                wait_time_sec = self.reconnect_delay_long_sec if (elapsed_min < 30) else self.reconnect_delay_short_sec
                logging.info("try reconnect in " + print_duration(wait_time_sec) + " sec...")
                sleep(wait_time_sec)
                logging.info("reconnecting")


class EventStream:

    def __init__(self, uri: str, auth: Auth, notify_listener, read_timeout_sec: int, max_lifetime_sec:int):
        self.uri = uri
        self.auth = auth
        self.read_timeout_sec = read_timeout_sec
        self.max_lifetime_sec = max_lifetime_sec
        self.notify_listener = notify_listener
        self.stream = None

    def close(self, reason: str = None):
        if self.stream is not None:
            if reason is not None:
                logging.info("closing event stream " + reason)
            try:
                self.stream.close()
            except Exception as e:
                pass
        self.stream = None

    def consume(self):
        connect_time = datetime.now()
        self.stream = None
        try:
            logging.info("opening event stream connection " + self.uri + "(read timeout " + str(self.read_timeout_sec) + " sec, lifetimeout " + str(self.max_lifetime_sec) + " sec)")
            self.response = requests.get(self.uri,
                                         stream=True,
                                         timeout=self.read_timeout_sec,
                                         headers={'Accept': 'text/event-stream', "Authorization": "Bearer " + self.auth.access_token})

            if 200 <= self.response.status_code <= 299:
                self.stream = sseclient.SSEClient(self.response)
                logging.info("notify event stream connected")
                self.notify_listener.on_connected()

                logging.info("consuming events... (read timeout: " + print_duration(self.read_timeout_sec) + ", max lifetime: " + print_duration(self.max_lifetime_sec) + ")")
                for event in self.stream.events():
                    if event.event.upper() == "NOTIFY":
                        self.notify_listener.on_notify_event(event)
                    elif event.event.upper() == "KEEP-ALIVE":
                        self.notify_listener.on_keep_alive_event(event)
                    elif event.event.upper() == "STATUS":
                        self.notify_listener.on_status_event(event)
                    elif event.event.upper() == "EVENT":
                        self.notify_listener.on_event_event(event)
                    elif event.event.upper() == "CONNECTED":
                        logging.info("device reconnected " + str(event))
                        self.notify_listener.on_connected()
                    elif event.event.upper() == "DISCONNECTED":
                        logging.info("device disconnected " + str(event))
                        self.notify_listener.on_disconnected()
                    else:
                        logging.info("unknown event type " + str(event.event))

                    if datetime.now() > (connect_time + timedelta(seconds=self.max_lifetime_sec)):
                        self.close("Max lifetime " + print_duration(self.max_lifetime_sec) + " reached (periodic reconnect)")

                    if self.stream is None:
                        return
            else:
                logging.warning("error occurred by opening event stream " + self.uri +
                                " Got " + str(self.response.status_code) + " " + self.response.text)
        finally:
            self.notify_listener.on_disconnected()
            self.close()


class EventStreamWatchDog:

    def __init__(self, event_stream: EventStream, max_lifetime_sec:int):
        self.event_stream = event_stream
        self.max_lifetime_sec = max_lifetime_sec

    def start(self):
        Thread(target=self.watch, daemon=True).start()

    def watch(self):
        sleep(self.max_lifetime_sec)
        self.event_stream.close("by watchdog (life time " + print_duration(self.max_lifetime_sec) + " exceeded)")
