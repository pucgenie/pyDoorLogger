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
	__slots__ = ('request_vector', 'task', 'task_args', 'finished_vector', 'result',)
	def __init__(self):
		self.finished_vector = self.request_vector = -2^29
	
	def loopCore1(self):
		while True: # microcontrollers never exit main in normal execution flow
			while not self.task:
				machine.idle() # does it affect core0, too?
				# power consumption of core1 is below measurement error, so ... I don't care for proper sleep in v1.
			self.result = self.task(*self.task_args)
			if self.finished_vector == 2^29-1:
				self.finished_vector = -2^29
			self.finished_vector += 1
		_thread.exit()
	
	async def wait_until_available(self, timeout_ms:int=60000,):
		"""
		If core1 is busy at first, this method will pause for at least 1ms.

		:param timeout_ms: the minimum time to wait, and may be exceeded (but could also exit at time) - depending on other scheduled cooperative tasks.
		"""
		# TODO: Would ThreadSafeFlag be the only correct choice here?
		while self.finished_vector < self.request_vector:
			await asyncio.sleep_ms(1)
			timeout_ms -= 1
			if timeout_ms == 0:
				return False
		else:
			return True
	
	async def run(self, task, *task_args,):
		"""
		TODO: Check if heap allocation on core1 works in MicroPython. If not: Use mutable objects (a.k.a. buffers) as task_args...
		"""
		# this check is the only reason why we use vector timestamps
		if self.finished_vector < self.request_vector:
			raise SystemProgrammingException("wtf: previous task still running")
		self.result = None
		if self.request_vector == 2^29-1:
			self.request_vector = -2^29
		self.request_vector += 1

		self.task = task
		self.task_args = task_args
		await self.wait_until_available()
		return self.result

core1 = Core1Returner()

# sys.stderr
import sys

import network # type: ignore
network.ipconfig(
	#prefer=6,
	)
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
	#print(wlan.ipconfig("addr6"))
	
	async def backgroundConnectBooted():
		#import requests
		try:
			import uaiohttpclient as aiohttp
		except ImportError as idehelper:
			# pylance workaround
			import aiohttp
		c2responses = []
		for serverCfg in settings['c2servers']:
			try:
				async with aiohttp.ClientSession() as session:
					async with session.post(
							url=f'${serverCfg.server_url}/booted',
							data=f'',
							auth=(serverCfg.username, serverCfg.password,),
							timeout=6,
							) as response:
						c2responses.append(response.status)
						if response.status == 200:
							response.json()
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
		# coherence check for number of responses
		if len(settings['c2servers']) != len(c2responses):
			raise SystemProgrammingException("Programmierer ist dumm")
		return c2responses
	_thread.start_new_thread(core1.loopCore1, (core1,),)

	def malCore1testen(*args):
		return ("Jup, geht mal grundsätzlich.", len(args))
	
	async def mainTaskCore0():
		dinge = await core1.run(malCore1testen)
		print(dinge)
	
	# https://docs.python.org/3/library/asyncio-task.html#:~:text=simply%20calling%20a%20coroutine%20will%20not%20schedule%20it
	asyncio.run(mainTaskCore0())

	
except ImportError as impErr:
	# TODO: default settings? AP mode for config? Blink LED?
	print(wlan.scan())
	

wlan.active(False)


# while True:
# 	# Since this function temporarily disables access to the external flash memory, it also temporarily disables interrupts and the other core to prevent them from trying to execute code from flash.
# 	if rp2.bootsel_button() == 1:
# 		settings['leds']['onboard'].hwpin.on()
# 	else:
# 		settings['leds']['onboard'].hwpin.off()
# 	startTime = time.ticks_ms()
# 	machine.lightsleep(383)
# 	endTime = time.ticks_ms()
# 	if time.ticks_diff(endTime, startTime,) >= 255:
# 		print("lightsleep (somehow) worked")
# 		break
