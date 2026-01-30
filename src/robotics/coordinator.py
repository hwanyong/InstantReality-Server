"""
Robot Coordinator

Orchestrates end-to-end robot control:
1. Gemini vision analysis
2. Coordinate transformation
3. IK solving
4. Servo execution
"""

import asyncio
from typing import Dict, Tuple, Optional, Callable, Awaitable
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
    visual_verified: bool = False
    verification_confidence: float = 0.0


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
    
    async def execute_with_capture(
        self,
        camera_fn: Callable[[], bytes],
        action_fn: Callable[[], Awaitable[MoveResult]],
        stabilization_delay: float = 0.3
    ) -> Tuple[MoveResult, bytes, bytes]:
        """
        Stop-Capture-Act sequence.
        
        1. Capture BEFORE image
        2. Execute action
        3. Wait for stabilization
        4. Capture AFTER image
        
        Args:
            camera_fn: Function that returns JPEG bytes
            action_fn: Async function that performs robot action
            stabilization_delay: Wait time after action (seconds)
        
        Returns:
            (MoveResult, before_image, after_image)
        """
        # 1. Capture BEFORE
        before_image = camera_fn()
        
        # 2. Execute action
        result = await action_fn()
        
        # 3. Wait for stabilization
        await asyncio.sleep(stabilization_delay)
        
        # 4. Capture AFTER
        after_image = camera_fn()
        
        return result, before_image, after_image
    
    async def grasp_with_verification(
        self,
        camera_fn: Callable[[], bytes],
        target_object: str,
        z_level: str = "low",
        max_attempts: int = 10
    ) -> Dict:
        """
        Grasp with visual verification and retry.
        
        Args:
            camera_fn: Function that returns JPEG bytes
            target_object: Object to grasp
            z_level: Height level
            max_attempts: Maximum retry attempts (default: 10)
        
        Returns:
            {
                "success": bool,
                "attempts": int,
                "final_result": MoveResult,
                "verification_log": list
            }
        """
        verification_log = []
        
        for attempt in range(1, max_attempts + 1):
            print(f"[Grasp Attempt {attempt}/{max_attempts}]")
            
            # Capture before
            before_image = camera_fn()
            
            # Get target and move
            result = await self.move_to_gemini_target(
                before_image, target_object, z_level
            )
            
            if not result.success:
                verification_log.append({
                    "attempt": attempt,
                    "move_success": False,
                    "error": result.error_message
                })
                continue
            
            # Wait and capture after
            await asyncio.sleep(0.3)
            after_image = camera_fn()
            
            # Verify success
            verification = await self.gemini.verify_action_success(
                before_image,
                after_image,
                f"robot moved to {target_object}"
            )
            
            verified = verification.get("success", False)
            confidence = verification.get("confidence", 0.0)
            
            result.visual_verified = verified
            result.verification_confidence = confidence
            
            print(f"  Visual Verification: success={verified}, confidence={confidence:.2f}")
            
            verification_log.append({
                "attempt": attempt,
                "move_success": True,
                "verified": verified,
                "confidence": confidence,
                "reason": verification.get("reason", "")
            })
            
            if verified:
                return {
                    "success": True,
                    "attempts": attempt,
                    "final_result": result,
                    "verification_log": verification_log
                }
        
        # All attempts failed
        return {
            "success": False,
            "attempts": max_attempts,
            "final_result": result if 'result' in dir() else None,
            "verification_log": verification_log
        }
