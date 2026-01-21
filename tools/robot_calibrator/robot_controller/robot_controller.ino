/*
 * Robot Controller Arduino Sketch (Pass-Through Mode)
 * Controls PCA9685 PWM driver via serial commands
 * 
 * Protocol:
 *   P              : Ping (Response: PONG)
 *   S <ch> <angle> : Set Servo angle (legacy, 0-180)
 *   W <ch> <us>    : Write Microseconds directly (500-2500)
 *   R <ch>         : Release single servo
 *   X              : Release all servos
 * 
 * NOTE: Uses non-blocking serial parser to avoid freezing.
 * NOTE: Pass-Through mode - Python calculates pulse, Arduino executes.
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// PCA9685 driver
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// PWM Constants
#define PWM_FREQ 50           // 50Hz = 20ms period
#define PWM_RESOLUTION 4096   // 12-bit
#define PERIOD_US 20000       // 20ms in microseconds

// Safety limits for pulse width (microseconds)
#define PULSE_MIN 500
#define PULSE_MAX 2500

// Serial Buffer
String inputString = "";
boolean stringComplete = false;

void setup() {
    Serial.begin(115200);
    Serial.setTimeout(10);
    
    while (!Serial) { ; } // Wait for Leonardo
    
    pwm.begin();
    pwm.setOscillatorFrequency(27000000);
    pwm.setPWMFreq(PWM_FREQ);
    
    inputString.reserve(50);
    
    delay(10);
}

void loop() {
    // 1. Non-blocking Serial Reading
    while (Serial.available()) {
        char inChar = (char)Serial.read();
        
        if (inChar == '\n') {
            stringComplete = true;
        } else if (inChar == '\r') {
            // Ignore CR
        } else {
            inputString += inChar;
        }
    }
    
    // 2. Process Command when line is complete
    if (stringComplete) {
        processCommand(inputString);
        inputString = "";
        stringComplete = false;
    }
}

void processCommand(String cmd) {
    if (cmd.length() == 0) return;
    
    char type = cmd.charAt(0);
    
    switch (type) {
        case 'P': // Ping
            Serial.println("PONG");
            break;
            
        case 'S': { // Legacy: Set Servo angle (0-180)
            int ch, angle;
            if (sscanf(cmd.c_str() + 1, "%d %d", &ch, &angle) == 2) {
                // Convert angle to microseconds (legacy support)
                angle = constrain(angle, 0, 180);
                int us = map(angle, 0, 180, PULSE_MIN, PULSE_MAX);
                writeMicroseconds(ch, us);
                Serial.println("OK");
            } else {
                Serial.println("ERR_PARSE");
            }
            break;
        }
        
        case 'W': { // Write Microseconds: W 0 1500
            int ch, us;
            if (sscanf(cmd.c_str() + 1, "%d %d", &ch, &us) == 2) {
                writeMicroseconds(ch, us);
                Serial.println("OK");
            } else {
                Serial.println("ERR_PARSE");
            }
            break;
        }
        
        case 'R': { // Release: R 0
            int ch;
            if (sscanf(cmd.c_str() + 1, "%d", &ch) == 1) {
                ch = constrain(ch, 0, 15);
                pwm.setPWM(ch, 0, 0);
                Serial.println("OK");
            }
            break;
        }
        
        case 'X': // Emergency Stop
            for (int i = 0; i < 16; i++) {
                pwm.setPWM(i, 0, 0);
            }
            Serial.println("OK");
            break;
            
        default:
            Serial.println("ERR_CMD");
            break;
    }
}

void writeMicroseconds(int ch, int us) {
    // Safety: Clamp channel and pulse width
    ch = constrain(ch, 0, 15);
    us = constrain(us, PULSE_MIN, PULSE_MAX);
    
    // Convert microseconds to PWM ticks
    // Formula: ticks = (us / period_us) * resolution
    // = (us * 4096) / 20000
    uint16_t ticks = (uint32_t)us * PWM_RESOLUTION / PERIOD_US;
    
    pwm.setPWM(ch, 0, ticks);
}

