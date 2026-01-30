"""
5-Link Inverse Kinematics Solver

Extracted from tools/robot_calibrator/ik_tester/tabs/full_slot2_view.py
Provides analytical IK for a 5-DOF robot arm with:
- θ1: Base Yaw
- θ2: Shoulder
- θ3: Elbow
- θ4: Wrist Pitch (auto-calculated for vertical approach)
- θ5: Roll (manual)
"""

import math
from dataclasses import dataclass
from typing import Optional, List, Tuple
import json


@dataclass
class IKSolution:
    """Single IK solution with joint angles."""
    theta1: float  # Base Yaw (degrees)
    theta2: float  # Shoulder (degrees)
    theta3: float  # Elbow (degrees)
    theta4: float  # Wrist Pitch (degrees)
    theta5: float  # Roll (degrees)
    is_valid: bool
    config_name: str  # "Elbow Up", "Elbow Down", "Pointing", etc.
    
    def to_dict(self) -> dict:
        return {
            "theta1": self.theta1,
            "theta2": self.theta2,
            "theta3": self.theta3,
            "theta4": self.theta4,
            "theta5": self.theta5,
        }


@dataclass
class IKResult:
    """IK computation result with multiple solutions."""
    solutions: List[IKSolution]
    is_reachable: bool
    target_xyz: Tuple[float, float, float]
    best_solution: Optional[IKSolution] = None
    
    @property
    def is_valid(self) -> bool:
        return self.is_reachable and self.best_solution is not None


class IKSolver:
    """
    5-Link Inverse Kinematics Solver
    
    Link lengths from servo_config.json:
    - d1: Base height (107mm)
    - a2: Shoulder to Elbow (105mm)
    - a3: Elbow to Wrist (150mm)
    - a4: Wrist to Roll joint (65mm)
    - a6: Gripper length (70mm)
    """
    
    def __init__(self, config_path: str = None):
        # Default link lengths (mm)
        self.d1 = 107.0  # Base height
        self.a2 = 105.0  # Shoulder to Elbow
        self.a3 = 150.0  # Elbow to Wrist
        self.a4 = 65.0   # Wrist to Roll joint
        self.a6 = 70.0   # Gripper length
        
        # Joint limits (degrees)
        self.limits = {
            "theta1": (-90.0, 90.0),
            "theta2": (-30.0, 132.4),
            "theta3": (-134.9, 125.0),
            "theta4": (-129.0, 51.0),
            "theta5": (0.0, 180.0),
        }
        
        if config_path:
            self._load_config(config_path)
    
    def _load_config(self, config_path: str):
        """Load link lengths and joint limits from servo_config.json."""
        with open(config_path) as f:
            config = json.load(f)
        
        arm = config.get("right_arm", {})
        
        # Extract link lengths
        self.d1 = arm.get("slot_1", {}).get("length", self.d1)
        self.a2 = arm.get("slot_2", {}).get("length", self.a2)
        self.a3 = arm.get("slot_3", {}).get("length", self.a3)
        self.a4 = arm.get("slot_4", {}).get("length", self.a4)
        self.a6 = arm.get("slot_6", {}).get("length", self.a6)
        
        # Extract joint limits (convert to math angles)
        for slot_key, limit_key in [("slot_2", "theta2"), ("slot_3", "theta3"), ("slot_4", "theta4")]:
            slot = arm.get(slot_key, {})
            if "min" in slot and "max" in slot:
                zero_offset = slot.get("zero_offset", 0)
                self.limits[limit_key] = (
                    slot["min"] - zero_offset,
                    slot["max"] - zero_offset
                )
    
    def forward_kinematics(
        self,
        theta1: float,
        theta2: float,
        theta3: float,
        theta4: float,
        theta5: float
    ) -> Tuple[float, float, float]:
        """
        Forward Kinematics: Calculate gripper tip position from servo angles.
        
        Args:
            theta1: Base yaw angle (degrees)
            theta2: Shoulder angle (degrees)
            theta3: Elbow angle (degrees) - note: inverted for Slot 3
            theta4: Wrist pitch angle (degrees)
            theta5: Roll angle (degrees) - does not affect position
        
        Returns:
            (x, y, z) position of gripper tip in mm
        """
        # Convert to radians
        t1 = math.radians(theta1)
        t2 = math.radians(theta2)
        t3 = math.radians(-theta3)  # Un-invert for FK calculation
        t4 = math.radians(theta4)
        
        # Calculate shoulder position (at height d1)
        # Shoulder is at base, raised by d1
        
        # Calculate elbow position relative to shoulder
        # a2 is the shoulder-to-elbow link
        elbow_r = self.a2 * math.cos(t2)
        elbow_z = self.d1 + self.a2 * math.sin(t2)
        
        # Calculate wrist position relative to elbow
        # a3 is the elbow-to-wrist link
        # Total angle from horizontal = theta2 + theta3
        wrist_angle = t2 + t3
        wrist_r = elbow_r + self.a3 * math.cos(wrist_angle)
        wrist_z = elbow_z + self.a3 * math.sin(wrist_angle)
        
        # Calculate roll joint position (a4 from wrist)
        # theta4 is wrist pitch
        roll_angle = wrist_angle + t4
        roll_r = wrist_r + self.a4 * math.cos(roll_angle)
        roll_z = wrist_z + self.a4 * math.sin(roll_angle)
        
        # Calculate gripper tip position (a6 from roll joint)
        # Gripper points down (perpendicular to roll joint)
        gripper_angle = roll_angle - math.radians(90)  # -90 for downward
        tip_r = roll_r + self.a6 * math.cos(gripper_angle)
        tip_z = roll_z + self.a6 * math.sin(gripper_angle)
        
        # Convert from polar (r, theta1) to Cartesian (x, y)
        x = tip_r * math.cos(t1)
        y = tip_r * math.sin(t1)
        z = tip_z
        
        return (x, y, z)
    
    def solve(self, x: float, y: float, z: float, roll: float = 90.0) -> IKResult:
        """
        Solve 5-Link IK for gripper tip position.
        
        Args:
            x: Target X position (mm) - right is negative
            y: Target Y position (mm) - forward is positive
            z: Target Z position (mm) - height above ground
            roll: Roll angle for gripper (degrees)
        
        Returns:
            IKResult with solutions and best solution
        """
        solutions = []
        
        # θ1: Base Yaw
        theta1 = math.degrees(math.atan2(y, x)) if (x != 0 or y != 0) else 0.0
        R = math.sqrt(x**2 + y**2)  # Horizontal distance
        
        # Gripper points down (-90°), so wrist is (a4 + a6) above target
        wrist_z = z + self.a4 + self.a6
        
        # 2-Link IK for θ2 and θ3
        theta2, theta3, is_reachable, config_name = self._solve_2link_ik(R, wrist_z)
        
        # Invert θ3 for Slot 3 servo orientation
        theta3 = -theta3
        
        # θ4: Auto-calculated for vertical approach (-90° gripper)
        # θ4 = -90 - θ2 + θ3 to keep gripper perpendicular to ground
        theta4 = -90.0 - theta2 + theta3
        
        # Create solution
        solution = IKSolution(
            theta1=theta1,
            theta2=theta2,
            theta3=theta3,
            theta4=theta4,
            theta5=roll,
            is_valid=is_reachable and self._is_valid_solution(theta2, -theta3),  # Use original θ3
            config_name=config_name
        )
        solutions.append(solution)
        
        # Find best valid solution
        best = None
        for sol in solutions:
            if sol.is_valid:
                best = sol
                break
        
        return IKResult(
            solutions=solutions,
            is_reachable=is_reachable,
            target_xyz=(x, y, z),
            best_solution=best if best else solutions[0]
        )
    
    def _solve_2link_ik(self, R: float, z: float) -> Tuple[float, float, bool, str]:
        """
        2-Link Planar IK Solver.
        
        Args:
            R: Horizontal distance from base
            z: Height (relative to ground, not shoulder)
        
        Returns:
            (theta2, theta3, is_reachable, config_name)
        """
        s = z - self.d1  # Vertical offset from shoulder
        dist_sq = R*R + s*s
        dist = math.sqrt(dist_sq)
        
        max_reach = self.a2 + self.a3
        min_reach = abs(self.a2 - self.a3)
        
        # Reachability check
        if dist > max_reach or dist < min_reach or dist == 0:
            # Pointing fallback
            theta2 = math.degrees(math.atan2(s, R)) if R > 0 else (90.0 if s >= 0 else -90.0)
            return theta2, 0.0, False, "Pointing"
        
        # Elbow angle (θ3) via Law of Cosines
        cos_theta3 = (dist_sq - self.a2**2 - self.a3**2) / (2 * self.a2 * self.a3)
        cos_theta3 = max(-1.0, min(1.0, cos_theta3))
        theta3_rad = math.acos(cos_theta3)
        
        # Shoulder angle components
        beta = math.atan2(s, R)
        cos_alpha = (self.a2**2 + dist_sq - self.a3**2) / (2 * self.a2 * dist)
        cos_alpha = max(-1.0, min(1.0, cos_alpha))
        alpha = math.acos(cos_alpha)
        
        # Try both Elbow Up and Elbow Down
        candidates = []
        
        # Elbow Up: θ2 = β + α, θ3 = -|θ3|
        theta2_up = math.degrees(beta + alpha)
        theta3_up = math.degrees(-theta3_rad)
        if self._is_valid_solution(theta2_up, theta3_up):
            candidates.append((theta2_up, theta3_up, "Elbow Up"))
        
        # Elbow Down: θ2 = β - α, θ3 = +|θ3|
        theta2_down = math.degrees(beta - alpha)
        theta3_down = math.degrees(theta3_rad)
        if self._is_valid_solution(theta2_down, theta3_down):
            candidates.append((theta2_down, theta3_down, "Elbow Down"))
        
        if not candidates:
            # No valid solution - Pointing fallback
            theta2 = math.degrees(math.atan2(s, R)) if R > 0 else (90.0 if s >= 0 else -90.0)
            return theta2, 0.0, False, "No Valid"
        
        # Prefer Elbow Up
        best = candidates[0]
        return best[0], best[1], True, best[2]
    
    def _is_valid_solution(self, theta2: float, theta3: float) -> bool:
        """Check if solution is within joint limits."""
        min2, max2 = self.limits["theta2"]
        min3, max3 = self.limits["theta3"]
        
        return (min2 <= theta2 <= max2) and (min3 <= theta3 <= max3)
    
    def get_reachable_area(self, z_height: float = 50.0, step: int = 25) -> List[Tuple[float, float]]:
        """
        Map the reachable area at a given height.
        
        Args:
            z_height: Height to test (mm)
            step: Grid step size (mm)
        
        Returns:
            List of (x, y) points that are reachable
        """
        reachable = []
        for x in range(-300, 50, step):
            for y in range(50, 400, step):
                result = self.solve(x, y, z_height)
                if result.is_valid:
                    reachable.append((x, y))
        return reachable
