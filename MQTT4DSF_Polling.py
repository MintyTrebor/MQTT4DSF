#!/usr/bin/env python3

import sys
import json
import os
import time
import signal
import requests
import datetime

class MQTT4DSF_PollingMonitor:
    SETTINGS_FILE = "/opt/dsf/sd/sys/MQTT4DSF_Config.json"
    def __init__(self, oLogQueue, bFirstRun, oSndMsgQ):
        self.logQ = oLogQueue
        self.MsgQ = oSndMsgQ
        self.bFirstRun = bFirstRun
        self._load_settings()
        self._getInitialInfo()
        self._timedMonitoring()

    
    def _load_settings(self):
        with open(self.SETTINGS_FILE) as json_settings:
            settings = json.load(json_settings)
            # Get Fixed Sys Variables and paramters from the config json
            self.RepStr_MachineName = str(settings["SYS_SETTINGS"]["Default_Replace_Strings"]["Machine_Name"])
            self.i_PollFreq = int(settings["GENERAL_SETTINGS"]["PollFrequencySeconds"])
            self.s_DSF_HTTP_REQ_URL = str(settings["GENERAL_SETTINGS"]["HTTP_DSF_REQ_ADD"])
            self.s_MachineName = str(settings["GENERAL_SETTINGS"]["MACHINE_NAME"])
            self.s_SYSTEM_MSG_TOPIC = settings["GENERAL_SETTINGS"]["MQTT4DSF_SYSTEM_TOPIC"]            
            #Get the MQTT MSGS Config Data
            self.j_MQTT4DSF_MONMSGS = settings["MONITORED_MQTT_MSGS"]            

    
    def _getInitialInfo(self):
        if self.bFirstRun == True:
            try:
                self.logQ.put(("DEBUG", "MQTT4DSF Is getting the Startup MSG"))
                s_machine_model = requests.get(url = self.s_DSF_HTTP_REQ_URL)
                #define machine json
                j_machine_model = json.loads(s_machine_model.text)
                s_machine_model = None
                #Get Machine Details - (Always get first instances)
                s_Machine_IP = str(j_machine_model["network"]["interfaces"][0]["actualIP"])
                s_Machine_DSF_Ver = str(j_machine_model["state"]["dsfVersion"])
                s_Machine_Board_FW_ver = str(j_machine_model["boards"][0]["firmwareVersion"])
                s_Machine_Initial_Msg = "NOW ONLINE:: Machine: " + self.s_MachineName + " -IP: " +str(s_Machine_IP) + " -DSF FW Ver: " + str(s_Machine_DSF_Ver) + " -Board FW Ver: " + str(s_Machine_Board_FW_ver)
                # Send msg to to Sys Msg Topic
                self.MsgQ.put((self.s_SYSTEM_MSG_TOPIC, s_Machine_Initial_Msg))
            except Exception as ex:
                self.logQ.put(("ERROR", str("MQTT4DSF_PollingMonitor getInitialInfo : " + str(ex))))
    
    
    def _getValFromKeys(self, json_object, path):
        # function to get the values from the keys based on the variable path defined in config json
        if type(path) == str:
            d_TMP_Path = path.split("/")
            j_TMP_JSON = json_object
            try:
                for idx, dsf in enumerate(d_TMP_Path):
                    j_TMP_JSON = j_TMP_JSON[d_TMP_Path[idx]]
                s_TMP_MSG = str(j_TMP_JSON)
                return s_TMP_MSG
            except KeyError:  
                return "None"
        else:
            return "None"


    def _getValFromArray(self, json_object, s_Variable, i_instance, s_DSF_DOM_Path):
        # function to get the values from an array on the variable path and instance defined in config json
        s_TMP_Path = s_DSF_DOM_Path
        if type(s_TMP_Path) == str:
            d_TMP_Path = s_TMP_Path.split("/")
            j_TMP_JSON = json_object
            # iterate through the json path
            for idx, domvar in enumerate(d_TMP_Path):
                j_TMP_JSON = j_TMP_JSON[d_TMP_Path[idx]]
            # iterate through the pathed json to get the value required
            for idx, j_TMP_DSF in enumerate(j_TMP_JSON):
                if idx == i_instance:
                    try:
                        return j_TMP_DSF[s_Variable]
                    except KeyError:
                        return "None"    
        else:
            return "None"

    
    def _processDSFMsgs(self, strMsg):
        # Function used to re-format DSF System Messages
        if len(str(strMsg)) > 0:
            strMsg = str(strMsg)
            try:
                strMsg = strMsg[1:-1]
                # had to put this here to fix badly formatted json
                strMsg = strMsg.replace("\'", "\"")
                msg_json = json.loads(strMsg)
                # Get Msg
                str_extracted_msg = str(msg_json['content'])
                if str(str_extracted_msg) != "":
                    return str(str_extracted_msg)
            except Exception as ex:
                self.logQ.put(("ERROR", str("MQTT4DSF_PollingMonitor _processDSFMsgs : " + str(ex))))
    
    
    def _timedMonitoring(self):               
        while True:
            try:
                s_machine_model = requests.get(url = self.s_DSF_HTTP_REQ_URL)
                #define machine json
                j_machine_model2 = json.loads(s_machine_model.text)
                s_machine_model = None
                for j_AllMsgs in self.j_MQTT4DSF_MONMSGS:
                    s_TMP_MsgType = j_AllMsgs["Type"]
                    for j_Msg in j_AllMsgs["Msgs"]:
                        # get the mqtt parameters first
                        s_TMP_Topic = j_Msg["MQTT_Topic_Path"]
                        s_TMP_Topic = s_TMP_Topic.replace(self.RepStr_MachineName, self.s_MachineName)
                        s_TMP_MsgText = j_Msg["MQTT_Topic_MSG"]
                        #ensure conditional booleans are re-set for each msg
                        b_Match_Found = False
                        b_SndMsg = False
                        #Iterate through msg variable groups in json config
                        for j_VarList in j_AllMsgs["JSON_Variables"]:
                            s_TMP_DSF_Variable_Type = j_VarList["DSF_Variable_Type"]
                            s_TMP_DSF_DOM_Path = j_VarList["DSF_DOM_Path"]
                            s_TMP_Trigger_Msg = j_VarList["Trigger_Msg"]
                            # get the msg variables to evaluate in the subscription update json from DSF
                            #iterate through in the individual msg variables in the msg variabls group
                            for j_Variables in j_VarList["Variables"]:
                                i_TMP_instance = int(j_Variables["instance"])
                                s_TMP_Variable = j_Variables["Variable"]
                                s_TMP_Replace_String = j_Variables["Replace_String"]
                                s_TMP_Var_Type = j_Variables["Var_Type"]
                                s_TMP_LastVal = j_Variables["lastval"]
                                i_TMP_Delta = int(j_Variables["Msg_Delta"])
                                if s_TMP_DSF_Variable_Type == "ARRAY":
                                    s_TMP_Val = self._getValFromArray(j_machine_model2, s_TMP_Variable, i_TMP_instance, s_TMP_DSF_DOM_Path)
                                if s_TMP_DSF_Variable_Type == "SINGLE":
                                    s_TMP_Val = self._getValFromKeys(j_machine_model2, str(str(s_TMP_DSF_DOM_Path) + "/" + str(s_TMP_Variable)))
                                if len(str(s_TMP_Val)) > 0 and str(s_TMP_Val) != "None":
                                    #We Have a Match so lets process & update the values and msg text
                                    #see if we should based on delta settings - if curr val is greater than delta from last val then snd msg
                                    s_TMP_DSF_Val = s_TMP_Val
                                    #if Trigger_Msg is set "N" then never trigger a msg from this msg variable - the msg will be triggered by diff variables
                                    if s_TMP_Trigger_Msg == "Y":
                                        if str(s_TMP_LastVal) != "noLast" and s_TMP_Var_Type != "string":
                                            if int(i_TMP_Delta) != 0:
                                                if b_SndMsg == False:
                                                    #deal with positive or negative deltas
                                                    i_TMP_Val = int(s_TMP_Val) - int(s_TMP_LastVal)
                                                    if i_TMP_Val > 0:
                                                        b_GoPos = True
                                                        i_TMP_Val = int(s_TMP_LastVal) + int(i_TMP_Delta)
                                                    else:
                                                        b_GoPos = False
                                                        i_TMP_Val = int(s_TMP_LastVal) - int(i_TMP_Delta)                                          
                                                    if b_GoPos == True and b_SndMsg == False:
                                                        if int(s_TMP_Val) >= i_TMP_Val:
                                                            b_SndMsg = True                                        
                                                    if b_GoPos == False and b_SndMsg == False:
                                                        if int(s_TMP_Val) <= i_TMP_Val:
                                                            b_SndMsg = True                                        
                                            else:
                                                b_SndMsg = True
                                        else:
                                            b_SndMsg = True
                                    #check for special processing requirements (msgType)
                                    if s_TMP_MsgType == "DSF":
                                        #This msg needs special formatting
                                        s_TMP_Val = self._processDSFMsgs(str(s_TMP_Val))
                                    if s_TMP_Var_Type == "time":
                                        #The value needs formatting into time
                                        s_TMP_Val = time.strftime("%H:%M:%S", time.gmtime(int(s_TMP_Val)))
                                    s_TMP_MsgText = s_TMP_MsgText.replace(str(s_TMP_Replace_String), str(s_TMP_Val))
                                    b_Match_Found = True
                                else:
                                    # If null just remove replace string from msg with NULL so we no no value was provided from the dom
                                    s_TMP_MsgText = s_TMP_MsgText.replace(str(s_TMP_Replace_String), str("NULL"))
                                if b_SndMsg == True: 
                                    # We are going to snd a msg so update lastval
                                    if s_TMP_Var_Type != "string":
                                        j_Variables["lastval"] = int(s_TMP_DSF_Val)
                                    else:
                                        j_Variables["lastval"] = str(s_TMP_DSF_Val)
                        if b_Match_Found == True and b_SndMsg == True:
                            s_TMP_MsgText = s_TMP_MsgText.replace(self.RepStr_MachineName, self.s_MachineName)
                            self.MsgQ.put((str(s_TMP_Topic), str(s_TMP_MsgText)))
            except Exception as ex:
                self.logQ.put(("ERROR", str("MQTT4DSF_PollingMonitor _timedMonitoring : " + str(ex))))
            # Polling Delay Here
            time.sleep(self.i_PollFreq)

