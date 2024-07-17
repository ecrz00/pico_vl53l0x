from machine import Pin, UART, SPI, RTC
import uos
from sdcard import SDCard
import ntptime
import network                            # importa el módulo network
import time

NUM_SENSORS = 2

UART_TX_PIN = Pin(17, Pin.OUT)
UART_RX_PIN = Pin(16, Pin.IN)
BAUD_RATE = 115200

SPI_MOSI_PIN = Pin(23)
SPI_MISO_PIN = Pin(19)
SPI_SCK_PIN = Pin(18)
SPI_CS_PIN = Pin(5, Pin.OUT, value=1) # Assign chip select (CS) pin (and start it high)

uart = None
spi = SPI(1, baudrate=1000000, polarity=0, phase=0,bits=8, firstbit=SPI.MSB, sck = SPI_SCK_PIN, mosi=SPI_MOSI_PIN, miso = SPI_MISO_PIN) # Intialize SPI peripheral (start with 1 MHz)

led_r = Pin(25, Pin.OUT, value = 1)
led_b = Pin(4, Pin.OUT, value = 1)
led_g = Pin(26, Pin.OUT, value = 1)

reference_write, last_write = '', ''

def connect_set_time(SSID, PASSWORD):
	sta_if = network.WLAN(network.STA_IF)
	if not sta_if.isconnected():
		sta_if.active(True)
		sta_if.connect(SSID, PASSWORD)
		while not sta_if.isconnected():
			pass
	ntptime.settime()
	(year, month, mday, weekday, hour, minute, second, milisecond)=RTC().datetime()
	RTC().init((year, month, mday, weekday, hour-6, minute, second, milisecond))
#end def

def get_time():
	tup = RTC().datetime()
	fecha = str(tup[0]) + '/' + str(tup[1]) + '/' + str(tup[2])
	hora  = str(tup[4]) + ':' + str(tup[5]) + ':' + str(tup[6])
	tiempo = f'{fecha},{hora}'
	return tiempo
#end def

def uart_handler(UART_RX_PIN):
	line = uart.readline()
	if line != None:
		line = line.decode('utf-8')
		line = line.strip()
		write(line)
#end def

def uart_init():
	global uart
	uart = UART(2, baudrate=BAUD_RATE, tx=UART_TX_PIN, rx=UART_RX_PIN, timeout=1, timeout_char=1)
	UART_RX_PIN.irq(handler = uart_handler, trigger = Pin.IRQ_FALLING)
#end def

def SDCard_init():
	global spi
	sd = SDCard(spi, SPI_CS_PIN)
	vfs = uos.VfsFat(sd)
	uos.mount(vfs, "/sd")
#end def

def convert_time(seconds):
	hours = int(seconds // 3600)
	minutes = int((seconds % 3600) // 60)
	remaining_seconds = int(seconds % 60)
	miliseconds = int((seconds - int(seconds)) * 1000)
	return hours, minutes, remaining_seconds, miliseconds
#end def

def process_string(string):
	result = []
	elements = string.split('. ')
	for element in elements:
		if element.endswith('.'):
			element = element[:-1]
		rat, time_in_seconds = element.split(': ')
		time_in_seconds = float(time_in_seconds)
		hours, minutes, seconds, miliseconds = convert_time(time_in_seconds)
		new_format = f"{rat}: {hours}h {minutes}m {seconds}s {miliseconds} ms"
		result.append(new_format)
	return '. '.join(result)
#end def

def write(data):
	global reference_write, last_write
	last_write = get_time()
	info = f'Inicio: {reference_write}. Final: {last_write}. '
	info += process_string(data)
	#print(info)
	try:
		with open("/sd/ratitas.txt", "a") as file:
			file.write(f'{info}\n')
	except:
		pass
	reference_write = last_write
#end def

def main():
	global reference_write
	connect_set_time("INFINITUM79CE","uX7PEv7w0I") 
	SDCard_init()
	uart_init()
	try:
		open("/sd/ratitas.txt", "x")
	except:
		pass
	reference_write = get_time()
	while True:
		pass
#end def

if __name__ == '__main__':
	try:
		main()
	except Exception as e:
		led_r.value(0)
		print('--- Caught Exception ---')
		import sys
		sys.print_exception(e)
		print('----------------------------')
