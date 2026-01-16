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
            "slot_1": {"channel": 0, "min": 0, "max": 180},
            "slot_2": {"channel": 1, "min": 0, "max": 180},
            "slot_3": {"channel": 2, "min": 0, "max": 180},
            "slot_4": {"channel": 3, "min": 0, "max": 180},
            "slot_5": {"channel": 4, "min": 0, "max": 180},
            "slot_6": {"channel": 5, "min": 0, "max": 180}
        },
        "right_arm": {
            "slot_1": {"channel": 6, "min": 0, "max": 180},
            "slot_2": {"channel": 7, "min": 0, "max": 180},
            "slot_3": {"channel": 8, "min": 0, "max": 180},
            "slot_4": {"channel": 9, "min": 0, "max": 180},
            "slot_5": {"channel": 10, "min": 0, "max": 180},
            "slot_6": {"channel": 11, "min": 0, "max": 180}
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
            self.config[arm][slot_key] = {"channel": 0, "min": 0, "max": 180}
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
            self.config[arm][slot_key] = {"channel": 0, "min": 0, "max": 180}
        self.config[arm][slot_key][limit_type] = value

    def get_saved_port(self):
        """Get saved COM port from config."""
        return self.config.get("connection", {}).get("port", "")

    def set_saved_port(self, port):
        """Save COM port to config."""
        if "connection" not in self.config:
            self.config["connection"] = {}
        self.config["connection"]["port"] = port

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
