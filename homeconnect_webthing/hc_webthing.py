from webthing import (MultipleThings, Property, Thing, Value, WebThingServer)
import logging
import tornado.ioloop
from homeconnect_webthing.homeconnect import HomeConnect, Dishwasher


class DishwasherThing(Thing):

    # regarding capabilities refer https://iot.mozilla.org/schemas
    # there is also another schema registry http://iotschema.org/docs/full.html not used by webthing

    def __init__(self, description: str, dishwasher: Dishwasher):
        Thing.__init__(
            self,
            'urn:dev:ops:Dishwasher-1',
            'Dishwasher',
            ['MultiLevelSensor'],
            description
        )

        self.ioloop = tornado.ioloop.IOLoop.current()

        self.dishwasher = dishwasher
        dishwasher.on_updates(self.on_updated)

        self.power = Value(dishwasher.power)
        self.add_property(
            Property(self,
                     'power',
                     self.power,
                     metadata={
                         'title': 'Power State',
                         "type": "string",
                         'description': 'The power state. See https://api-docs.home-connect.com/settings?#power-state',
                         'readOnly': True,
                     }))

        self.operation = Value(dishwasher.operation)
        self.add_property(
            Property(self,
                     'operation',
                     self.operation,
                     metadata={
                         'title': 'Operation State',
                         "type": "string",
                         'description': 'The operation state. See https://api-docs.home-connect.com/states?#operation-state',
                         'readOnly': True,
                     }))

        self.remote_start_allowed = Value(dishwasher.remote_start_allowed)
        self.add_property(
            Property(self,
                     'remote_start_allowed',
                     self.remote_start_allowed,
                     metadata={
                         'title': 'Remote Start Allowed State',
                         "type": "boolean",
                         'description': 'Remote Start Allowance State. See https://api-docs.home-connect.com/states?#remote-start-allowance-state',
                         'readOnly': True,
                     }))

        self.door = Value(dishwasher.door)
        self.add_property(
            Property(self,
                     'door',
                     self.door,
                     metadata={
                         'title': 'Door State',
                         "type": "string",
                         'description': 'Door State. See https://api-docs.home-connect.com/states?#door-state',
                         'readOnly': True,
                     }))

        self.program = Value(dishwasher.program)
        self.add_property(
            Property(self,
                     'program',
                     self.program,
                     metadata={
                         'title': 'Selected Program',
                         "type": "string",
                         'description': 'Selected Program. See https://api-docs.home-connect.com/programs-and-options?#cleaning-robot',
                         'readOnly': True,
                     }))

        self.remote_start = Value(False, self.dishwasher.start_program)
        self.add_property(
            Property(self,
                     'remote start',
                     self.remote_start,
                     metadata={
                         'title': 'Remote start',
                         "type": "bool",
                         'description': 'Remote start state',
                         'readOnly': False,
                     }))

        self.name = Value(dishwasher.name)
        self.add_property(
            Property(self,
                     'name',
                     self.name,
                     metadata={
                         'title': 'Name',
                         "type": "string",
                         'description': 'The device name',
                         'readOnly': True,
                     }))

        self.type = Value(dishwasher.type)
        self.add_property(
            Property(self,
                     'type',
                     self.type,
                     metadata={
                         'title': 'Type',
                         "type": "string",
                         'description': 'The device type',
                         'readOnly': True,
                     }))

        self.haid = Value(dishwasher.haid)
        self.add_property(
            Property(self,
                     'haid',
                     self.haid,
                     metadata={
                         'title': 'haid',
                         "type": "string",
                         'description': 'The device haid',
                         'readOnly': True,
                     }))

        self.brand = Value(dishwasher.brand)
        self.add_property(
            Property(self,
                     'brand',
                     self.brand,
                     metadata={
                         'title': 'Brand',
                         "type": "string",
                         'description': 'The device brand',
                         'readOnly': True,
                     }))

        self.vib = Value(dishwasher.vib)
        self.add_property(
            Property(self,
                     'vib',
                     self.vib,
                     metadata={
                         'title': 'Vib',
                         "type": "string",
                         'description': 'The device vib',
                         'readOnly': True,
                     }))

        self.enumber = Value(dishwasher.enumber)
        self.add_property(
            Property(self,
                     'enumber',
                     self.enumber,
                     metadata={
                         'title': 'Enumber',
                         "type": "string",
                         'description': 'The device enumber',
                         'readOnly': True,
                     }))

    def on_updated(self, reason):
        self.ioloop.add_callback(self.__on_updated, reason)

    def __on_updated(self, reason):
        self.power.notify_of_external_update(self.dishwasher.power)
        self.door.notify_of_external_update(self.dishwasher.door)
        self.operation.notify_of_external_update(self.dishwasher.operation)
        self.remote_start_allowed.notify_of_external_update(self.dishwasher.remote_start_allowed)
        self.enumber.notify_of_external_update(self.dishwasher.enumber)
        self.vib.notify_of_external_update(self.dishwasher.vib)
        self.brand.notify_of_external_update(self.dishwasher.brand)
        self.haid.notify_of_external_update(self.dishwasher.haid)
        self.name.notify_of_external_update(self.dishwasher.name)
        self.type.notify_of_external_update(self.dishwasher.type)
        self.remote_start.notify_of_external_update(False)


def run_server(port: int, description: str):
    homeappliances = []
    for device in HomeConnect().devices():
        if device.is_dishwasher():
            homeappliances.append(DishwasherThing(description, device))
    server = WebThingServer(MultipleThings(homeappliances, 'homeappliances'), port=port, disable_host_validation=True)
    try:
        logging.info('starting the server')
        server.start()
    except KeyboardInterrupt:
        logging.info('stopping the server')
        server.stop()
        logging.info('done')
