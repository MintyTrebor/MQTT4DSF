#!/usr/bin/env python3

import sys
import json
import os
import time
import requests
import datetime
import queue
import signal
from importlib import reload
from pydsfapi import pydsfapi
from pydsfapi.commands import basecommands, code
from pydsfapi.initmessages.clientinitmessages import InterceptionMode, SubscriptionMode

class MQTT4DSF_DSFQueueMonitor:
    SETTINGS_FILE = "/opt/dsf/sd/sys/MQTT4DSF_Config.json"
    def __init__(self, oLogQueue, oSndMsgQ, oDSFEventQ):
        self.logQ = oLogQueue
        self.MsgQ = oSndMsgQ
        self.DSFEventQ = oDSFEventQ
        self._load_settings()
        self._eventMonitoring()

    
    def _load_settings(self):
        with open(self.SETTINGS_FILE) as json_settings:
            settings = json.load(json_settings)
            # Get Fixed Sys Variables and parameters from the config json
            self.RepStr_MachineName = str(settings["SYS_SETTINGS"]["Default_Replace_Strings"]["Machine_Name"])
            self.s_MachineName = str(settings["GENERAL_SETTINGS"]["MACHINE_NAME"])
            self.s_SYSTEM_MSG_TOPIC = settings["GENERAL_SETTINGS"]["MQTT4DSF_SYSTEM_TOPIC"]
            self.s_MSG_CMD_Prefix = str(settings["GENERAL_SETTINGS"]["MQTT_MSG_CMD_Prefix"])
            self.s_MSG_CMD_RESPONSE = str(settings["GENERAL_SETTINGS"]["MQTT_MSG_CMD_RESPONSE"])            
            #Get the MQTT MSGS Config Data
            self.j_MQTT4DSF_MQTTMSGS = settings["MQTT_MESSAGES"]
            self.j_MQTT4DSF_CMDMSGS = settings["MQTT_MSG_CMDS"]           


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
            try:
                d_TMP_Path = s_TMP_Path.split("/")
                j_TMP_JSON = json_object
                # iterate through the json path
                for idx, domvar in enumerate(d_TMP_Path):
                    j_TMP_JSON = j_TMP_JSON[d_TMP_Path[idx]]
                # iterate through the pathed json to get the value required
                try:
                    for idx, j_TMP_DSF in enumerate(j_TMP_JSON):
                        try:
                            if idx == i_instance:
                                try:
                                    return j_TMP_DSF[s_Variable]
                                except KeyError:
                                    return "None"
                        except:
                            continue
                except:
                    return "None"             
            except:
                return "None"   
        else:
            return "None"


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
                self.logQ.put(("ERROR", str("MQTT4DSF_DSFQueueMonitor _processDSFMsgs : " + str(ex))))

    def _sndAckCmd(self):
        try: 
            command_connection = pydsfapi.CommandConnection(debug=False)
            command_connection.connect()
            try:
                # Perform a simple command and wait for its output
                command_connection.perform_simple_code('M117 "' + self.s_MSG_CMD_RESPONSE + '"')
            finally:
                command_connection.close()
        except Exception as ex:
            command_connection.close()
            self.logQ.put(("ERROR", str("MQTT4DSF_DSFQueueMonitor _SndAckCmd : " + str(ex))))

    # Function to check and get the cmd msg
    def _getMSGCMDFromKeys(self, json_object, path):
        try:
            if type(path) == str:
                d_TMP_Path = path.split("/")
                j_TMP_JSON = json_object
                try:
                    for idx, dsf in enumerate(d_TMP_Path):
                        j_TMP_JSON = j_TMP_JSON[d_TMP_Path[idx]]
                    s_TMP_CMDMSG = str(j_TMP_JSON)    
                    #Check if Cmd Msg
                    if s_TMP_CMDMSG.find(self.s_MSG_CMD_Prefix) != -1:
                        #this is a cmd msg remove the cmd string identifier from the string
                        s_TMP_CMDMSG = s_TMP_CMDMSG.replace(self.s_MSG_CMD_Prefix, "")
                        for j_CMDMSG in self.j_MQTT4DSF_CMDMSGS:
                            if j_CMDMSG["CMD_STRING"] == s_TMP_CMDMSG and j_CMDMSG["Enabled"] == "Y":
                                #match found so lets send the msg
                                for j_Msgs in j_CMDMSG["Msgs"]:
                                    s_TMP_Topic = str(j_Msgs["MQTT_Topic_Path"]) 
                                    s_TMP_MsgText = str(j_Msgs["MQTT_Topic_MSG"])
                                    if len(s_TMP_Topic) > 0 and len(s_TMP_MsgText) > 0:
                                        s_TMP_MsgText = s_TMP_MsgText.replace(self.RepStr_MachineName, self.s_MachineName)
                                        s_TMP_Topic = s_TMP_Topic.replace(self.RepStr_MachineName, self.s_MachineName)
                                        self.MsgQ.put((str(s_TMP_Topic), str(s_TMP_MsgText)))
                                        self._sndAckCmd()
                        #even if no cmd msg needs to be sent, this is still a cmd msg so return true
                        return True
                    #check for cmd response msg (sent after responding to cmd msg) and return different val
                    elif s_TMP_CMDMSG.find(self.s_MSG_CMD_RESPONSE) != -1:
                        return True
                    else:
                        return False
                except KeyError:
                    return False
            else:
                return False
        except Exception as ex:
            self.logQ.put(("ERROR", str("MQTT4DSF_DSFQueueMonitor _getMSGCMDFromKeys : " + str(ex))))
    
    
    def _eventMonitoring(self):               
        try:
            while True:
                #get next update from the queue
                j_patch = self.DSFEventQ.get()
                try:
                    j_latest = json.loads(j_patch)
                except:
                    continue

                #for each subscription update event iterate through all MQTT_MESSAGES in config and identify matches
                for j_AllMsgs in self.j_MQTT4DSF_MQTTMSGS:
                    #Get MSG Type
                    s_TMP_MsgType = str(j_AllMsgs["Type"])
                    s_TMP_Enabled = str(j_AllMsgs["Enabled"])
                    b_IsCMD = False
                    #check for MQTT_CMD_MSGS
                    if s_TMP_MsgType == "MSG":
                        b_IsCMD = self._getMSGCMDFromKeys(j_latest, j_AllMsgs["DSF_DOM_Filter"])
                    #check if this is enabled and its not a MQTTCMD MSG : if not then skip
                    if s_TMP_Enabled == "Y" and b_IsCMD == False:
                        for j_Msg in j_AllMsgs["Msgs"]:
                            # get the mqtt parameters first
                            s_TMP_Topic = j_Msg["MQTT_Topic_Path"]
                            s_TMP_Topic = s_TMP_Topic.replace(self.RepStr_MachineName, self.s_MachineName)
                            s_TMP_MsgText = j_Msg["MQTT_Topic_MSG"]
                            # clear/set some conditonal variables
                            b_Match_Found = False
                            b_SndMsg = False
                            # get the msg variables to check in the update json from DSF
                            for j_Variables in j_AllMsgs["JSON_Variables"]:
                                s_TMP_Variable = j_Variables["Variable"]
                                s_TMP_Replace_String = j_Variables["Replace_String"]
                                s_TMP_Var_Type = j_Variables["Var_Type"]
                                s_TMP_LastVal = j_Variables["lastval"]
                                i_TMP_Delta = j_Variables["Msg_Delta"]
                                #check to see in the jsonpath and value are present in the update json string
                                s_TMP_Val = self._getValFromKeys(j_latest, s_TMP_Variable)
                                if len(str(s_TMP_Val)) > 0 and str(s_TMP_Val) != "None":
                                    #We Have a Match so lets process & update the values and msg text
                                    #see if we should based on delta settings - if curr val is greater than delta from last val then snd msg
                                    s_TMP_DSF_Val = s_TMP_Val
                                    if str(s_TMP_LastVal) != "noLast" and s_TMP_Var_Type != "string":
                                        if int(i_TMP_Delta) != 0:
                                            #deal with positive or negative deltas
                                            i_TMP_Val = int(s_TMP_Val) - int(s_TMP_LastVal)
                                            if i_TMP_Val > 0:
                                                b_GoPos = True
                                                i_TMP_Val = int(s_TMP_LastVal) + int(i_TMP_Delta)
                                            else:
                                                b_GoPos = False
                                                i_TMP_Val = int(s_TMP_LastVal) - int(i_TMP_Delta)                                          
                                            if b_GoPos == True and b_SndMsg ==False:
                                                if int(s_TMP_Val) >= i_TMP_Val:
                                                    b_SndMsg = True                                        
                                            if b_GoPos == False and b_SndMsg ==False:
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
                            #If correct conditions update the msg text with the extracted values and send the mqtt msg            
                            if b_Match_Found == True and b_SndMsg == True:
                                s_TMP_MsgText = s_TMP_MsgText.replace(self.RepStr_MachineName, self.s_MachineName)
                                self.MsgQ.put((str(s_TMP_Topic), str(s_TMP_MsgText)))
        except Exception as ex:
            self.logQ.put(("ERROR", "MQTT4DSF_DSFQueueMonitor _eventMonitoring : " + str(ex)))


class MQTT4DSF_DSFEventMonitor:
    SETTINGS_FILE = "/opt/dsf/sd/sys/MQTT4DSF_Config.json"
    
    def __init__(self, oLogQueue, oDSFEventQ):
        self.logQ = oLogQueue
        self.DSFEventQ = oDSFEventQ
        self._load_settings()
        self._DSFEventMonitor()

    def _load_settings(self):
        with open(self.SETTINGS_FILE) as json_settings:
            settings = json.load(json_settings)
            #Get the MQTT MSGS Config Data
            self.j_MQTT4DSF_MQTTMSGS = settings["MQTT_MESSAGES"]   


    # function to construct the filter for the DSF plugin subscription service
    def _constructFilter(self):
        try:
            s_DSF_Filter = ""
            self.logQ.put(("DEBUG", str("MQTT4DSF_DSFEventMonitor _constructFilter json: " + str(self.j_MQTT4DSF_MQTTMSGS))))
            for DSF_DOM_Filter in self.j_MQTT4DSF_MQTTMSGS:
                #if type of MSG or DSF always add to filter as they are needed by MQTT4DSF functions
                if str(DSF_DOM_Filter["Type"]) == "MSG" or str(DSF_DOM_Filter["Type"]) == "DSF":
                    s_DSF_Filter = s_DSF_Filter + str(DSF_DOM_Filter["DSF_DOM_Filter"]) + "|"
                #otherwise add to filter if enabled and std
                elif str(DSF_DOM_Filter["Enabled"]) == "Y" and str(DSF_DOM_Filter["Type"]) == "STD":
                    s_DSF_Filter = s_DSF_Filter + str(DSF_DOM_Filter["DSF_DOM_Filter"]) + "|"
            #check we have some text
            if len(s_DSF_Filter) > 0:
                # remove last "|" as its not needed
                s_DSF_Filter = s_DSF_Filter[0:-1]
                #remove duplicates
                s_DSF_Filter = '|'.join(set(s_DSF_Filter.split('|')))
                #send it back
                self.logQ.put(("DEBUG", str("MQTT4DSF_DSFEventMonitor _constructFilter DSF API Filter : " + str(s_DSF_Filter))))
                return s_DSF_Filter
            else:
                return ""
        except Exception as ex:
            self.logQ.put(("ERROR", str("MQTT4DSF_DSFEventMonitor _constructFilter : " + str(ex))))
            return ""
    
    # function that checks DSF is running and responding as expected
    def _checkDSF(self):
        self.logQ.put(("ERROR", "MQTT4DSF_DSFEventMonitor: DSF API has Crashed. Trying to recover. DSF Events will not be monitored unitil the API responds."))
        while True:
            try:
                reload(pydsfapi)
                #wait for 5 seconds so we don't spam the plugin
                time.sleep(5)
                sub_conn = pydsfapi.SubscribeConnection(SubscriptionMode.FULL, debug=False)
                sub_conn.connect()
                #if we get this far dsf is backup so return with OK
                sub_conn.close()
                sub_conn = None
                self.logQ.put(("ERROR", "MQTT4DSF_DSFEventMonitor: DSF API has recovered. DSF Event monitoring will resume."))
                self._DSFEventMonitor()
            except:
                sub_conn = None


    # Monitors the DSF api for pushed events and adds them to the queue for processing - requires a process
    def _DSFEventMonitor(self):
        try:
            reload(pydsfapi)
            #get the filter string
            str_TMP_Filter = self._constructFilter()
            subscribe_connection3 = pydsfapi.SubscribeConnection(SubscriptionMode.PATCH, str_TMP_Filter, debug=False)
            subscribe_connection3.connect()

            #get the first msg and discard
            j_DSFEventMsg = subscribe_connection3.get_machine_model_patch()
            j_DSFEventMsg = ""
            subscribe_connection3.connect()

            while True:            
                while subscribe_connection3.get_machine_model_patch():
                    j_DSFEventMsg = subscribe_connection3.get_machine_model_patch()
                    self.DSFEventQ.put(j_DSFEventMsg)
                    subscribe_connection3.connect()
        
        except Exception as ex:
            self.logQ.put(("ERROR", str("MQTT4DSF_DSFEventMonitor _DSFEventMonitor : " + str(ex))))
            self._checkDSF()
