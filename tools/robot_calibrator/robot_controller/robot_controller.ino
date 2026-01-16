/*
 * Robot Controller Arduino Sketch (Non-blocking Version)
 * Controls PCA9685 PWM driver via serial commands
 * 
 * Protocol:
 *   P              : Ping (Response: PONG)
 *   S <ch> <angle> : Set Servo angle
 *   R <ch>         : Release single servo
 *   X              : Release all servos
 * 
 * NOTE: Uses non-blocking serial parser to avoid freezing.
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// PCA9685 driver
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// Servo constants
#define SERVO_MIN  150
#define SERVO_MAX  600
#define SERVO_FREQ 50

// Serial Buffer
String inputString = "";
boolean stringComplete = false;

void setup() {
    Serial.begin(115200);
    // Non-blocking parser doesn't rely on timeout, 
    // but setting it low is good practice just in case.
    Serial.setTimeout(10); 
    
    while (!Serial) { ; } // Wait for Leo
    
    pwm.begin();
    pwm.setOscillatorFrequency(27000000);
    pwm.setPWMFreq(SERVO_FREQ);
    
    // Pre-allocate buffer to avoid fragmentation
    inputString.reserve(50);
    
    delay(10);
}

void loop() {
    // 1. Non-blocking Serial Reading
    while (Serial.available()) {
        char inChar = (char)Serial.read();
        
        if (inChar == '\n') {
            stringComplete = true;
            // Don't append \n to string
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
            
        case 'S': { // Set Servo: S 0 90
            // Parse using sscanf is safer and non-blocking
            // (compared to repeated parseInt calls)
            int ch, angle;
            // Skip first char 'S' and space (index 2)
            if (sscanf(cmd.c_str() + 1, "%d %d", &ch, &angle) == 2) {
                setServo(ch, angle);
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

void setServo(int ch, int angle) {
    ch = constrain(ch, 0, 15);
    angle = constrain(angle, 0, 180);
    int pulse = map(angle, 0, 180, SERVO_MIN, SERVO_MAX);
    pwm.setPWM(ch, 0, pulse);
}
