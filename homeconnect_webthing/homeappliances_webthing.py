from webthing import (MultipleThings, Property, Thing, Value, WebThingServer)
import logging
import tornado.ioloop
from datetime import datetime
from homeconnect_webthing.homeappliances import HomeConnect, Dishwasher



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

        self.dishwasher = dishwasher

        self.name = Value(dishwasher.name)
        self.add_property(
            Property(self,
                     'device_name',
                     self.name,
                     metadata={
                         'title': 'Name',
                         "type": "string",
                         'description': 'The device name',
                         'readOnly': True,
                     }))

        self.device_type = Value(dishwasher.device_type)
        self.add_property(
            Property(self,
                     'device_type',
                     self.device_type,
                     metadata={
                         'title': 'Type',
                         "type": "string",
                         'description': 'The device type',
                         'readOnly': True,
                     }))


        self.haid = Value(dishwasher.haid)
        self.add_property(
            Property(self,
                     'device_haid',
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
                     'device_brand',
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
                     'device_vib',
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
                     'device_enumber',
                     self.enumber,
                     metadata={
                         'title': 'Enumber',
                         "type": "string",
                         'description': 'The device enumber',
                         'readOnly': True,
                     }))

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

        self.selected_program = Value(dishwasher.program_selected)
        self.add_property(
            Property(self,
                     'program_selected',
                     self.selected_program,
                     metadata={
                         'title': 'Selected Program',
                         "type": "string",
                         'description': 'Selected Program',
                         'readOnly': True,
                     }))

        self.program_vario_speed_plus = Value(dishwasher.program_vario_speed_plus)
        self.add_property(
            Property(self,
                     'program_vario_speed_plus',
                     self.program_vario_speed_plus,
                     metadata={
                         'title': 'program_vario_speed_plus',
                         "type": "boolean",
                         'description': 'VarioSpeed Plus Option. See https://api-docs.home-connect.com/programs-and-options?#dishwasher_variospeed-plus-option',
                         'readOnly': True,
                     }))


        self.program_hygiene_plus = Value(dishwasher.program_hygiene_plus)
        self.add_property(
            Property(self,
                     'program_hygiene_plus',
                     self.program_hygiene_plus,
                     metadata={
                         'title': 'program_hygiene_plus',
                         "type": "boolean",
                         'description': 'Hygiene Plus Option',
                         'readOnly': True,
                     }))


        self.program_extra_try = Value(dishwasher.program_extra_try)
        self.add_property(
            Property(self,
                     'program_extra_try',
                     self.program_extra_try,
                     metadata={
                         'title': 'program_extra_try',
                         "type": "boolean",
                         'description': 'Extra Try Option',
                         'readOnly': True,
                     }))

        self.start_date = Value(dishwasher.start_date, dishwasher.set_start_date)
        self.add_property(
            Property(self,
                     'program_start_date',
                     self.start_date,
                     metadata={
                         'title': 'Start date',
                         "type": "string",
                         'description': 'The start date',
                         'readOnly': False,
                     }))

        self.program_progress = Value(dishwasher.program_progress)
        self.add_property(
            Property(self,
                     'program_progress',
                     self.program_progress,
                     metadata={
                         'title': 'Progress',
                         "type": "number",
                         'description': 'progress',
                         'readOnly': True,
                     }))

        self.ioloop = tornado.ioloop.IOLoop.current()
        self.dishwasher.register_value_changed_listener(self.on_value_changed)


    def on_value_changed(self):
        self.ioloop.add_callback(self.__on_value_changed)

    def __on_value_changed(self):
        logging.info("webthing - processing on value changed event")
        self.power.notify_of_external_update(self.dishwasher.power)
        self.door.notify_of_external_update(self.dishwasher.door)
        self.operation.notify_of_external_update(self.dishwasher.operation)
        self.remote_start_allowed.notify_of_external_update(self.dishwasher.remote_start_allowed)
        self.enumber.notify_of_external_update(self.dishwasher.enumber)
        self.selected_program.notify_of_external_update(self.dishwasher.program_selected)
        self.program_vario_speed_plus.notify_of_external_update(self.dishwasher.program_vario_speed_plus)
        self.program_hygiene_plus.notify_of_external_update(self.dishwasher.program_hygiene_plus)
        self.program_extra_try.notify_of_external_update(self.dishwasher.program_extra_try)
        self.program_progress.notify_of_external_update(self.dishwasher.program_progress)
        self.vib.notify_of_external_update(self.dishwasher.vib)
        self.brand.notify_of_external_update(self.dishwasher.brand)
        self.haid.notify_of_external_update(self.dishwasher.haid)
        self.name.notify_of_external_update(self.dishwasher.name)
        self.device_type.notify_of_external_update(self.dishwasher.device_type)
        self.start_date.notify_of_external_update(self.dishwasher.start_date)


def run_server( description: str, port: int, refresh_token: str, client_secret: str):
    homeappliances = []
    for device in HomeConnect(refresh_token, client_secret).devices():
        if device.is_dishwasher():
            homeappliances.append(DishwasherThing(description, device))
    homeappliances.sort()
    logging.info(str(len(homeappliances)) + " homeappliances found: " + ", ".join([homeappliance.dishwasher.name + "/" + homeappliance.dishwasher.enumber for homeappliance in homeappliances]))
    server = WebThingServer(MultipleThings(homeappliances, 'homeappliances'), port=port, disable_host_validation=True)
    logging.info('running webthing server http://localhost:' + str(port))
    try:
        server.start()
    except KeyboardInterrupt:
        logging.info('stopping webthing server')
        server.stop()
        logging.info('done')

