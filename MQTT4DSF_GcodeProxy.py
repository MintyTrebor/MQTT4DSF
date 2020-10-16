#!/usr/bin/env python3

import paho.mqtt.client as GCodeProxy_MQTT
import sys
import json
import signal
import os
from pydsfapi import pydsfapi as GCodeProxy_pydsapi
from pydsfapi.commands import basecommands as GCodeProxy_pydsapi_basecommands
from pydsfapi.commands import code as GCodeProxy_pydsapi_code

#setup class for settings management
class GCodeProxy():
    SETTINGS_FILE = "/opt/dsf/sd/sys/MQTT4DSF_Config.json"
    def __init__(self, oLogQueue):
        self.logQ = oLogQueue
        self._load_settings()
        self._connect_to_MQTT()

    def _load_settings(self):
        with open(self.SETTINGS_FILE) as json_settings:
            settings = json.load(json_settings)
            # MQTT
            self.MQTT_SVR_Add = settings["MQTT_SETTINGS"]["MQTT_SVR_ADD"]
            self.MQTT_SVR_Port = int(settings["MQTT_SETTINGS"]["MQTT_SVR_PORT"])
            self.MQTT_Client_Name = settings["MQTT_SETTINGS"]["MQTT_Client_Name"]
            self.MQTT_User_Name = settings["MQTT_SETTINGS"]["MQTT_UserName"]
            self.MQTT_Password = settings["MQTT_SETTINGS"]["MQTT_Password"]       
            # Get Fixed Sys Variables and paramters from the config json
            self.s_RepStr_MachineName = str(settings["SYS_SETTINGS"]["Default_Replace_Strings"]["Machine_Name"])
            self.s_MachineName = str(settings["GENERAL_SETTINGS"]["MACHINE_NAME"])
            self.s_GCode_Proxy_Topic = str(settings["GENERAL_SETTINGS"]["MQTT4DSF_GCODE_PROXY_TOPIC"])
            self.s_MQTT4DSF_Logging_level = str(settings["GENERAL_SETTINGS"]["MQTT4DSF_SYSTEM_LOGGING_LEVEL"])

    def _connect_to_MQTT(self):
        try:
            self.MQTTClient = GCodeProxy_MQTT.Client(self.MQTT_Client_Name)
            self.MQTTClient.username_pw_set(username=self.MQTT_User_Name, password=self.MQTT_Password)
            self.MQTTClient.on_connect = self._GCodeProxy_On_MQTT_Connect
            self.MQTTClient.on_message = self._GCodeProxy_On_MQTT_MSG
            self.MQTTClient.connect(self.MQTT_SVR_Add, self.MQTT_SVR_Port)
            self.MQTTClient.loop_forever()
        except Exception as ex:
            self.logQ.put(("ERROR", str("GCodeProxy _connect_to_MQTT - Failed to connect to MQTT: " + str(ex))))

    def _GCodeProxy_On_MQTT_Connect(self, client, userdata, flags, rc):
        try:
            s_TMP_Topic = self.s_GCode_Proxy_Topic.replace(self.s_RepStr_MachineName, self.s_MachineName)
            self.MQTTClient.subscribe(s_TMP_Topic)
            self.logQ.put(("DEBUG", str("GCodeProxy _GCodeProxy_On_MQTT_Connect - Subscribed To: " + str(s_TMP_Topic))))
            #print("Subscribed To: " + str(s_TMP_Topic))
        except Exception as ex:
            self.logQ.put(("ERROR", str("GCodeProxy _GCodeProxy_On_MQTT_Connect - Failed to subscribe to MQTT: " + str(ex))))

    def _GCodeProxy_On_MQTT_MSG(self, client, userdata, msg):
        try: 
            GCodeProxy_DSF_Conn = GCodeProxy_pydsapi.CommandConnection(debug=False)
            GCodeProxy_DSF_Conn.connect()
            s_TMP_MQTTMSG = str(msg.payload)
            #have to remove some weired charachters added by the MQTT broker - not sure if this will be required in production needs testing with diff broker
            s_TMP_MQTTMSG = s_TMP_MQTTMSG[2:-1]
            self.logQ.put(("DEBUG", str("GCodeProxy _GCodeProxy_On_MQTT_MSG - Sending: " + str(s_TMP_MQTTMSG))))
            try:
                GCodeProxy_DSF_Conn.perform_simple_code(s_TMP_MQTTMSG)
            finally:
                GCodeProxy_DSF_Conn.close()
        except Exception as ex:
            GCodeProxy_DSF_Conn.close()
            self.logQ.put(("ERROR", str("GCodeProxy _GCodeProxy_On_MQTT_MSG - Failed to send to DSF: " + str(ex))))

       
