"""
Servo Manager
Manages servo configuration, pin mapping, and limit settings.
"""

import json
import os


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
        self.config_path = config_path
        self.config = None
        self.load_config()

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

    def save_config(self):
        """Save configuration to JSON file."""
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
