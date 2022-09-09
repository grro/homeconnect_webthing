from webthing import (MultipleThings, Property, Thing, Value, WebThingServer)
import logging
import tornado.ioloop
from homeconnect_webthing.homeappliances import HomeConnect, Appliance, Dishwasher, Dryer, DISHWASHER, DRYER



class ApplianceThing(Thing):

    # regarding capabilities refer https://iot.mozilla.org/schemas
    # there is also another schema registry http://iotschema.org/docs/full.html not used by webthing

    def __init__(self, description: str, appliance: Appliance):
        Thing.__init__(
            self,
            'urn:dev:ops:' + appliance.device_type + '-1',
            appliance.device_type,
            ['MultiLevelSensor'],
            description
        )
        self.ioloop = tornado.ioloop.IOLoop.current()
        self.appliance = appliance

        self.name = Value(appliance.name)
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

        self.device_type = Value(appliance.device_type)
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

        self.haid = Value(appliance.haid)
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

        self.brand = Value(appliance.brand)
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

        self.vib = Value(appliance.vib)
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

        self.enumber = Value(appliance.enumber)
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

        self.power = Value(appliance.power)
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

        self.door = Value(appliance.door)
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

        self.operation = Value(appliance.operation)
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

        self.remote_start_allowed = Value(appliance.remote_start_allowed)
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

        self.start_date = Value(appliance.read_start_date(), appliance.write_start_date)
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

    def activate(self):
        self.appliance.register_value_changed_listener(self.on_value_changed)
        return self

    def on_value_changed(self):
        self.ioloop.add_callback(self._on_value_changed, self.appliance)

    def _on_value_changed(self, appliance):
        logging.info(self.appliance.haid + " webthing - processing on value changed event")
        self.power.notify_of_external_update(self.appliance.power)
        self.door.notify_of_external_update(self.appliance.door)
        self.operation.notify_of_external_update(self.appliance.operation)
        self.remote_start_allowed.notify_of_external_update(self.appliance.remote_start_allowed)
        self.start_date.notify_of_external_update(appliance.read_start_date())
        self.enumber.notify_of_external_update(self.appliance.enumber)
        self.vib.notify_of_external_update(self.appliance.vib)
        self.brand.notify_of_external_update(self.appliance.brand)
        self.haid.notify_of_external_update(self.appliance.haid)
        self.name.notify_of_external_update(self.appliance.name)
        self.device_type.notify_of_external_update(self.appliance.device_type)


class DishwasherThing(ApplianceThing):

    def __init__(self, description: str, dishwasher: Dishwasher):
        super().__init__(description, dishwasher)

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

        self.program_remaining_time = Value(dishwasher.program_remaining_time_sec)
        self.add_property(
            Property(self,
                     'program_remaining_time',
                     self.program_remaining_time,
                     metadata={
                         'title': 'Remaining time',
                         "type": "int",
                         'description': 'The remaining time in sec',
                         'readOnly': True,
                     }))

        self.program_energy_forecast = Value(dishwasher.program_energy_forecast_percent)
        self.add_property(
            Property(self,
                     'program_energy_forecast',
                     self.program_energy_forecast,
                     metadata={
                         'title': 'Energy forecase',
                         "type": "int",
                         'description': 'The energy forecast in %',
                         'readOnly': True,
                     }))

        self.program_water_forecast = Value(dishwasher.program_water_forecast_percent)
        self.add_property(
            Property(self,
                     'program_water_forecast',
                     self.program_water_forecast,
                     metadata={
                         'title': 'Water forcast',
                         "type": "int",
                         'description': 'The water forecast in %',
                         'readOnly': True,
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

    def _on_value_changed(self, dishwasher: Dishwasher):
        super()._on_value_changed(dishwasher)
        self.selected_program.notify_of_external_update(dishwasher.program_selected)
        self.program_vario_speed_plus.notify_of_external_update(dishwasher.program_vario_speed_plus)
        self.program_hygiene_plus.notify_of_external_update(dishwasher.program_hygiene_plus)
        self.program_extra_try.notify_of_external_update(dishwasher.program_extra_try)
        self.program_progress.notify_of_external_update(dishwasher.program_progress)
        self.program_water_forecast.notify_of_external_update(dishwasher.program_water_forecast_percent)
        self.program_energy_forecast.notify_of_external_update(dishwasher.program_energy_forecast_percent)
        self.program_remaining_time.notify_of_external_update(dishwasher.program_remaining_time_sec)


class DryerThing(ApplianceThing):

    def __init__(self, description: str, dryer: Dryer):
        super().__init__(description, dryer)

        '''
        self.start_date = Value(dryer.start_date, dryer.set_start_date)
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
        '''

    def _on_value_changed(self, dryer: Dryer):
        super()._on_value_changed(dryer)
        #self.start_date.notify_of_external_update(dryer.start_date)



def run_server( description: str, port: int, refresh_token: str, client_secret: str):
    homeappliances = []
    for appliance in HomeConnect(refresh_token, client_secret).appliances():
        if appliance.device_type.lower() == DISHWASHER:
            homeappliances.append(DishwasherThing(description, appliance).activate())
        elif appliance.device_type.lower() == DRYER:
            homeappliances.append(DryerThing(description, appliance).activate())
    homeappliances.sort()
    logging.info(str(len(homeappliances)) + " homeappliances found: " + ", ".join([homeappliance.appliance.name + "/" + homeappliance.appliance.enumber for homeappliance in homeappliances]))
    server = WebThingServer(MultipleThings(homeappliances, 'homeappliances'), port=port, disable_host_validation=True)
    logging.info('running webthing server http://localhost:' + str(port))
    try:
        server.start()
    except KeyboardInterrupt:
        logging.info('stopping webthing server')
        server.stop()
        logging.info('done')

