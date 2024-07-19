from machine import Pin, UART, SPI, RTC
import uos
from sdcard import SDCard
import ntptime
import network                            
import utime
import usocket
import re

NUM_SENSORS = 2

UART_TX_PIN = Pin(17, Pin.OUT)
UART_RX_PIN = Pin(16, Pin.IN)
BAUD_RATE = 115200

SPI_MOSI_PIN = Pin(23)
SPI_MISO_PIN = Pin(19)
SPI_SCK_PIN = Pin(18)
SPI_CS_PIN = Pin(5, Pin.OUT, value=1) # Assign chip select (CS) pin (and start it high)

SSID = 'Ratitas'
PASS = '12345678'

ERRHDR = 'HTTP/1.1 {0} {1}\r\nServer: ESP32\r\nContent-Length: {2}\r\n'
ERRHDR+= 'Connection: Close\r\nContent-Type: text/html; charset=iso-8859-1\r\n\r\n'
ERRHDR+= '<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">\r\n'
ERRHDR+= '<html><head><title>{0} {1}</title></head>'
ERRHDR+= '<body><h1>{1}</h1></body></html>'
ERR404 = ERRHDR.format(404, 'Not Found', '{0}')
ERR404 = ERR404.format(len(ERR404) + 3)
ERR500 = ERRHDR.format(500, 'Internal Server Error', '{0}')
ERR500 = ERR500.format(len(ERR500) + 3)

uart = None
nic     = None
s_web   = None

led_r = Pin(25, Pin.OUT, value = 1)
led_b = Pin(4, Pin.OUT, value = 1)
led_g = Pin(26, Pin.OUT, value = 1)

reference_write, last_write, init_time, data_writen= '', '', '', ''

def get_time():
	tup = RTC().datetime()
	fecha = str(tup[0]) + '/' + str(tup[1]) + '/' + str(tup[2])
	hora  = str(tup[4]) + ':' + str(tup[5]) + ':' + str(tup[6])
	tiempo = f'{fecha},{hora}'
	return tiempo
#end def

def connect_set_time(SSID, PASSWORD):
	global init_time
	sta_if = network.WLAN(network.STA_IF)
	if not sta_if.isconnected():
		sta_if.active(True)
		sta_if.connect(SSID, PASSWORD)
		while not sta_if.isconnected():
			pass
	ntptime.settime()
	(year, month, mday, weekday, hour, minute, second, milisecond)=RTC().datetime()
	RTC().init((year, month, mday, weekday, hour-6, minute, second, milisecond))
	init_time = get_time()
	utime.sleep(0.5)
	if sta_if.isconnected():
		sta_if.disconnect()                    
		sta_if.active(False)      
#end def

def decode_line(line):
	try:
		line = line.decode('utf-8')
		line = line.strip()
		return line
	except UnicodeError:
		valid_bytes = bytearray()
		for byte in line:
			try:
				valid_bytes.extend(byte.to_bytes(1, 'big').decode('utf-8').encode('utf-8'))
			except UnicodeError:
				continue
		line = valid_bytes.decode('utf-8')
		line = line.strip()
		sujetos = []
		partes = line.split('. ')
		for parte in partes:
			if 'Sujeto' in parte:
				try:
					dato = parte.split(': ')[1]
					sujetos.append(dato)
				except IndexError:
					pass
		aux = ''
		for i, dato in enumerate(sujetos):
			aux += f'Sujeto {i+1}: {dato}'
			if i < len(sujetos) - 1:
				aux += '. '
		return aux

def uart_handler(UART_RX_PIN):
	line = uart.readline()
	if line != None:
		data = decode_line(line)
		write(data)
#end def

def uart_init():
	global uart, UART_RX_PIN 
	uart = UART(2, baudrate=BAUD_RATE, tx=UART_TX_PIN, rx=UART_RX_PIN, timeout=1, timeout_char=1)
	UART_RX_PIN.irq(handler = uart_handler, trigger = Pin.IRQ_FALLING)
#end def

def SDCard_init():
	spi = SPI(1, baudrate=1000000, polarity=0, phase=0,bits=8, firstbit=SPI.MSB, sck = SPI_SCK_PIN, mosi=SPI_MOSI_PIN, miso = SPI_MISO_PIN)
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
	global reference_write, last_write, data_writen
	last_write = get_time()
	data2convert = process_string(data)
	info = f'Inicio: {reference_write}. Final: {last_write}. '
	info += data2convert
	print(info)
	try:
		with open("/sd/ratitas.txt", "a") as file:
			file.write(f'{info}\n')
	except:
		pass
	reference_write = last_write
	data_writen = data2convert
#end def

def setup_wifi():
	global nic
	nic = network.WLAN(network.AP_IF)
	nic.active(False)
	nic.active(True)
	nic.config(
		ssid=SSID,
		security=network.AUTH_WPA2_PSK,
		key=PASS
	)
	nic.ifconfig(('192.168.1.1', '255.255.255.0', '192.168.1.1', '192.168.1.1'))
	network.hostname('ESP32')
# end def

def setup_sockets():
	global s_web
	while not nic.active():
		utime.sleep(0.25)
	print('AP initialized successfully')
	s_web  = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
	ip  = nic.ifconfig()[0]
	s_web.bind( (ip, 80) )
	s_web.listen()
	print(f'Listening on {ip}:80')
# end def

def serve_web():
    cnn, addr = s_web.accept()
    #print(f'Client connected from { str(addr) }')
    request = cnn.recv(1024).decode('utf-8')
    #print(f'Request: { request.split("\r")[0] }')
    try:
        file = get_file_from_request(request)
        payload = get_payload(file)
        if not payload:
            cnn.send( ERR404 )
        else:
            if file == '/index.html':
                payload = payload.format(init_time, data_writen, last_write)
            cnn.send( payload )
    except Exception as e:
        import sys
        sys.print_exception(e)
        cnn.send( ERR500 )
    cnn.close()
#end def

def get_payload(file):
    try:
        with open(file, 'r') as f:
            payload = f.read()
        return payload
    except:
        return None
#end def

def get_file_from_request(request):
	if not request.startswith('GET /'):
		return None
	file = request.split(' ', 3)[1]
	if file in ['/', '/index.htm']:
		file = '/index.html'
	return file
# end def

def main():
	global reference_write
	connect_set_time("INFINITUM79CE","uX7PEv7w0I") 
	SDCard_init()
	uart_init()
	nic = setup_wifi()
	setup_sockets()
	try:
		open("/sd/ratitas.txt", "x")
	except:
		pass
	reference_write = get_time()
	while True:
		serve_web()
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

