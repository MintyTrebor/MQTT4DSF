#!/bin/bash
wget -O MQTT4DSF.tar.gz "https://github.com/MintyTrebor/MQTT4DSF/releases/download/v0.1-ALPHA/MQTT4DSF.tar.gz"
sudo chmod a+rwx MQTT4DSF.tar.gz
mkdir MQTT4DSF
sudo chmod a+rw MQTT4DSF
tar vxf MQTT4DSF.tar.gz
cd MQTT4DSF
#copy config file to duet sys folder for easy editing
sudo cp MQTT4DSF_Config.json /opt/dsf/sd/sys/MQTT4DSF_Config.json
#give permissions to rw
sudo chmod a+rw /opt/dsf/sd/sys/MQTT4DSF_Config.json
#copy MQTT4DSF python file to duet plugins folder
sudo mkdir /opt/dsf/plugins/MQTT4DSF
sudo chmod a+rw /opt/dsf/plugins/MQTT4DSF
sudo cp -R *.py /opt/dsf/plugins/MQTT4DSF
#give permissions to rw
sudo chmod a+rwx /opt/dsf/plugins/MQTT4DSF/*.py
#create the service
if [ -f /etc/systemd/system/MQTT4DSF.service ]; then
 sudo systemctl stop MQTT4DSF.service
 sudo systemctl disable MQTT4DSF.service
else
 sudo cp -f MQTT4DSF.service /etc/systemd/system/MQTT4DSF.service
fi
sudo systemctl enable MQTT4DSF.service
sudo systemctl daemon-reload
echo "  "
echo "In DWC refresh the sys folder and edit MQTT4DSF_Config.json. Enter you MQTT server/broker details and save the file."
echo "Please refer to the readme @ https://github.com/MintyTrebor/MQTT4DSF for configuration guidence"
echo "Type 'sudo systemctl start MQTT4DSF.service' to start MQTT4DSF. If everything check out you should have a startup MQTT msg sent to the 'Duet/Announce' topic"
echo "If the service is working as expected type 'sudo systemctl enable MQTT4DSF.service' to enable MQTT4DSF to start at boot."

