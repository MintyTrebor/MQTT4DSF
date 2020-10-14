#!/usr/bin/env python3

import sys
import signal
import time
import paho.mqtt.client as mqtt
import json
import datetime
import logging
import requests
import os
import multiprocessing
from pydsfapi import pydsfapi
from pydsfapi.commands import basecommands, code
from pydsfapi.initmessages.clientinitmessages import InterceptionMode, SubscriptionMode
from importlib import reload
from queue import Queue

#setup logging:
global logging
logging.basicConfig(filename='/var/log/MQTT4DSF.log',
                            filemode='a',
                            format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.INFO)

# ********************************
# ** MQTT4DSF Service Functions **
# ********************************

#setup class for settings management
class Settings:
    SETTINGS_FILE = "/opt/dsf/sd/sys/MQTT4DSF_Config.json"

    def __init__(self):
        self._load_settings()

    def update_settings(self):
        if self._last_update != os.stat(self.SETTINGS_FILE).st_mtime:
            logging.info("Settings Last Update = " + str(self._last_update))
            self._load_settings()
            return True
        return False

    def _load_settings(self):
        with open(self.SETTINGS_FILE) as json_settings:
            settings = json.load(json_settings)
            #logging.info("Settings Class Loading json = " + str(settings))
            self._last_update = os.fstat(json_settings.fileno()).st_mtime
            
            # MQTT
            self.MQTT_SVR_Add = settings["MQTT_SETTINGS"]["MQTT_SVR_ADD"]
            self.MQTT_SVR_Port = int(settings["MQTT_SETTINGS"]["MQTT_SVR_PORT"])
            self.MQTT_Client_Name = settings["MQTT_SETTINGS"]["MQTT_Client_Name"]
            self.MQTT_User_Name = settings["MQTT_SETTINGS"]["MQTT_UserName"]
            self.MQTT_Password = settings["MQTT_SETTINGS"]["MQTT_Password"]           

            # Get Fixed Sys Variables and paramters from the config json
            self.RepStr_MachineName = str(settings["SYS_SETTINGS"]["Default_Replace_Strings"]["Machine_Name"])
            self.i_PollFreq = int(settings["GENERAL_SETTINGS"]["PollFrequencySeconds"])
            self.s_MSG_CMD_Prefix = str(settings["GENERAL_SETTINGS"]["MQTT_MSG_CMD_Prefix"])
            self.s_MSG_CMD_RESPONSE = str(settings["GENERAL_SETTINGS"]["MQTT_MSG_CMD_RESPONSE"])
            self.q_MQTT_MSG_Size = int(settings["GENERAL_SETTINGS"]["MQTT_MSG_QUEUE_SIZE"])
            self.q_DSF_Updates_Size = int(settings["GENERAL_SETTINGS"]["DSF_UPDATE_QUEUE_SIZE"])
            self.s_DSF_HTTP_REQ_URL = str(settings["GENERAL_SETTINGS"]["HTTP_DSF_REQ_ADD"])
            self.s_MachineName = str(settings["GENERAL_SETTINGS"]["MACHINE_NAME"])
            self.s_Enable_GCode_Proxy = str(settings["GENERAL_SETTINGS"]["ENABLE_DFSMQTT_GCODE_PROXY"])
            self.s_GCode_Proxy_Topic = str(settings["GENERAL_SETTINGS"]["MQTT4DSF_GCODE_PROXY_TOPIC"])
            self.s_MQTT4DSF_Logging_level = str(settings["GENERAL_SETTINGS"]["MQTT4DSF_SYSTEM_LOGGING_LEVEL"])
            self.s_ConfigPath = "/opt/dsf/sd/sys/MQTT4DSF_Config.json"

            #Get the MQTT MSGS Config Data
            self.j_MQTT4DSF_SYSMSGS = settings["SYS_SETTINGS"]["SYS_MSGS"]
            self.j_MQTT4DSF_MQTTMSGS = settings["MQTT_MESSAGES"]
            self.j_MQTT4DSF_MONMSGS = settings["MONITORED_MQTT_MSGS"]
            self.j_MQTT4DSF_CMDMSGS = settings["MQTT_MSG_CMDS"]
            #self.j_MQTT4DSF_FULLCONFIG = settings


                
#setup the defaults connections values etc for the MQTT4DSF service
def MQTT4DSF_InitServiceDefaults(settingsobj):
    global logging
    #global o_Sys_Settings
    logging.info("Loading Settings Now")
    
    #Setup Global Variables
    global glob_MQTT_SVR_Add
    glob_MQTT_SVR_Add = settingsobj.MQTT_SVR_Add
    global glob_MQTT_SVR_Port
    glob_MQTT_SVR_Port = settingsobj.MQTT_SVR_Port
    global glob_MQTT_Client_Name
    glob_MQTT_Client_Name = settingsobj.MQTT_Client_Name
    global glob_MQTT_User_Name
    glob_MQTT_User_Name = settingsobj.MQTT_User_Name
    global glob_MQTT_Password
    glob_MQTT_Password = settingsobj.MQTT_Password      

    # Get Fixed Sys Variables and paramters from the config json
    global glob_RepStr_MachineName
    glob_RepStr_MachineName = settingsobj.RepStr_MachineName
    global glob_i_PollFreq
    glob_i_PollFreq = settingsobj.i_PollFreq
    global glob_s_MSG_CMD_Prefix
    glob_s_MSG_CMD_Prefix = settingsobj.s_MSG_CMD_Prefix
    global glob_s_MSG_CMD_RESPONSE
    glob_s_MSG_CMD_RESPONSE = settingsobj.s_MSG_CMD_RESPONSE
    global glob_q_MQTT_MSG_Size
    glob_q_MQTT_MSG_Size = settingsobj.q_MQTT_MSG_Size
    global glob_q_DSF_Updates_Size
    glob_q_DSF_Updates_Size = settingsobj.q_DSF_Updates_Size
    global glob_s_DSF_HTTP_REQ_URL
    glob_s_DSF_HTTP_REQ_URL = settingsobj.s_DSF_HTTP_REQ_URL
    global glob_s_MachineName
    glob_s_MachineName = settingsobj.s_MachineName
    global glob_s_Enable_GCode_Proxy
    glob_s_Enable_GCode_Proxy = settingsobj.s_Enable_GCode_Proxy
    global glob_s_GCode_Proxy_Topic
    glob_s_GCode_Proxy_Topic = settingsobj.s_GCode_Proxy_Topic
    global glob_s_MQTT4DSF_Logging_level
    glob_s_MQTT4DSF_Logging_level = settingsobj.s_MQTT4DSF_Logging_level
    global glob_s_ConfigPath
    glob_s_ConfigPath = settingsobj.s_ConfigPath
    
    # Setup MQTT Client Connection
    global client
    client = mqtt.Client(glob_MQTT_Client_Name)
    client.username_pw_set(username=glob_MQTT_User_Name, password=glob_MQTT_Password)
    client.connect(glob_MQTT_SVR_Add, glob_MQTT_SVR_Port)

    #Get the MQTT MSGS json Data
    global glob_j_MQTT4DSF_SYSMSGS
    glob_j_MQTT4DSF_SYSMSGS = settingsobj.j_MQTT4DSF_SYSMSGS
    global glob_j_MQTT4DSF_MQTTMSGS
    glob_j_MQTT4DSF_MQTTMSGS = settingsobj.j_MQTT4DSF_MQTTMSGS
    global glob_j_MQTT4DSF_MONMSGS
    glob_j_MQTT4DSF_MONMSGS = settingsobj.j_MQTT4DSF_MONMSGS
    global glob_j_MQTT4DSF_CMDMSGS
    glob_j_MQTT4DSF_CMDMSGS = settingsobj.j_MQTT4DSF_CMDMSGS

    #logging.info("Settings Loaded = " + str(settingsobj.j_MQTT4DSF_FULLCONFIG))


# ***************************
# ** GCode Proxy Functions **
# ***************************

# This function monitors the GCode Proxy MQTT top and passess it to the DSF API for action - requirers a process
def GCodeProxyTopicMonitor():    
    #get the global variables & settings
    global glob_s_MachineName
    global glob_MQTT_Client_Name  
    global glob_s_GCode_Proxy_Topic
    global glob_MQTT_SVR_Add
    global glob_MQTT_SVR_Port
    global glob_MQTT_User_Name
    global glob_MQTT_Password

    #define variable for this mqtt connection
    global client3

    try:
        #connect to broker
        logging.info("GCodeProxyTopicMonitor waiting for msg from " + str(glob_s_GCode_Proxy_Topic))
        client3 = mqtt.Client(glob_MQTT_Client_Name)
        client3.username_pw_set(username=glob_MQTT_User_Name, password=glob_MQTT_Password)
        client3.connect(glob_MQTT_SVR_Add, glob_MQTT_SVR_Port)
        client3.on_connect = GCodeProxyOnConnect
        client3.on_message = GCodeProxySndCmd
        client3.loop_forever()
    except Exception as ex:
        logging.error("GCodeProxyTopicMonitor : " + str(ex))
        constructSystemMsg("SysMsg", str("GCodeProxyTopicMonitor: " + str(ex)))

# This function is triggered when connection is made to the GCode Proxy MQTT topic
def GCodeProxyOnConnect(client3, userdata, flags, rc):
    #get the global variables & settings
    global glob_s_MachineName  
    global glob_s_GCode_Proxy_Topic
    global glob_RepStr_MachineName

    s_TMP_Topic = glob_s_GCode_Proxy_Topic.replace(glob_RepStr_MachineName, glob_s_MachineName)
    client3.subscribe(s_TMP_Topic)
    logging.info("GCodeProxyOnConnect waiting for msg from " + str(s_TMP_Topic)) 

def GCodeProxySndCmd(client3, userdata, msg):
    try: 
        command_connection5 = pydsfapi.CommandConnection(debug=False)
        command_connection5.connect()
        s_TMP_MQTTMSG = str(msg.payload)
        #have to remove some weired charachters added by the MQTT broker - not sure if this will be required in production needs testing with diff broker
        s_TMP_MQTTMSG = s_TMP_MQTTMSG[2:-1]
        try:
            # Perform a simple command and wait for its output
            logging.info("GCodeProxySndCmd : " + s_TMP_MQTTMSG)
            ack = command_connection5.perform_simple_code(s_TMP_MQTTMSG)
        finally:
            command_connection5.close()
    except Exception as ex:
        command_connection5.close()
        logging.error("GCodeProxySndCmd : " + s_TMP_MQTTMSG + " : " + str(ex))
        constructSystemMsg("SysMsg", str("GCodeProxySndCmd: " + str(ex)))


# ************************
# ** MQTT MSG Functions **
# ************************

# function to add mqtt msg to send queue
def addToSndMsgQueue(s_FullMsgTopic, s_FullMsgTxt):
    global glob_q_MQTT_MSG
    if type(s_FullMsgTopic) == str and type(s_FullMsgTxt) == str:
        glob_q_MQTT_MSG.put((s_FullMsgTopic, s_FullMsgTxt))

# This function will monitor the MQTT MSG Queue and snd msgs to the broker - requires a process
def MsgQueueMonitor():
    #get the global variables & settings
    global glob_s_MachineName
    global glob_MQTT_Client_Name  
    global glob_s_GCode_Proxy_Topic
    global glob_MQTT_SVR_Add
    global glob_MQTT_SVR_Port
    global glob_MQTT_User_Name
    global glob_MQTT_Password
    global glob_q_MQTT_MSG
    
    global client2
    try:
        client2 = mqtt.Client(str(glob_MQTT_Client_Name))

        while True:
            o_TMP_QueueItem = glob_q_MQTT_MSG.get()
            logging.info("About to send : " + str(o_TMP_QueueItem[1]) + " To : " + str(o_TMP_QueueItem[0]))
            client2.username_pw_set(username=glob_MQTT_User_Name,password=glob_MQTT_Password)
            client2.connect(glob_MQTT_SVR_Add, glob_MQTT_SVR_Port)
            client2.publish(str(o_TMP_QueueItem[0]), str(o_TMP_QueueItem[1]))
            time.sleep(0.2)
    except:
        return("32")

# Function to send System Messages - Should only be called internally
def constructSystemMsg(msgName, msgText):
    #get the global variables & settings
    global glob_s_MachineName
    global glob_j_MQTT4DSF_SYSMSGS 
    global glob_s_GCode_Proxy_Topic
    global glob_RepStr_MachineName

    try:
        if len(msgName) > 0 and len(msgText) > 0:
            for j_MsgName in glob_j_MQTT4DSF_SYSMSGS:
                if j_MsgName["MsgName"] == msgName:
                    sTMP_ReplaceStr = str(j_MsgName["Replace_String"])
                    for j_Msgs in j_MsgName["Msgs"]:
                        s_TMP_Topic = str(j_Msgs["MQTT_Topic_Path"]) 
                        s_TMP_MsgText = str(j_Msgs["MQTT_Topic_MSG"])
                        if len(s_TMP_Topic) > 0 and len(s_TMP_MsgText) > 0:
                            s_TMP_MsgText = s_TMP_MsgText.replace(str(sTMP_ReplaceStr), str(msgText))
                            s_TMP_MsgText = s_TMP_MsgText.replace(str(glob_RepStr_MachineName), str(glob_s_MachineName))
                            addToSndMsgQueue(str(s_TMP_Topic), str(s_TMP_MsgText))
                            logging.warning(str(s_TMP_MsgText))

    except Exception as ex:
        logging.error("Construct Sys Msg : " + str(ex))



# ************************
# ** MQTT CMD Functions **
# ************************

# Send a cmd to printer to acknowledge a cmd msg
# We have to do this as the monitor will not trigger if the same cmd is issued twice in a row
# By sending this M177 we effectively clear the last msg
def AckCmd():
    global glob_s_MSG_CMD_RESPONSE
    try: 
        command_connection = pydsfapi.CommandConnection(debug=False)
        command_connection.connect()
        try:
            # Perform a simple command and wait for its output
            ack = command_connection.perform_simple_code('M117 "' + str(glob_s_MSG_CMD_RESPONSE)+ '"')
        finally:
            command_connection.close()
    except Exception as ex:
        command_connection.close()
        logging.error("AckCmd : " + str(ex))
        constructSystemMsg("SysMsg", str("AckCmd: " + str(ex)))

# Function to check and get the cmd msg
def getMSGCMDFromKeys(json_object, path):
    global glob_s_MSG_CMD_Prefix
    global glob_s_MSG_CMD_RESPONSE
    global glob_j_MQTT4DSF_CMDMSGS

    if type(path) == str:
        d_TMP_Path = path.split("/")
        j_TMP_JSON = json_object
        try:
            for idx, dsf in enumerate(d_TMP_Path):
                j_TMP_JSON = j_TMP_JSON[d_TMP_Path[idx]]
            s_TMP_CMDMSG = str(j_TMP_JSON)    
            #should have the msg now            
            i_FindVal = s_TMP_CMDMSG.find(glob_s_MSG_CMD_Prefix)
            if i_FindVal != -1:
                #this is a cmd msg remove the cmd string identifier from the string
                s_TMP_CMDMSG = s_TMP_CMDMSG.replace(str(glob_s_MSG_CMD_Prefix), "")
                return s_TMP_CMDMSG
            #check for cmd response and return different val
            i_FindVal = s_TMP_CMDMSG.find(glob_s_MSG_CMD_RESPONSE)
            if i_FindVal != -1:
                #this is a cmd msg remove the cmd string identifier from the string
                return "CMDRESPONSE"
            else:
                return "NOTCMD"
        except KeyError:
            return "NOTCMD"
    else:
        return "NOTCMD"

# function to process and format the cmd msg
def processCMDMsg(s_CMD_MSG):
    global glob_RepStr_MachineName
    global glob_s_MachineName
    global glob_j_MQTT4DSF_CMDMSGS

    for j_CMDMSG in glob_j_MQTT4DSF_CMDMSGS:
        if j_CMDMSG["CMD_STRING"] == s_CMD_MSG and j_CMDMSG["Enabled"] == "Y":
            #match found so lets send the msg
            try:
                for j_Msgs in j_CMDMSG["Msgs"]:
                    s_TMP_Topic = str(j_Msgs["MQTT_Topic_Path"]) 
                    s_TMP_MsgText = str(j_Msgs["MQTT_Topic_MSG"])
                    if len(s_TMP_Topic) > 0 and len(s_TMP_MsgText) > 0:
                        s_TMP_MsgText = s_TMP_MsgText.replace(str(glob_RepStr_MachineName), str(glob_s_MachineName))
                        s_TMP_Topic = s_TMP_Topic.replace(str(glob_RepStr_MachineName), str(glob_s_MachineName))
                        addToSndMsgQueue(str(s_TMP_Topic), str(s_TMP_MsgText))
                        AckCmd()
            except Exception as ex:
                logging.error("processCMDMsgs : " + str(ex))
                constructSystemMsg("SysMsg", str("processCMDMsg: " + str(ex)))        


# **************************************
# ** DSF Message Formatting Functions **
# **************************************

# Function used to re-format DSF System Messages
def processDSFMsgs(strMsg):
    
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
        except KeyError as ex:
            logging.error("processDSFMsgs : " + str(ex))
            constructSystemMsg("SysMsg", "An KeyError occurred in processDSFMSG. You should check the DWC GUI for this machine")
            return "Error: msg processing"



# ***********************
# ** DSF API Functions **
# ***********************

# function to get the values from the keys based on the variable path defined in config jason
def getValFromKeys(json_object, path):
    
    logging.debug("GetValFromKeys data: " + str(json_object) + " PATH : " + str(path))
    if type(path) == str:
        d_TMP_Path = path.split("/")
        j_TMP_JSON = json_object
        try:
            for idx, dsf in enumerate(d_TMP_Path):
                logging.debug("GetValFromKeys idx: " + str(idx))
                j_TMP_JSON = j_TMP_JSON[d_TMP_Path[idx]]
            s_TMP_MSG = str(j_TMP_JSON)  
            logging.debug("GetValFromKeys val: " + str(s_TMP_MSG))  
            return s_TMP_MSG
        except KeyError:
            logging.debug("GetValFromKeys keyerr: " + str(j_TMP_JSON))  
            return "None"
    else:
        return "None"

def getValFromArray(json_object, s_Variable, i_instance, s_DSF_DOM_Path):
    
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

# function to construct the filter for the DSF plugin subscription service
def constructFilter():
    global glob_j_MQTT4DSF_MQTTMSGS

    try:
        s_DSF_Filter = ""
        for DSF_DOM_Filter in glob_j_MQTT4DSF_MQTTMSGS:
            #if type of MSG or DSF always add to filter as they are needed by MQTT4DSF functions
            if str(DSF_DOM_Filter["Type"]) == "MSG" or str(DSF_DOM_Filter["Type"]) == "DSF":
                s_DSF_Filter = s_DSF_Filter + str(DSF_DOM_Filter["DSF_DOM_Filter"]) + "|"
            #otherwise add to filter if enabled and std
            elif str(DSF_DOM_Filter["Enabled"]) == "Y" and str(DSF_DOM_Filter["Type"]) == "STD":
                s_DSF_Filter = s_DSF_Filter + str(DSF_DOM_Filter["DSF_DOM_Filter"]) + "|"

        # remove last "|" as its not needed
        if len(s_DSF_Filter) > 0:
            s_DSF_Filter = s_DSF_Filter[0:-1]
            return s_DSF_Filter
        else:
            return ""
    except Exception as ex:
        logging.error("Construct Filter : " + str(ex))
        constructSystemMsg("SysMsg", str("ConstructFilter: " + str(ex)))
        return ""


# ********************************************************
# ** DSF Error Handling and process monitoring Functions **
# ********************************************************

#Handle Errors
def MQTT4DSF_ErrHandler(errMsg):
    
    if errMsg == "[Errno 32] Broken pipe":
        #DSF is down - 
        constructSystemMsg("SysMsg", str("Reset or DSF is down. MQTT4DSF will attempt auto recovery"))
        return "32"
    if errMsg == "[Errno 111] Connection refused":
        # Invalid MQTT settings or MQTT server is down
        constructSystemMsg("SysMsg", str("Connection to DSF Refused. MQTT4DSF will attempt auto recovery"))
        return "32"
    if errMsg == "Err In DSFEventMonitor: Extra data: line 1 column 17 (char 16)":
        return "32"
    if errMsg == "Err In timedMonitoring: list indices must be integers or slices, not str":
        return "32"
    else:
        constructSystemMsg("SysMsg", str(" Err: " + str(errMsg) + ". MQTT4DSF will attempt auto recovery"))
        return "32"

# function that checks DSF is running and responding as expected
def checkDSF():
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
            logging.warning(str("CheckDSF has recovered"))
            return "OK"
        except Exception as ex:
            sub_conn = None
            reload(pydsfapi)
            logging.error("CheckDSF err: " + str(ex))
            logging.warning(str("CheckDSF has failed to recover: retrying in 5 seconds"))
            return "32"

#this function keeps things running and handles errors for process 1
def daemon_one():
    o_Sys_Set_four = Settings()
    while True:
        MQTT4DSF_InitServiceDefaults(o_Sys_Set_four)
        str_RetCode = MsgQueueMonitor()
        while str_RetCode == "32":
            time.sleep(5)

#this function keeps things running and handles errors for process 1
def daemon_two():
    o_Sys_Set_one = Settings()
    while True:
        MQTT4DSF_InitServiceDefaults(o_Sys_Set_one)
        str_RetCode = DSFEventMonitor()
        while str_RetCode == "32":
            str_RetCode = checkDSF()
        # add other error conditions here if required

#this function keeps things running and handles errors for process 2
def daemon_three():
    o_Sys_Set_two = Settings()
    while True:
        MQTT4DSF_InitServiceDefaults(o_Sys_Set_two)
        str_RetCode = timedMonitoring()
        while str_RetCode == "32":
            time.sleep(5)

#this function keeps things running and handles errors for process 3
def daemon_four():
    o_Sys_Set_three = Settings()
    while True:
        MQTT4DSF_InitServiceDefaults(o_Sys_Set_three)
        str_RetCode = processDSFEventQueue()
        while str_RetCode == "32":
            time.sleep(5)


#this function kicks off the gcode proxy listner in a process (5)
def daemon_five():
    o_Sys_Set_five = Settings()
    MQTT4DSF_InitServiceDefaults(o_Sys_Set_five)
    if o_Sys_Set_five.s_Enable_GCode_Proxy == "Y":
        logging.info("Starting GCode Proxy Monitor")
        GCodeProxyTopicMonitor()




# ********************
# ** Core Functions **
# ********************

# Monitors the DSF api for pushed events and adds them to the queue for processing - requires a process
def DSFEventMonitor():
    global glob_q_DSF_Updates
    
    try:
        #get the filter string
        str_TMP_Filter = constructFilter()
        subscribe_connection3 = pydsfapi.SubscribeConnection(SubscriptionMode.PATCH, str_TMP_Filter, debug=False)
        subscribe_connection3.connect()

        #get the first msg and discard
        j_DSFEventMsg = subscribe_connection3.get_machine_model_patch()
        j_DSFEventMsg = ""
        subscribe_connection3.connect()

        while True:            
            while subscribe_connection3.get_machine_model_patch():
                j_DSFEventMsg = subscribe_connection3.get_machine_model_patch()
                glob_q_DSF_Updates.put(j_DSFEventMsg)
                subscribe_connection3.connect()
    
    except Exception as ex:
        subscribe_connection3.close()
        logging.error("DSF Event Monitor Error : " + str(ex))
        return(MQTT4DSF_ErrHandler(str("Err In DSFEventMonitor: " + str(ex))))



# Function to get initial information from the DSF Dom - Normally only called on startup of this script or major DSF failures
def getInitialInfo():
    global glob_s_MachineName
    global glob_s_DSF_HTTP_REQ_URL
    
    try:
        s_machine_model = requests.get(url = glob_s_DSF_HTTP_REQ_URL)
        #define machine json
        j_machine_model = json.loads(s_machine_model.text)
        s_machine_model = None
        #Get Machine Details - (Always get first instances)
        s_Machine_IP = str(j_machine_model["network"]["interfaces"][0]["actualIP"])
        s_Machine_DSF_Ver = str(j_machine_model["state"]["dsfVersion"])
        s_Machine_Board_FW_ver = str(j_machine_model["boards"][0]["firmwareVersion"])
        s_Machine_Initial_Msg = "NOW ONLINE:: -Machine: " + str(glob_s_MachineName) + " -IP: " +str(s_Machine_IP) + " -DSF FW Ver: " + str(s_Machine_DSF_Ver) + " -Board FW Ver: " + str(s_Machine_Board_FW_ver)
        # Send msg to to Duet/Announce/
        constructSystemMsg("SysAnnounce", str(s_Machine_Initial_Msg))
    except Exception as ex:
        logging.error("getInitialnfo : " + str(ex))
        return(MQTT4DSF_ErrHandler(str("Err In getInitialInfo: "+ str(ex))))


# function that does the main job of monitoring for updates from DSF queue and publishing the MQTT messages - needs a process
def processDSFEventQueue():
    global glob_s_MachineName
    global glob_RepStr_MachineName
    global glob_j_MQTT4DSF_MQTTMSGS
    global o_Sys_Settings


    try:
        while True:
            #get next update from the queue
            j_patch = glob_q_DSF_Updates.get()
            try:
                j_latest = json.loads(j_patch)
            except:
                continue

            #for each subscription update event iterate through all MQTT_MESSAGES in config and identify matches
            for j_AllMsgs in glob_j_MQTT4DSF_MQTTMSGS:
                #Get MSG Type
                s_TMP_MsgType = str(j_AllMsgs["Type"])
                s_TMP_Enabled = str(j_AllMsgs["Enabled"])
                b_IsCMD = False
                #check for MQTT_CMD_MSGS
                if s_TMP_MsgType == "MSG":
                    s_TMP_CMD_MsgVal = getMSGCMDFromKeys(j_latest, j_AllMsgs["DSF_DOM_Filter"])
                    if s_TMP_CMD_MsgVal != "NOTCMD" and s_TMP_CMD_MsgVal != "CMDRESPONSE":
                        #this is a cmd msg
                        b_IsCMD = True
                        processCMDMsg(s_TMP_CMD_MsgVal)
                    elif s_TMP_CMD_MsgVal == "CMDRESPONSE":
                        #This is the response sent to the machine from MQTT4DSF after it has processed a m177 cmd so no further action is required
                        b_IsCMD = True
                    else:
                        b_IsCMD = False
                #check if this is enabled and its not a MQTTCMD MSG : if not then skip
                if s_TMP_Enabled == "Y" and b_IsCMD == False:
                    for j_Msg in j_AllMsgs["Msgs"]:
                        # get the mqtt parameters first
                        s_TMP_Topic = j_Msg["MQTT_Topic_Path"]
                        s_TMP_Topic = s_TMP_Topic.replace(str(glob_RepStr_MachineName), str(glob_s_MachineName))
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
                            s_TMP_Val = getValFromKeys(j_latest, s_TMP_Variable)
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
                                    s_TMP_Val = processDSFMsgs(str(s_TMP_Val))
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
                            s_TMP_MsgText = s_TMP_MsgText.replace(str(glob_RepStr_MachineName),str(glob_s_MachineName))
                            addToSndMsgQueue(str(s_TMP_Topic), str(s_TMP_MsgText))
    except Exception as ex:
        logging.error("processDSFEventQueue : " + str(ex))
        return(MQTT4DSF_ErrHandler(str("Err In processDSFEventQueue: "+ str(ex))))
                            
# function that does the main job of polling DSF for updates based on defined polling frequency
def timedMonitoring():
    global glob_s_MachineName
    global glob_RepStr_MachineName
    global glob_i_PollFreq
    global glob_s_DSF_HTTP_REQ_URL
    global glob_j_MQTT4DSF_MONMSGS
    global o_Sys_Settings
    
    while True:
        try:
            s_machine_model = requests.get(url = glob_s_DSF_HTTP_REQ_URL)
            #define machine json
            j_machine_model2 = json.loads(s_machine_model.text)
            s_machine_model = None
            for j_AllMsgs in glob_j_MQTT4DSF_MONMSGS:
                s_TMP_MsgType = j_AllMsgs["Type"]
                for j_Msg in j_AllMsgs["Msgs"]:
                    # get the mqtt parameters first
                    s_TMP_Topic = j_Msg["MQTT_Topic_Path"]
                    s_TMP_Topic = s_TMP_Topic.replace(str(glob_RepStr_MachineName), str(glob_s_MachineName))
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
                                s_TMP_Val = getValFromArray(j_machine_model2, s_TMP_Variable, i_TMP_instance, s_TMP_DSF_DOM_Path)
                            if s_TMP_DSF_Variable_Type == "SINGLE":
                                s_TMP_Val = getValFromKeys(j_machine_model2, str(str(s_TMP_DSF_DOM_Path) + "/" + str(s_TMP_Variable)))
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
                                    s_TMP_Val = processDSFMsgs(str(s_TMP_Val))
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
                        s_TMP_MsgText = s_TMP_MsgText.replace(str(glob_RepStr_MachineName),str(glob_s_MachineName))
                        addToSndMsgQueue(str(s_TMP_Topic), str(s_TMP_MsgText))
            # Polling Delay Here
            time.sleep(glob_i_PollFreq)
        except Exception as ex:
            logging.error("timedMonitoring : " + str(ex))
            return(MQTT4DSF_ErrHandler(str("Err In timedMonitoring: "+ str(ex))))


# ***********************
# ** Processes Startup **
# ***********************
def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def startMyProcessess(b_FirstTime):
    global glob_q_MQTT_MSG
    global glob_q_DSF_Updates   
    # Initialise & get MQTT4DSF settings values & Config
    MQTT4DSF_InitServiceDefaults(o_Sys_Settings)
    #Setup Queues
    glob_q_MQTT_MSG = multiprocessing.Queue(maxsize = glob_q_MQTT_MSG_Size)
    glob_q_DSF_Updates = multiprocessing.Queue(maxsize = glob_q_DSF_Updates_Size)
    # Change the logging level to the value from the config file (Re-Visit)
    if o_Sys_Settings.s_MQTT4DSF_Logging_level == "DEBUG": logging.getLogger().setLevel(logging.DEBUG)
    if o_Sys_Settings.s_MQTT4DSF_Logging_level == "INFO": logging.getLogger().setLevel(logging.INFO)
    if o_Sys_Settings.s_MQTT4DSF_Logging_level == "CRITICAL": logging.getLogger().setLevel(logging.CRITICAL)
    if o_Sys_Settings.s_MQTT4DSF_Logging_level == "WARNING": logging.getLogger().setLevel(logging.WARNING)
    if o_Sys_Settings.s_MQTT4DSF_Logging_level == "ERROR": logging.getLogger().setLevel(logging.ERROR)
    o_pool = multiprocessing.Pool(5, init_worker)
    o_pool.apply_async(daemon_one)
    if b_FirstTime == True:
        # Get the initial information needed for processing do not continue unless sucessful
        str_RetCode = getInitialInfo()
        while str_RetCode == "32":
            str_RetCode = checkDSF()
    # start the daemons for normal operation
    o_pool.apply_async(daemon_two)
    o_pool.apply_async(daemon_three)
    o_pool.apply_async(daemon_four)
    o_pool.apply_async(daemon_five)    
    return True



# **************************
# ** Initialising Service **
# **************************

# Define some critical variables and parameters
global glob_s_MachineName
glob_s_MachineName = "Unknown"
global o_Sys_Settings
o_Sys_Settings = Settings()
global o_pool

# reload the DSF Python Plugin on startup to avoid errors - it can be tempromental under certain conditions
reload(pydsfapi)

if __name__ == "__main__":
    o_pool = multiprocessing.Pool(5, init_worker)
    try:
        startMyProcessess(True)
        #Check for config changes every 10 seconds if true config reload
        while True:
            while o_Sys_Settings.update_settings() == True:        
                logging.info("Triggering Reload of settings!")
                #Kill & Reload Processess
                o_pool.terminate()
                o_pool.join()
                # ReInitialise & get MQTT4DSF settings values & Config
                MQTT4DSF_InitServiceDefaults(o_Sys_Settings)
                #ReSetup Queues
                reload(pydsfapi)
                startMyProcessess(False)
            time.sleep(10)
    except KeyboardInterrupt:
        logging.debug("Caught KeyboardInterrupt, terminating pool")
        o_pool.terminate()
        o_pool.join()