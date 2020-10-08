# DSFMQTT
A Python script to send MQTT msgs from a SBC running Duet DSF. Uses the DSF pydsfapi plugin.

This is a python script which interfaces with the DFS Python API to enable the DSF system to send Msgs to an MQTT broker.
It is currently in very early stages, and relies on editing a json file via the DWC interface to configure the script.

Currently it can:

1.Monitor DSF for events (user configurable) and send mqtt msgs to a broker of choice
2.Poll DSF on a frequency and send mqtt msgs based on a value delta (user configurable)
3.Send MQTT msgs when specially formatted msgs are recieved from DSF.

Installer scripts are available which will also setup DSFMQTT as a service to run at boot.

Configuration instructions & examples to follow shortly
