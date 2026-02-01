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
        },
        "vertices": {
            "1": None, "2": None, "3": None, "4": None,
            "5": None, "6": None, "7": None, "8": None
        },
        "share_points": {
            "left_arm": None,
            "right_arm": None
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

        # 3. Compute Geometry (bases, vertices positions)
        try:
            self.compute_geometry()
        except Exception as e:
            print(f"Warning: Failed to compute geometry: {e}")

        # 4. Save to file
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

    def get_pulse_min(self, arm, slot):
        """Get pulse_min (0-degree reference) for a given slot."""
        slot_key = f"slot_{slot}"
        return self.config.get(arm, {}).get(slot_key, {}).get("pulse_min", 500)

    def get_pulse_max(self, arm, slot):
        """Get pulse_max for a given slot."""
        slot_key = f"slot_{slot}"
        return self.config.get(arm, {}).get(slot_key, {}).get("pulse_max", 2500)

    def set_pulse_reference(self, arm, slot, pulse_min_value):
        """
        Set pulse_min as 0-degree reference and auto-calculate pulse_max.
        Also converts all dependent pulse values to maintain physical angles.
        
        Args:
            arm: 'left_arm' or 'right_arm'
            slot: Slot number (1-6)
            pulse_min_value: Current pulse to set as 0-degree reference
        """
        slot_key = f"slot_{slot}"
        self._ensure_slot_exists(arm, slot_key)
        slot_config = self.config[arm][slot_key]
        
        # Get old and new pulse_min
        old_pulse_min = slot_config.get("pulse_min", 500)
        new_pulse_min = int(pulse_min_value)
        delta = new_pulse_min - old_pulse_min
        
        # Convert dependent pulse values (shift by delta to preserve physical angles)
        dependent_keys = ["initial_pulse", "zero_pulse", "min_pulse", "max_pulse_limit"]
        for key in dependent_keys:
            if key in slot_config:
                old_val = slot_config[key]
                new_val = max(0, min(3000, old_val + delta))  # Clamp to 0-3000
                slot_config[key] = new_val
        
        # Set new pulse_min and pulse_max
        slot_config["pulse_min"] = new_pulse_min
        slot_config["pulse_max"] = new_pulse_min + 2000  # Fixed 2000us range

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

    # ========== Vertex Management (Exclusive Ownership) ==========

    def _ensure_vertices_exists(self):
        """Ensure vertices key exists in config."""
        if "vertices" not in self.config:
            self.config["vertices"] = {
                "1": None, "2": None, "3": None, "4": None,
                "5": None, "6": None, "7": None, "8": None
            }

    def set_vertex(self, vertex_id, arm):
        """
        Save current arm's pulse values to a vertex.
        Exclusive ownership: if another arm owned this vertex, it's overwritten.

        Args:
            vertex_id: 1-8
            arm: 'left_arm' or 'right_arm'
        """
        self._ensure_vertices_exists()
        vertex_key = str(vertex_id)

        # Collect current pulse values from the arm
        pulses = {}
        for slot in range(1, 7):
            pulse = self.get_initial_pulse(arm, slot)
            pulses[f"slot_{slot}"] = pulse

        self.config["vertices"][vertex_key] = {
            "owner": arm,
            "pulses": pulses
        }

    def get_vertex(self, vertex_id):
        """
        Get vertex data.

        Args:
            vertex_id: 1-8

        Returns:
            dict: {"owner": arm, "pulses": {...}} or None if not set
        """
        self._ensure_vertices_exists()
        vertex_key = str(vertex_id)
        return self.config["vertices"].get(vertex_key)

    def get_vertex_owner(self, vertex_id):
        """
        Quick check for vertex ownership.

        Args:
            vertex_id: 1-8

        Returns:
            str: 'left_arm', 'right_arm', or None
        """
        vertex = self.get_vertex(vertex_id)
        if vertex:
            return vertex.get("owner")
        return None

    def clear_vertex(self, vertex_id):
        """
        Clear a vertex.

        Args:
            vertex_id: 1-8
        """
        self._ensure_vertices_exists()
        vertex_key = str(vertex_id)
        self.config["vertices"][vertex_key] = None

    # ========== Share Point Management (Per Arm) ==========

    def _ensure_share_points_exists(self):
        """Ensure share_points key exists in config."""
        if "share_points" not in self.config:
            self.config["share_points"] = {
                "left_arm": None,
                "right_arm": None
            }

    def set_share_point(self, arm):
        """
        Save current arm's pulse values as its share point.

        Args:
            arm: 'left_arm' or 'right_arm'
        """
        self._ensure_share_points_exists()

        # Collect current pulse values from the arm
        pulses = {}
        for slot in range(1, 7):
            pulse = self.get_initial_pulse(arm, slot)
            pulses[f"slot_{slot}"] = pulse

        self.config["share_points"][arm] = {"pulses": pulses}

    def get_share_point(self, arm):
        """
        Get share point data for an arm.

        Args:
            arm: 'left_arm' or 'right_arm'

        Returns:
            dict: {"pulses": {...}} or None if not set
        """
        self._ensure_share_points_exists()
        return self.config["share_points"].get(arm)

    def clear_share_point(self, arm):
        """
        Clear a share point.

        Args:
            arm: 'left_arm' or 'right_arm'
        """
        self._ensure_share_points_exists()
        self.config["share_points"][arm] = None

    # ========== Geometry Precomputation ==========

    # ========== Dual Reach Protocol (Stance-Adaptive Kinematics) ==========

    # Hardware constants for kinematics
    KINEMATICS_CONSTANTS = {
        "d1": 107.0,   # Base height (mm)
        "L1": 105.0,   # Upper arm length - Slot 2 (mm)
        "L2": 150.0,   # Forearm length - Slot 3 (mm)
        "L_wrist": 147.0,  # Wrist + Gripper effective length (mm)
        "stance_threshold": 60.0  # Yaw delta threshold for stance determination (degrees)
    }

    def compute_delta_angle(self, arm, slot_num, point_data):
        """
        Calculate delta angle from Zero reference.
        
        Formula: |physical_angle - zero_offset|
        
        Args:
            arm: 'left_arm' or 'right_arm'
            slot_num: Slot number (1-6)
            point_data: dict with 'angles' key
            
        Returns:
            float: Delta angle in degrees (always positive)
        """
        slot_key = f"slot_{slot_num}"
        angles = point_data.get("angles", {})
        
        physical_angle = angles.get(slot_key, 0)
        slot_config = self.config.get(arm, {}).get(slot_key, {})
        zero_offset = slot_config.get("zero_offset", 0)
        
        return abs(physical_angle - zero_offset)

    def determine_stance(self, yaw_delta):
        """
        Determine robot stance based on yaw delta angle.
        
        Open Stance: |yaw_delta| < 60° → Extended arms for side/forward work
        Closed Stance: |yaw_delta| >= 60° → Folded arms for back/inner work
        
        Args:
            yaw_delta: Yaw delta angle in degrees
            
        Returns:
            str: 'open' or 'closed'
        """
        threshold = self.KINEMATICS_CONSTANTS["stance_threshold"]
        if abs(yaw_delta) < threshold:
            return "open"
        return "closed"

    def compute_internal_angle(self, arm, point_data):
        """
        Compute the internal angle between L1 and L2 links.
        
        Open Stance (Compensation Logic):
            θ_int = 180° - |θ_E_delta - θ_S_delta|
            Shoulder rotation is compensated by elbow, keeping arm extended.
            
        Closed Stance (Folded Logic):
            θ_int = θ_E_delta
            No compensation, elbow delta directly becomes fold angle.
            
        Args:
            arm: 'left_arm' or 'right_arm'
            point_data: dict with 'angles' key
            
        Returns:
            dict: {
                'yaw_delta': float,
                'shoulder_delta': float,
                'elbow_delta': float,
                'stance': str,
                'internal_angle': float
            }
        """
        # Calculate delta angles
        yaw_delta = self.compute_delta_angle(arm, 1, point_data)
        shoulder_delta = self.compute_delta_angle(arm, 2, point_data)
        elbow_delta = self.compute_delta_angle(arm, 3, point_data)
        
        # Determine stance
        stance = self.determine_stance(yaw_delta)
        
        # Calculate internal angle based on stance
        if stance == "open":
            # Open Stance: Compensation logic
            # θ_int = 180° - |θ_E_delta - θ_S_delta|
            internal_angle = 180.0 - abs(elbow_delta - shoulder_delta)
        else:
            # Closed Stance: Folded logic
            # θ_int = θ_E_delta
            internal_angle = elbow_delta
        
        return {
            "yaw_delta": yaw_delta,
            "shoulder_delta": shoulder_delta,
            "elbow_delta": elbow_delta,
            "stance": stance,
            "internal_angle": internal_angle
        }

    def compute_3d_reach(self, arm, point_data):
        """
        Compute 3D reach using Law of Cosines (Dual Reach Protocol).
        
        R_3d = √(L1² + L2² - 2·L1·L2·cos(θ_int))
        Z_drop = R_3d × sin(θ_S_delta)
        Z_final = d1 - Z_drop
        r_xy = R_3d × cos(θ_S_delta)
        
        Args:
            arm: 'left_arm' or 'right_arm'
            point_data: dict with 'angles' key
            
        Returns:
            dict: {
                'angles': {yaw_delta, shoulder_delta, elbow_delta, internal_angle},
                'stance': str,
                'r_3d': float (mm),
                'r_xy': float (mm),
                'z_drop': float (mm),
                'z_final': float (mm)
            }
        """
        import math
        
        # Get internal angle data
        angle_data = self.compute_internal_angle(arm, point_data)
        
        # Hardware constants
        L1 = self.KINEMATICS_CONSTANTS["L1"]
        L2 = self.KINEMATICS_CONSTANTS["L2"]
        d1 = self.KINEMATICS_CONSTANTS["d1"]
        
        # Convert internal angle to radians
        theta_int_rad = math.radians(angle_data["internal_angle"])
        
        # Law of Cosines: R_3d = √(L1² + L2² - 2·L1·L2·cos(θ_int))
        r_3d = math.sqrt(L1**2 + L2**2 - 2 * L1 * L2 * math.cos(theta_int_rad))
        
        # Convert shoulder delta to radians for projection
        theta_s_rad = math.radians(angle_data["shoulder_delta"])
        
        # Height calculation (assuming pitch down)
        z_drop = r_3d * math.sin(theta_s_rad)
        z_final = d1 - z_drop
        
        # Horizontal reach
        r_xy = r_3d * math.cos(theta_s_rad)
        
        return {
            "angles": {
                "yaw_delta": angle_data["yaw_delta"],
                "shoulder_delta": angle_data["shoulder_delta"],
                "elbow_delta": angle_data["elbow_delta"],
                "internal_angle": angle_data["internal_angle"]
            },
            "stance": angle_data["stance"],
            "r_3d": r_3d,
            "r_xy": r_xy,
            "z_drop": z_drop,
            "z_final": z_final
        }

    def compute_reach(self, arm, point_data, is_vertex=True):
        """
        Compute reach distance from base to gripper.

        Args:
            arm: 'left_arm' or 'right_arm'
            point_data: dict with 'pulses' and 'angles'
            is_vertex: True for vertex (approach 90°), False for share point

        Returns:
            float: reach distance in mm
        """
        import math

        if is_vertex:
            # Vertex: approach angle = 90° (gripper perpendicular to ground)
            # Wrist section points straight down, contributing 0 to horizontal reach
            # So reach = a2*cos(θ2) + a3*cos(θ2+θ3)
            angles = point_data.get("angles", {})

            def get_logical_angle(slot_num):
                slot_key = f"slot_{slot_num}"
                slot_config = self.config.get(arm, {}).get(slot_key, {})
                physical = angles.get(slot_key, 0)
                zero_offset = slot_config.get("zero_offset", 0)

                if slot_num == 4:
                    logical = zero_offset - physical
                else:
                    logical = physical - zero_offset

                return math.radians(logical)

            theta2 = get_logical_angle(2)
            theta3 = get_logical_angle(3)

            a2 = self.config.get(arm, {}).get("slot_2", {}).get("length", 0)
            a3 = self.config.get(arm, {}).get("slot_3", {}).get("length", 0)

            # Horizontal projection (wrist section = 0 because cos(-90°) = 0)
            r = a2 * math.cos(theta2) + a3 * math.cos(theta2 + theta3)
            return max(0, abs(r))
        else:
            # Share Point: FK horizontal projection based on angles
            angles = point_data.get("angles", {})
            lengths = []
            for slot in range(2, 7):
                slot_key = f"slot_{slot}"
                lengths.append(self.config.get(arm, {}).get(slot_key, {}).get("length", 0))

            # Get logical angles matching IK code formulas
            def get_logical_angle(slot_num):
                slot_key = f"slot_{slot_num}"
                slot_config = self.config.get(arm, {}).get(slot_key, {})
                physical = angles.get(slot_key, 0)
                zero_offset = slot_config.get("zero_offset", 0)

                # FK formulas derived from IK code (full_slot2_view.py)
                # Slot 2: IK uses phy = θ + zero → FK: θ = phy - zero
                # Slot 3: IK uses phy = zero + θ (after inversion) → FK: θ = phy - zero
                # Slot 4: IK uses phy = zero - θ → FK: θ = zero - phy
                if slot_num == 4:
                    logical = zero_offset - physical
                else:
                    logical = physical - zero_offset

                return math.radians(logical)

            theta2 = get_logical_angle(2)
            theta3 = get_logical_angle(3)
            theta4 = get_logical_angle(4)

            a2, a3, a4, a5, a6 = lengths
            # FK horizontal projection with wrist angle
            wrist_angle = theta2 + theta3 + theta4
            r = a2 * math.cos(theta2) + a3 * math.cos(theta2 + theta3) + (a4 + a5 + a6) * math.cos(wrist_angle)
            return max(0, r)

    def compute_yaw(self, arm, point_data):
        """
        Compute yaw angle (slot 1 logical angle) in world coordinate.

        Args:
            arm: 'left_arm' or 'right_arm'
            point_data: dict with 'angles'

        Returns:
            float: yaw angle in radians (world coordinate: +X=up, +Y=left)
        """
        import math

        angles = point_data.get("angles", {})
        slot_1_angle = angles.get("slot_1", 0)

        slot_1_config = self.config.get(arm, {}).get("slot_1", {})
        zero_offset = slot_1_config.get("zero_offset", 0)

        # Logical angle: physical - zero_offset
        # zero_offset already encodes coordinate system difference between arms
        logical_angle = slot_1_angle - zero_offset

        return math.radians(logical_angle)

    def compute_base_direct(self, point_x, point_y, reach, yaw):
        """
        Compute base position by reversing reach + yaw from point.

        Args:
            point_x, point_y: Point position (relative to origin)
            reach: Distance from base to point
            yaw: Direction angle in radians

        Returns:
            tuple: (base_x, base_y)
        """
        import math

        base_x = point_x - reach * math.cos(yaw)
        base_y = point_y - reach * math.sin(yaw)
        return (base_x, base_y)

    def compute_geometry(self):
        """
        Compute geometry section: bases, vertices, share points positions.
        Uses Share Point as origin (0, 0).
        """
        import math

        geometry = {
            "coordinate_system": "+X=up, +Y=left",
            "origin": "share_point",
            "share_points": {},
            "bases": {},
            "vertices": {}
        }

        # 1. Add Share Points as origin (0, 0)
        for arm in ["left_arm", "right_arm"]:
            share_point = self.config.get("share_points", {}).get(arm)
            if share_point:
                geometry["share_points"][arm] = {"x": 0.0, "y": 0.0}

        # 2. Compute Base positions from Share Points only
        for arm in ["left_arm", "right_arm"]:
            share_point = self.config.get("share_points", {}).get(arm)
            if not share_point:
                continue

            reach = self.compute_reach(arm, share_point, is_vertex=False)
            yaw = self.compute_yaw(arm, share_point)

            # Share Point is origin (0, 0), compute base relative to origin
            base_x, base_y = self.compute_base_direct(0, 0, reach, yaw)

            geometry["bases"][arm] = {
                "x": round(base_x, 1),
                "y": round(base_y, 1),
                "sources": 1
            }

        # 3. Compute Vertex positions relative to origin (1-8) using Dual Reach Protocol
        for vid in range(1, 9):
            vertex = self.config.get("vertices", {}).get(str(vid))
            if not vertex:
                continue

            owner = vertex.get("owner")
            if not owner or owner not in geometry["bases"]:
                continue

            base = geometry["bases"][owner]
            
            # Use new Dual Reach Protocol for 3D computation
            reach_data = self.compute_3d_reach(owner, vertex)
            yaw = self.compute_yaw(owner, vertex)

            # Vertex position = base + r_xy in yaw direction
            r_xy = reach_data["r_xy"]
            vx = base["x"] + r_xy * math.cos(yaw)
            vy = base["y"] + r_xy * math.sin(yaw)

            geometry["vertices"][str(vid)] = {
                "x": round(vx, 1),
                "y": round(vy, 1),
                "z": round(reach_data["z_final"], 1),
                "owner": owner,
                "stance": reach_data["stance"],
                "r_3d": round(reach_data["r_3d"], 1),
                "angles": {
                    "yaw_delta": round(reach_data["angles"]["yaw_delta"], 1),
                    "shoulder_delta": round(reach_data["angles"]["shoulder_delta"], 1),
                    "elbow_delta": round(reach_data["angles"]["elbow_delta"], 1),
                    "internal_angle": round(reach_data["angles"]["internal_angle"], 1)
                }
            }


        # 4. Compute distance matrix
        distances = {
            "vertex_to_vertex": {},
            "base_to_vertex": {},
            "share_point_to_vertex": {},
            "base_to_base": None
        }

        # Vertex to Vertex distances
        vertex_ids = list(geometry["vertices"].keys())
        for i, v1 in enumerate(vertex_ids):
            for v2 in vertex_ids[i+1:]:
                p1 = geometry["vertices"][v1]
                p2 = geometry["vertices"][v2]
                dist = math.sqrt((p1["x"] - p2["x"])**2 + (p1["y"] - p2["y"])**2)
                distances["vertex_to_vertex"][f"{v1}_{v2}"] = round(dist, 1)

        # Base to Vertex distances
        for arm, base in geometry["bases"].items():
            arm_distances = {}
            for vid, vertex in geometry["vertices"].items():
                dist = math.sqrt((base["x"] - vertex["x"])**2 + (base["y"] - vertex["y"])**2)
                arm_distances[vid] = round(dist, 1)
            distances["base_to_vertex"][arm] = arm_distances

        # Share Point to Vertex distances (from origin 0,0)
        for vid, vertex in geometry["vertices"].items():
            dist = math.sqrt(vertex["x"]**2 + vertex["y"]**2)
            distances["share_point_to_vertex"][vid] = round(dist, 1)

        # Base to Base distance
        if "left_arm" in geometry["bases"] and "right_arm" in geometry["bases"]:
            left = geometry["bases"]["left_arm"]
            right = geometry["bases"]["right_arm"]
            dist = math.sqrt((left["x"] - right["x"])**2 + (left["y"] - right["y"])**2)
            distances["base_to_base"] = round(dist, 1)

        geometry["distances"] = distances

        self.config["geometry"] = geometry
        return geometry


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
