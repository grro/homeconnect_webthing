# homeconnect_webthing
A webthing adapter of HomeConnect devices 

This project provides a [webthing API](https://iot.mozilla.org/wot/) to access [HomeConnect devices](https://api-docs.home-connect.com/). 
Currently, the device type ***dishwasher*** is supported only 

The homeconnect_webthing package exposes a http webthing endpoint for each detected and supported HomeConnect devices. E.g. 
```
# webthing has been started on host 192.168.0.23
curl http://192.168.0.23:8744/0/properties 

{
   "device_name":"Geschirrspüler",
   "device_type":"Dishwasher",
   "device_haid":"BOSCH-SMV68TX06E-68A40E40C208",
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

To install this software you may use [PIP](https://realpython.com/what-is-pip/) package manager such as shown below

**PIP approach**
```
sudo pip3 install homeconnect_webthing
```

After this installation you may start the webthing http endpoint inside your python code or via command line using
```
sudo homeconnect --command listen --port 8744 --refresh_token 9yJ4LXJlZyI6IfVVIiwi...2YXRlIn0= --client_secret FEAE...522BD0 
```
Here, the webthing API will be bound to the local port 8744. Furthermore, the refresh_token and client_secret have to be set. 
Please refer [HomeConnect Authorization](https://api-docs.home-connect.com/quickstart?#authorization) to get your refresh_token and client_secret

Alternatively to the *listen* command, you can use the *register* command to register and start the webthing service as systemd unit.
By doing this the webthing service will be started automatically on boot. Starting the server manually using the *listen* command is no longer necessary.
```
sudo homeconnect --command register --port 8744 --refresh_token 9yJ4LXJlZyI6IfVVIiwi...2YXRlIn0= --client_secret FEAE...522BD0
```  
