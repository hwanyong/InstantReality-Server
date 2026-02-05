"""
Pulse Mapper
Converts physical degrees to pulse width for heterogeneous servo motors.
Supports motors with different actuation ranges (180°, 270°, etc.).
"""


class PulseMapper:
    """
    Maps physical target angles to pulse widths in microseconds.
    
    Pulse Range: 500us - 2500us (standard servo range)
    """
    
    def __init__(self):
        pass
    
    def physical_to_pulse(self, target_physical_deg, motor_config):
        """
        Convert physical target angle directly to pulse width in microseconds.
        
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
        actuation_range = motor_config.get("actuation_range", 180)
        pulse_min = motor_config.get("pulse_min", 500)
        pulse_max = motor_config.get("pulse_max", 2500)
        
        # Clamp target to valid range
        target_physical_deg = max(0, min(actuation_range, target_physical_deg))
        
        # Calculate pulse width
        ratio = target_physical_deg / actuation_range
        pulse_us = pulse_min + (ratio * (pulse_max - pulse_min))
        
        # Safety clamp
        pulse_us = max(0, min(3000, int(pulse_us)))
        
        return pulse_us

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
