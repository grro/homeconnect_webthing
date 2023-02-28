from webthing import (MultipleThings, Property, Thing, Value, WebThingServer)
import logging
import tornado.ioloop
from homeconnect_webthing.appliances import Appliance, Dishwasher, Dryer, Washer
from homeconnect_webthing.homeconnect import HomeConnect



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

        self.state = Value(appliance.state)
        self.add_property(
            Property(self,
                     'state',
                     self.state,
                     metadata={
                         'title': 'State',
                         "type": "string",
                         'description': 'The state (valid values ' + ", ".join(appliance.VALID_STATES) + ')',
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

        self.remote_control_active = Value(appliance.program_remote_control_active)
        self.add_property(
            Property(self,
                     'remote_control_active',
                     self.remote_control_active,
                     metadata={
                         'title': 'Remote Control active',
                         "type": "boolean",
                         'description': 'Remote Control Active State. See https://api-docs.home-connect.com/states?#remote-control-activation-state',
                         'readOnly': True,
                     }))

        self.selected_program = Value(appliance.program_selected)
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

        self.program_progress = Value(appliance.program_progress)
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


    def activate(self):
        self.appliance.register_value_changed_listener(self.on_value_changed)
        return self

    def on_value_changed(self):
        self.ioloop.add_callback(self._on_value_changed, self.appliance)

    def _on_value_changed(self, appliance):
        self.power.notify_of_external_update(self.appliance.power)
        self.door.notify_of_external_update(self.appliance.door)
        self.operation.notify_of_external_update(self.appliance.operation)
        self.remote_start_allowed.notify_of_external_update(self.appliance.remote_start_allowed)
        self.state.notify_of_external_update(self.appliance.state)
        self.remote_control_active.notify_of_external_update(self.appliance.program_remote_control_active)
        self.enumber.notify_of_external_update(self.appliance.enumber)
        self.vib.notify_of_external_update(self.appliance.vib)
        self.brand.notify_of_external_update(self.appliance.brand)
        self.haid.notify_of_external_update(self.appliance.haid)
        self.name.notify_of_external_update(self.appliance.name)
        self.device_type.notify_of_external_update(self.appliance.device_type)
        self.program_progress.notify_of_external_update(appliance.program_progress)
        self.selected_program.notify_of_external_update(appliance.program_selected)


    def __hash__(self):
        return hash(self.appliance)

    def __lt__(self, other):
        return self.appliance < other.appliance

    def __eq__(self, other):
        return self.appliance == other.appliance


class DishwasherThing(ApplianceThing):

    def __init__(self, description: str, dishwasher: Dishwasher):
        super().__init__(description, dishwasher)

        self.start_date = Value(dishwasher.read_start_date(), dishwasher.write_start_date)
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

    def _on_value_changed(self, dishwasher: Dishwasher):
        super()._on_value_changed(dishwasher)
        self.start_date.notify_of_external_update(dishwasher.read_start_date())
        self.program_vario_speed_plus.notify_of_external_update(dishwasher.program_vario_speed_plus)
        self.program_hygiene_plus.notify_of_external_update(dishwasher.program_hygiene_plus)
        self.program_extra_try.notify_of_external_update(dishwasher.program_extra_try)
        self.program_water_forecast.notify_of_external_update(dishwasher.program_water_forecast_percent)
        self.program_energy_forecast.notify_of_external_update(dishwasher.program_energy_forecast_percent)
        self.program_remaining_time.notify_of_external_update(dishwasher.program_remaining_time_sec)


class DryerThing(ApplianceThing):

    def __init__(self, description: str, dryer: Dryer):
        super().__init__(description, dryer)

        self.start_date = Value(dryer.read_start_date(), dryer.write_start_date)
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


        self.program_gentle = Value(dryer.program_gentle)
        self.add_property(
            Property(self,
                     'program_gentle',
                     self.program_gentle,
                     metadata={
                         'title': 'Gentle',
                         "type": "bool",
                         'description': 'True if gentle mode is activated',
                         'readOnly': True,
                     }))

        self.program_drying_target = Value(dryer.program_drying_target)
        self.add_property(
            Property(self,
                     'program_drying_target',
                     self.program_drying_target,
                     metadata={
                         'title': 'Drying target',
                         "type": "string",
                         'description': 'The drying target',
                         'readOnly': True,
                     }))

        self.program_drying_target_adjustment = Value(dryer.program_drying_target_adjustment)
        self.add_property(
            Property(self,
                     'program_drying_target_adjustment',
                     self.program_drying_target_adjustment,
                     metadata={
                         'title': 'Drying target adjustment',
                         "type": "string",
                         'description': 'The drying target adjustment',
                         'readOnly': True,
                     }))

        self.program_wrinkle_guard = Value(dryer.program_wrinkle_guard)
        self.add_property(
            Property(self,
                     'program_wrinkle_guard',
                     self.program_wrinkle_guard,
                     metadata={
                         'title': 'wrinkle guard',
                         "type": "string",
                         'description': 'The wrinkle guard',
                         'readOnly': True,
                     }))

        self.child_lock = Value(dryer.child_lock)
        self.add_property(
            Property(self,
                     'child_lock',
                     self.child_lock,
                     metadata={
                         'title': 'child lock',
                         "type": "bool",
                         'description': 'True if child lock is active',
                         'readOnly': True,
                     }))

    def _on_value_changed(self, dryer: Dryer):
        super()._on_value_changed(dryer)
        self.start_date.notify_of_external_update(dryer.read_start_date())
        self.child_lock.notify_of_external_update(dryer.child_lock)
        self.program_gentle.notify_of_external_update(dryer.program_gentle)
        self.program_wrinkle_guard.notify_of_external_update(dryer.program_wrinkle_guard)
        self.program_drying_target.notify_of_external_update(dryer.program_drying_target)
        self.program_drying_target_adjustment.notify_of_external_update(dryer.program_drying_target_adjustment)


class WasherThing(ApplianceThing):

    def __init__(self, description: str, washer: Washer):
        super().__init__(description, washer)

        self.start_date = Value(washer.read_start_date(), washer.write_start_date)
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

        self.idos1_active = Value(washer.idos1_active)
        self.add_property(
            Property(self,
                     'idos1_active',
                     self.idos1_active,
                     metadata={
                         'title': 'i-Dos 1 active',
                         "type": "boolean",
                         'description': 'True if i-Dos 1 is active',
                         'readOnly': True,
                     }))

        self.idos2_active = Value(washer.idos2_active)
        self.add_property(
            Property(self,
                     'idos2_active',
                     self.idos2_active,
                     metadata={
                         'title': 'i-Dos 2 active',
                         "type": "boolean",
                         'description': 'True if i-Dos 2 is active',
                         'readOnly': True,
                     }))

        self.idos1_baselevel = Value(washer.idos1_baselevel)
        self.add_property(
            Property(self,
                     'idos1_baselevel',
                     self.idos1_baselevel,
                     metadata={
                         'title': 'i-Dos 1 base level',
                         "type": "number",
                         'description': 'The i-Dos 1 base level (ml)',
                         'readOnly': True,
                     }))

        self.idos2_baselevel = Value(washer.idos2_baselevel)
        self.add_property(
            Property(self,
                     'idos2_baselevel',
                     self.idos2_baselevel,
                     metadata={
                         'title': 'i-Dos 2 base level',
                         "type": "number",
                         'description': 'The i-Dos 2 base level (ml)',
                         'readOnly': True,
                     }))

        self.temperature = Value(washer.temperature)
        self.add_property(
            Property(self,
                     'temperature',
                     self.idos1_baselevel,
                     metadata={
                         'title': 'temperature',
                         "type": "number",
                         'description': 'The temperature',
                         'readOnly': True,
                     }))

        self.spin_speed = Value(washer.spin_speed)
        self.add_property(
            Property(self,
                     'spin_speed',
                     self.spin_speed,
                     metadata={
                         'title': 'spin speed',
                         "type": "string",
                         'description': 'The spin speed',
                         'readOnly': True,
                     }))

        self.load_recommendation = Value(washer.load_recommendation)
        self.add_property(
            Property(self,
                     'load_recommendation',
                     self.load_recommendation,
                     metadata={
                         'title': 'Load Recommendation',
                         "type": "number",
                         'description': 'The load recommendation',
                         'readOnly': True,
                     }))

        self.energy_forecast = Value(washer.energy_forecast)
        self.add_property(
            Property(self,
                     'energy_forecast',
                     self.energy_forecast,
                     metadata={
                         'title': 'Energy Forecast',
                         "type": "number",
                         'description': 'The energy forecast',
                         'readOnly': True,
                     }))

        self.water_forecast = Value(washer.water_forecast)
        self.add_property(
            Property(self,
                     'water_forecast',
                     self.water_forecast,
                     metadata={
                         'title': 'Water Forecast',
                         "type": "number",
                         'description': 'The water forecast',
                         'readOnly': True,
                     }))

        self.intensive_plus = Value(washer.intensive_plus)
        self.add_property(
            Property(self,
                     'intensive_plus',
                     self.intensive_plus,
                     metadata={
                         'title': 'Intensive Plus',
                         "type": "boolean",
                         'description': 'True, if intensive plus',
                         'readOnly': True,
                     }))

        self.prewash = Value(washer.prewash)
        self.add_property(
            Property(self,
                     'prewash',
                     self.prewash,
                     metadata={
                         'title': 'Pre-wash',
                         "type": "boolean",
                         'description': 'True, if pre-wash',
                         'readOnly': True,
                     }))

        self.rinse_plus1 = Value(washer.rinse_plus1)
        self.add_property(
            Property(self,
                     'rinse_plus1',
                     self.rinse_plus1,
                     metadata={
                         'title': 'Rinse Plus 1',
                         "type": "boolean",
                         'description': 'True, if rinse plus',
                         'readOnly': True,
                     }))

        self.speed_perfect = Value(washer.speed_perfect)
        self.add_property(
            Property(self,
                     'speed_perfect',
                     self.speed_perfect,
                     metadata={
                         'title': 'Speed Perfect',
                         "type": "boolean",
                         'description': 'True, if speed perfect',
                         'readOnly': True,
                     }))

        self.program_duration = Value(washer.program_duration_hours)
        self.add_property(
            Property(self,
                     'program_duration',
                     self.program_duration,
                     metadata={
                         'title': 'Program Duration',
                         "type": "number",
                         'description': 'The program duration in hours',
                         'readOnly': True,
                     }))


    def _on_value_changed(self, washer: Washer):
        super()._on_value_changed(washer)
        self.start_date.notify_of_external_update(washer.read_start_date())
        self.spin_speed.notify_of_external_update(washer.spin_speed)
        self.idos1_baselevel.notify_of_external_update(washer.idos1_baselevel)
        self.idos2_baselevel.notify_of_external_update(washer.idos2_baselevel)
        self.idos1_active.notify_of_external_update(washer.idos1_active)
        self.idos2_active.notify_of_external_update(washer.idos2_active)
        self.load_recommendation.notify_of_external_update(washer.load_recommendation)
        self.temperature.notify_of_external_update(washer.temperature)
        self.energy_forecast.notify_of_external_update(washer.energy_forecast)
        self.water_forecast.notify_of_external_update(washer.water_forecast)
        self.intensive_plus.notify_of_external_update(washer.intensive_plus)
        self.prewash.notify_of_external_update(washer.prewash)
        self.rinse_plus1.notify_of_external_update(washer.rinse_plus1)
        self.speed_perfect.notify_of_external_update(washer.speed_perfect)
        self.program_duration.notify_of_external_update(washer.program_duration_hours)

def run_server( description: str, port: int, refresh_token: str, client_secret: str):
    homeappliances = []
    for appliance in HomeConnect(refresh_token, client_secret).appliances:
        if appliance.device_type.lower() == Dishwasher.DeviceType:
            homeappliances.append(DishwasherThing(description, appliance).activate())
        elif appliance.device_type.lower() == Washer.DeviceType:
            homeappliances.append(WasherThing(description, appliance).activate())
        elif appliance.device_type.lower() == Dryer.DeviceType:
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

