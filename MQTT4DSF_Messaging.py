#!/usr/bin/env python3

import paho.mqtt.client as Main_Msg_MQTT
import sys
import json
import os
import signal
import time

class MQTT4DSF_SndMsg_Queue_Monitor():
    SETTINGS_FILE = "/opt/dsf/sd/sys/MQTT4DSF_Config.json"
    def __init__(self, oLogQueue, oSndMsgQ):
        self.logQ = oLogQueue
        self.MsgQ = oSndMsgQ
        self._load_settings()
        self._monitor_msgq()

    def _load_settings(self):
        with open(self.SETTINGS_FILE) as json_settings:
            settings = json.load(json_settings)
            self._bRunMonitor = True                
            # MQTT
            self.MQTT_SVR_Add = settings["MQTT_SETTINGS"]["MQTT_SVR_ADD"]
            self.MQTT_SVR_Port = int(settings["MQTT_SETTINGS"]["MQTT_SVR_PORT"])
            self.MQTT_Client_Name = settings["MQTT_SETTINGS"]["MQTT_Client_Name"]
            self.MQTT_User_Name = settings["MQTT_SETTINGS"]["MQTT_UserName"]
            self.MQTT_Password = settings["MQTT_SETTINGS"]["MQTT_Password"]       


    def _monitor_msgq(self):
        try:
            self.logQ.put(("DEBUG", "MQTT4DSF_SndMsg_Queue_Monitor has started"))
            self.MQTTClient = Main_Msg_MQTT.Client(self.MQTT_Client_Name)
            self.MQTTClient.username_pw_set(username=self.MQTT_User_Name, password=self.MQTT_Password)        
            while self._bRunMonitor == True:
                o_TMP_QueueItem = self.MsgQ.get()
                if type(o_TMP_QueueItem[0]) == str and type(o_TMP_QueueItem[1]) == str:
                    self.MQTTClient.connect(self.MQTT_SVR_Add, self.MQTT_SVR_Port, 60)
                    self.MQTTClient.publish(o_TMP_QueueItem[0], o_TMP_QueueItem[1])
                    time.sleep(0.2)
        except Exception as ex:
            self.logQ.put(("ERROR", str("MQTT4DSF_SndMsg_Queue_Monitor _monitor_msgq : " + str(ex))))
