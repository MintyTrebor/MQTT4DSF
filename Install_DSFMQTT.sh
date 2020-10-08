sudo wget -O DSFMQTT.tar.gz 'https://github.com/MintyTrebor/DSFMQTT/releases/download/v0.01-ALPHA/DSFMQTT.tar.gz'

sudo chmod a+rwx DSFMQTT.tar.gz

mkdir DSFMQTT
sudo chmod a+rw DSFMQTT
tar vxf DSFMQTT.tar.gz
cd DSFMQTT

#copy config file to duet sys folder for easy editing
sudo cp DSFMQTT_Config.json /opt/dsf/sd/sys/DSFMQTT_Config.json
#give permissions to rw
sudo chmod a+rw /opt/dsf/sd/sys/DSFMQTT_Config.json

#copy DSFMQTT python file to duet plugins folder
sudo mkdir /opt/dsf/plugins/DSFMQTT
sudo chmod a+rw /opt/dsf/plugins/DSFMQTT
sudo cp DSFMQTT.py /opt/dsf/plugins/DSFMQTT/DSFMQTT.py
#give permissions to rw
sudo chmod a+rwx /opt/dsf/plugins/DSFMQTT/DSFMQTT.py

#create the service
if [ -f /etc/systemd/system/DSFMQTT.service ]; then
 sudo systemctl stop DSFMQTT.service
 sudo systemctl disable DSFMQTT.service
else
 sudo cp -f DSFMQTT.service /etc/systemd/system/DSFMQTT.service
fi

echo "In DWC refresh the sys folder and edit DSFMQTT_Config.json. Enter you MQTT server/broker details and save the file."
echo "Please refer to the readme @ https://github.com/MintyTrebor/DSFMQTT for configuration guidence"
echo "Type 'sudo systemctl start DSFMQTT.service' to start DSFMQTT. If everything check out you should have a startup MQTT msg sent to the 'Duet/Announce' topic"
echo "If the service is working as expected type 'sudo systemctl enable DSFMQTT.service' to enable DSFMQTT to start at boot."

sudo systemctl enable DSFMQTT.service
sudo systemctl daemon-reload
#sudo systemctl start DSFMQTT.service
