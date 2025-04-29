# Project Overview
This project uses the Time-to-flight (VL53L0X) sensor to detect presence. It is base on the tutorial from [MCU Application Lab](https://www.youtube.com/watch?v=VumcBR-MNf0&t=22s&ab_channel=MCUApplicationLab) and it uses the ST API and makes them compatible with SDK.
So far this project works with two TOF sensors connected at the same I2C bus via an I2C multiplexer (TCA9548A). All components are connected to a [DualMCU](https://github.com/UNIT-Electronics/DualMCU) which combines a RP2040 and an ESP32.

### Tasks Handled by the RP2040

The pico_vl52l0x.c performs the following tasks:
* Initializes I2C1 and each sensor
* Starts the measurement process. Each time a sensor detects something it adds a time differential to a detection interval.
* After a certain period it sends the respective interval via UART.

### Tasks Handled by the ESP32

The ESP32.py performs the following tasks:
* Connects to internet to run a RTC with the current local time
* Creates a web server to monitor the state of the program easier
* Read the UART line using a TX interrupt and decodes it
* Writes the information from each sensor, including the measuring interval, to an SD card.

The information written to the SD card is the same displayed on the web page. The sdcard.py code was obtained from [micropython-lib](https://github.com/micropython/micropython-lib/blob/master/micropython/drivers/storage/sdcard/sdcard.py)


# First setup

## PicoSDK

Considering is the first time working with the PicoSDK and a RP2040, is recommended to follow the next steps:

In order to make compatible Windows with some commands, is required to create a Linux environment. For this guide, WSL will be used. Is recommended that, if any issue appears during the steps, check the [Commmon issues](#commond-issues) section
1. Open PowerShell and run `wsl --install`. Once the installation has finished, restart the computer.
2. Open WSL, create and add a password to a default Unix user account.
3. It is recommended to use `sudo apt update && sudo apt upgrade` with the Ubuntu terminal.

Now, the PicoSDK will be installed:
1. Install the tool chain for ARM Cortex M series, with the WSL terminal do:

   `sudo apt install gcc-arm-none-eabi`
   
   Verify the installation with
   
   `arm-none-eabi-gcc --version`
   
2. Install the packages to compile the PicoSDK:
   
   `sudo apt install build-essential git cmake gtkterm`
   
3. Create a directory where all the files will be located. Do:

   `mkdir ~/pico`
   
   `cd ~/pico`
   
4. Clone the pico-sdk git repository:

   `git clone https://github.com/raspberrypi/pico-sdk.git --branch master`
   
   `cd pico-sdk`
   
   `git submodule update --init`
   
   Wait patiently:)

   
5. Clone the pico-examples git repository:
    
   `cd ..`
   
   `git clone https://github.com/raspberrypi/pico-examples.git --branch master`

6. Create a build directory for the example:

   `cd pico-examples`
   
   `mkdir build`
   
   `cd build`
   
7. Set the pico-sdk path:

   `export PICO_SDK_PATH=../../pico-sdk`
   
8. Use **cmake** to build the directory:
    
  `cmake ..`
  
Wait till process ends.

9. Build every c-code examples using **make**. Ensure to be located in **\pico\pico-examples** with the WSL terminal, then do

    `make`

   Inside the pico/pico-example/build directory are all the build projects, inside each of them a .uf2 file is located.

The uf2 file, once uploaded, is automatically programmed to the RP2040, so everytime the RP2040 is powered the program starts to work.

Before continuing with the project itself, is recommended to upload an example code into the RP2040, for example the blink.uf2. To learn how to uploaded, check the [Uploading file into DualMCU](#uploading-files-into-dualmcu)

## ESP32 and Thonny

The ESP32 use Micropython for its programming. If its the first time working with a ESP32 and Micropython, is recommended to follow the next steps: 
1. Install [Python](https://www.python.org/downloads/), during installation mark the checkbox **Add Python to PATH** and continue as always.
2. Open PowerShell and install *esptool* doing:
   
   `pip install esptool`

3. Now, is necesarry to erase the flash on the ESP32. Do:

   `esptool --chip esp32 --port com# erase_flash`

   **Note**: Replace the hash (#) with the COM port where the board is connected. Verify that using the Device Manager.

4. Download the latest version of [Micropython](https://micropython.org/download/ESP32_GENERIC/), check the firmware section and download the .bin file.
5. Move the .bin file into C:\Users\yourUser
6. In PowerShell do
    `esptool --chip esp32 --port com# --baud 460800 write_flash -z 0x1000 ESP32_GENERIC-20250415-v1.25.0.bin`
   **Note:** for any other version, replace the  *ESP32_GENERIC-20250415-v1.25.0.bin* for the downloaded bin file in step 4. As mentioned, replace the hash (#) with the COM port where the board is connected.
8. Install [Thonny](https://thonny.org/)
9. Open the IDE and go to

   Run > Configure interpreter and select MicroPython (ESP32) and the respective USB Serial @ COM  from both dropdown menus. 
   
Everything is ready to work with the ESP32 and RP2040

### Uploading files into DualMCU

   Some microcontrollers, as the RP2040, have a bootloader mode which allow them to be recognized as a USB Mass Storage. 
   1. Press and hold the Boot button on the board.

      ![DualMCU boot](https://github.com/user-attachments/assets/72a25425-98ab-444e-9838-491bb990f8c5)

   2. Without releasing the buttonm, connect the board into the computer.
   3. After a few seconds, the computer will recognize the board as a mass storage device. The device's names should be RPI-RP2 or similar.
   4. Drag and drop or copy and paste the uf2 file into the device. Actomatically the volume should be closed and the program starts.

For the ESP32 

## Commond issues
* If the installation has finished but WSL is not opening, check the following:
   * Verify if `Windows Subsystem for Linux` and `Virtual Machine Platform` are enable.
      1. Go to Control Panel > Programs > Turn Windows features on or off.
      2. Make sure `Windows Subsystem for Linux` and `Virtual Machine Platform` are checked and enabled.
      3. Click on accept and wait till changes are applied.
      4. Restart the computer.
   * Check WSL version
     1. Use ` wsl --list --verbose` to verify the distribution's version. If no distribution is installed, use `wsl.exe --install Ubuntu-24.04` to install Ubuntu.   
* For any problem uploading files into both microcontrollers

# Pico VL53L0X project setup
   


# Future enhancements
 
In the future it will support eight seensors (four on I2C0 and four on I2C1) using the RP2040's cores.

