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

#define GREEN_LED_PIN       11 
#define BLUE_LED_PIN        14

#define SDA_PIN_1           2
#define SCL_PIN_1           3
#define I2C_SPEED           400

#define UART_ID             uart0
#define BAUD_RATE           115200
#define DATA_BITS           8
#define STOP_BITS           1
#define PARITY              UART_PARITY_NONE

#define UART_TX_PIN         0
#define UART_RX_PIN         1

#define NUM_SENSORS         2
#define DISTANCE            15

#define TIME2SEND           60          // seconds

#define MUX_ADDR            _u(0x70)

int leds[] = {GREEN_LED_PIN, BLUE_LED_PIN};

typedef struct {
    uint16_t distance;
    absolute_time_t start_detection;
    absolute_time_t last_measurement;
    int64_t detection_interval;
    bool is_detecting;
    uint8_t mux_channel;  // Canal del multiplexor para este sensor
} Sensor;

Sensor sensors[NUM_SENSORS];

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

void I2C1_init(){
    i2c_init(i2c1, 400 * 1000);
    gpio_set_function(SDA_PIN_1, GPIO_FUNC_I2C);
    gpio_set_function(SCL_PIN_1, GPIO_FUNC_I2C);
    gpio_pull_up(SDA_PIN_1);
    gpio_pull_up(SCL_PIN_1);
}

void UART_init(){
    uart_init(UART_ID, BAUD_RATE);
    gpio_set_function(UART_TX_PIN, GPIO_FUNC_UART);
}

void select_mux_channel(uint8_t channel) {
    uint8_t data = 1 << channel;
    i2c_write_blocking(i2c1, MUX_ADDR, &data, 1, false);
}

void vl53l0x_init_all(VL53L0X_Dev_t *pDevice){
    int muxes[] = {2,7};
    for(int i = 0; i < NUM_SENSORS; i++){
        sensors[i].mux_channel = muxes[i];
        select_mux_channel(sensors[i].mux_channel);
        VL53L0X_dev_i2c_initialise(pDevice, i2c1, SDA_PIN_1, SCL_PIN_1, I2C_SPEED, VL53L0X_HIGH_SPEED);
        sensors[i].detection_interval = 0;
        sensors[i].is_detecting = false;
        sensors[i].last_measurement = get_absolute_time();
    }
}

void measure_detection(VL53L0X_Dev_t *pDevice){
    uint16_t measure = 32;
    for(int i = 0; i< NUM_SENSORS; i++){
        select_mux_channel(sensors[i].mux_channel);
        VL53L0X_Error edo = singleRanging(pDevice, &sensors[i].distance);
        absolute_time_t current_time = get_absolute_time();
        int64_t time_diff = absolute_time_diff_us(sensors[i].last_measurement, current_time);
        if (edo == VL53L0X_ERROR_NONE){
            if (sensors[i].distance < DISTANCE*10){
                sensors[i].detection_interval += time_diff;
                if(!sensors[i].is_detecting){
                    sensors[i].is_detecting = true;
                    gpio_put(leds[i], 1);
                }   
            }else if(sensors[i].is_detecting){
                sensors[i].is_detecting = false;
                gpio_put(leds[i], 0);      
            }     
        }
        sensors[i].last_measurement = current_time;
    }
}

void send_detection_times(){
    int size = 50;
    static absolute_time_t reference2write = {0};
    char output[size];
    char final_output[size*NUM_SENSORS];
    if(absolute_time_diff_us(reference2write, get_absolute_time()) >= TIME2SEND*1000000) {
        for (int i = 0; i < NUM_SENSORS; i++) {
            //printf("Sensor %d - Tiempo de detección: %.6f segundos\n", i+1, sensors[i].detection_interval / 1000000.0);
            snprintf(output, size, "Sujeto %d: %.6f. ", i+1, sensors[i].detection_interval / 1000000.0);
            strcat(final_output, output);
            sensors[i].detection_interval = 0; 
        }
        strcat(final_output, "\n");
        uart_puts(UART_ID, final_output);
        reference2write = get_absolute_time();
    }
}

int main(void){
    VL53L0X_Error Status = VL53L0X_ERROR_NONE;

    VL53L0X_Dev_t *pDevice = &gVL53L0XDevice;
    pDevice->I2cDevAddr      =  0x29; 
    pDevice->comms_type      =  1;  
    pDevice->comms_speed_khz =  400;

    uint16_t continuousRingingValue[32];
    uint16_t validCount;
    uint16_t ranging_value=32;

    stdio_init_all();

    gpio_init(leds[0]);
    gpio_init(leds[1]);
    gpio_set_dir_out_masked(1 << leds[0]|1 << leds[1]);

    //continuousRanging(pDevice, continuousRingingValue, &validCount);
    I2C1_init();
    UART_init();
    //send_info();
    vl53l0x_init_all(pDevice);
    while(1){ 
        measure_detection(pDevice);
        send_detection_times();
   }
    return 0;
}