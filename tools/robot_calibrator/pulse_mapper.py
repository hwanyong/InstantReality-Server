"""
Pulse Mapper
Converts physical degrees to virtual degrees for heterogeneous servo motors.
Supports motors with different actuation ranges (180°, 270°, etc.).
"""


class PulseMapper:
    """
    Maps physical target angles to Arduino-compatible virtual angles.
    
    Arduino Assumption:
        The Arduino firmware uses: map(angle, 0, 180, 500, 2500)
        So sending 0 = 500us, 90 = 1500us, 180 = 2500us.
    
    Problem:
        A 270° motor (DS3225) receiving 1500us will rotate to 135° physically,
        not 90° as the user intended.
    
    Solution:
        Calculate the pulse width needed for the target physical angle,
        then reverse-engineer the Arduino input that produces that pulse.
    """
    
    # Arduino's internal mapping constants (assumed fixed in firmware)
    ARDUINO_MIN_ANGLE = 0
    ARDUINO_MAX_ANGLE = 180
    ARDUINO_MIN_PULSE = 500   # us
    ARDUINO_MAX_PULSE = 2500  # us
    
    def __init__(self):
        pass
    
    def physical_to_virtual(self, target_physical_deg, motor_config):
        """
        Convert physical target angle to Arduino virtual angle.
        
        Args:
            target_physical_deg: Desired physical rotation (e.g., 90°)
            motor_config: Dict with 'actuation_range', 'pulse_min', 'pulse_max'
        
        Returns:
            float: Virtual angle (0-180) to send to Arduino
        
        Example:
            DS3225 (270° range), target = 90°
            -> Ratio = 90/270 = 0.333
            -> Target Pulse = 500 + (0.333 * 2000) = 1166us
            -> Virtual Angle = (1166 - 500) * 180 / 2000 = 60°
            -> Send 60 to Arduino, motor rotates to physical 90°
        """
        # Get motor specs (with defaults for 180° motors)
        actuation_range = motor_config.get("actuation_range", 180)
        pulse_min = motor_config.get("pulse_min", self.ARDUINO_MIN_PULSE)
        pulse_max = motor_config.get("pulse_max", self.ARDUINO_MAX_PULSE)
        
        # Clamp target to valid range
        target_physical_deg = max(0, min(actuation_range, target_physical_deg))
        
        # Step 1: Calculate required pulse width for target physical angle
        ratio = target_physical_deg / actuation_range
        target_pulse = pulse_min + (ratio * (pulse_max - pulse_min))
        
        # Step 2: Reverse-engineer Arduino input angle
        # Arduino maps: input_angle -> pulse = 500 + (input/180 * 2000)
        # Inverse: input_angle = (target_pulse - 500) * 180 / 2000
        arduino_pulse_range = self.ARDUINO_MAX_PULSE - self.ARDUINO_MIN_PULSE
        arduino_angle_range = self.ARDUINO_MAX_ANGLE - self.ARDUINO_MIN_ANGLE
        
        virtual_angle = ((target_pulse - self.ARDUINO_MIN_PULSE) * arduino_angle_range) / arduino_pulse_range
        
        # Clamp to Arduino's valid range
        virtual_angle = max(0, min(180, virtual_angle))
        
        return virtual_angle
    
    def physical_to_pulse(self, target_physical_deg, motor_config):
        """
        Convert physical target angle directly to pulse width in microseconds.
        For Pass-Through mode where Arduino receives raw pulse values.
        
        Args:
            target_physical_deg: Desired physical rotation (e.g., 90°)
            motor_config: Dict with 'actuation_range', 'pulse_min', 'pulse_max'
        
        Returns:
            int: Pulse width in microseconds (500-2500)
        
        Example:
            DS3225 (270° range), target = 135°
            -> Ratio = 135/270 = 0.5
            -> Pulse = 500 + (0.5 * 2000) = 1500us
        """
        # Get motor specs (with defaults for 180° motors)
        actuation_range = motor_config.get("actuation_range", 180)
        pulse_min = motor_config.get("pulse_min", 500)
        pulse_max = motor_config.get("pulse_max", 2500)
        
        # Clamp target to valid range
        target_physical_deg = max(0, min(actuation_range, target_physical_deg))
        
        # Calculate pulse width
        ratio = target_physical_deg / actuation_range
        pulse_us = pulse_min + (ratio * (pulse_max - pulse_min))
        
        # Clamp to safe range
        pulse_us = max(500, min(2500, int(pulse_us)))
        
        return pulse_us
    
    def virtual_to_physical(self, virtual_angle, motor_config):
        """
        Convert Arduino virtual angle back to physical angle (for display/FK).
        
        Args:
            virtual_angle: Angle sent to Arduino (0-180)
            motor_config: Dict with 'actuation_range', 'pulse_min', 'pulse_max'
        
        Returns:
            float: Physical rotation angle
        """
        actuation_range = motor_config.get("actuation_range", 180)
        pulse_min = motor_config.get("pulse_min", self.ARDUINO_MIN_PULSE)
        pulse_max = motor_config.get("pulse_max", self.ARDUINO_MAX_PULSE)
        
        # Step 1: Calculate pulse from virtual angle
        arduino_pulse_range = self.ARDUINO_MAX_PULSE - self.ARDUINO_MIN_PULSE
        pulse = self.ARDUINO_MIN_PULSE + (virtual_angle / 180.0) * arduino_pulse_range
        
        # Step 2: Calculate physical angle from pulse
        motor_pulse_range = pulse_max - pulse_min
        ratio = (pulse - pulse_min) / motor_pulse_range
        physical_angle = ratio * actuation_range
        
        return max(0, min(actuation_range, physical_angle))

    def pulse_to_angle(self, pulse_us, motor_config):
        """
        Convert pulse width (us) back to physical angle (for display).
        
        Args:
            pulse_us: Pulse width in microseconds
            motor_config: Dict with 'actuation_range', 'pulse_min', 'pulse_max'
        
        Returns:
            float: Physical angle (approximate)
        """
        actuation_range = motor_config.get("actuation_range", 180)
        pulse_min = motor_config.get("pulse_min", 500)
        pulse_max = motor_config.get("pulse_max", 2500)
        
        # Calculate ratio from pulse
        ratio = (pulse_us - pulse_min) / (pulse_max - pulse_min)
        
        # Convert to angle
        angle = ratio * actuation_range
        
        return max(0, min(actuation_range, angle))


# Self-test
if __name__ == "__main__":
    mapper = PulseMapper()
    
    print("=== PulseMapper Test ===")
    
    # Test 180° motor (MG996R) - should be identity mapping
    mg996r = {"actuation_range": 180, "pulse_min": 500, "pulse_max": 2500}
    print("\n[MG996R - 180°]")
    for deg in [0, 45, 90, 135, 180]:
        virtual = mapper.physical_to_virtual(deg, mg996r)
        back = mapper.virtual_to_physical(virtual, mg996r)
        print(f"  Physical {deg:3}° -> Virtual {virtual:6.2f}° -> Back {back:.2f}°")
    
    # Test 270° motor (DS3225)
    ds3225 = {"actuation_range": 270, "pulse_min": 500, "pulse_max": 2500}
    print("\n[DS3225 - 270°]")
    for deg in [0, 45, 90, 135, 180, 225, 270]:
        virtual = mapper.physical_to_virtual(deg, ds3225)
        back = mapper.virtual_to_physical(virtual, ds3225)
        print(f"  Physical {deg:3}° -> Virtual {virtual:6.2f}° -> Back {back:.2f}°")
