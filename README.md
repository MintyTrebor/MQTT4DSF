# DSFMQTT
**A Python script to send MQTT msgs from a SBC running Duet DSF. Uses the DSF pydsfapi plugin.**

This is a python script which interfaces with the DFS Python API to enable the DSF system to send Msgs to an MQTT broker.
It is currently in very early stages, and relies on editing a json file via the DWC interface to configure the script.

Currently it can:

 1. Monitor DSF for events (user configurable) and send mqtt msgs to a
    broker of choice
 2. Poll DSF on a frequency and send mqtt msgs based on a value delta
    (user configurable)
 3. Send MQTT msgs when specially formatted msgs are recieved from DSF.

This has only been tested on a raspberry pi running DSF from [https://github.com/gloomyandy/RepRapFirmware/wiki](https://github.com/gloomyandy/RepRapFirmware/wiki)

Note: Much of DSFMQTT is dependant on Beta versions of DSF settings and therefore much of this code is subject to change as things develop. There is very little guidance on best practice for using and deploying code dependant on DSF so best efforts have been made to make sensible choices. 

# Installation

DSFMQTT requires Python 3, the python paho.mqtt.client, and the DSF dsfpiapi [plugin](https://github.com/Duet3D/DSF-APIs)

Please refer to the other_setup_steps.txt for an example of how to install all of the dependencies.

Once the dependencies are installed and running, run the following command from your home folder :

    sudo wget -O - https://github.com/MintyTrebor/DSFMQTT/releases/download/v0.02-ALPHA/Install_DSFMQTT.sh | bash

This will deploy DSFMQTT as a service to the DSF plugin directory.

A DSFMQTT_Config.json configuration file will be placed in the DSF SYS folder, which should be accessible through DWC web interface for easy editing.

You will need to enter your MQTT broker details in the config file before running the DSFMQTT service.

Enter `sudo systemctl start DSFMQTT.service` to start DSFMQTT
Enter `sudo systemctl stop DSFMQTT.service` to stop DSFMQTT

DSFMQTT has a delayed 30 start to ensure DSF is running after boot of the pi.

MQTT Broker Config:
The default config uses the following topics to sends messages to:

 - Duet/Announce Duet/[!*MachineName*!] 
 - Duet/[!*MachineName*!]/currtool
 - Duet/[!*MachineName*!]/jobname 
 - Duet/[!*MachineName*!]/joblayer
 - Duet/[!*MachineName*!]/timesleft 
 - Duet/[!*MachineName*!]/temps
 - Duet/[!*MachineName*!]/status
 - Duet/[!*MachineName*!]/dsfmsg
 - Duet/[!*MachineName*!]/displaymsg

The system will automatically replace [!*MachineName*!] with the machine name you enter in the DSFMQTT_Config.json (see below). For example if you enter your machine name as ***DAFFY*** then the topic path will be Duet/DAFFY/currtool


To see DSFMQTT system msgs you can also use:

 - Duet/DSFMQTT/sysmsg Duet/DSFMQTT/log

A standard log file is located in /var/log/DSFMQTT.log

# Configuration
All configuration is done through DSFMQTT_Config.json available in the SYS folder of DWC.

***Initial Configuration***
-Update "MQTT_SETTINGS" with you MQTT broker settings:

    "MQTT_SVR_ADD" : "10.66.1.51",
    "MQTT_SVR_PORT" : 1883,
    "MQTT_Client_Name" : "DSFMQTT"

Note : Secure MQTT is not currently supported

-In "GENERAL SETTINGS" update "MACHINE_NAME" to your machine name. Other "GENERAL_SETTINGS" can be updated as required, but the standard settings should work for most cases.

***DSF Event based mqtt messages***

