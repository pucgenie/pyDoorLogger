#print(machine.freq())
#machine.freq(15_625_000)
#machine.freq(16_000_000)

# pucgenie: I want to have asyncio on core0 (interrupts etc.) and a custom scheduler on core1 (is GIL still a problem?).
# I still need to think about a thread-safe mechanism to notify core0 about core1's results.
# Or we simply only execute optional code on core1 where it doesn't matter if it fails.
# BUT most optional code I can think of now is network-related stuff - which only works on core0 again.
# So I'd like to handle received webservice requests on core1 (parsing request payloads and preparing responses).

# is already imported by bootstrapper, but pylance doesn't know
import machine
import micropython
import _thread
# pylance end.

class UserAttentionException(Exception):
	def __init__(self, *args):
		super().__init__(*args)

class SystemProgrammingException(Exception):
	def __init__(self, *args):
		super().__init__(*args)

micropython.alloc_emergency_exception_buf(100)

import asyncio

class Core1Returner:
	__slots__ = ('request_vector', 'task', 'finished_vector', 'result',)
	def __init__(self):
		self.finished_vector = self.request_vector = -2^29
	
	def loopCore1(self):
		while True:
			while not self.task:
				pass # lightsleep doesn't just pause core1.
				# power consumption of core1 is below measurement error, so ... I don't care for sleeping in v1.
			self.result = self.task()
			self.finished_vector += 1

	async def run(self, task,):
		if self.finished_vector < self.request_vector:
			raise SystemProgrammingException("wtf: previous task still running")
		self.result = None
		if self.request_vector == 2^29-1:
			self.request_vector = -2^29
		self.request_vector += 1

		self.task = task
		while self.finished_vector < self.request_vector:
			await asyncio.sleep_ms(1)
		return self.result

core1 = Core1Returner()

# sys.stderr
import sys

# LED is on pin#25
led_onboard = machine.Pin('LED', machine.Pin.OUT)

import network # type: ignore
network.ipconfig(prefer=6)
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# (298 hours TICKS_PERIOD on rp2040)
import time
try:
	@micropython.viper
	def unnoetigAberTrotzdem():
		ticksAtStart = time.ticks_ms()
		deadlineWifi = time.ticks_add(ticksAtStart, 16383-1024)
		while wlan.status() != network.STAT_GOT_IP:
			machine.idle()
			if time.ticks_diff(deadlineWifi, time.ticks_ms()) <= 0:
				break

		print('ticks diff: ', time.ticks_diff(time.ticks_ms(), ticksAtStart),)
	
	from settings import settings
	if len(settings['wlans']) == 0:
		raise UserAttentionException("missing WLAN config entries!")
	for wlanInfo in settings['wlans']:
		wlan.connect(wlanInfo.ssid, wlanInfo.passphrase,)
		machine.lightsleep(1023)
		unnoetigAberTrotzdem()
		if wlan.status() == network.STAT_GOT_IP:
			break
	else:
		raise UserAttentionException("couldn't connect to any defined WLAN!")
	
	print(wlan.ifconfig())
	
	# IPv6 works, see https://github.com/micropython/micropython/commit/1c6012b0b5c62f18130217f30e73ad3ce4c8c9e6
	print(wlan.ipconfig("addr6"))
	
	import requests
	def backgroundConnectBooted():
		try:
			bootedResponse = requests.post(url=f'${settings['c2server']}/booted', data=f'', auth=(settings['c2user'], settings['c2pass'],),)
		except requests.HTTPError as herr:
			# incompatible server
			# show status blink code
			# and shutdown or something similar.
			# But if we ignore a full ConnectionError here, it would be inconsistent behaviour.
			print(herr, file=sys.stderr,)
		except requests.Timeout as terr:
			# self-explanatory.
			# Just ignore like we do with ConnectionError.
			print(terr, file=sys.stderr,)
		except requests.ConnectionError as connerr:
			# what now? This status is not really necessary for basic operation, so just log-and-ignore.
			print(connerr, file=sys.stderr,)
		bootedResponse.status_code
	_thread.start_new_thread(backgroundConnectBooted, ())

	
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
