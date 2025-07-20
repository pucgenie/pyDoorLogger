from collections import namedtuple
# pucgenie: I don't have EAP networks to test with
Wlan_network_meta = namedtuple('Wlan_network_meta', 'ssid passphrase',)
Command_and_control_server_meta = namedtuple('Command_and_control_server_meta', 'server_url username password',)
# https://softwareengineering.stackexchange.com/questions/351126/how-bad-of-an-idea-is-it-to-use-python-files-as-configuration-files
