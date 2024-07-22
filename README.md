# Project Overview
This project uses the Time-to-flight (VL53L0X) sensor to detect presence. It is base on the tutorial from [MCU Application Lab](https://www.youtube.com/watch?v=VumcBR-MNf0&t=22s&ab_channel=MCUApplicationLab) and it uses the ST API and makes them compatible with SDK.
So far this project works with two TOF sensors connected at the same I2C bus via an I2C multiplexer (TCA9548A). All components are connected to a [DualMCU](https://github.com/UNIT-Electronics/DualMCU) which combines a RP2040 and an ESP32.

## Tasks Handled by the RP2040

The pico_vl52l0x.c performs the following tasks:
* Initializes I2C1 and each sensor
* Starts the measurement process. Each time a sensor detects something it adds a time differential to a detection interval.
* After a certain period it sends the respective interval via UART.

## Tasks Handled by the ESP32

The ESP32.py performs the following tasks:
* Connects to internet to run a RTC with the current local time
* Creates a web server to monitor the state of the program easier
* Read the UART line using a TX interrupt and decodes it
* Writes the information from each sensor, including the measuring interval, to an SD card.

The information written to the SD card is the same displayed on the web page. The sdcard.py code was obtained from [micropython-lib](https://github.com/micropython/micropython-lib/blob/master/micropython/drivers/storage/sdcard/sdcard.py)

# Future enhancements
 
In the future it will support eight seensors (four on I2C0 and four on I2C1) using the RP2040's cores.
