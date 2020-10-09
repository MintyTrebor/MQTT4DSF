#!/usr/bin/env python3

import sys
import time
import paho.mqtt.client as mqtt
import json
import datetime
import logging
import requests
from threading import Thread
from pydsfapi import pydsfapi
from pydsfapi.commands import basecommands, code
from pydsfapi.initmessages.clientinitmessages import InterceptionMode, SubscriptionMode
from importlib import reload
from queue import Queue 

#setup logging:
logging.basicConfig(filename='/var/log/DSFMQTT.log',
                            filemode='a',
                            format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.INFO)

#setup some variables incase they are used before dynamic value assignment
s_MachineName = "Unknown"
s_ConfigPath = "/opt/dsf/sd/sys/DSFMQTT_Config.json"


# load DSFMQTT_Config.json & setup system variables and MQTT connection
# assumes file is in the location /opt/dsf/sd/sys/DSFMQTT_Config.json as this makes it easier to edit in DWC
try:
    with open(s_ConfigPath) as config_file:
        config_json = json.load(config_file)
        MQTT_SVR_Add = config_json["MQTT_SETTINGS"]["MQTT_SVR_ADD"]
        MQTT_SVR_Port = config_json["MQTT_SETTINGS"]["MQTT_SVR_PORT"]
        MQTT_Client_Name = config_json["MQTT_SETTINGS"]["MQTT_Client_Name"]
        
        
        # Setup MQTT Client Connection
        MQTT_SVR_Port = int(MQTT_SVR_Port)
        client = mqtt.Client(str(MQTT_Client_Name))
        client.connect(MQTT_SVR_Add,MQTT_SVR_Port)

        # Get Fixed Sys Variables and paramters from the config json
        RepStr_MachineName = config_json["SYS_SETTINGS"]["Default_Replace_Strings"]["Machine_Name"]
        i_PollFreq = int(config_json["GENERAL_SETTINGS"]["PollFrequencySeconds"])
        s_MSG_CMD_Prefix = str(config_json["GENERAL_SETTINGS"]["MQTT_MSG_CMD_Prefix"])
        s_MSG_CMD_RESPONSE = str(config_json["GENERAL_SETTINGS"]["MQTT_MSG_CMD_RESPONSE"])
        q_MQTT_MSG = Queue(maxsize = int(config_json["GENERAL_SETTINGS"]["MQTT_MSG_QUEUE_SIZE"]))
        q_DSF_Updates = Queue(maxsize = int(config_json["GENERAL_SETTINGS"]["DSF_UPDATE_QUEUE_SIZE"]))
        s_DSF_HTTP_REQ_URL = str(config_json["GENERAL_SETTINGS"]["HTTP_DSF_REQ_ADD"])
        s_MachineName = str(config_json["GENERAL_SETTINGS"]["MACHINE_NAME"])
                
except KeyError:
    logging.critical("Configuration file is invalid")
except Exception as ex:
    logging.critical("Initialise error: " + str(ex))


# ***************
# ** Functions **
# ***************

# function to get the values from the keys based on the variable path defined in config jason
def getValFromKeys(json_object, path):
    
    #logging.info("GetValFromKeys data: " + str(json_object) + " PATH : " + str(path))
    if type(path) == str:
        d_TMP_Path = path.split("/")
        j_TMP_JSON = json_object
        try:
            for idx, dsf in enumerate(d_TMP_Path):
                j_TMP_JSON = j_TMP_JSON[d_TMP_Path[idx]]
            s_TMP_MSG = str(j_TMP_JSON)  
            #logging.info("GetValFromKeys val: " + str(s_TMP_MSG))  
            return s_TMP_MSG
        except KeyError:
            #logging.info("GetValFromKeys keyerr: " + str(j_TMP_JSON))  
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

def addToSndMsgQueue(s_FullMsgTopic, s_FullMsgTxt):
    global q_MQTT_MSG
    if type(s_FullMsgTopic) == str and type(s_FullMsgTxt) == str:
        q_MQTT_MSG.put((s_FullMsgTopic, s_FullMsgTxt))


# This function will monitor the MQTT MSG Queue and snd msgs to the broker - requires a thread
def MsgQueueMonitor():
    global q_MQTT_MSG
    try:
        client2 = mqtt.Client(str(MQTT_Client_Name))
        while True:
            o_TMP_QueueItem = q_MQTT_MSG.get()
            logging.info("About to send : " + str(o_TMP_QueueItem[1]) + " To : " + str(o_TMP_QueueItem[0]))
            client2.connect(MQTT_SVR_Add, MQTT_SVR_Port)
            client2.publish(str(o_TMP_QueueItem[0]), str(o_TMP_QueueItem[1]))
            time.sleep(0.2)
    except:
        return("32")

# Monitors the DSF api for pushed updates and adds them to the queue for processing - requires a thread
def DSFEventMonitor():
    global s_MachineName
    global RepStr_MachineName
    global q_DSF_Updates
    global config_json
    global str_TMP_Filter
    global s_ConfigPath

    try:
        #reload the config file just incase
        with open(s_ConfigPath) as config_file:
            config_json = json.load(config_file)
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
                #print("Event : "+ str(j_DSFEventMsg))
                q_DSF_Updates.put(j_DSFEventMsg)
                subscribe_connection3.connect()

    except Exception as ex:
        subscribe_connection3.close()
        logging.error("DSF Event Monitor Error : " + str(ex))
        return(DSFMQTT_ErrHandler(str("Err In DSFEventMonitor: " + str(ex))))


# Function to send System Messages - Should only be called internally
def constructSystemMsg(msgName, msgText):
    global s_MachineName
    global RepStr_MachineName
    global MQTT_SVR_Add
    global MQTT_SVR_Port

    try:
        if len(msgName) > 0 and len(msgText) > 0:
            for j_MsgName in config_json["SYS_SETTINGS"]["SYS_MSGS"]:
                if j_MsgName["MsgName"] == msgName:
                    sTMP_ReplaceStr = str(j_MsgName["Replace_String"])
                    for j_Msgs in j_MsgName["Msgs"]:
                        s_TMP_Topic = str(j_Msgs["MQTT_Topic_Path"]) 
                        s_TMP_MsgText = str(j_Msgs["MQTT_Topic_MSG"])
                        if len(s_TMP_Topic) > 0 and len(s_TMP_MsgText) > 0:
                            s_TMP_MsgText = s_TMP_MsgText.replace(str(sTMP_ReplaceStr), str(msgText))
                            s_TMP_MsgText = s_TMP_MsgText.replace(str(RepStr_MachineName), str(s_MachineName))
                            addToSndMsgQueue(str(s_TMP_Topic), str(s_TMP_MsgText))
                            logging.warning(str(s_TMP_MsgText))

    except Exception as ex:
        logging.error("Construct Sys Msg : " + str(ex))


# function to construct the filter for the DSF plugin subscription service
def constructFilter():
    try:
        s_DSF_Filter = ""
        for DSF_DOM_Filter in config_json["MQTT_MESSAGES"]:
            #if type of MSG or DSF always add to filter as they are needed by DSFMQTT functions
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
        constructSystemMsg("SysMsg", str("ConstructFilter: " + str(ex)))
        return ""

# Send a cmd to printer to acknowledge a cmd msg
# We have to do this as the monitor will not trigger if the same cmd is issued twice in a row
# By sending this M177 we effectively clear the last msg
def AckCmd():
    try: 
        command_connection = pydsfapi.CommandConnection(debug=False)
        command_connection.connect()
        try:
            # Perform a simple command and wait for its output
            ack = command_connection.perform_simple_code('M117 "' + str(s_MSG_CMD_RESPONSE)+ '"')
        finally:
            command_connection.close()
    except Exception as ex:
        command_connection.close()
        constructSystemMsg("SysMsg", str("AckCmd: " + str(ex)))

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
        except KeyError:
            constructSystemMsg("SysMsg", "An KeyError occurred in processDSFMSG. You should check the DWC GUI for this machine")
            return "Error: msg processing"

# Function to check and get the cmd msg
def getMSGCMDFromKeys(json_object, path):
    global s_MSG_CMD_Prefix
    if type(path) == str:
        d_TMP_Path = path.split("/")
        j_TMP_JSON = json_object
        try:
            for idx, dsf in enumerate(d_TMP_Path):
                j_TMP_JSON = j_TMP_JSON[d_TMP_Path[idx]]
            s_TMP_CMDMSG = str(j_TMP_JSON)    
            #should have the msg now            
            i_FindVal = s_TMP_CMDMSG.find(s_MSG_CMD_Prefix)
            if i_FindVal != -1:
                #this is a cmd msg remove the cmd string identifier from the string
                s_TMP_CMDMSG = s_TMP_CMDMSG.replace(str(s_MSG_CMD_Prefix), "")
                return s_TMP_CMDMSG
            #check for cmd response and return different val
            i_FindVal = s_TMP_CMDMSG.find(s_MSG_CMD_RESPONSE)
            if i_FindVal != -1:
                #this is a cmd msg remove the cmd string identifier from the string
                return "CMDRESPONSE"
            else:
                return "NOTCMD"
        except KeyError:
            return "NOTCMD"
    else:
        return "NOTCMD"



def processCMDMsg(s_CMD_MSG):
    global config_json
    global RepStr_MachineName
    global s_MachineName
    global MQTT_SVR_Add
    global MQTT_SVR_Port

    for j_CMDMSG in config_json["MQTT_MSG_CMDS"]:
        if j_CMDMSG["CMD_STRING"] == s_CMD_MSG and j_CMDMSG["Enabled"] == "Y":
            #match found so lets send the msg
            try:
                for j_Msgs in j_CMDMSG["Msgs"]:
                    s_TMP_Topic = str(j_Msgs["MQTT_Topic_Path"]) 
                    s_TMP_MsgText = str(j_Msgs["MQTT_Topic_MSG"])
                    if len(s_TMP_Topic) > 0 and len(s_TMP_MsgText) > 0:
                        s_TMP_MsgText = s_TMP_MsgText.replace(str(RepStr_MachineName), str(s_MachineName))
                        s_TMP_Topic = s_TMP_Topic.replace(str(RepStr_MachineName), str(s_MachineName))
                        addToSndMsgQueue(str(s_TMP_Topic), str(s_TMP_MsgText))
                        AckCmd()
            except Exception as ex:
                constructSystemMsg("SysMsg", str("ConstructFilter: " + str(ex)))        


#Handle Errors Thread 1
def DSFMQTT_ErrHandler(errMsg):
    global s_MachineName
    global RepStr_MachineName
    if errMsg == "[Errno 32] Broken pipe":
        #DSF is down - 
        constructSystemMsg("SysMsg", str("Reset or DSF is down. DSFMQTT will attempt auto recovery"))
        return "32"
    if errMsg == "[Errno 111] Connection refused":
        # Invalid MQTT settings or MQTT server is down
        constructSystemMsg("SysMsg", str("Connection to DSF Refused. DSFMQTT will attempt auto recovery"))
        return "32"
    if errMsg == "Err In DSFEventMonitor: Extra data: line 1 column 17 (char 16)":
        return "32"
    if errMsg == "Err In timedMonitoring: list indices must be integers or slices, not str":
        return "32"
    else:
        constructSystemMsg("SysMsg", str(" Err: " + str(errMsg) + ". DSFMQTT will attempt auto recovery"))
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
            return "OK"
            logging.info(str("CheckDSF has recovered"))
        except Exception as ex:
            sub_conn = None
            reload(pydsfapi)
            logging.error("CheckDSF err: " + str(ex))
            logging.warning(str("CheckDSF has failed to recover: retrying in 5 seconds"))
            return "32"


#this function keeps things running and handles errors for thread 1
def daemon_one():
    while True:
        str_RetCode = DSFEventMonitor()
        while str_RetCode == "32":
            str_RetCode = checkDSF()
        # add other error conditions here if required

#this function keeps things running and handles errors for thread 2
def daemon_two():
    while True:
        str_RetCode = timedMonitoring()
        while str_RetCode == "32":
            time.sleep(5)

#this function keeps things running and handles errors for thread 3
def daemon_three():
    while True:
        str_RetCode = processDSFEventQueue()
        while str_RetCode == "32":
            time.sleep(5)

#this function keeps things running and handles errors for thread 4
def daemon_four():
    while True:
        str_RetCode = MsgQueueMonitor()
        while str_RetCode == "32":
            time.sleep(5)


# Function to get initial information from the DSF Dom - Normally only called on startup of this script or major DSF failures
def getInitialInfo():
        global s_MachineName
        global RepStr_MachineName
        global s_DSF_HTTP_REQ_URL

        try:
            s_machine_model = requests.get(url = s_DSF_HTTP_REQ_URL)
            #define machine json
            j_machine_model = json.loads(s_machine_model.text)
            s_machine_model = None


            #Get Machine Details - (Always get first instances)
            s_Machine_IP = str(j_machine_model["network"]["interfaces"][0]["actualIP"])
            s_Machine_DSF_Ver = str(j_machine_model["state"]["dsfVersion"])
            s_Machine_Board_FW_ver = str(j_machine_model["boards"][0]["firmwareVersion"])
            s_Machine_Initial_Msg = "NOW ONLINE:: -Machine: " + str(s_MachineName) + " -IP: " +str(s_Machine_IP) + " -DSF FW Ver: " + str(s_Machine_DSF_Ver) + " -Board FW Ver: " + str(s_Machine_Board_FW_ver)
                
            # Send msg to to Duet/Announce/
            constructSystemMsg("SysAnnounce", str(s_Machine_Initial_Msg))
        
        except Exception as ex:
            return(DSFMQTT_ErrHandler(str("Err In getInitialInfo: "+ str(ex))))


# function that does the main job of monitoring for updates from DSF queue and publishing the MQTT messages - needs a thread
def processDSFEventQueue():
    global s_MachineName
    global RepStr_MachineName
    global str_TMP_Filter
    global config_json

    #try:
    while True:
        #get next update from the queue
        j_patch = q_DSF_Updates.get()
        try:
            j_latest = json.loads(j_patch)
        except Exception as ex:
            continue

        #for each subscription update event iterate through all MQTT_MESSAGES in config and identify matches
        for j_AllMsgs in config_json["MQTT_MESSAGES"]:
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
                    #This is the response sent to the machine from DSFMQTT after it has processed a m177 cmd so no further action is required
                    b_IsCMD = True
                else:
                    b_IsCMD = False
            #check if this is enabled and its not a MQTTCMD MSG : if not then skip
            if s_TMP_Enabled == "Y" and b_IsCMD == False:
                for j_Msg in j_AllMsgs["Msgs"]:
                    # get the mqtt parameters first
                    s_TMP_Topic = j_Msg["MQTT_Topic_Path"]
                    s_TMP_Topic = s_TMP_Topic.replace(str(RepStr_MachineName), str(s_MachineName))
                    s_TMP_MsgText = j_Msg["MQTT_Topic_MSG"]
                    # get the variables to check in the subscription update json from DSF
                    b_Match_Found = False
                    b_SndMsg = False
                    for j_Variables in j_AllMsgs["JSON_Variables"]:
                        s_TMP_Variable = j_Variables["Variable"]
                        s_TMP_Replace_String = j_Variables["Replace_String"]
                        s_TMP_Var_Type = j_Variables["Var_Type"]
                        s_TMP_LastVal = j_Variables["lastval"]
                        i_TMP_Delta = j_Variables["Msg_Delta"]
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
                    if b_Match_Found == True and b_SndMsg == True:
                        s_TMP_MsgText = s_TMP_MsgText.replace(str(RepStr_MachineName),str(s_MachineName))
                        addToSndMsgQueue(str(s_TMP_Topic), str(s_TMP_MsgText))

    #except Exception as ex:
    #    return(DSFMQTT_ErrHandler(str("Err In processDSFEventQueue: "+ str(ex))))
                            
# function that does the main job of polling DSF for updates based on defined polling frequency
def timedMonitoring():
    global s_MachineName
    global RepStr_MachineName
    global i_PollFreq
    global s_DSF_HTTP_REQ_URL
    
    while True:
        try:
            s_machine_model = requests.get(url = s_DSF_HTTP_REQ_URL)
            #define machine json
            j_machine_model2 = json.loads(s_machine_model.text)
            s_machine_model = None

            for j_AllMsgs in config_json["MONITORED_MQTT_MSGS"]:
                s_TMP_MsgType = j_AllMsgs["Type"]
                for j_Msg in j_AllMsgs["Msgs"]:
                    # get the mqtt parameters first
                    s_TMP_Topic = j_Msg["MQTT_Topic_Path"]
                    s_TMP_Topic = s_TMP_Topic.replace(str(RepStr_MachineName), str(s_MachineName))
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
                            i_TMP_instance = j_Variables["instance"]
                            s_TMP_Variable = j_Variables["Variable"]
                            s_TMP_Replace_String = j_Variables["Replace_String"]
                            s_TMP_Var_Type = j_Variables["Var_Type"]
                            s_TMP_LastVal = j_Variables["lastval"]
                            i_TMP_Delta = j_Variables["Msg_Delta"]
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
                        s_TMP_MsgText = s_TMP_MsgText.replace(str(RepStr_MachineName),str(s_MachineName))
                        addToSndMsgQueue(str(s_TMP_Topic), str(s_TMP_MsgText))

            # Polling Delay Here
            time.sleep(i_PollFreq)

        except Exception as ex:
            return(DSFMQTT_ErrHandler(str("Err In timedMonitoring: "+ str(ex))))

            


# reload the DSF Python Plugin on startup to avoid errors - it can be tempromental under certain conditions
reload(pydsfapi)

#start the queue for mqtt msgs
Thread(target = daemon_four).start()

#Get the initail information needed for processing
str_RetCode = getInitialInfo()
while str_RetCode == "32":
    str_RetCode = checkDSF()

# start the daemons for normal operation
Thread(target = daemon_one).start()
Thread(target = daemon_two).start()
Thread(target = daemon_three).start()


