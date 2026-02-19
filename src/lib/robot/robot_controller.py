"""
Robot Controller
Unified controller for dual-arm robot with smooth motion.
Integrates ServoState, MotionPlanner, and SerialDriver with 30Hz sender thread.
"""

import json
import time
import threading
from pathlib import Path

from .servo_state import ServoState
from .motion_planner import MotionPlanner
from .serial_driver import SerialDriver
from .pulse_mapper import PulseMapper


# Constants
SENDER_LOOP_INTERVAL = 0.033  # ~30Hz
SENDER_CMD_DELAY = 0.002  # 2ms between commands (matches calibrator_gui.py)


class RobotController:
    """
    Unified robot controller with sender thread pattern.
    Replicates calibrator_gui.py architecture for reliable motion.
    """
    
    def __init__(self, config_path=None):
        """
        Initialize robot controller.
        
        Args:
            config_path: Path to servo_config.json (defaults to project root)
        """
        # Config - use same PROJECT_ROOT calculation as server_v2.py
        if config_path is None:
            # src/lib/robot/robot_controller.py → parent.parent.parent = src/
            # src/ → parent = project root
            project_root = Path(__file__).parent.parent.parent.parent
            config_path = project_root / "servo_config.json"
        self.config_path = Path(config_path)
        self.config = {}
        self._load_config()
        
        # Core components
        self.driver = SerialDriver()
        self.servo_state = ServoState()
        self.motion_planner = MotionPlanner(self.servo_state)
        self.pulse_mapper = PulseMapper()
        
        # Sender thread
        self._sender_running = False
        self._sender_thread = None
        self._connected = False
    
    def _load_config(self):
        """Load servo configuration from JSON file."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            print(f"[RobotController] Loaded config from {self.config_path}")
        else:
            print(f"[RobotController] Config not found: {self.config_path}")
            self.config = {}
    
    def connect(self):
        """
        Connect to robot via serial port and start sender thread.
        
        Returns:
            bool: True if connected successfully
        """
        port = self.config.get("connection", {}).get("port", "COM7")
        
        if self.driver.connect(port):
            self._connected = True
            
            # Start sender thread
            self._sender_running = True
            self._sender_thread = threading.Thread(
                target=self._sender_loop, daemon=True
            )
            self._sender_thread.start()
            
            print(f"[RobotController] Connected to {port}, sender thread started")
            return True
        
        return False
    
    def disconnect(self):
        """Disconnect from robot and stop sender thread."""
        self._sender_running = False
        
        if self._sender_thread and self._sender_thread.is_alive():
            self._sender_thread.join(timeout=0.5)
        
        if self.driver:
            self.driver.disconnect()
        
        self._connected = False
        print("[RobotController] Disconnected")
    
    def is_connected(self):
        """Check connection status."""
        return self._connected and self.driver.is_connected()
    
    def _sender_loop(self):
        """
        Background thread for sending servo commands.
        Runs at ~30Hz. Only sends changed values.
        """
        while self._sender_running:
            if self._connected:
                updates = self.servo_state.get_pending_updates()
                
                for channel, pulse in updates:
                    if self.driver.write_pulse(channel, pulse):
                        self.servo_state.mark_as_sent(channel, pulse)
                    time.sleep(SENDER_CMD_DELAY)
            
            time.sleep(SENDER_LOOP_INTERVAL)
    
    def _get_channel(self, arm, slot):
        """Get PCA9685 channel for an arm/slot."""
        slot_key = f"slot_{slot}"
        return self.config.get(arm, {}).get(slot_key, {}).get("channel", slot - 1)
    
    def go_home(self, motion_time=3.0):
        """
        Move all servos to home position (initial_pulse) with smooth motion.
        
        Args:
            motion_time: Duration for motion in seconds
        
        Returns:
            bool: True if command was issued
        """
        if not self.is_connected():
            return False
        
        # Force updates
        self.servo_state.clear_history()
        
        # Build target list for both arms
        targets = []
        for arm in ["left_arm", "right_arm"]:
            arm_config = self.config.get(arm, {})
            for slot in range(1, 7):
                slot_key = f"slot_{slot}"
                slot_config = arm_config.get(slot_key, {})
                initial_pulse = slot_config.get("initial_pulse", 1500)
                channel = slot_config.get("channel", slot - 1)
                targets.append((channel, initial_pulse))
        
        # Execute smooth motion
        self.motion_planner.move_all(targets, motion_time)
        self.motion_planner.wait_for_completion(timeout=motion_time + 2.0)
        return True
    
    def go_zero(self, motion_time=3.0):
        """
        Move all servos to zero position (zero_pulse) with smooth motion.
        
        Args:
            motion_time: Duration for motion in seconds
        
        Returns:
            bool: True if command was issued
        """
        if not self.is_connected():
            return False
        
        # Force updates
        self.servo_state.clear_history()
        
        # Build target list for both arms
        targets = []
        for arm in ["left_arm", "right_arm"]:
            arm_config = self.config.get(arm, {})
            for slot in range(1, 7):
                slot_key = f"slot_{slot}"
                slot_config = arm_config.get(slot_key, {})
                zero_pulse = slot_config.get("zero_pulse", 1500)
                channel = slot_config.get("channel", slot - 1)
                targets.append((channel, zero_pulse))
        
        # Execute smooth motion
        self.motion_planner.move_all(targets, motion_time)
        self.motion_planner.wait_for_completion(timeout=motion_time + 2.0)
        return True
    
    def release_all(self):
        """Release all servos (E-STOP)."""
        if self.driver:
            self.driver.release_all()
        self.servo_state.clear_history()
    
    def get_status(self):
        """Get controller status."""
        return {
            "connected": self.is_connected(),
            "port": self.config.get("connection", {}).get("port", ""),
            "sender_running": self._sender_running
        }
    
    def move_to_pulses(self, targets, motion_time=2.0, wait=False):
        """
        Move specified channels to target pulses with smooth motion.
        
        Args:
            targets: List of (channel, pulse) tuples
            motion_time: Duration for motion in seconds
            wait: If True, block until motion completes
        
        Returns:
            bool: True if command was issued
        """
        if not self.is_connected():
            return False
        
        self.servo_state.clear_history()
        self.motion_planner.move_all(targets, motion_time)
        if wait:
            self.motion_planner.wait_for_completion(timeout=motion_time + 2.0)
        return True
    
    def _normalize_arm(self, arm):
        """Normalize arm parameter to config key."""
        if arm in ("left_arm", "right_arm"):
            return arm
        if arm == "left":
            return "left_arm"
        return "right_arm"
    
    def open_gripper(self, arm="right", motion_time=0.5):
        """
        Open the gripper (slot_6 → min_pulse).
        
        Args:
            arm: "left", "right", "left_arm", or "right_arm"
            motion_time: Duration for motion in seconds
        
        Returns:
            bool: True if command was issued
        """
        if not self.is_connected():
            return False
        
        arm_key = self._normalize_arm(arm)
        slot_config = self.config.get(arm_key, {}).get("slot_6", {})
        channel = slot_config.get("channel", 5)
        open_pulse = slot_config.get("min_pulse", 500)
        
        print(f"[RobotController] open_gripper({arm_key}) ch={channel} pulse={open_pulse}")
        return self.move_to_pulses([(channel, open_pulse)], motion_time, wait=True)
    
    def close_gripper(self, arm="right", motion_time=0.5):
        """
        Close the gripper (slot_6 → max_pulse_limit).
        
        Args:
            arm: "left", "right", "left_arm", or "right_arm"
            motion_time: Duration for motion in seconds
        
        Returns:
            bool: True if command was issued
        """
        if not self.is_connected():
            return False
        
        arm_key = self._normalize_arm(arm)
        slot_config = self.config.get(arm_key, {}).get("slot_6", {})
        channel = slot_config.get("channel", 5)
        close_pulse = slot_config.get("max_pulse_limit", 1250)
        
        print(f"[RobotController] close_gripper({arm_key}) ch={channel} pulse={close_pulse}")
        return self.move_to_pulses([(channel, close_pulse)], motion_time, wait=True)
