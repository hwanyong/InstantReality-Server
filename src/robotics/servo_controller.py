"""
Servo Controller for Arduino PCA9685

Handles serial communication to Arduino for PWM servo control.
Ports robot calibrator's servo_driver logic.
"""

import serial
import time
import json
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class ServoConfig:
    """Configuration for a single servo."""
    channel: int
    pulse_min: int
    pulse_max: int
    zero_pulse: int
    zero_offset: float
    actuation_range: int
    length: float
    min_pos: str  # "bottom", "top", "left", "right", etc.
    
    @classmethod
    def from_dict(cls, data: dict, channel: int) -> 'ServoConfig':
        return cls(
            channel=channel,
            pulse_min=data.get("min_pulse", data.get("pulse_min", 500)),
            pulse_max=data.get("max_pulse_limit", data.get("pulse_max", 2500)),
            zero_pulse=data.get("zero_pulse", 1500),
            zero_offset=data.get("zero_offset", 0.0),
            actuation_range=data.get("actuation_range", 180),
            length=data.get("length", 0.0),
            min_pos=data.get("min_pos", "bottom")
        )


class ServoController:
    """
    Controller for PCA9685 servo driver via Arduino.
    
    Protocol:
    - Move: "M<channel>:<pulse>\\n"
    - Move All: "A<p0>,<p1>,<p2>,...\\n"
    - Query: "Q<channel>\\n"
    """
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200, config_path: str = None):
        """
        Initialize servo controller.
        
        Args:
            port: Serial port
            baudrate: Baud rate
            config_path: Path to servo_config.json
        """
        self.port = port
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None
        self.servos: Dict[int, ServoConfig] = {}
        self.current_pulses: Dict[int, int] = {}
        
        if config_path:
            self.load_config(config_path)
    
    def load_config(self, config_path: str, arm: str = "right_arm"):
        """Load servo configuration from JSON."""
        with open(config_path) as f:
            config = json.load(f)
        
        arm_config = config.get(arm, {})
        for slot_key, slot_data in arm_config.items():
            if slot_key.startswith("slot_"):
                slot_num = int(slot_key.split("_")[1])
                channel = slot_data.get("channel", slot_num - 1)
                self.servos[slot_num] = ServoConfig.from_dict(slot_data, channel)
                self.current_pulses[slot_num] = slot_data.get("initial_pulse", 1500)
    
    def connect(self) -> bool:
        """Connect to Arduino."""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino reset
            return True
        except serial.SerialException as e:
            print(f"Serial connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Arduino."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.serial = None
    
    def math_angle_to_pulse(self, slot: int, math_angle: float) -> int:
        """
        Convert IK math angle to servo pulse.
        
        Args:
            slot: Slot number (1-6)
            math_angle: Angle from IK solver (degrees)
        
        Returns:
            Pulse width (microseconds)
        """
        if slot not in self.servos:
            raise ValueError(f"Unknown slot: {slot}")
        
        cfg = self.servos[slot]
        
        # Apply zero offset
        physical_angle = math_angle + cfg.zero_offset
        
        # Clamp to actuation range
        physical_angle = max(0, min(cfg.actuation_range, physical_angle))
        
        # Calculate pulse
        pulse_range = cfg.pulse_max - cfg.pulse_min
        pulse = cfg.pulse_min + (physical_angle / cfg.actuation_range) * pulse_range
        
        return int(pulse)
    
    def move_servo(self, slot: int, pulse: int, wait: bool = False):
        """
        Move a single servo to pulse position.
        
        Args:
            slot: Slot number (1-6)
            pulse: Target pulse width
            wait: Wait for movement to complete
        """
        if slot not in self.servos:
            raise ValueError(f"Unknown slot: {slot}")
        
        cfg = self.servos[slot]
        pulse = max(cfg.pulse_min, min(cfg.pulse_max, pulse))
        
        if self.serial and self.serial.is_open:
            cmd = f"M{cfg.channel}:{pulse}\n"
            self.serial.write(cmd.encode())
            self.current_pulses[slot] = pulse
            
            if wait:
                time.sleep(0.3)  # Basic delay for movement
    
    def move_to_angles(self, angles: Dict[int, float], wait: bool = True):
        """
        Move multiple servos to IK angles.
        
        Args:
            angles: Dict of {slot: math_angle}
            wait: Wait for movement
        """
        for slot, angle in angles.items():
            pulse = self.math_angle_to_pulse(slot, angle)
            self.move_servo(slot, pulse, wait=False)
        
        if wait:
            time.sleep(0.5)  # Wait for all movements
    
    def move_all(self, pulses: List[int], wait: bool = True):
        """
        Move all servos simultaneously.
        
        Args:
            pulses: List of pulse values for channels 0-5
            wait: Wait for movement
        """
        if self.serial and self.serial.is_open:
            pulse_str = ",".join(str(p) for p in pulses)
            cmd = f"A{pulse_str}\n"
            self.serial.write(cmd.encode())
            
            for i, pulse in enumerate(pulses):
                self.current_pulses[i + 1] = pulse
            
            if wait:
                time.sleep(0.5)
    
    def get_current_pose(self) -> Dict[int, int]:
        """Get current pulse positions for all servos."""
        return dict(self.current_pulses)
    
    def go_home(self):
        """Move all servos to home position."""
        for slot, cfg in self.servos.items():
            self.move_servo(slot, cfg.zero_pulse, wait=False)
        time.sleep(1.0)
