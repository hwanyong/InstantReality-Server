"""
Serial Driver for Arduino Robot Controller
Uses raw serial commands to control PCA9685 via Arduino.
Protocol:
  S <ch> <angle>  : Set Servo (legacy, 0-180)
  W <ch> <us>     : Write Microseconds (500-2500)
  R <ch>          : Release Servo
  X               : Release All
  P               : Ping (Response: PONG)
"""

import serial
import time
import threading

class SerialDriver:
    """
    Communicates with Arduino sketch via serial port.
    Implements ACK-based flow control.
    """

    def __init__(self):
        self.ser = None
        self._connected = False
        self._lock = threading.Lock()

    def connect(self, port, baudrate=115200):
        """
        Connect to Arduino via serial.
        """
        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino Leonardo reset
            
            # Flush existing data
            self.ser.reset_input_buffer()
            
            # Ping check
            if self._ping():
                self._connected = True
                print(f"Connected to {port}")
                return True
            else:
                self.ser.close()
                return False

        except serial.SerialException as e:
            print(f"Serial connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect serial port."""
        if self.ser and self.ser.is_open:
            self.release_all()
            self.ser.close()
        self.ser = None
        self._connected = False

    def is_connected(self):
        return self._connected

    def _send_command(self, cmd, wait_ack=True):
        """
        Send command string to Arduino and wait for ACK.
        Returns: True if ACK ('OK') received, else False.
        """
        if not self._connected or not self.ser:
            return False
        
        with self._lock:
            try:
                full_cmd = f"{cmd}\n"
                self.ser.write(full_cmd.encode('utf-8'))
                
                if not wait_ack:
                    return True

                # Wait for ACK (OK)
                self.ser.timeout = 0.1 
                response = self.ser.readline().decode().strip()
                self.ser.timeout = 1.0

                if response == "OK":
                    return True
                else:
                    return False
                    
            except Exception as e:
                print(f"Send failed: {e}")
                self.disconnect()
                return False

    def _ping(self):
        """Send Ping command and wait for PONG."""
        if not self.ser:
            return False
            
        try:
            self.ser.write(b"P\n")
            start = time.time()
            while time.time() - start < 2.0:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode().strip()
                    if line == "PONG":
                        return True
                time.sleep(0.01)
            return False
        except Exception:
            return False

    def set_servo_angle(self, channel, angle):
        """
        Set servo angle (legacy mode).
        Returns True if successful (ACK received).
        """
        angle = max(0, min(180, int(angle)))
        return self._send_command(f"S {channel} {angle}", wait_ack=True)

    def write_pulse(self, channel, microseconds):
        """
        Write pulse width directly in microseconds (Pass-Through mode).
        Returns True if successful (ACK received).
        
        Args:
            channel: PCA9685 channel (0-15)
            microseconds: Pulse width in us (500-2500)
        """
        microseconds = max(0, min(3000, int(microseconds)))
        return self._send_command(f"W {channel} {microseconds}", wait_ack=True)

    def release_channel(self, channel):
        """Release specific servo."""
        self._send_command(f"R {channel}", wait_ack=True)

    def release_all(self):
        """Release all servos (E-STOP)."""
        self._send_command("X", wait_ack=True)
