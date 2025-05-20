/*
Script Name:   pico_vl53l0x.py
Description:   Measuring presence using ToF sensors
Author:        Erick Gómez
Date Created: July 2024
Last Modified: May 2025
Version:       1.0.0

Overview: 

This program runs on a Raspberry Pi Pico and uses two VL53L0X time-of-flight (ToF) sensors, connected through a TCA9548A I2C multiplexer, to detect the presence of subjects based on proximity measurements. The sensors are connected on different channels of the multiplexer and are read sequentially. Each sensor measures distance in millimeters. If an object is detected closer than a defined threshold, the system starts recording the detection time for that sensor. When the object moves away, detection ends and the total duration is accumulated.

The main loop continuously checks for presence and accumulates detection time for each sensor. After a predefined interval (`TIME2SEND`), the detection durations are transmitted via UART to another device (e.g., an ESP32), formatted as text. LEDs connected to GPIOs are used as indicators to show real-time detection status per sensor.

The program is structured to:
- Define constants, pin configurations, and data structures for sensor tracking.
- Initialize I2C communication at 400 kHz on specific GPIOs.
- Configure UART0 for transmitting sensor data at 115200 baud.
- Initialize the VL53L0X sensors and assign their respective MUX channels.
- Use the TCA9548A multiplexer to select the correct channel before each measurement.
- Perform single ranging measurements per sensor and track detection intervals.
- Use onboard LEDs to signal detection state for each sensor.
- Periodically send detection times through UART based on elapsed time.

All timing operations rely on the Raspberry Pi Pico SDK's `absolute_time_t` API to ensure accurate microsecond resolution for measuring presence durations.
*/

#include "stdio.h"
#include "stdlib.h"
#include "string.h"
#include "pico/stdlib.h"
#include "pico/time.h"

#include "vl53l0x_api.h"
#include "vl53l0x_rp2040.h"
#include "pico/multicore.h"

#include "hardware/uart.h"

VL53L0X_RangingMeasurementData_t gRangingData;
VL53L0X_Dev_t gVL53L0XDevice;

// ---------- LED indicators used for testing purposes ----------
#define GREEN_LED_PIN       11 
#define BLUE_LED_PIN        14

// ---------- I2C and UART configuration parameters ----------
#define SDA_PIN_1           2
#define SCL_PIN_1           3
#define I2C_SPEED           400                 // I2C speed in kHz

#define UART_TX_PIN         0
#define UART_RX_PIN         1                   // UART receive pin (not used in this project)

#define UART_ID             uart0               // UART instance used (for the DUALMCU, uart0 is connected with the ESP32 chip)
#define BAUD_RATE           115200 
#define DATA_BITS           8                   // Number of data bits
#define STOP_BITS           1                   // Number of stop bits
#define PARITY              UART_PARITY_NONE    // No parity bit

// ---------- Program-specific definitions ----------
#define NUM_SENSORS          2                  // Total number of sensors connected
#define THRESHOLD            15                 // Distance threshold in millimeters for detection

#define TIME2SEND            60                // Time interval (in seconds) to send detection data via UART

#define MUX_ADDR            _u(0x70)            // I2C address of the TCA9548A multiplexer 

int leds[] = {GREEN_LED_PIN, BLUE_LED_PIN};     // LED array used to indicate detection status for each sensor

// ---------- Structure to store sensor-related data ----------
typedef struct {
    uint16_t distance;                  // Measured distance from the sensor
    absolute_time_t start_detection;    // Time when detection started
    absolute_time_t last_measurement;   // Time of the last measurement taken
    int64_t detection_interval;         // Cumulative duration where detection was active
    bool is_detecting;                  // Flag indicating whether the sensor is currently detecting something
    uint8_t mux_channel;                // Multiplexer channel assigned to the sensor
} Sensor;

Sensor sensors[NUM_SENSORS]; // Array of sensor structures, one for each connected sensor

VL53L0X_Error singleRanging(VL53L0X_Dev_t *pDevice, uint16_t *MeasuredData) {
    VL53L0X_Error Status;
    Status = VL53L0X_SingleRanging(pDevice, MeasuredData);
    /* 
    if (Status == VL53L0X_ERROR_NONE) 
        printf("Measured distance: %d\n",*MeasuredData);
    else 
        printf("measure error\n");
    */
    return Status;
}

VL53L0X_Error continuousRanging(VL53L0X_Dev_t *pDevice, uint16_t *ContinuousData, uint16_t *validCount) {
    uint32_t sum=0;
    uint16_t MeasuredData=0;
    VL53L0X_Error Status;
    sum=0;
    Status = VL53L0X_ContinuousRanging(pDevice, ContinuousData, 16, validCount);
    for (int i = 0; i < *validCount; i++) {
        sum += ContinuousData[i];
    }
    if (*validCount > 0) {
        MeasuredData = sum/(*validCount);
        printf("Average continuous measured distance: %4d,\n" 
                "\tmeasuerd count: %d, valid count: %d\n\n",MeasuredData, 16, *validCount);
    }    else {  
        printf("measure error\n");
    }
    return Status;

}
// ---------- Funtions that initializes I2C and UART ----------
void I2C1_init(){
    i2c_init(i2c1, I2C_SPEED * 1000); // Initialize I2C1 with the defined speed (converted to Hz)
    // Configure SDA and SCL pins for I2C functionality and enable internal pull-up resistors
    gpio_set_function(SDA_PIN_1, GPIO_FUNC_I2C); 
    gpio_set_function(SCL_PIN_1, GPIO_FUNC_I2C);
    gpio_pull_up(SDA_PIN_1);
    gpio_pull_up(SCL_PIN_1);
}

void UART_init(){
    uart_init(UART_ID, BAUD_RATE); // Initialize UART with the specified baud rate
    gpio_set_function(UART_TX_PIN, GPIO_FUNC_UART); // Configure the UART TX pin; this project only transmits data to the ESP32
}

// ---------- Function that selects a channel on the TCA9548A I2C multiplexer ----------
void select_mux_channel(uint8_t channel) {
    uint8_t data = 1 << channel; // Create a bitmask to select the desired channel
    i2c_write_blocking(i2c1, MUX_ADDR, &data, 1, false); // Send the channel selection command via I2C
}

// ---------- funtion that initialize each TOF sensor -----------
void vl53l0x_init_all(VL53L0X_Dev_t *pDevice){
    int muxes[] = {2,7};  // Define the I2C multiplexer channels where each sensor is connected. In this version, two sensors are used and are connected to channels 2 and 7
    for(int i = 0; i < NUM_SENSORS; i++){ 
        sensors[i].mux_channel = muxes[i]; // Assign the corresponding mux channel to each sensor's configuration
        select_mux_channel(sensors[i].mux_channel); // Select the active multiplexer channel
        VL53L0X_dev_i2c_initialise(pDevice, i2c1, SDA_PIN_1, SCL_PIN_1, I2C_SPEED, VL53L0X_HIGH_SPEED);  // Initialize the sensor with I2C1 interface using the defined SDA and SCL pins, at high-speed mode
        sensors[i].detection_interval = 0; // Reset detection interval to 0 at startup 
        sensors[i].is_detecting = false; // Set initial detection state to false (no detection)
        sensors[i].last_measurement = get_absolute_time();  // Store current time as initial timestamp for detection tracking
    }
}

void process_sensor(VL53L0X_Dev_t *pDevice, Sensor *sensor, int led_pin) {
    select_mux_channel(sensor->mux_channel); // Select the appropriate channel on the I2C multiplexer for this sensor
    VL53L0X_Error status = singleRanging(pDevice, &sensor->distance); // Perform a single distance measurement and store the result
    absolute_time_t current_time = get_absolute_time(); // Get the current time in microseconds
    int64_t time_diff = absolute_time_diff_us(sensor->last_measurement, current_time); // Calculate the time since the last measurement

    if (status == VL53L0X_ERROR_NONE) {
        if (sensor->distance < THRESHOLD * 10) { // If the measured distance is below the threshold
            sensor->detection_interval += time_diff; // Accumulate the duration of detected presence
            if (!sensor->is_detecting) {
                sensor->is_detecting = true; // Mark the sensor as currently detecting
                gpio_put(led_pin, 1); // Turn on the corresponding LED
            }
        } else if (sensor->is_detecting) {
            sensor->is_detecting = false; // Mark the sensor as no longer detecting
            gpio_put(led_pin, 0); // Turn off the corresponding LED
        }
    }
    sensor->last_measurement = current_time; // Update the timestamp of the last measurement
}

//----------- funtion that handles the measurement ----------
void measure_detection(VL53L0X_Dev_t *pDevice){
    for(int i = 0; i< NUM_SENSORS; i++){
        process_sensor(pDevice, &sensors[i], leds[i]);
    }
}

size_t get_csv_buffer_size(){
    int digits_before_dot = 1;  
    int digits_after_dot = 4; //due to %.4f format  
    int decimal_point = 1;
    int new_line_char = 1;
    int null_termination = 1;
    int comma = 1;
    uint32_t temp = TIME2SEND;
    while(temp >= 10){
        temp /= 10;
        digits_before_dot++;
    }
    int per_sensor = digits_before_dot + decimal_point + digits_after_dot + comma;
    int last_sensor = digits_before_dot + decimal_point + digits_after_dot;
    size_t total = per_sensor * (NUM_SENSORS - 1) + last_sensor + new_line_char + null_termination;

    return total;
}

void build_csv(char *buffer, size_t buffer_size) {
    size_t offset = 0;

    for (int i = 0; i < NUM_SENSORS; i++) {
        float seconds = sensors[i].detection_interval / 1000000.0;

        // Write formatted time into buffer directly at offset
        int written;
        if (i < NUM_SENSORS - 1)
            written = snprintf(buffer + offset, buffer_size - offset, "%.4f,", seconds);
        else
            written = snprintf(buffer + offset, buffer_size - offset, "%.4f", seconds);
        // Check for overflow or snprintf error
        if (written < 0 || (size_t)written >= buffer_size - offset)
            break;
        offset += written;
        sensors[i].detection_interval = 0; // Reset after reading
    }
    // Append newline if there is still space
    if (offset + 1 < buffer_size) {
        buffer[offset++] = '\n';
        buffer[offset] = '\0'; // Null-terminate
    }
}

void send_detection_times(){
    static absolute_time_t reference2write = {0}; // Timestamp of the last UART transmission
    size_t buffer_size = get_csv_buffer_size();
    char final_output[buffer_size]; // Enough space to store all detection times in CSV format
    // Check if TIME2SEND seconds have passed since the last transmission
    if (absolute_time_diff_us(reference2write, get_absolute_time()) >= TIME2SEND * 1000000) {
        build_csv(final_output, buffer_size); // Generate CSV string of detection intervals
        uart_puts(UART_ID, final_output); // Send the result over UART
        reference2write = get_absolute_time(); // Update the timestamp for the next scheduled transmission
    }
}

int main(void){
    VL53L0X_Error Status = VL53L0X_ERROR_NONE;

    VL53L0X_Dev_t *pDevice = &gVL53L0XDevice;   // Create a pointer to the global device structure
    pDevice->I2cDevAddr      =  0x29;           // Default I2C address for VL53L0X sensors
    pDevice->comms_type      =  1;              // Communication type: 1 = I2C
    pDevice->comms_speed_khz =  I2C_SPEED;      // I2C speed in kHz

    stdio_init_all(); // Initialize all standard I/O (needed for printf via USB, etc.)
    
    // Initialize LEDs for visual indication of detection
    gpio_init(leds[0]);
    gpio_init(leds[1]);
    gpio_set_dir_out_masked(1 << leds[0]|1 << leds[1]);  // Set both pins as output using a bitmask

    //continuousRanging(pDevice, continuousRingingValue, &validCount);
    I2C1_init();                // Set up I2C communication
    UART_init();                // Set up UART for sending data
    vl53l0x_init_all(pDevice);  // Initialize all VL53L0X sensors and store their configuration
    // Main loop: continuously measure and report detections
    while(1){ 
        measure_detection(pDevice); // Perform distance measurements and update detection state
        send_detection_times();    // If enough time has passed, send detection intervals over UART
   }
    return 0;
}

