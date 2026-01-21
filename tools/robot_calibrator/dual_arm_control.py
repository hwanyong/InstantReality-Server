"""
Dual Arm Controller
High-level controller for managing both robot arms.
Handles dispatch logic and test sequence execution.
"""

import random
import json
import os
import time

from coordinate_mapper import CoordinateMapper
from smart_robot_arm import SmartRobotArm
from servo_state import ServoState
from motion_planner import MotionPlanner
import threading


class DualArmController:
    """
    Controls both left and right robot arms.
    Dispatches tasks based on target position.
    Executes pre-defined test sequences.
    """
    
    # Test Sequences
    SEQUENCES = {
        "sweep": {
            "name": "Workspace Sweep",
            "points": [
                (500, 100),   # Far Center
                (100, 100),   # Far Left
                (900, 100),   # Far Right
                (500, 500),   # Mid Center
                (500, 900),   # Near Center
            ]
        },
        "linear": {
            "name": "Linear Accuracy",
            "points": [
                (300, 500), (400, 500), (500, 500), (600, 500), (700, 500)
            ]
        },
        "pick_place": {
            "name": "Pick and Place",
            "actions": [
                {"action": "move", "pos": (300, 400), "z": 50},
                {"action": "move", "pos": (300, 400), "z": 0},
                {"action": "grip", "state": "close"},
                {"action": "move", "pos": (300, 400), "z": 50},
                {"action": "move", "pos": (700, 400), "z": 50},
                {"action": "move", "pos": (700, 400), "z": 0},
                {"action": "grip", "state": "open"},
                {"action": "move", "pos": (700, 400), "z": 50},
            ]
        },
        "max_rect": {
            "name": "Max Rectangle (Left Arm)",
            "actions": [
                # Draw largest reachable rectangle at Z=50mm
                # Bottom-Left corner
                {"action": "move", "pos": (125, 833), "z": 50},
                # Bottom-Right corner
                {"action": "move", "pos": (425, 833), "z": 50},
                # Top-Right corner
                {"action": "move", "pos": (425, 433), "z": 50},
                # Top-Left corner
                {"action": "move", "pos": (125, 433), "z": 50},
                # Return to start
                {"action": "move", "pos": (125, 833), "z": 50},
            ]
        }
    }
    
    def __init__(self, config_path="servo_config.json", 
                 workspace_width=400, workspace_height=300,
                 driver=None):
        """
        Initialize dual arm controller.
        
        Args:
            config_path: Path to servo_config.json
            workspace_width: Workspace width in mm
            workspace_height: Workspace height in mm
            driver: SerialDriver instance (shared or None for simulation)
        """
        self.config_path = config_path
        self.driver = driver
        self.mapper = CoordinateMapper(workspace_width, workspace_height)
        
        # Load config and create arms
        self._load_config()
        
        self.left_arm = SmartRobotArm("left_arm", self.config.get("left_arm", {}), driver)
        self.right_arm = SmartRobotArm("right_arm", self.config.get("right_arm", {}), driver)
        
        # Default Z height for movements
        self.default_z = 100  # mm
        
        # Motion planner for smooth motion
        self.servo_state = ServoState()
        self.motion_planner = MotionPlanner(self.servo_state)
        
        # Sender thread for continuous communication
        self._sender_running = True
        self._sender_thread = threading.Thread(target=self._sender_thread_loop, daemon=True)
        if self.driver:
            self._sender_thread.start()
    
    def _load_config(self):
        """Load configuration from JSON file."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            raise FileNotFoundError(f"Config not found: {self.config_path}")
    
    def _sender_thread_loop(self):
        """Background thread to continuously send pending angle updates."""
        while self._sender_running:
            if self.driver:
                updates = self.servo_state.get_pending_updates()
                for channel, angle in updates:
                    self.driver.set_servo_angle(channel, int(angle))
                    self.servo_state.mark_as_sent(channel, angle)
            time.sleep(0.02)  # 50Hz update rate
    
    def stop_sender(self):
        """Stop the sender thread."""
        self._sender_running = False
    
    def dispatch(self, gemini_x):
        """
        Determine which arm should handle the target.
        
        Args:
            gemini_x: Gemini X coordinate (0-1000)
        
        Returns:
            str: "left" or "right"
        """
        return self.mapper.dispatch(gemini_x)
    
    def get_arm(self, arm_name):
        """Get arm instance by name."""
        if arm_name == "left":
            return self.left_arm
        elif arm_name == "right":
            return self.right_arm
        else:
            raise ValueError(f"Invalid arm name: {arm_name}")
    
    def move_to_gemini_coord(self, gemini_x, gemini_y, z=None, arm=None, duration=1.0):
        """
        Move to a position specified in Gemini coordinates.
        
        Args:
            gemini_x: X coordinate (0-1000)
            gemini_y: Y coordinate (0-1000)
            z: Z height in mm (uses default if None)
            arm: Force specific arm ("left" or "right"), auto-dispatch if None
            duration: Motion duration in seconds
        
        Returns:
            dict: Result with arm used and angles calculated
        """
        if z is None:
            z = self.default_z
        
        # Dispatch if arm not specified
        if arm is None:
            arm = self.dispatch(gemini_x)
        
        # Get arm instance
        arm_obj = self.get_arm(arm)
        
        # Convert coordinates
        local_x, local_y = self.mapper.map_to_local(gemini_x, gemini_y, arm)
        
        # Solve IK
        try:
            angles = arm_obj.solve_ik(local_x, local_y, z)
            
            # Use MotionPlanner for smooth motion if driver is available
            if self.driver:
                targets = arm_obj.get_servo_targets(angles)
                self.motion_planner.move_all(targets, duration)
            else:
                arm_obj.apply_motion(angles, duration)
            
            return {
                "success": True,
                "arm": arm,
                "local": (local_x, local_y, z),
                "angles": angles
            }
        except ValueError as e:
            return {
                "success": False,
                "arm": arm,
                "local": (local_x, local_y, z),
                "error": str(e)
            }
    
    def _generate_random_poke_sequence(self, count=5):
        """Generate a random poke sequence."""
        actions = []
        for _ in range(count):
            # Generate random X, Y in safe range
            gx = random.randint(100, 900)
            gy = random.randint(200, 800)
            
            # Pattern: Hover -> Poke -> Hover
            actions.append({"action": "move", "pos": (gx, gy), "z": 150}) # Hover
            actions.append({"action": "move", "pos": (gx, gy), "z": 80})  # Poke (Wrist at 80mm puts Tip at ~0mm)
            actions.append({"action": "move", "pos": (gx, gy), "z": 150}) # Hover
            
        return {"name": "Random Poke", "actions": actions}

    def run_sequence(self, sequence_name, delay=1.0, callback=None):
        """
        Execute a pre-defined test sequence.
        
        Args:
            sequence_name: Name of sequence ("sweep", "linear", "pick_place", "random_poke")
            delay: Delay between movements in seconds
            callback: Optional callback for progress updates
        
        Returns:
            list: Results of each step
        """
        if sequence_name == "random_poke":
            sequence = self._generate_random_poke_sequence()
        elif sequence_name in self.SEQUENCES:
            sequence = self.SEQUENCES[sequence_name]
        else:
            raise ValueError(f"Unknown sequence: {sequence_name}")
        results = []
        
        if callback:
            callback(f"Starting sequence: {sequence['name']}")
        
        # Handle different sequence types
        if "points" in sequence:
            # Simple point-to-point movement
            for i, point in enumerate(sequence["points"]):
                gx, gy = point
                if callback:
                    callback(f"Step {i+1}/{len(sequence['points'])}: Moving to ({gx}, {gy})")
                
                result = self.move_to_gemini_coord(gx, gy)
                results.append(result)
                time.sleep(delay)
        
        elif "actions" in sequence:
            # Action-based sequence (pick & place)
            for i, action in enumerate(sequence["actions"]):
                if callback:
                    callback(f"Step {i+1}/{len(sequence['actions'])}: {action['action']}")
                
                if action["action"] == "move":
                    gx, gy = action["pos"]
                    z = action.get("z", self.default_z)
                    result = self.move_to_gemini_coord(gx, gy, z)
                    results.append(result)
                
                elif action["action"] == "grip":
                    # Determine arm from last move
                    arm = results[-1]["arm"] if results else "left"
                    arm_obj = self.get_arm(arm)
                    arm_obj.control_gripper(action["state"])
                    results.append({"action": "grip", "state": action["state"]})
                
                time.sleep(delay)
        
        if callback:
            callback(f"Sequence complete: {len(results)} steps")
        
        return results
    
    def home(self):
        """Move both arms to home position."""
        # Get initial angles from config
        for arm_name in ["left", "right"]:
            arm_key = f"{arm_name}_arm"
            arm_config = self.config.get(arm_key, {})
            
            angles = []
            for slot in range(1, 5):
                slot_key = f"slot_{slot}"
                initial = arm_config.get(slot_key, {}).get("initial", 90)
                angles.append(initial)
            
            arm_obj = self.get_arm(arm_name)
            arm_obj.apply_motion(angles)


# Test code
if __name__ == "__main__":
    print("=== DualArmController Test ===")
    
    # Create controller (simulation mode)
    config_path = os.path.join(os.path.dirname(__file__), "servo_config.json")
    
    try:
        controller = DualArmController(config_path)
        
        # Test dispatch
        print(f"\nDispatch Test:")
        print(f"  X=200 -> {controller.dispatch(200)}")
        print(f"  X=500 -> {controller.dispatch(500)}")
        print(f"  X=800 -> {controller.dispatch(800)}")
        
        # Test move
        print(f"\nMove Test:")
        result = controller.move_to_gemini_coord(300, 400, z=100)
        print(f"  Result: {result}")
        
        # Test sequence (dry run)
        print(f"\nSequence Test (Sweep):")
        results = controller.run_sequence("sweep", delay=0.1, 
                                          callback=lambda msg: print(f"  {msg}"))
        
        print(f"\n  Total steps: {len(results)}")
        print(f"  Successful: {sum(1 for r in results if r.get('success', False))}")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
