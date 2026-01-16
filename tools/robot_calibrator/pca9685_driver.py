"""
PCA9685 Driver via Firmata I2C
Standalone driver for PCA9685 16-channel PWM controller.
"""

import time
from pyfirmata import Arduino, util

# PCA9685 Register Addresses
PCA9685_ADDRESS = 0x40
MODE1 = 0x00
MODE2 = 0x01
PRE_SCALE = 0xFE
LED0_ON_L = 0x06

# MODE1 bits
SLEEP = 0x10
ALLCALL = 0x01
RESTART = 0x80

# Servo pulse width constants (for 50Hz)
SERVO_MIN_PULSE = 150   # ~0.5ms pulse
SERVO_MAX_PULSE = 600   # ~2.5ms pulse


class PCA9685Driver:
    """
    PCA9685 PWM Driver using Firmata I2C protocol.
    """

    def __init__(self, address=PCA9685_ADDRESS):
        self.address = address
        self.board = None
        self._connected = False

    def connect(self, port):
        """
        Connect to Arduino board via Firmata.

        Args:
            port: COM port string (e.g., 'COM3')

        Returns:
            bool: True if connection successful
        """
        try:
            self.board = Arduino(port)

            # Start iterator thread for reading data
            it = util.Iterator(self.board)
            it.start()

            # Give board time to initialize
            time.sleep(0.5)

            # Configure I2C
            self._configure_i2c()

            # Initialize PCA9685
            self._init_pca9685()

            self._connected = True
            return True

        except Exception as e:
            print(f"Connection failed: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from Arduino board."""
        if self.board:
            self.release_all()
            self.board.exit()
            self.board = None
        self._connected = False

    def is_connected(self):
        """Check if board is connected."""
        return self._connected

    def _configure_i2c(self):
        """Configure I2C on Firmata."""
        # I2C_CONFIG command
        # Sysex: 0x78, delay_lsb, delay_msb
        self.board.send_sysex(0x78, [0, 0])
        time.sleep(0.1)

    def _init_pca9685(self):
        """Initialize PCA9685 for servo control."""
        # Reset MODE1
        self._write_register(MODE1, 0x00)
        time.sleep(0.005)

        # Set PWM frequency to 50Hz (for servos)
        self._set_pwm_freq(50)

    def _set_pwm_freq(self, freq_hz):
        """
        Set PWM frequency.

        Args:
            freq_hz: Frequency in Hz (typically 50 for servos)
        """
        # Calculate prescale value
        # prescale = round(25MHz / (4096 * freq)) - 1
        prescale = int(round(25000000.0 / (4096.0 * freq_hz)) - 1)

        # Read current MODE1
        old_mode = 0x00  # Assume default

        # Enter sleep mode to change prescale
        self._write_register(MODE1, (old_mode & 0x7F) | SLEEP)
        time.sleep(0.005)

        # Set prescale
        self._write_register(PRE_SCALE, prescale)

        # Restore MODE1 and restart
        self._write_register(MODE1, old_mode)
        time.sleep(0.005)

        # Enable auto-increment
        self._write_register(MODE1, old_mode | RESTART)
        time.sleep(0.005)

    def _write_register(self, reg, value):
        """
        Write a single byte to PCA9685 register via I2C.

        Args:
            reg: Register address
            value: Byte value to write
        """
        # I2C_REQUEST: 0x76
        # Format: address, mode, reg, value
        # mode: 0b00000000 = write (7-bit address mode)
        data = [
            self.address,
            0x00,  # Write mode
            reg & 0x7F,
            value & 0x7F,
            (reg >> 7) & 0x7F,
            (value >> 7) & 0x7F
        ]
        self.board.send_sysex(0x76, data)
        time.sleep(0.001)

    def set_pwm(self, channel, on, off):
        """
        Set PWM for a specific channel.

        Args:
            channel: PCA9685 channel (0-15)
            on: ON time (0-4095)
            off: OFF time (0-4095)
        """
        if not self._connected:
            return

        # Calculate register address for this channel
        reg_base = LED0_ON_L + 4 * channel

        # Write all 4 bytes
        self._write_register(reg_base, on & 0xFF)
        self._write_register(reg_base + 1, (on >> 8) & 0x0F)
        self._write_register(reg_base + 2, off & 0xFF)
        self._write_register(reg_base + 3, (off >> 8) & 0x0F)

    def set_servo_angle(self, channel, angle):
        """
        Set servo angle for a specific channel.

        Args:
            channel: PCA9685 channel (0-15)
            angle: Angle in degrees (0-180)
        """
        if not self._connected:
            return

        # Clamp angle
        angle = max(0, min(180, angle))

        # Map angle to pulse width
        pulse = int(SERVO_MIN_PULSE + (angle / 180.0) * (SERVO_MAX_PULSE - SERVO_MIN_PULSE))

        # Set PWM (ON at 0, OFF at pulse)
        self.set_pwm(channel, 0, pulse)

    def release_channel(self, channel):
        """
        Release a specific channel (stop PWM output).

        Args:
            channel: PCA9685 channel (0-15)
        """
        if not self._connected:
            return

        # Set full OFF (bit 4 of OFF_H)
        reg_base = LED0_ON_L + 4 * channel
        self._write_register(reg_base + 3, 0x10)

    def release_all(self):
        """Release all channels (E-STOP function)."""
        for ch in range(16):
            self.release_channel(ch)


# Test code
if __name__ == "__main__":
    import serial.tools.list_ports

    print("Available COM ports:")
    ports = serial.tools.list_ports.comports()
    for port in ports:
        print(f"  {port.device}: {port.description}")

    if ports:
        driver = PCA9685Driver()
        test_port = ports[0].device
        print(f"\nTesting connection to {test_port}...")

        if driver.connect(test_port):
            print("Connected!")
            print("Moving servo on channel 0 to 90 degrees...")
            driver.set_servo_angle(0, 90)
            time.sleep(1)
            print("Releasing all channels...")
            driver.release_all()
            driver.disconnect()
            print("Done.")
        else:
            print("Connection failed.")
