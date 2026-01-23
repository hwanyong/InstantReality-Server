"""
Servo Manager
Manages servo configuration, pin mapping, and limit settings.
"""

import json
import os
from pulse_mapper import PulseMapper


class ServoManager:
    """
    Manages servo configuration including channel mapping and limits.
    """

    DEFAULT_CONFIG = {
        "left_arm": {
            "slot_1": {"channel": 0, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0},
            "slot_2": {"channel": 1, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0},
            "slot_3": {"channel": 2, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0},
            "slot_4": {"channel": 3, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0},
            "slot_5": {"channel": 4, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0},
            "slot_6": {"channel": 5, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0}
        },
        "right_arm": {
            "slot_1": {"channel": 6, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0},
            "slot_2": {"channel": 7, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0},
            "slot_3": {"channel": 8, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0},
            "slot_4": {"channel": 9, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0},
            "slot_5": {"channel": 10, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0},
            "slot_6": {"channel": 11, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0}
        },
        "connection": {
            "port": ""
        }
    }

    def __init__(self, config_path="servo_config.json"):
        if not os.path.isabs(config_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, config_path)
            
        self.config_path = config_path
        self.config = None
        self.mapper = PulseMapper()
        self._observers = []
        self.load_config()

    def add_observer(self, callback):
        """Register a callback to be notified on config changes."""
        if callback not in self._observers:
            self._observers.append(callback)

    def _notify_observers(self):
        """Notify all observers that config has changed."""
        for callback in self._observers:
            try:
                callback()
            except Exception as e:
                print(f"Error notifying observer: {e}")

    def load_config(self):
        """Load configuration from JSON file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                print(f"Config loaded from {self.config_path}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Failed to load config: {e}")
                self.config = self._deep_copy(self.DEFAULT_CONFIG)
        else:
            self.config = self._deep_copy(self.DEFAULT_CONFIG)
            print("Using default config")
        
        self._notify_observers()

    def save_config(self):
        """Save configuration to JSON file."""
        # 1. Migration: Ensure Pulse values exist (Angle -> Pulse)
        try:
            self._ensure_pulses_native() 
        except Exception as e:
            print(f"Warning: Failed to ensure pulse values: {e}")

        # 2. Enforcement: Sync Angles from Pulse (Pulse -> Angle)
        try:
            self._sync_angles_from_pulses() 
        except Exception as e:
            print(f"Warning: Failed to sync angles from pulses: {e}")
            # Try to save anyway to persist pulse values
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            print(f"Config saved to {self.config_path}")
            return True
        except IOError as e:
            print(f"Failed to save config: {e}")
            return False

    def _deep_copy(self, obj):
        """Create a deep copy of a dictionary."""
        return json.loads(json.dumps(obj))

    def _sync_angles_from_pulses(self):
        """
        Synchronize derived Angle values from primary Pulse values.
        Called automatically before saving to disk.
        """
        if not self.config: return

        for arm_name, arm_data in self.config.items():
            if arm_name not in ["left_arm", "right_arm"]: continue
            
            for slot_key, slot_config in arm_data.items():
                # 1. Sync Initial
                if "initial_pulse" in slot_config:
                    pulse = slot_config["initial_pulse"]
                    angle = self.mapper.pulse_to_angle(pulse, slot_config)
                    slot_config["initial"] = float(f"{angle:.1f}")

                # 2. Sync Zero Offset
                if "zero_pulse" in slot_config:
                    pulse = slot_config["zero_pulse"]
                    angle = self.mapper.pulse_to_angle(pulse, slot_config)
                    slot_config["zero_offset"] = float(f"{angle:.1f}")
                
                # 3. Sync Min/Max Limits
                if "min_pulse" in slot_config:
                    pulse = slot_config["min_pulse"]
                    angle = self.mapper.pulse_to_angle(pulse, slot_config)
                    slot_config["min"] = float(f"{angle:.1f}")

                if "max_pulse_limit" in slot_config:
                    pulse = slot_config["max_pulse_limit"]
                    angle = self.mapper.pulse_to_angle(pulse, slot_config)
                    slot_config["max"] = float(f"{angle:.1f}")

    def _ensure_pulses_native(self):
        """
        Migration Step: Ensure all slots have Pulse values.
        If Pulse values are missing, calculate them from existing Angles.
        """
        if not self.config: return

        for arm_name, arm_data in self.config.items():
            if arm_name not in ["left_arm", "right_arm"]: continue
            
            for slot_key, slot_config in arm_data.items():
                # Backfill Initial Pulse
                if "initial_pulse" not in slot_config:
                    angle = slot_config.get("initial", 90)
                    slot_config["initial_pulse"] = self._calculate_pulse(arm_name, slot_key.split('_')[1], angle)
                
                # Backfill Zero Pulse
                if "zero_pulse" not in slot_config:
                    angle = slot_config.get("zero_offset", 0)
                    slot_config["zero_pulse"] = self._calculate_pulse(arm_name, slot_key.split('_')[1], angle)

                # Backfill Min Pulse (Limit)
                if "min_pulse" not in slot_config:
                    angle = slot_config.get("min", 0)
                    slot_config["min_pulse"] = self._calculate_pulse(arm_name, slot_key.split('_')[1], angle)

                # Backfill Max Pulse (Limit)
                if "max_pulse_limit" not in slot_config:
                    angle = slot_config.get("max", 180)
                    slot_config["max_pulse_limit"] = self._calculate_pulse(arm_name, slot_key.split('_')[1], angle)

    def get_channel(self, arm, slot):
        """
        Get PCA9685 channel for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)

        Returns:
            int: PCA9685 channel (0-15)
        """
        slot_key = f"slot_{slot}"
        return self.config.get(arm, {}).get(slot_key, {}).get("channel", 0)

    def set_channel(self, arm, slot, channel):
        """
        Set PCA9685 channel for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)
            channel: PCA9685 channel (0-15)
        """
        slot_key = f"slot_{slot}"
        if arm not in self.config:
            self.config[arm] = {}
        if slot_key not in self.config[arm]:
            self.config[arm][slot_key] = {"channel": 0, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0}
        self.config[arm][slot_key]["channel"] = channel

    def get_limits(self, arm, slot):
        """
        Get min/max limits for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)

        Returns:
            dict: {"min": int, "max": int}
        """
        slot_key = f"slot_{slot}"
        slot_config = self.config.get(arm, {}).get(slot_key, {})
        return {
            "min": slot_config.get("min", 0),
            "max": slot_config.get("max", 180)
        }

    def set_limit(self, arm, slot, limit_type, value):
        """
        Set min or max limit for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)
            limit_type: 'min' or 'max'
            value: Angle value (0-180)
        """
        slot_key = f"slot_{slot}"
        if arm not in self.config:
            self.config[arm] = {}
        if slot_key not in self.config[arm]:
            self.config[arm][slot_key] = {"channel": 0, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0}
        self.config[arm][slot_key][limit_type] = value
        
        self.config[arm][slot_key][limit_type] = value
        
    def set_limit_pulse(self, arm, slot, limit_type, value):
        """Set min/max pulse limit directly."""
        slot_key = f"slot_{slot}"
        self._ensure_slot_exists(arm, slot_key)
        key = "min_pulse" if limit_type == "min" else "max_pulse_limit"
        self.config[arm][slot_key][key] = int(value)

    def _calculate_pulse(self, arm, slot, angle):
        """Calculate pulse width (us) for a given physical angle."""
        slot_key = f"slot_{slot}"
        config = self.config.get(arm, {}).get(slot_key, {})
        
        actuation_range = config.get("actuation_range", 180)
        pulse_min = config.get("pulse_min", 500)
        pulse_max = config.get("pulse_max", 2500)
        
        # Basic mapping: pulse = min + (angle / range) * (max - min)
        if actuation_range <= 0: actuation_range = 180 # Safety
        
        pulse = pulse_min + (float(angle) / actuation_range) * (pulse_max - pulse_min)
        return int(pulse)

    def get_saved_port(self):
        """Get saved COM port from config."""
        return self.config.get("connection", {}).get("port", "")

    def set_saved_port(self, port):
        """Save COM port to config."""
        if "connection" not in self.config:
            self.config["connection"] = {}
        self.config["connection"]["port"] = port

    # ========== Kinematics Properties ==========

    def get_type(self, arm, slot):
        """
        Get movement type for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)

        Returns:
            str: 'vertical' or 'horizontal'
        """
        slot_key = f"slot_{slot}"
        return self.config.get(arm, {}).get(slot_key, {}).get("type", "vertical")

    def set_type(self, arm, slot, value):
        """
        Set movement type for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)
            value: 'vertical' or 'horizontal'
        """
        slot_key = f"slot_{slot}"
        self._ensure_slot_exists(arm, slot_key)
        self.config[arm][slot_key]["type"] = value

    def get_min_pos(self, arm, slot):
        """
        Get min angle position indicator for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)

        Returns:
            str: For vertical: 'top'/'bottom', For horizontal: 'left'/'right'
        """
        slot_key = f"slot_{slot}"
        return self.config.get(arm, {}).get(slot_key, {}).get("min_pos", "bottom")

    def set_min_pos(self, arm, slot, value):
        """
        Set min angle position indicator for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)
            value: For vertical: 'top'/'bottom', For horizontal: 'left'/'right'
        """
        slot_key = f"slot_{slot}"
        self._ensure_slot_exists(arm, slot_key)
        self.config[arm][slot_key]["min_pos"] = value

    def get_length(self, arm, slot):
        """
        Get link length to next joint for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)

        Returns:
            float: Distance in mm
        """
        slot_key = f"slot_{slot}"
        return self.config.get(arm, {}).get(slot_key, {}).get("length", 0)

    def set_length(self, arm, slot, value):
        """
        Set link length to next joint for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)
            value: Distance in mm
        """
        slot_key = f"slot_{slot}"
        self._ensure_slot_exists(arm, slot_key)
        self.config[arm][slot_key]["length"] = value

    def _ensure_slot_exists(self, arm, slot_key):
        """Helper to ensure arm and slot exist in config."""
        if arm not in self.config:
            self.config[arm] = {}
        if slot_key not in self.config[arm]:
            self.config[arm][slot_key] = {"channel": 0, "min": 0, "max": 180, "type": "vertical", "min_pos": "bottom", "length": 0, "initial": 90, "zero_offset": 0}

    def get_initial(self, arm, slot):
        """
        Get initial (home) position angle for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)

        Returns:
            int: Initial angle (0-180)
        """
        slot_key = f"slot_{slot}"
        return self.config.get(arm, {}).get(slot_key, {}).get("initial", 90)

    def set_initial(self, arm, slot, value):
        """
        Set initial (home) position angle for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)
            value: Angle (0-180)
        """
        slot_key = f"slot_{slot}"
        self._ensure_slot_exists(arm, slot_key)
        self.config[arm][slot_key]["initial"] = value
        
    def set_initial_pulse(self, arm, slot, value):
        """Set initial position pulse width directly."""
        slot_key = f"slot_{slot}"
        self._ensure_slot_exists(arm, slot_key)
        self.config[arm][slot_key]["initial_pulse"] = int(value)

    def get_initial_pulse(self, arm, slot):
        """Get initial position in microseconds."""
        slot_key = f"slot_{slot}"
        # Return saved pulse if exists, else calculate it
        saved = self.config.get(arm, {}).get(slot_key, {}).get("initial_pulse")
        if saved is not None:
            return saved
        angle = self.get_initial(arm, slot)
        return self._calculate_pulse(arm, slot, angle)

    def get_zero_offset(self, arm, slot):
        """
        Get zero point offset for a given slot.
        This is the physical angle corresponding to Logical 0 (vertical pose).

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)

        Returns:
            float: Offset angle in degrees
        """
        slot_key = f"slot_{slot}"
        return self.config.get(arm, {}).get(slot_key, {}).get("zero_offset", 0)

    def set_zero_offset(self, arm, slot, value):
        """
        Set zero point offset for a given slot.
        This should be called when the robot is in the vertical calibration pose.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)
            value: Offset angle (physical angle at Logical 0)
        """
        slot_key = f"slot_{slot}"
        self._ensure_slot_exists(arm, slot_key)
        self.config[arm][slot_key]["zero_offset"] = value
        
    def set_zero_pulse(self, arm, slot, value):
        """Set zero offset pulse width directly."""
        slot_key = f"slot_{slot}"
        self._ensure_slot_exists(arm, slot_key)
        self.config[arm][slot_key]["zero_pulse"] = int(value)

    def get_zero_pulse(self, arm, slot):
        """Get zero offset in microseconds."""
        slot_key = f"slot_{slot}"
        saved = self.config.get(arm, {}).get(slot_key, {}).get("zero_pulse")
        if saved is not None:
            return saved
        angle = self.get_zero_offset(arm, slot)
        return self._calculate_pulse(arm, slot, angle)

    def get_actuation_range(self, arm, slot):
        """
        Get motor's physical actuation range for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)

        Returns:
            int: 180 or 270 (degrees)
        """
        slot_key = f"slot_{slot}"
        return self.config.get(arm, {}).get(slot_key, {}).get("actuation_range", 180)

    def set_actuation_range(self, arm, slot, value):
        """
        Set motor's physical actuation range for a given slot.

        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)
            value: 180 or 270 (degrees)
        """
        slot_key = f"slot_{slot}"
        self._ensure_slot_exists(arm, slot_key)
        self.config[arm][slot_key]["actuation_range"] = value

    def get_all_slots(self):
        """
        Get all slot configurations.

        Returns:
            dict: Full configuration for both arms
        """
        return {
            "left_arm": self.config.get("left_arm", {}),
            "right_arm": self.config.get("right_arm", {})
        }


# Test code
if __name__ == "__main__":
    manager = ServoManager("test_config.json")

    # Test channel mapping
    print(f"Left Arm Slot 1 Channel: {manager.get_channel('left_arm', 1)}")

    # Change channel
    manager.set_channel('left_arm', 1, 5)
    print(f"After change: {manager.get_channel('left_arm', 1)}")

    # Set limits
    manager.set_limit('left_arm', 1, 'min', 10)
    manager.set_limit('left_arm', 1, 'max', 170)
    print(f"Limits: {manager.get_limits('left_arm', 1)}")

    # Save config
    manager.save_config()

    # Clean up test file
    if os.path.exists("test_config.json"):
        os.remove("test_config.json")
        print("Test config removed.")
