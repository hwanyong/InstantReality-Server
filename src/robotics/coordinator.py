"""
Robot Coordinator

Orchestrates end-to-end robot control:
1. Gemini vision analysis
2. Coordinate transformation
3. IK solving
4. Servo execution
"""

import asyncio
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

from .ik_solver import IKSolver, IKResult
from .coord_transformer import CoordinateTransformer
from .gemini_robotics import GeminiRoboticsClient
from .servo_controller import ServoController


@dataclass
class MoveResult:
    """Result of a robot move operation."""
    success: bool
    target_xyz: Tuple[float, float, float]
    ik_result: Optional[IKResult]
    error_message: Optional[str] = None


class RobotCoordinator:
    """
    High-level robot control coordinator.
    
    Combines:
    - Vision (GeminiRoboticsClient)
    - Coordinate transformation
    - IK solving
    - Servo control
    """
    
    def __init__(
        self,
        serial_port: str = "/dev/ttyUSB0",
        config_path: str = "servo_config.json",
        calibration_path: str = "calibration.json"
    ):
        """
        Initialize robot coordinator.
        
        Args:
            serial_port: Arduino serial port
            config_path: Path to servo_config.json
            calibration_path: Path to calibration.json
        """
        # Initialize components
        self.ik_solver = IKSolver(config_path)
        self.transformer = CoordinateTransformer(calibration_path=calibration_path)
        self.gemini = GeminiRoboticsClient()
        self.servo = ServoController(port=serial_port, config_path=config_path)
        
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to robot hardware."""
        self._connected = self.servo.connect()
        return self._connected
    
    def disconnect(self):
        """Disconnect from robot."""
        self.servo.disconnect()
        self._connected = False
    
    async def move_to_gemini_target(
        self,
        image_bytes: bytes,
        target_object: str,
        z_level: str = "low",
        roll: float = 90.0
    ) -> MoveResult:
        """
        Move robot to target detected by Gemini.
        
        Args:
            image_bytes: Camera image (JPEG bytes)
            target_object: Object to find (e.g., "red block")
            z_level: Height level ("high", "medium", "low", "ground")
            roll: Gripper roll angle (degrees)
        
        Returns:
            MoveResult with success status and IK result
        """
        # 1. Get target coordinates from Gemini
        try:
            gemini_result = await self.gemini.get_target_coordinates(
                image_bytes, target_object
            )
        except Exception as e:
            return MoveResult(
                success=False,
                target_xyz=(0, 0, 0),
                ik_result=None,
                error_message=f"Gemini error: {e}"
            )
        
        y_gemini = gemini_result["point"][0]
        x_gemini = gemini_result["point"][1]
        
        # 2. Transform to physical coordinates
        x_mm, y_mm, z_mm = self.transformer.gemini_to_physical(
            y_gemini, x_gemini, z_level
        )
        
        # 3. Move to physical position
        return await self.move_to_position(x_mm, y_mm, z_mm, roll)
    
    async def move_to_position(
        self,
        x: float,
        y: float,
        z: float,
        roll: float = 90.0
    ) -> MoveResult:
        """
        Move robot to physical position.
        
        Args:
            x: Physical X (mm)
            y: Physical Y (mm)
            z: Physical Z (mm)
            roll: Gripper roll (degrees)
        
        Returns:
            MoveResult with status
        """
        # 1. Solve IK
        ik_result = self.ik_solver.solve(x, y, z, roll)
        
        if not ik_result.is_valid:
            return MoveResult(
                success=False,
                target_xyz=(x, y, z),
                ik_result=ik_result,
                error_message="Position unreachable"
            )
        
        # 2. Execute movement
        if not self._connected:
            return MoveResult(
                success=False,
                target_xyz=(x, y, z),
                ik_result=ik_result,
                error_message="Robot not connected"
            )
        
        sol = ik_result.best_solution
        angles = {
            1: sol.theta1,
            2: sol.theta2,
            3: sol.theta3,
            4: sol.theta4,
            5: sol.theta5,
        }
        
        try:
            self.servo.move_to_angles(angles)
            await asyncio.sleep(0.5)  # Wait for movement
            
            return MoveResult(
                success=True,
                target_xyz=(x, y, z),
                ik_result=ik_result
            )
        except Exception as e:
            return MoveResult(
                success=False,
                target_xyz=(x, y, z),
                ik_result=ik_result,
                error_message=f"Servo error: {e}"
            )
    
    def set_gripper(self, open_percent: float = 100.0):
        """
        Set gripper open percentage.
        
        Args:
            open_percent: 0 = closed, 100 = fully open
        """
        # Map 0-100 to servo angle
        angle = (100 - open_percent) / 100 * 55.7  # Max close angle from config
        self.servo.move_servo(6, self.servo.math_angle_to_pulse(6, angle))
    
    def go_home(self):
        """Move robot to home position."""
        self.servo.go_home()
