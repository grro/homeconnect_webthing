# homeconnect_webthing
A webthing adapter for HomeConnect smart home devices.

This project provides a [webthing API](https://iot.mozilla.org/wot/) for accessing [HomeConnect devices](https://api-docs.home-connect.com/).
Currently, only the ***dishwasher***, ***washing machine*** and ***dryer*** device types are supported.

The homeconnect_webthing package provides an http webthing endpoint for each detected and supported smart home device. E.g.
```
# webthing has been started on host 192.168.0.23
curl http://192.168.0.23:8744/0/properties 

{
   "device_name":"Geschirrspüler",
   "device_type":"Dishwasher",
   "device_haid":"BOSCH-SMV68TX06E-70C62F17C8E4",
   "device_brand":"Bosch",
   "device_vib":"SMV68TX06E",
   "device_enumber":"SMV68TX06E/74",
   "power":"Off",
   "door":"Open",
   "operation":"Inactive",
   "remote_start_allowed":false,
   "program_selected":"Eco50",
   "program_vario_speed_plus":false,
   "program_hygiene_plus":false,
   "program_extra_try":false,
   "program_start_date":"",
   "program_progress":0
}
```


