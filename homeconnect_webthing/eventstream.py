import logging
import requests
import sseclient
from abc import ABC, abstractmethod
from time import sleep
from threading import Thread
from datetime import datetime, timedelta
from homeconnect_webthing.auth import Auth
from homeconnect_webthing.utils import print_duration, DailyRequestCounter



class EventListener(ABC):

    @abstractmethod
    def id(self) -> str:
        pass

    def on_connected(self, event):
        pass

    def on_disconnected(self, event):
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
                 request_counter: DailyRequestCounter,
                 read_timeout_sec: int,
                 max_lifetime_sec:int):
        self.uri = uri
        self.auth = auth
        self.read_timeout_sec = read_timeout_sec
        self.max_lifetime_sec = max_lifetime_sec
        self.request_counter = request_counter
        self.notify_listener = notify_listener
        self.stream = None
        self.is_running = True

    def close(self, reason: str = None):
        if reason is not None:
            logging.info("terminating reconnecting event stream " + reason)
        self.is_running = False
        self.stream.close()

    def consume(self):
        num_trials = 0
        while self.is_running:
            try:
                num_trials += 1
                self.stream = EventStream(self.uri, self.auth, self.notify_listener, self.request_counter, self.read_timeout_sec, self.max_lifetime_sec)
                EventStreamWatchDog(self.stream, int(self.max_lifetime_sec * 1.1)).start()
                self.stream.consume()
                num_trials = 0
            except Exception as e:
                logging.warning("error has been occurred for event stream " + self.uri + " " + str(e))
                if num_trials < 3:
                    wait_time_sec = 5
                elif num_trials < 5:
                    wait_time_sec = 30
                else:
                    wait_time_sec = 60*60
                logging.info("try reconnect in " + print_duration(wait_time_sec) + " sec...")
                sleep(wait_time_sec)
                logging.info("reconnecting")


class EventStream:

    def __init__(self, uri: str, auth: Auth, notify_listener, request_counter: DailyRequestCounter, read_timeout_sec: int, max_lifetime_sec:int):
        self.uri = uri
        self.auth = auth
        self.read_timeout_sec = read_timeout_sec
        self.max_lifetime_sec = max_lifetime_sec
        self.request_counter = request_counter
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
            logging.info("opening event stream connection " + self.uri + " (read timeout: " + print_duration(self.read_timeout_sec) + ", life timeout: " + print_duration(self.max_lifetime_sec) + ")")
            self.request_counter.inc()
            self.response = requests.get(self.uri,
                                         stream=True,
                                         timeout=self.read_timeout_sec,
                                         headers={'Accept': 'text/event-stream', "Authorization": "Bearer " + self.auth.access_token})

            if 200 <= self.response.status_code <= 299:
                self.stream = sseclient.SSEClient(self.response)
                self.notify_listener.on_connected(None)

                logging.info("consuming events...")
                try:
                    for event in self.stream.events():
                        next_reconnect_date = connect_time + timedelta(seconds=self.max_lifetime_sec)
                        remaining_secs_next_reconnect = round((next_reconnect_date - datetime.now()).total_seconds())
                        if event.event.upper() == "NOTIFY":
                            self.notify_listener.on_notify_event(event)
                        elif event.event.upper() == "KEEP-ALIVE":
                            logging.debug("keep alive event (remaining life time " + print_duration(remaining_secs_next_reconnect) + ")")
                            self.notify_listener.on_keep_alive_event(event)
                        elif event.event.upper() == "STATUS":
                            self.notify_listener.on_status_event(event)
                        elif event.event.upper() == "EVENT":
                            self.notify_listener.on_event_event(event)
                        elif event.event.upper() == "CONNECTED":
                            logging.info("device reconnected " + str(event))
                            self.notify_listener.on_connected(event)
                        elif event.event.upper() == "DISCONNECTED":
                            logging.info("device disconnected " + str(event))
                            self.notify_listener.on_disconnected(event)
                        else:
                            logging.info("unknown event type " + str(event.event))

                        if remaining_secs_next_reconnect <= 0:
                            self.close("Max lifetime " + print_duration(self.max_lifetime_sec) + " reached (periodic reconnect)")

                        if self.stream is None:
                            return
                except Exception as e:
                    if datetime.now() > (connect_time + timedelta(seconds=self.max_lifetime_sec)):
                        self.close("Max lifetime " + print_duration(self.max_lifetime_sec) + " reached (periodic reconnect)")
                    else:
                        raise e
            else:
                if self.response.headers.get('Content-Type', 'text/event-stream').lower() == 'text/event-stream':
                    raise Exception("opening event stream returns " + str(self.response.status_code))
                else:
                    raise Exception("opening event stream returns " + str(self.response.status_code) + " " + self.response.text)
        finally:
            try:
                self.close()
                logging.info("event stream closed (elapsed: " + print_duration(int((datetime.now()-connect_time).total_seconds())) + ")")
            finally:
                self.notify_listener.on_disconnected(None)



class EventStreamWatchDog:

    def __init__(self, event_stream: EventStream, max_lifetime_sec:int):
        self.event_stream = event_stream
        self.max_lifetime_sec = max_lifetime_sec

    def start(self):
        Thread(target=self.watch, daemon=True).start()

    def watch(self):
        sleep(self.max_lifetime_sec)
        self.event_stream.close("by watchdog (life time " + print_duration(self.max_lifetime_sec) + " exceeded)")
