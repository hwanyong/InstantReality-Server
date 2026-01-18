"""
Smart Robot Arm
4-DOF Geometric IK solver with hardware control integration.
Handles angle conversion, safety clamping, and motor mapping.
"""

import math
import json
import os


class SmartRobotArm:
    """
    Controls a single robot arm with integrated IK solver.
    
    Joint Configuration (4-DOF for position):
        Slot 1: Base Yaw (horizontal rotation)
        Slot 2: Shoulder Pitch (vertical rotation)
        Slot 3: Elbow Pitch (vertical rotation)
        Slot 4: Wrist Yaw (horizontal rotation) - not used in basic IK
    
    Additional:
        Slot 5: Wrist Roll (not affecting position)
        Slot 6: Gripper
    """
    
    def __init__(self, arm_name, config, driver=None):
        """
        Initialize the robot arm controller.
        
        Args:
            arm_name: "left_arm" or "right_arm"
            config: Dictionary containing arm configuration from servo_config.json
            driver: SerialDriver instance (optional, for simulation)
        """
        self.arm_name = arm_name
        self.config = config
        self.driver = driver
        
        # Extract link lengths from config
        self.d1 = config.get("slot_1", {}).get("length", 107.0)  # Base height
        self.a2 = config.get("slot_2", {}).get("length", 105.0)  # Shoulder to Elbow
        self.a3 = config.get("slot_3", {}).get("length", 150.0)  # Elbow to Wrist
        
        # Calculate max reach for reachability check
        self.max_reach = self.a2 + self.a3
        self.min_reach = abs(self.a3 - self.a2)
        
        # Direction multipliers for angle conversion
        # Determined by min_pos configuration
        self._setup_directions()
    
    def _setup_directions(self):
        """Setup direction multipliers based on motor mounting."""
        self.directions = {}
        
        for slot in range(1, 7):
            slot_key = f"slot_{slot}"
            slot_config = self.config.get(slot_key, {})
            min_pos = slot_config.get("min_pos", "bottom")
            joint_type = slot_config.get("type", "vertical")
            
            # Determine direction based on min_pos
            if joint_type == "vertical":
                # bottom: positive angle goes up (+1)
                # top: positive angle goes down (-1)
                self.directions[slot] = 1 if min_pos == "bottom" else -1
            elif joint_type == "horizontal":
                # left: positive angle goes right (+1)
                # right: positive angle goes left (-1)
                self.directions[slot] = 1 if min_pos == "left" else -1
            elif joint_type == "roll":
                self.directions[slot] = 1 if min_pos == "ccw" else -1
            elif joint_type == "gripper":
                self.directions[slot] = 1 if min_pos == "open" else -1
            else:
                self.directions[slot] = 1
    
    def _get_zero_offset(self, slot):
        """Get zero offset for a slot."""
        slot_key = f"slot_{slot}"
        return self.config.get(slot_key, {}).get("zero_offset", 90.0)
    
    def _get_limits(self, slot):
        """Get min/max limits for a slot."""
        slot_key = f"slot_{slot}"
        slot_cfg = self.config.get(slot_key, {})
        return (slot_cfg.get("min", 0), slot_cfg.get("max", 180))
    
    def _get_channel(self, slot):
        """Get PCA9685 channel for a slot."""
        slot_key = f"slot_{slot}"
        return self.config.get(slot_key, {}).get("channel", slot - 1)
    
    def _math_to_physical(self, slot, math_angle_deg):
        """
        Convert mathematical angle to physical servo angle.
        
        Formula: physical = zero_offset + (direction * math_angle)
        
        Args:
            slot: Slot number (1-6)
            math_angle_deg: Mathematical angle in degrees
        
        Returns:
            float: Physical servo angle
        """
        zero_offset = self._get_zero_offset(slot)
        direction = self.directions.get(slot, 1)
        
        physical = zero_offset + (direction * math_angle_deg)
        return physical
    
    def _clamp_angle(self, slot, angle):
        """
        Clamp angle to safe limits.
        
        Args:
            slot: Slot number
            angle: Angle to clamp
        
        Returns:
            float: Clamped angle
        """
        min_limit, max_limit = self._get_limits(slot)
        return max(min_limit, min(max_limit, angle))
    
    def solve_ik(self, x, y, z):
        """
        4-DOF Geometric Inverse Kinematics solver.
        
        Args:
            x: Local X coordinate (mm) - lateral
            y: Local Y coordinate (mm) - forward/reach
            z: Local Z coordinate (mm) - height
        
        Returns:
            list: [theta1, theta2, theta3, theta4] in physical degrees
            
        Raises:
            ValueError: If target is unreachable
        """
        # Step 1: Calculate horizontal distance and vertical offset
        r = math.sqrt(x**2 + y**2)  # Horizontal distance to target
        s = z - self.d1            # Vertical distance (above base)
        
        # Step 2: Calculate total distance
        D = math.sqrt(r**2 + s**2)
        
        # Reachability check
        if D > self.max_reach:
            raise ValueError(f"Target unreachable: D={D:.1f}mm exceeds max reach {self.max_reach:.1f}mm")
        if D < self.min_reach:
            raise ValueError(f"Target too close: D={D:.1f}mm below min reach {self.min_reach:.1f}mm")
        
        # Step 3: Calculate Base Yaw (theta1)
        theta1_math = math.degrees(math.atan2(x, y))
        
        # Step 4: Calculate Elbow angle (theta3) using law of cosines
        cos_theta3 = (D**2 - self.a2**2 - self.a3**2) / (2 * self.a2 * self.a3)
        cos_theta3 = max(-1, min(1, cos_theta3))  # Clamp for numerical stability
        theta3_math = math.degrees(math.acos(cos_theta3))
        
        # Asymmetry Fix: Left Arm requires "Elbow Up" solution (negative theta3)
        # to map correctly to physical servo limits (0-144, zero_offset=55).
        # Right Arm uses "Elbow Down" (positive theta3).
        if self.arm_name == "left_arm":
            theta3_math = -theta3_math
        
        # Step 5: Calculate Shoulder angle (theta2)
        alpha = math.atan2(s, r)
        beta = math.atan2(self.a3 * math.sin(math.radians(theta3_math)),
                         self.a2 + self.a3 * math.cos(math.radians(theta3_math)))
        theta2_math = math.degrees(alpha - beta)
        
        # Step 6: Wrist Yaw (theta4) - keep horizontal by default
        theta4_math = 0
        
        # Step 7: Convert to physical angles
        theta1_phy = self._math_to_physical(1, theta1_math)
        theta2_phy = self._math_to_physical(2, theta2_math)
        theta3_phy = self._math_to_physical(3, theta3_math)
        theta4_phy = self._math_to_physical(4, theta4_math)
        
        # Step 8: Apply safety clamping
        theta1_phy = self._clamp_angle(1, theta1_phy)
        theta2_phy = self._clamp_angle(2, theta2_phy)
        theta3_phy = self._clamp_angle(3, theta3_phy)
        theta4_phy = self._clamp_angle(4, theta4_phy)
        
        return [theta1_phy, theta2_phy, theta3_phy, theta4_phy]
    
    def apply_motion(self, angles, duration=1.0):
        """
        Apply calculated angles to servos.
        
        Args:
            angles: List of physical angles [theta1, theta2, theta3, theta4]
            duration: Motion duration in seconds (for smooth motion)
        """
        if self.driver is None:
            print(f"[SIM] {self.arm_name}: Moving to angles {[f'{a:.1f}' for a in angles]}")
            return
        
        for slot in range(1, 5):
            channel = self._get_channel(slot)
            angle = int(angles[slot - 1])
            self.driver.set_servo_angle(channel, angle)
    
    def get_servo_targets(self, angles):
        """
        Convert physical angles list to (channel, angle) tuples for MotionPlanner.
        
        Args:
            angles: List of physical angles [theta1, theta2, theta3, theta4]
        
        Returns:
            list: List of (channel, angle) tuples
        """
        targets = []
        for slot in range(1, len(angles) + 1):
            channel = self._get_channel(slot)
            angle = int(angles[slot - 1])
            targets.append((channel, angle))
        return targets
    
    def control_gripper(self, state):
        """
        Control the gripper.
        
        Args:
            state: "open" or "close"
        """
        slot = 6
        slot_config = self.config.get("slot_6", {})
        min_angle = slot_config.get("min", 0)
        max_angle = slot_config.get("max", 180)
        min_pos = slot_config.get("min_pos", "open")
        
        if min_pos == "open":
            target = min_angle if state == "open" else max_angle
        else:  # min_pos == "close"
            target = max_angle if state == "open" else min_angle
        
        if self.driver is None:
            print(f"[SIM] {self.arm_name}: Gripper {state} -> {target}deg")
            return
        
        channel = self._get_channel(6)
        self.driver.set_servo_angle(channel, int(target))
    
    def get_current_position(self, angles):
        """
        Forward Kinematics: Calculate end-effector position from angles.
        
        Args:
            angles: [theta1, theta2, theta3, theta4] in physical degrees
        
        Returns:
            tuple: (x, y, z) in mm
        """
        # Convert physical to mathematical angles
        theta1 = (angles[0] - self._get_zero_offset(1)) / self.directions.get(1, 1)
        theta2 = (angles[1] - self._get_zero_offset(2)) / self.directions.get(2, 1)
        theta3 = (angles[2] - self._get_zero_offset(3)) / self.directions.get(3, 1)
        
        # Forward kinematics
        theta1_rad = math.radians(theta1)
        theta2_rad = math.radians(theta2)
        theta3_rad = math.radians(theta3)
        
        # Calculate position
        r = self.a2 * math.cos(theta2_rad) + self.a3 * math.cos(theta2_rad + theta3_rad)
        z = self.d1 + self.a2 * math.sin(theta2_rad) + self.a3 * math.sin(theta2_rad + theta3_rad)
        
        x = r * math.sin(theta1_rad)
        y = r * math.cos(theta1_rad)
        
        return (x, y, z)


# Test code
if __name__ == "__main__":
    # Load config
    config_path = os.path.join(os.path.dirname(__file__), "servo_config.json")
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            full_config = json.load(f)
        
        right_config = full_config.get("right_arm", {})
        left_config = full_config.get("left_arm", {})
        
        print("=== SmartRobotArm Test ===")
        
        # Create arms (simulation mode - no driver)
        right_arm = SmartRobotArm("right_arm", right_config)
        left_arm = SmartRobotArm("left_arm", left_config)
        
        # Test IK
        print(f"\nRight Arm Link Lengths: d1={right_arm.d1}, a2={right_arm.a2}, a3={right_arm.a3}")
        print(f"Max Reach: {right_arm.max_reach}mm")
        
        # Test point
        try:
            angles = right_arm.solve_ik(0, 200, 150)
            print(f"\nIK for (0, 200, 150): {[f'{a:.1f}' for a in angles]}")
            
            # Verify with FK
            pos = right_arm.get_current_position(angles)
            print(f"FK Verification: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})")
            
        except ValueError as e:
            print(f"IK Error: {e}")
        
        # Test gripper
        right_arm.control_gripper("open")
        right_arm.control_gripper("close")
        
    else:
        print(f"Config not found: {config_path}")
