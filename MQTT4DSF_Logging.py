#!/usr/bin/env python3

import logging
import os
import sys
import time
import datetime
import signal
import json

class MQTTDSF_Logging:
    SETTINGS_FILE = "/opt/dsf/sd/sys/MQTT4DSF_Config.json"
    def __init__(self):
        self._load_settings()
        self._log_setup()        

    def _load_settings(self):
        with open(self.SETTINGS_FILE) as json_settings:
            settings = json.load(json_settings)
            self.s_MQTT4DSF_Logging_level = str(settings["GENERAL_SETTINGS"]["MQTT4DSF_SYSTEM_LOGGING_LEVEL"])

    def _log_setup(self):
        logging.basicConfig(filename='/var/log/MQTT4DSF.log',
                            filemode='a',
                            format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.INFO)
        #logging.WARNING("Started The Log")
        self.log = logging.getLogger("MQTT4DSF")
        self.log.warning("Started the Log")
        self._change_logging_level()

    def _change_logging_level(self):
        self.log.warning("Chnaging Log Level to = " + str(self.s_MQTT4DSF_Logging_level))
        if self.s_MQTT4DSF_Logging_level == "DEBUG": self.log.setLevel(logging.DEBUG)
        if self.s_MQTT4DSF_Logging_level == "INFO": self.log.setLevel(logging.INFO)
        if self.s_MQTT4DSF_Logging_level == "CRITICAL": self.log.setLevel(logging.CRITICAL)
        if self.s_MQTT4DSF_Logging_level == "WARNING": self.log.setLevel(logging.WARNING)
        if self.s_MQTT4DSF_Logging_level == "ERROR": self.log.setLevel(logging.ERROR)

    def AddLogEntry(self, sloglevel, slogtxt):
        if sloglevel == "DEBUG": self.log.debug(str(slogtxt))
        if sloglevel == "INFO": self.log.info(str(slogtxt))
        if sloglevel == "CRITICAL": self.log.critical(str(slogtxt))
        if sloglevel == "WARNING": self.log.warning(str(slogtxt))
        if sloglevel == "ERROR": self.log.error(str(slogtxt))



