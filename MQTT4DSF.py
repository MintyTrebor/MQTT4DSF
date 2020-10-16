#!/usr/bin/env python3

import sys
import signal
import time
import json
import datetime
import logging
import os
import multiprocessing
from MQTT4DSF_GcodeProxy import GCodeProxy
from MQTT4DSF_Logging import MQTTDSF_Logging
from MQTT4DSF_Messaging import MQTT4DSF_SndMsg_Queue_Monitor
from MQTT4DSF_Polling import MQTT4DSF_PollingMonitor
from MQTT4DSF_DSFEvents import MQTT4DSF_DSFEventMonitor, MQTT4DSF_DSFQueueMonitor

class MQTT4DSF_Startup():
    SETTINGS_FILE = "/opt/dsf/sd/sys/MQTT4DSF_Config.json"

    def __init__(self):
        self._load_settings()
        
    def update_settings(self):
        if self._last_update != os.stat(self.SETTINGS_FILE).st_mtime:
            self._load_settings()
            #self.stop_processess()
            #self.start_processes(False, self.o_LogObj, self.o_SndMsg, self.o_DSFEvent)
            return True
        return False

    def _load_settings(self):
        with open(self.SETTINGS_FILE) as json_settings:
            settings = json.load(json_settings)
            self._last_update = os.fstat(json_settings.fileno()).st_mtime            
            self.q_MQTT_MSG_Size = int(settings["GENERAL_SETTINGS"]["MQTT_MSG_QUEUE_SIZE"])
            self.q_DSF_Updates_Size = int(settings["GENERAL_SETTINGS"]["DSF_UPDATE_QUEUE_SIZE"])
            self.s_Enable_GCode_Proxy = str(settings["GENERAL_SETTINGS"]["ENABLE_MQTT4DSF_GCODE_PROXY"])
            self.s_MQTT4DSF_Logging_level = str(settings["GENERAL_SETTINGS"]["MQTT4DSF_SYSTEM_LOGGING_LEVEL"])
            self.jConfigData = settings

    def _init_worker(self):
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    def start_processes(self, bFirstTime):
        #Define Pool
        self.mp_Pool = multiprocessing.Pool(6, self._init_worker)
        self.mp_Manager = multiprocessing.Manager()
        #define queues
        self.o_LogObj = self.mp_Manager.Queue(maxsize = 1000)
        self.o_SndMsg = self.mp_Manager.Queue(maxsize = self.q_MQTT_MSG_Size)
        self.o_DSFEvent = self.mp_Manager.Queue(maxsize = self.q_DSF_Updates_Size)
        #Others
        self.bFirstTime = bFirstTime
        try:
            #start the logging queue
            self.mp_Pool.apply_async(MQTT4DSF_Logging_Queue_Monitor, args=(self.o_LogObj,))
            self.o_LogObj.put(("WARNING", "MQTT4DSF Startup. Logging has been started"))
            #Start The Send MQTT Msg Queue Process
            self.mp_Pool.apply_async(MQTT4DSF_SndMsg_Queue_Monitor, args=(self.o_LogObj, self.o_SndMsg,))
            self.mp_Pool.apply_async(MQTT4DSF_PollingMonitor, args=(self.o_LogObj, self.bFirstTime, self.o_SndMsg,))
            self.mp_Pool.apply_async(MQTT4DSF_DSFEventMonitor, args=(self.o_LogObj, self.o_DSFEvent,))
            self.mp_Pool.apply_async(MQTT4DSF_DSFQueueMonitor, args=(self.o_LogObj, self.o_SndMsg, self.o_DSFEvent,))
            #start the GCodeProxy service if enabled in config
            if self.s_Enable_GCode_Proxy == "Y" or self.s_Enable_GCode_Proxy == "y":
                self.o_LogObj.put(("WARNING", "Starting GCode Proxy"))
                self.mp_Pool.apply_async(GCodeProxy, args=(self.o_LogObj,))
        except Exception as ex:
            print(str(ex))
            self.o_LogObj.put(("ERROR", "MQTT4DSF_Startup _start_processes : " + str(ex)))

    def stop_processess(self):
        self.o_LogObj.put(("WARNING", "Stopping Services. MQTT4DSF is going down"))
        time.sleep(1)
        self._terminate()

    def _terminate(self):
        time.sleep(1)
        self.mp_Pool.terminate()
        self.mp_Pool.join()
        self.mp_Pool = None
        self.mp_Manager = None



# Logging queue monitor (requires thread/process) send log entry to logging function
def MQTT4DSF_Logging_Queue_Monitor(oLogQ):
    MQTT4DSF_Logger = MQTTDSF_Logging()
    while True:
        o_TMP_QueueItem = oLogQ.get()
        MQTT4DSF_Logger.AddLogEntry(o_TMP_QueueItem[0], o_TMP_QueueItem[1])


# Startup
if __name__ == "__main__":
    try:
        #Startup and load config
        o_svsmanager = MQTT4DSF_Startup()        
        #start the processes for the first time
        o_svsmanager.start_processes(True)
        #Check for config changes every 10 seconds if true config reload
        while True:
            while o_svsmanager.update_settings() == True:        
                #Kill & Reload Processess
                o_svsmanager.stop_processess()
                #restart processess
                o_svsmanager.start_processes(False)
            time.sleep(10)
    except KeyboardInterrupt:
        o_svsmanager._terminate()
        o_svsmanager = None
    finally:
        o_svsmanager = None

