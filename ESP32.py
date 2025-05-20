import machine
from sdcard import SDCard
import uos
import ntptime
import network                            
import utime
import usocket
import re

UART_ID = 2
UART_TX_PIN = 17
UART_RX_PIN = 16
UART_BAUD_RATE = 115200
WORD_TO_REPORT = 'Sujeto'

SPI_ID = 1
SPI_MOSI_PIN = 23
SPI_MISO_PIN = 19
SPI_SCK_PIN = 18
SPI_CS_PIN = 5
SPI_CLOCK_RATE = 1000000

CLIENT_SSID = "INFINITUM79CE"
CLIENT_PWD = "uX7PEv7w0I"

AP_SSID = 'Ratitas'
AP_PWD = '12345678'

START_DATE = ''
WORD_TO_REPORT = 'Sujeto'
FILES_NAME = ''
REFERENCE_WRITE, LAST_WRITE, INIT_TIME, DATA_WRITEN = '', '', '', ''

ERRHDR = 'HTTP/1.1 {0} {1}\r\nServer: ESP32\r\nContent-Length: {2}\r\n'
ERRHDR+= 'Connection: Close\r\nContent-Type: text/html; charset=iso-8859-1\r\n\r\n'
ERRHDR+= '<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">\r\n'
ERRHDR+= '<html><head><title>{0} {1}</title></head>'
ERRHDR+= '<body><h1>{1}</h1></body></html>'
ERR404 = ERRHDR.format(404, 'Not Found', '{0}')
ERR404 = ERR404.format(len(ERR404) + 3)
ERR500 = ERRHDR.format(500, 'Internal Server Error', '{0}')
ERR500 = ERR500.format(len(ERR500) + 3)

class webServer:
    def __init__(self, client_ssid: str, client_password: str, ap_ssid: str, ap_password: str):
        self.client_ssid = client_ssid 
        self.client_psw = client_password
        self.ap_ssid = ap_ssid
        self.ap_psw = ap_password
        self.sta_if = None
        self.s_web = None
        self.nic = None
    #end def
        
    def connect_to_client(self):
        self.sta_if = network.WLAN(network.STA_IF)
        if not self.sta_if.isconnected():
            self.sta_if.active(True)
            self.sta_if.connect(self.client_ssid, self.client_psw)
            while not self.sta_if.isconnected():
                pass
        utime.sleep(0.5)
    #end def
    
    def disconnect_from_client(self):
        if self.sta_if.isconnected():
            self.sta_if.disconnect()
            self.sta_if.active(False)
    #end def
    
    def setup_wifi(self):
        self.nic = network.WLAN(network.AP_IF)
        self.nic.active(False)
        self.nic.active(True)
        self.nic.config(
            ssid = self.ap_ssid,
            security = network.AUTH_WPA2_PSK,
            key = self.ap_psw
        )
        self.nic.ifconfig(('192.168.1.1', '255.255.255.0','192.168.1.1','192.168.1.1'))
        network.hostname('ESP32')
    #end def
    
    def setup_sockets(self):
        while not self.nic.active():
            utime.sleep(0.25)
        print('AP initialized successfully')
        self.s_web = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
        ip = self.nic.ifconfig()[0]
        self.s_web.bind( (ip, 80) )
        self.s_web.listen()
        print(f'Listening on {ip}:80')
    #end def
    
    def serve_web(self):
        cnn, addr = self.s_web.accept()
        request = cnn.recv(1024).decode('utf-8')
        try:
            file = self.get_file_from_request(request)
            payload = self.get_payload(file)
            if not payload:
                cnn.send(ERR404)
            else:
                if file == '/index.html':
                    payload = payload.format(INIT_TIME, DATA_WRITEN, LAST_WRITE)
                cnn.send(payload)
        except Exception as e:
            import sys
            sys.pint_exception(e)
            cnn.send(ERR500)
        finally:
            cnn.close()
    #end def
    
    def get_file_from_request(self, request):
        if not request.startswith('GET /'):
            return None
        file = request.split(' ', 3)[1]
        if file in ['/', '/index.htm']:
            file = '/index.html'
        return file
    #end def
    
    def get_payload(self, file):
        try:
            with open(file, 'r') as f:
                payload = f.read()
            return payload
        except:
            return None
    #end def
#end class

class Communications:
    def __init__(self):
        self.uart = None
        self.uart_tx_pin = None
        self.uart_rx_pin = None
        self.spi = None
        self.spi_mosi_pin = None
        self.spi_miso_pin = None
        self.spi_sck_pin = None
        self.spi_cs_pin = None
    #end def
    
    def uart_init(self, id: int, rx_pin: int, tx_pin: int, baud_rate: int):
        self.uart_rx_pin = machine.Pin(rx_pin, machine.Pin.IN)
        self.uart_tx_pin = machine.Pin(tx_pin, machine.Pin.OUT)
        self.uart = machine.UART(id, baudrate = baud_rate, tx = self.uart_tx_pin, rx  = self.uart_rx_pin, timeout = 1, timeout_char=1)
        self.uart_rx_pin.irq(handler=lambda pin: self.uart_handler(pin), trigger = machine.Pin.IRQ_FALLING)
    #end def
    
    def uart_handler(self, pin):
        line = self.uart.readline()
        if line != None:
            data = self.decode_and_process_line(line)
            if data != 'Error':
                self.sdcard_write(data)
    #end def
        
    def spi_init(self, id: int, clk_rate: int, mosi_pin: int, miso_pin: int, sck_pin: int, cs_pin: int):
        self.spi_mosi_pin = machine.Pin(mosi_pin)
        self.spi_miso_pin = machine.Pin(miso_pin)
        self.spi_sck_pin = machine.Pin(sck_pin)
        self.spi_cs_pin = machine.Pin(cs_pin, machine.Pin.OUT, value = 1)
        self.spi = machine.SPI(id, baudrate = clk_rate, polarity = 0, phase = 0, bits = 8, firstbit = machine.SPI.MSB, sck = self.spi_sck_pin, mosi = self.spi_mosi_pin, miso = self.spi_miso_pin)
    #end def
    
    def sdcard_init(self):
        sd = SDCard(self.spi, self.spi_cs_pin)
        vfs = uos.VfsFat(sd)
        uos.mount(vfs, "/sd")
    #end def
    
    def sdcard_write(self, data: dict):
        import ujson
        global LAST_WRITE, DATA_WRITEN, REFERENCE_WRITE
        LAST_WRITE = self.get_iso_utc()
        #info = f'Start time: {REFERENCE_WRITE}. End time: {LAST_WRITE}'
        #info += str(data)
        #print(info)
        json_entry = {
            "interval": {
              "start": REFERENCE_WRITE,
              "end": LAST_WRITE  
            },
            "subjects": data
        }
        print(json_entry)
        try:
            with open(f"/sd/{FILES_NAME}.json", "a") as file:
                #file.write(f'{info}\n')
                ujson.dump(json_entry, file)
                file.write('\n')
        except Exception as e:
            print('Error writing json: ', e)
        REFERENCE_WRITE = LAST_WRITE
        DATA_WRITEN = data
    #end def
    
    def decode_and_process_line(self, line: str):
        try:
            keys = []
            line = line.decode('utf-8')
            line = line.strip()
            data = line.split(',')
            i = 1
            for elements in data:
                keys.append(f'{WORD_TO_REPORT} {i}')
                i += 1
            values = self.convert_data(data)
            dicti = self.build_dictionary(keys, values)
            return dicti
        except UnicodeError:
            print('cannot decode')
            return 'Error'
    #end def
            
    def build_dictionary(self, keys, values):
        return dict(zip(keys, values))
    #end def

    def convert_data(self, data: list):
        data_converted = []
        for time in data:
            time = float(time)
            hours = int(time // 3600)
            minutes = int((time % 3600) // 60)
            seconds = int(time % 60)
            miliseconds = int((time - int(time)) * 1000)
            data_converted.append(f'{hours}h {minutes}m {seconds}s {miliseconds} ms')
        return data_converted
    #end def
    
    def set_time(self):
        ntptime.settime()
        (year, month, mday, weekday, hour, minute, second, milisecond) = machine.RTC().datetime()
    #end def
    
    def get_date(self):
        tup = machine.RTC().datetime()
        date = str(tup[0]) + '-' + str(tup[1]) + '-' + str(tup[2])
        return date
    #end def
    
    def get_iso_utc(self):
        year, month, mday, weekday, hour, minute, second, ms = machine.RTC().datetime()
        return f"{year:04d}-{month:02d}-{mday:02d}T{hour:02d}:{minute:02d}:{second:02d}Z"
#end class


def main():
    global START_DATE, FILES_NAME, INIT_TIME, REFERENCE_WRITE
    comm = Communications()
    server = webServer(client_ssid=CLIENT_SSID, client_password=CLIENT_PWD, ap_ssid=AP_SSID, ap_password=AP_PWD)
    
    server.connect_to_client()
    comm.set_time()
    REFERENCE_WRITE = comm.get_iso_utc()
    START_DATE = comm.get_date()
    
    utime.sleep(0.5)
    server.disconnect_from_client()
    
    comm.uart_init(id = UART_ID, rx_pin=UART_RX_PIN, tx_pin=UART_TX_PIN, baud_rate= UART_BAUD_RATE)
    comm.spi_init(id = SPI_ID, clk_rate=SPI_CLOCK_RATE, mosi_pin=SPI_MOSI_PIN, miso_pin=SPI_MISO_PIN, sck_pin=SPI_SCK_PIN, cs_pin=SPI_CS_PIN)
    comm.sdcard_init()

    FILES_NAME = START_DATE
    INIT_TIME = REFERENCE_WRITE
    
    try:
        open(f"/sd/{FILES_NAME}.json", "x")
    except:
        pass
    server.setup_wifi()
    server.setup_sockets()
    while True:
        server.serve_web()
    
    

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('--- Caught Exception ---')
        import sys
        sys.print_exception(e)
        print('----------------------------')