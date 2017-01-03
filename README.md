# mqtt-hifi

A Python script to provide a MQTT interface to a Marantz Hifi (developed & tested with M-CR610).

I'm using this with OpenHAB as the default Denon binding had some limitations. 

My OpenHAB items look like:

```
Group Hifi
Group:Switch:OR(ON,OFF) Hifi_Favorites

Switch Hifi_Power           "Power"                 (Hifi)      {mqtt=">[mosquitto:/hifi/power:command:*:default],<[mosquitto:/hifi/power:state:default]"}
Switch Hifi_Mute            "Mute"          <mute>  (Hifi)      {mqtt=">[mosquitto:/hifi/mute:command:*:default],<[mosquitto:/hifi/mute:state:default]"}

Dimmer Hifi_Volume          "Volume [%d]"   <speaker>   (Hifi, gDashboard)      {mqtt=">[mosquitto:/hifi/volume:command:*:default],<[mosquitto:/hifi/volume:state:default]"}

String Hifi_Source          "Source [%s]"   <music> (Hifi)  {mqtt="<[mosquitto:/hifi/source:state:default]"}
String Hifi_Favorite        "Favorite [%s]" <music> (Hifi)  {mqtt=">[mosquitto:/hifi/favorite:command:*:default]"}
String Hifi_Playing         "Playing [%s]"  <music> (Hifi)  {mqtt="<[mosquitto:/hifi/playing:state:default]"}

Switch Hifi_Favorite_01       "ABC Illawarra"     (Hifi, Hifi_Favorites, gDashboard)
Switch Hifi_Favorite_02       "ABC Classic"       (Hifi, Hifi_Favorites, gDashboard)
Switch Hifi_Favorite_03       "Double J"          (Hifi, Hifi_Favorites, gDashboard)
```
