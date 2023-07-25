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

To install this software, you can use the [PIP](https://realpython.com/what-is-pip/) package manager as shown below

**PIP approach**
```
sudo pip3 install homeconnect_webthing
```

After this installation, you can use the Webthing http endpoint in your Python code or from the command line with
```
sudo homeconnect --command listen --port 8744 --refresh_token 9yJ4LXJlZyI6IfVVIiwi...2YXRlIn0= --client_secret FEAE...522BD0 
```
Here the webthing API is bound to the local port 8744. Also, refresh_token and client_secret must be set.
Please refer to [HomeConnect Authorization](https://api-docs.home-connect.com/quickstart?#authorization) to obtain your refresh_token and client_secret

As an alternative to the *list* command, you can also use the *register* command to register and start the webthing service as a systemd entity.
This way, the webthing service is started automatically at boot time. Starting the server manually with the *listen* command is no longer necessary.
```
sudo homeconnect --command register --port 8744 --refresh_token 9yJ4LXJlZyI6IfVVIiwi...2YXRlIn0= --client_secret FEAE...522BD0
```  
