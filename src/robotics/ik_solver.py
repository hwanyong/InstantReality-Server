"""
4-DOF Analytical Inverse Kinematics Solver

Solves IK for a YPPY (Yaw-Pitch-Pitch-Yaw) robot arm structure:
- Slot 1: Base Yaw (Z-axis rotation)
- Slot 2: Shoulder Pitch (X-axis rotation in vertical plane)
- Slot 3: Elbow Pitch (X-axis rotation in vertical plane)
- Slot 4: Wrist Yaw (Z-axis rotation)

Returns multiple solutions with cost evaluation for AI integration.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class IKSolution:
    """Single IK solution with all joint angles."""
    theta1: float = 0.0  # Base Yaw (deg)
    theta2: float = 0.0  # Shoulder Pitch (deg)
    theta3: float = 0.0  # Elbow Pitch (deg)
    theta4: float = 0.0  # Wrist Yaw (deg)
    
    config_name: str = ""  # "Elbow Up", "Elbow Down", etc.
    is_valid: bool = False  # Within joint limits
    cost: float = float('inf')  # Lower is better
    
    def to_dict(self):
        return {
            'theta1': self.theta1,
            'theta2': self.theta2,
            'theta3': self.theta3,
            'theta4': self.theta4,
            'config_name': self.config_name,
            'is_valid': self.is_valid,
            'cost': self.cost
        }


@dataclass
class IKResult:
    """Result containing all solutions and metadata."""
    solutions: List[IKSolution] = field(default_factory=list)
    best_solution: Optional[IKSolution] = None
    
    target: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    is_reachable: bool = False
    error_message: str = ""
    
    # Clamping info
    was_clamped: bool = False
    clamped_target: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    
    def get_valid_solutions(self) -> List[IKSolution]:
        return [s for s in self.solutions if s.is_valid]
    
    def get_solution_names(self) -> List[str]:
        return [s.config_name for s in self.solutions if s.is_valid]


class IKSolver:
    """
    Analytical 4-DOF Inverse Kinematics Solver.
    
    Solves for Gripper Tip position (X, Y, Z) and returns all valid joint configurations.
    """
    
    def __init__(self, link_lengths: dict, joint_limits: dict):
        """
        Args:
            link_lengths: {d1, a2, a3, a4} - Link lengths in mm
            joint_limits: {slot_N: {math_min, math_max}} - Joint angle limits in deg
        """
        self.d1 = link_lengths.get('d1', 107.0)  # Base height
        self.a2 = link_lengths.get('a2', 105.0)  # Upper arm
        self.a3 = link_lengths.get('a3', 150.0)  # Forearm
        self.a4 = link_lengths.get('a4', 135.0)  # Hand (Wrist + Gripper)
        
        # Derived constant for cylindrical clamping
        self.R_ARM = self.a2 + self.a3  # Max arm reach (255.0 mm)
        
        self.limits = joint_limits
    
    def clamp_target_to_cylinder(self, x, y, z, wrist_angle=0.0):
        """
        Dynamic Cylindrical Clamping: Preserves Z-height while clamping X/Y to
        the maximum reachable radius at that height.
        
        Args:
            x, y, z: Target coordinates in mm
            wrist_angle: Wrist angle in degrees (affects effective reach)
        
        Returns:
            (x_clamped, y_clamped, z, was_clamped, error_msg)
        """
        L_BASE = self.d1
        R_ARM = self.R_ARM
        L_HAND = self.a4
        
        # 1. Calculate relative height from shoulder
        h = z - L_BASE
        
        # 2. Check vertical reachability
        if abs(h) > R_ARM:
            return x, y, z, False, f"Height unreachable: |h|={abs(h):.1f} > R_ARM={R_ARM}"
        
        # 3. Calculate arm's horizontal projection at height h
        R_arm_proj = math.sqrt(R_ARM**2 - h**2)
        
        # 4. Calculate effective hand length (wrist angle in degrees)
        L_eff = L_HAND * math.cos(math.radians(wrist_angle))
        
        # 5. Calculate max reachable radius
        R_limit = R_arm_proj + L_eff
        
        # 6. Calculate current request distance
        d = math.sqrt(x**2 + y**2)
        
        # 7. Apply clamping if exceeded
        if d > R_limit and d > 0:
            scale = R_limit / d
            return x * scale, y * scale, z, True, None
        
        return x, y, z, False, None
    
    def solve(self, target_xyz: Tuple[float, float, float], 
              gripper_direction: Optional[float] = None) -> IKResult:
        """
        Solve IK for target Gripper Tip position.
        
        Args:
            target_xyz: (X, Y, Z) target position in mm
            gripper_direction: Optional desired gripper direction (deg), 
                              None = calculate automatically
        
        Returns:
            IKResult with all valid solutions
        """
        X, Y, Z = target_xyz
        result = IKResult(target=target_xyz)
        
        # Dynamic Cylindrical Clamping - DISABLED
        # To re-enable, uncomment the following lines:
        # wrist_angle = gripper_direction if gripper_direction else 0.0
        # X, Y, Z, was_clamped, clamp_error = self.clamp_target_to_cylinder(X, Y, Z, wrist_angle)
        # if clamp_error:
        #     result.error_message = clamp_error
        #     result.is_reachable = False
        #     return result
        
        # Bypass: No clamping applied
        was_clamped = False
        result.was_clamped = was_clamped
        result.clamped_target = (X, Y, Z)
        
        # Calculate all possible θ1 candidates
        # θ1 is the base yaw angle
        base_angle = math.degrees(math.atan2(Y, X)) if (X != 0 or Y != 0) else 0.0
        theta1_candidates = [base_angle, base_angle + 180.0]
        
        for theta1 in theta1_candidates:
            # Normalize θ1 to standard range
            theta1 = self._normalize_angle(theta1)
            
            # For this robot, θ4 rotates in X-Y plane (Yaw)
            # The gripper direction in world frame = θ1 + θ4
            # If gripper_direction is specified, θ4 = gripper_direction - θ1
            if gripper_direction is not None:
                theta4 = gripper_direction - theta1
            else:
                # Auto: θ4 = 0 (gripper points in same direction as base)
                theta4 = 0.0
            
            # Calculate Wrist position by backtracking from Gripper Tip
            # Gripper Tip = Wrist + a4 * direction(θ1 + θ4)
            gripper_dir_rad = math.radians(theta1 + theta4)
            wrist_x = X - self.a4 * math.cos(gripper_dir_rad)
            wrist_y = Y - self.a4 * math.sin(gripper_dir_rad)
            wrist_z = Z  # θ4 is yaw, doesn't affect Z
            
            # Calculate R (horizontal distance from base to wrist)
            R = math.sqrt(wrist_x**2 + wrist_y**2)
            
            # Verify θ1 consistency
            wrist_angle = math.degrees(math.atan2(wrist_y, wrist_x)) if R > 0.01 else theta1
            wrist_angle = self._normalize_angle(wrist_angle)
            
            # Skip if wrist angle doesn't match θ1 (invalid configuration)
            angle_diff = abs(self._normalize_angle(theta1 - wrist_angle))
            if angle_diff > 90 and angle_diff < 270:
                continue  # Wrist behind base for this θ1
            
            # Solve 2-Link IK in R-Z plane for θ2, θ3
            elbow_solutions = self._solve_2link_ik(R, wrist_z)
            
            for theta2, theta3, config_name in elbow_solutions:
                sol = IKSolution(
                    theta1=theta1,
                    theta2=theta2,
                    theta3=theta3,
                    theta4=theta4,
                    config_name=config_name
                )
                
                # Validate joint limits
                sol.is_valid = self._validate_limits(sol)
                
                # Compute cost
                sol.cost = self._compute_cost(sol)
                
                result.solutions.append(sol)
        
        # Find best solution
        valid_solutions = result.get_valid_solutions()
        if valid_solutions:
            result.is_reachable = True
            result.best_solution = min(valid_solutions, key=lambda s: s.cost)
        else:
            result.is_reachable = False
            if len(result.solutions) == 0:
                result.error_message = "Unreachable: Target outside workspace"
            else:
                result.error_message = "Unreachable: All solutions exceed joint limits"
        
        return result
    
    def _solve_2link_ik(self, R: float, Z: float) -> List[Tuple[float, float, str]]:
        """
        Solve 2-Link planar IK in R-Z plane.
        
        Args:
            R: Horizontal distance to wrist
            Z: Height of wrist
        
        Returns:
            List of (θ2, θ3, config_name) tuples
        """
        solutions = []
        
        # Vertical offset from shoulder to target
        s = Z - self.d1
        
        # Distance from shoulder to wrist
        dist_sq = R*R + s*s
        dist = math.sqrt(dist_sq)
        
        # Reachability check
        max_reach = self.a2 + self.a3
        min_reach = abs(self.a2 - self.a3)
        
        if dist > max_reach or dist < min_reach or dist < 0.001:
            # Unreachable - return pointing solution as fallback
            theta2 = math.degrees(math.atan2(s, R)) if R > 0 else (90.0 if s >= 0 else -90.0)
            solutions.append((theta2, 0.0, "Pointing"))
            return solutions
        
        # Law of Cosines for elbow angle
        cos_theta3 = (dist_sq - self.a2**2 - self.a3**2) / (2 * self.a2 * self.a3)
        cos_theta3 = max(-1.0, min(1.0, cos_theta3))
        theta3_rad = math.acos(cos_theta3)
        
        # Shoulder angle components
        beta = math.atan2(s, R)
        cos_alpha = (self.a2**2 + dist_sq - self.a3**2) / (2 * self.a2 * dist)
        cos_alpha = max(-1.0, min(1.0, cos_alpha))
        alpha = math.acos(cos_alpha)
        
        # Elbow Up: θ2 = β + α, θ3 = -|θ3|
        theta2_up = math.degrees(beta + alpha)
        theta3_up = -math.degrees(theta3_rad)
        solutions.append((theta2_up, theta3_up, "Elbow Up"))
        
        # Elbow Down: θ2 = β - α, θ3 = +|θ3|
        theta2_down = math.degrees(beta - alpha)
        theta3_down = math.degrees(theta3_rad)
        solutions.append((theta2_down, theta3_down, "Elbow Down"))
        
        return solutions
    
    def _validate_limits(self, sol: IKSolution) -> bool:
        """Check if solution is within all joint limits."""
        checks = [
            ('slot_1', sol.theta1),
            ('slot_2', sol.theta2),
            ('slot_3', sol.theta3),
            ('slot_4', sol.theta4),
        ]
        
        for slot_name, angle in checks:
            if slot_name in self.limits:
                lim = self.limits[slot_name]
                if not (lim['math_min'] <= angle <= lim['math_max']):
                    return False
        
        return True
    
    def _compute_cost(self, sol: IKSolution) -> float:
        """
        Compute cost for a solution.
        Lower cost = better solution.
        """
        if not sol.is_valid:
            return float('inf')
        
        # Cost factors:
        # 1. Distance from neutral position (prefer centered joints)
        neutral_cost = (
            abs(sol.theta1) * 0.1 +
            abs(sol.theta2) * 0.2 +
            abs(sol.theta3) * 0.2 +
            abs(sol.theta4) * 0.1
        )
        
        # 2. Prefer Elbow Up configuration
        config_cost = 0.0 if "Up" in sol.config_name else 10.0
        
        return neutral_cost + config_cost
    
    def _normalize_angle(self, angle: float) -> float:
        """Normalize angle to [-180, 180) range."""
        while angle >= 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle
