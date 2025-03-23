#print(machine.freq())
#machine.freq(15_625_000)
#machine.freq(16_000_000)

led_onboard = machine.Pin('LED', machine.Pin.OUT)

import network
network.ipconfig(prefer=6)
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# (298 hours TICKS_PERIOD on rp2040)
import time
try:
	from settings import settings
	wlan.connect(settings['ssid'], settings['pass'],)
	
	machine.lightsleep(1023)
	
	@micropython.viper
	def unnoetigAberTrotzdem():
		ticksAtStart = time.ticks_ms()
		deadlineWifi = time.ticks_add(ticksAtStart, 16383)
		while wlan.status() != network.STAT_GOT_IP:
			machine.idle()
			if time.ticks_diff(deadlineWifi, time.ticks_ms()) <= 0:
				break

		print('ticks diff: ', time.ticks_diff(time.ticks_ms(), ticksAtStart),)
	
	unnoetigAberTrotzdem()
	print(wlan.ifconfig())
	
	# IPv6 works, see https://github.com/micropython/micropython/commit/1c6012b0b5c62f18130217f30e73ad3ce4c8c9e6
	print(wlan.ipconfig("addr6"))
	
	import requests
	bootedResponse = requests.post(url=f'${settings.c2server}/booted', data=f'', auth=(settings.c2user, settings.c2pass,),)
	bootedResponse.status_code

	
except ImportError as impErr:
	# TODO: default settings? AP mode for config? Blink LED?
	print(wlan.scan())
	

wlan.active(False)


# while True:
# 	# Since this function temporarily disables access to the external flash memory, it also temporarily disables interrupts and the other core to prevent them from trying to execute code from flash.
# 	if rp2.bootsel_button() == 1:
# 		led_onboard.on()
# 	else:
# 		led_onboard.off()
# 	startTime = time.ticks_ms()
# 	machine.lightsleep(383)
# 	endTime = time.ticks_ms()
# 	if time.ticks_diff(endTime, startTime,) >= 255:
# 		print("lightsleep (somehow) worked")
# 		break
