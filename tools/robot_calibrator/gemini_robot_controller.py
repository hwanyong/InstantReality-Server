"""
Gemini Robot Controller
Bridges Google Gemini Robotics API (Vision output) with a 5-DOF Robot Arm.
Implements specific Geometric Vector Decomposition for Horizontal Wrist compensation.
"""

import math
import json
import time

# Hardware Integration Imports
from serial_driver import SerialDriver
from servo_manager import ServoManager
from pulse_mapper import PulseMapper

class GeminiInterface:
    """
    Parses vision data from Gemini and determines physical strategies.
    """
    
    def parse_vision_data(self, json_response):
        """
        Parse JSON response from Gemini.
        Expected format: [{"point": [y, x], "label": "label", "description": "desc"}]
        Note: Gemini returns normalized [1000, 1000] space.
        """
        if isinstance(json_response, str):
            data = json.loads(json_response)
        else:
            data = json_response
            
        if not isinstance(data, list) or not data:
            raise ValueError("Invalid Gemini response format")
        
        return data[0]

    def determine_strategy(self, description):
        """
        Determine wrist strategy based on object description.
        Returns: 
            wrist_angle (degrees): Physical angle modification for the wrist.
            reason (str): Explanation for the strategy.
        """
        desc = description.lower()
        
        if "handle" in desc and "right" in desc:
            return -90, "Hook Right (Handle is on Right)"
        elif "handle" in desc and "left" in desc:
            return 90, "Hook Left (Handle is on Left)"
        elif "horizontal" in desc or "flat" in desc:
            return 0, "Straight (Horizontal/Flat object)"
        else:
            return 0, "Straight (Default)"

class RobotArmIK:
    """
    Geometric Vector Decomposition IK Solver.
    Specifically solves for a robot with a Horizontal Wrist configuration.
    """
    
    def __init__(self, d1=107.0, a2=105.0, a3=150.0, l_hand=165.0):
        """
        Args:
            d1: Base Height (mm)
            a2: Shoulder Length (mm)
            a3: Forearm Length (mm)
            l_hand: Wrist + Gripper Center Length (mm)
        """
        self.d1 = d1
        self.a2 = a2
        self.a3 = a3
        self.l_hand = l_hand

    def solve(self, x, y, z, wrist_angle):
        """
        Solve Inverse Kinematics with Vector Decomposition.
        
        Args:
            x, y, z: Target Coordinate in Robot Frame (mm)
            wrist_angle: Desired Wrist Angle (degrees). 0=Straight, -90=Right, +90=Left
            
        Returns:
            list: [theta1, theta2, theta3, theta4] (Degrees)
        """
        # 1. Vector Decomposition
        # Calculate Effective Length (Projected length of hand on main axis)
        # and Side Offset (Lateral displacement due to wrist angle)
        rad_wrist = math.radians(wrist_angle)
        
        l_eff = self.l_hand * math.cos(rad_wrist)
        o_side = self.l_hand * math.sin(rad_wrist)
        
        # 2. Base Compensation (Theta 1)
        # We need to point the base such that the wrist ends up offset by O_side
        dist_target = math.sqrt(x**2 + y**2)
        
        # Check if target is too close for the offset
        if abs(o_side) > dist_target:
            raise ValueError(f"Target too close for offset: {o_side:.1f} > {dist_target:.1f}")
            
        # Original angle to target
        angle_to_target = math.atan2(y, x)
        
        # Offset compensation angle
        # sin(offset_angle) = O_side / Dist
        offset_angle = math.asin(o_side / dist_target)
        
        theta1_rad = angle_to_target - offset_angle
        theta1 = math.degrees(theta1_rad)
        
        # 3. Virtual Target for Planar IK (J2, J3)
        # The wrist center (J4) is at distance (Dist * cos(offset_angle)) - L_eff from origin
        # along the new Theta1 vector.
        r_wrist = (dist_target * math.cos(offset_angle)) - l_eff
        
        if r_wrist < 0:
             raise ValueError("Target too close (Negative Joint Reach)")
             
        # Z height relative to shoulder
        s = z - self.d1
        
        # Planar IK (2-Link)
        D_sq = r_wrist**2 + s**2
        D = math.sqrt(D_sq)
        
        # Law of Cosines for Elbow (Theta 3)
        cos_theta3 = (D_sq - self.a2**2 - self.a3**2) / (2 * self.a2 * self.a3)
        
        # Clamp for numerical stability
        cos_theta3 = max(-1.0, min(1.0, cos_theta3))
        theta3 = math.degrees(math.acos(cos_theta3))
        
        # IMPORTANT: "Elbow Up" vs "Elbow Down"
        # Based on SmartRobotArm logic, we typically use one configuration.
        # Assuming Elbow Up (negative theta3 logic in some systems, positive here relative to straight)
        # Let's align with the standard geometric derivation first:
        # Standard: Elbow bends "down" normally.
        # SmartRobotArm uses "Left Arm" -> Negative Theta3 (Elbow Up equivalent for that physical mount)
        # We will return the mathematical Angle, and let the Mapper handle physical conversion if needed.
        # However, this solver is generic. We'll return Standard Elbow Down (Pos) and Up (Neg).
        # We will use "Elbow Down" (Positive relative value) as default math.
        
        # Theta 2 (Shoulder)
        alpha = math.atan2(s, r_wrist)
        beta = math.atan2(self.a3 * math.sin(math.radians(theta3)), 
                          self.a2 + self.a3 * math.cos(math.radians(theta3)))
        
        theta2 = math.degrees(alpha - beta)
        
        # Theta 4 (Wrist)
        # Simplification: Absolute wrist control or relative?
        # The prompt asks for "WristMode" which implies a relative angle to the arm or global?
        # Usually Hook/Straight is relative to the forearm vector for simple grippers.
        # If the wrist is "Hooked", it is bent relative to J3.
        # Let's pass the mathematical wrist angle directly.
        theta4 = wrist_angle
        
        return [theta1, theta2, theta3, theta4]


class RobotController:
    """
    Main Orchestrator for Gemini Robot Tasks.
    """
    
    def __init__(self, config_path="servo_config.json"):
        self.gemini = GeminiInterface()
        self.ik_solver = RobotArmIK()
        
        # Hardware components
        self.servo_manager = ServoManager(config_path)
        self.pulse_mapper = PulseMapper()
        self.driver = SerialDriver()
        
        # Workspace Configuration
        self.workspace_w = 600.0  # mm
        self.workspace_h = 500.0  # mm
        self.robot_mount_x = 0    # Robot is at (0,0,0) in Robot Frame
        
    def transform_coordinates(self, gemini_point):
        """
        Transform Gemini [1000, 1000] to Robot Frame (mm).
        
        Gemini: Top-Left (0,0) -> Bottom-Right (1000,1000)
        Robot: Base is Origin (0,0).
        
        Prompt Rules:
        X_robot = (X_gem / 1000 * W) - W  (Right side mount moving Left)
        Y_robot = (1 - Y_gem / 1000) * H  (Invert Y)
        """
        y_gem, x_gem = gemini_point # Gemini returns [y, x] often, but prompt says "point: [100, 200]" usually [y,x] or [x,y]?
        # Prompt Example: "Point [300, 400] ... means Y=300, X=400"
        # So input list is [Y, X]
        
        x_rob = (x_gem / 1000.0 * self.workspace_w) - self.workspace_w
        y_rob = (1.0 - y_gem / 1000.0) * self.workspace_h
        
        return x_rob, y_rob

    def connect(self):
        """Connect to robot hardware."""
        port = self.servo_manager.get_saved_port()
        if not port:
            print("No port configured.")
            return False
            
        return self.driver.connect(port)

    def disconnect(self):
        self.driver.disconnect()

    def execute_grasp_task(self, json_response, object_height=50.0):
        """
        Execute full grasp pipeline.
        """
        print("\n--- Starting Grasp Task ---")
        
        # 1. Parse Gemini Data
        data = self.gemini.parse_vision_data(json_response)
        target_point = data["point"] # [Y, X]
        description = data["description"]
        print(f"Vision Data: Label='{data['label']}', Desc='{description}', Point={target_point}")
        
        # 2. Transform Coordinates
        x_rob, y_rob = self.transform_coordinates(target_point)
        z_rob = object_height # Should be relative to base? Prompt says Z_robot = Z_target - L1? 
        # Prompt: Z_robot = Z_target - L1. "Z_target" is usually absolute world height.
        # Let's assume object_height is Z_target. 
        # But wait, usually IK takes Z relative to base (Height above base).
        # If object is on table (Z=0 world), and Robot Base is raised (L1), then Z is negative?
        # Or Robot Base is on table? Prompt: L1=107 (Base).
        # Prompt Rule: Z_robot = Z_target - L1. 
        # If object is at height 50mm on table, and L1 is 107mm, then Z_robot = 50 - 107 = -57mm.
        # This implies the shoulder is the Z=0 plane for calculation?
        # SmartRobotArm IK: s = z - d1. "z" input is "Height above base".
        # So if we pass 50mm as Z input, SmartRobotArm does 50 - 107.
        # Our IK Solver also has s = z - d1.
        # So we should pass the Object Height relative to the table surface as "Z", 
        # provided the "d1" accounts for the base offset.
        # Yes, IK Solver init: d1=107.
        # So we pass Z = object_height (above mounting surface).
        
        print(f"Target (Robot Frame): X={x_rob:.1f}, Y={y_rob:.1f}, Z={object_height:.1f}")
        
        # 3. Determine Strategy
        wrist_angle, reason = self.gemini.determine_strategy(description)
        print(f"Strategy: {reason} (Angle: {wrist_angle}°)")
        
        # 4. Solve IK
        try:
            # We use 'left_arm' logic implicitly as per prompt "Reach to its left"
            # In SmartRobotArm, Left Arm uses negative theta3.
            # Our IK solver returns mathematical theta3.
            # We need to adapt the IK output for the physical arm if we were sending to hardware.
            # For this task, we focus on the Math Output.
            
            angles = self.ik_solver.solve(x_rob, y_rob, object_height, wrist_angle)
            print(f"Calculated Joint Angles: {['%.2f' % a for a in angles]}")
            
            return angles
            
        except ValueError as e:
            print(f"IK Failure: {e}")
            return None


# --- Verification Block (Example Scenario) ---
if __name__ == "__main__":
    print("=== Gemini Robot Controller Verification ===")
    
    # Example Scenario from Prompt
    # Gemini Output: [{"point": [300, 400], "label": "cup", "description": "handle on the right side"}]
    # Note: Point [300, 400] -> Y=300, X=400 as per prompt note.
    
    mock_response = [
        {"point": [300, 400], "label": "cup", "description": "handle on the right side"}
    ]
    
    controller = RobotController()
    
    # Execute
    angles = controller.execute_grasp_task(mock_response, object_height=50.0)
    
    if angles:
        print("\nVerification Passed: Angles generated successfully.")
        
        # Additional Check: Base Yaw Compensation
        # Target X = 400/1000 * 600 - 600 = -360
        # Target Y = (1 - 300/1000) * 500 = 350
        # Target Dist = sqrt(-360^2 + 350^2) = 502.1
        # Wrist = -90 (Right) -> O_side = 165 * sin(-90) = -165
        # Offset Angle = asin(-165 / 502.1) = -19.2 degrees
        # Original Atan2(350, -360) = 135.8 degrees
        # Theta 1 = 135.8 - (-19.2) = 155.0 degrees
        
        t1 = angles[0]
        print(f"Check Theta 1: Expected ~155.0°, Got {t1:.1f}°")
        
    else:
        print("\nVerification Failed.")
