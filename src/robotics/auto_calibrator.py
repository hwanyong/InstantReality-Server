"""
AI-Powered Auto-Calibration System

Automates camera-to-robot calibration using Gemini vision:
1. Robot base position detection
2. Grid calibration for Homography
3. Workspace size calculation
4. Reachable area mapping
5. Calibration data saving/loading
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import numpy as np

from .ik_solver import IKSolver
from .gemini_robotics import GeminiRoboticsClient
from .coordinator import RobotCoordinator


@dataclass
class CalibrationResult:
    """Complete calibration result."""
    version: str
    created_at: str
    camera: Dict
    workspace: Dict
    robot: Dict
    transform: Dict
    quality: Dict
    
    def to_dict(self) -> Dict:
        return asdict(self)


class AutoCalibrator:
    """
    AI-Powered Auto-Calibration System.
    
    Uses Gemini vision to detect gripper positions and
    compute camera-to-robot coordinate transformation.
    """
    
    DEFAULT_GRID_SIZE = 9  # 3x3 grid
    
    def __init__(
        self,
        robot: RobotCoordinator,
        camera,  # CameraManager instance
        gemini: GeminiRoboticsClient = None,
        ik_solver: IKSolver = None
    ):
        """
        Initialize auto-calibrator.
        
        Args:
            robot: RobotCoordinator instance
            camera: Camera manager with capture() method
            gemini: Optional Gemini client (uses robot's if not provided)
            ik_solver: Optional IK solver (uses robot's if not provided)
        """
        self.robot = robot
        self.camera = camera
        self.gemini = gemini or robot.gemini
        self.ik_solver = ik_solver or robot.ik_solver
        
        self.calibration_points: List[Tuple[Tuple[float, float], Tuple[int, int]]] = []
        self._progress_callback = None
    
    def set_progress_callback(self, callback):
        """Set callback for progress updates: callback(step, total, message)"""
        self._progress_callback = callback
    
    def _report_progress(self, step: int, total: int, message: str):
        """Report progress to callback if set."""
        if self._progress_callback:
            self._progress_callback(step, total, message)
    
    async def run_full_calibration(
        self,
        grid_size: int = 9,
        z_height: float = 120.0,
        save_path: str = "calibration.json"
    ) -> CalibrationResult:
        """
        Run complete auto-calibration routine.
        
        Args:
            grid_size: Number of calibration points (9=3x3, 16=4x4)
            z_height: Height for gripper during calibration (mm)
            save_path: Path to save calibration.json
        
        Returns:
            CalibrationResult with all calibration data
        """
        total_steps = 4 + grid_size
        current_step = 0
        
        result = {
            "version": "1.0",
            "created_at": datetime.now().isoformat()
        }
        
        # Step 1: Detect robot base position
        self._report_progress(current_step, total_steps, "Detecting robot base...")
        result["robot"] = await self._detect_robot_base()
        current_step += 1
        
        # Step 2: Get camera info
        self._report_progress(current_step, total_steps, "Getting camera info...")
        result["camera"] = self._get_camera_info()
        current_step += 1
        
        # Step 3: Grid calibration
        self._report_progress(current_step, total_steps, "Starting grid calibration...")
        calibration = await self._run_grid_calibration(grid_size, z_height, current_step, total_steps)
        result["transform"] = calibration["transform"]
        result["quality"] = calibration["quality"]
        current_step += grid_size
        
        # Step 4: Calculate workspace size
        self._report_progress(current_step, total_steps, "Calculating workspace...")
        result["workspace"] = self._calculate_workspace(calibration["points"])
        current_step += 1
        
        # Step 5: Map reachable area
        self._report_progress(current_step, total_steps, "Mapping reachable area...")
        result["robot"]["reachable_area"] = self._map_reachable_area()
        current_step += 1
        
        # Step 6: Calculate Z-height map (default values)
        result["transform"]["z_height_map"] = {
            "high": 150.0,
            "medium": 100.0,
            "low": 50.0,
            "ground": 10.0
        }
        
        # Save calibration
        self._save_calibration(result, save_path)
        self._report_progress(total_steps, total_steps, "Calibration complete!")
        
        return CalibrationResult(**result)
    
    async def _detect_robot_base(self) -> Dict:
        """Detect robot base position using Gemini vision."""
        # Move gripper to safe position first
        await self.robot.move_to_position(0, 200, 150)
        await asyncio.sleep(1.0)
        
        # Capture image and detect base
        frame = self.camera.capture()
        image_bytes = GeminiRoboticsClient.encode_frame(frame)
        
        response = await self.gemini.get_robot_base_position(image_bytes)
        
        return {
            "base_pixel": response["point"],  # [y, x]
            "base_physical_mm": [0, 0]
        }
    
    def _get_camera_info(self) -> Dict:
        """Get camera configuration info."""
        # Try to get from camera manager
        try:
            resolution = self.camera.resolution
        except AttributeError:
            resolution = [1920, 1080]
        
        return {
            "id": getattr(self.camera, 'camera_id', 'unknown'),
            "resolution": list(resolution),
            "distortion_coeffs": None  # Not calibrated
        }
    
    async def _run_grid_calibration(
        self,
        grid_size: int,
        z_height: float,
        start_step: int,
        total_steps: int
    ) -> Dict:
        """Run grid calibration to collect point correspondences."""
        physical_coords = []
        pixel_coords = []
        
        grid_points = self._generate_grid_points(grid_size)
        
        for i, (x, y) in enumerate(grid_points):
            self._report_progress(
                start_step + i,
                total_steps,
                f"Moving to point {i+1}/{grid_size}: ({x}, {y})"
            )
            
            # Move robot
            result = await self.robot.move_to_position(x, y, z_height)
            if not result.success:
                continue  # Skip unreachable points
            
            await asyncio.sleep(1.5)  # Wait for stabilization
            
            # Capture and detect gripper
            frame = self.camera.capture()
            image_bytes = GeminiRoboticsClient.encode_frame(frame)
            
            try:
                response = await self.gemini.get_gripper_position(image_bytes)
                
                # Store point pair
                physical_coords.append([x, y])
                pixel_coords.append([response["point"][1], response["point"][0]])  # [x, y]
                
                self.calibration_points.append(
                    ((x, y), (response["point"][1], response["point"][0]))
                )
            except Exception as e:
                print(f"Failed to detect gripper at ({x}, {y}): {e}")
                continue
        
        # Calculate Homography
        if len(physical_coords) < 4:
            raise ValueError(f"Not enough valid points: {len(physical_coords)}/4 minimum")
        
        try:
            import cv2
            H, mask = cv2.findHomography(
                np.array(pixel_coords, dtype=np.float32),
                np.array(physical_coords, dtype=np.float32),
                cv2.RANSAC
            )
            homography = H.tolist()
        except ImportError:
            # Fallback without OpenCV - use simple linear transform
            homography = self._calculate_linear_transform(pixel_coords, physical_coords)
        
        # Calculate errors
        quality = self._calculate_errors(physical_coords, pixel_coords, homography)
        
        return {
            "transform": {"homography": homography},
            "quality": quality,
            "points": list(zip(physical_coords, pixel_coords))
        }
    
    def _generate_grid_points(self, grid_size: int) -> List[Tuple[float, float]]:
        """Generate NxN grid points in robot workspace."""
        # Workspace bounds (typical for right arm)
        x_min, x_max = -250, -50
        y_min, y_max = 100, 300
        
        n = int(np.sqrt(grid_size))
        if n * n != grid_size:
            n = 3  # Default to 3x3
        
        points = []
        x_step = (x_max - x_min) / (n - 1) if n > 1 else 0
        y_step = (y_max - y_min) / (n - 1) if n > 1 else 0
        
        for i in range(n):
            for j in range(n):
                x = x_min + i * x_step
                y = y_min + j * y_step
                points.append((x, y))
        
        return points
    
    def _calculate_workspace(self, points: List[Tuple[List[float], List[int]]]) -> Dict:
        """Calculate workspace dimensions from calibration points."""
        physical = [p[0] for p in points]
        x_vals = [p[0] for p in physical]
        y_vals = [p[1] for p in physical]
        
        return {
            "width_mm": float(max(x_vals) - min(x_vals)),
            "height_mm": float(max(y_vals) - min(y_vals)),
            "origin": "bottom-right"
        }
    
    def _map_reachable_area(self) -> Dict:
        """Map reachable area using IK solver."""
        x_vals, y_vals, z_vals = [], [], []
        
        for x in range(-300, 50, 25):
            for y in range(50, 400, 25):
                for z in range(10, 220, 30):
                    result = self.ik_solver.solve(x, y, z)
                    if result.is_valid:
                        x_vals.append(x)
                        y_vals.append(y)
                        z_vals.append(z)
        
        if not x_vals:  # No valid points
            return {
                "x_range": [-280, 0],
                "y_range": [80, 350],
                "z_range": [10, 200]
            }
        
        return {
            "x_range": [min(x_vals), max(x_vals)],
            "y_range": [min(y_vals), max(y_vals)],
            "z_range": [min(z_vals), max(z_vals)]
        }
    
    def _calculate_linear_transform(
        self,
        pixel_coords: List[List[int]],
        physical_coords: List[List[float]]
    ) -> List[List[float]]:
        """Calculate simple linear transformation (fallback without OpenCV)."""
        # Use mean-based scaling
        px_mean = np.mean(pixel_coords, axis=0)
        ph_mean = np.mean(physical_coords, axis=0)
        
        px_std = np.std(pixel_coords, axis=0) + 1e-6
        ph_std = np.std(physical_coords, axis=0) + 1e-6
        
        scale_x = ph_std[0] / px_std[0]
        scale_y = ph_std[1] / px_std[1]
        
        # Simple affine transform as 3x3 homography
        return [
            [scale_x, 0, ph_mean[0] - scale_x * px_mean[0]],
            [0, scale_y, ph_mean[1] - scale_y * px_mean[1]],
            [0, 0, 1]
        ]
    
    def _calculate_errors(
        self,
        physical: List[List[float]],
        pixels: List[List[int]],
        homography: List[List[float]]
    ) -> Dict:
        """Calculate calibration error statistics."""
        H = np.array(homography)
        errors = []
        
        for (px, py), (phx, phy) in zip(pixels, physical):
            # Apply homography
            point = np.array([px, py, 1])
            transformed = H @ point
            transformed = transformed[:2] / transformed[2]
            
            # Calculate error
            error = np.sqrt((transformed[0] - phx)**2 + (transformed[1] - phy)**2)
            errors.append(error)
        
        return {
            "mean_error_mm": float(np.mean(errors)),
            "max_error_mm": float(np.max(errors)),
            "calibration_points": len(physical)
        }
    
    def _save_calibration(self, data: Dict, path: str):
        """Save calibration data to JSON file."""
        # Convert numpy arrays to lists for JSON serialization
        def convert(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            return obj
        
        # Deep convert
        json_data = json.loads(json.dumps(data, default=convert))
        
        with open(path, "w") as f:
            json.dump(json_data, f, indent=2)
    
    @staticmethod
    def load_calibration(path: str = "calibration.json") -> Dict:
        """Load calibration data from JSON file."""
        with open(path) as f:
            return json.load(f)
    
    async def verify_calibration(self, num_points: int = 3) -> Dict:
        """
        Verify calibration accuracy by moving to random points.
        
        Args:
            num_points: Number of verification points
        
        Returns:
            Dict with error statistics
        """
        import random
        
        errors = []
        grid_points = self._generate_grid_points(num_points * 2)
        test_points = random.sample(grid_points, min(num_points, len(grid_points)))
        
        for x, y in test_points:
            # Move to position
            await self.robot.move_to_position(x, y, 100)
            await asyncio.sleep(1.5)
            
            # Detect actual position
            frame = self.camera.capture()
            image_bytes = GeminiRoboticsClient.encode_frame(frame)
            
            response = await self.gemini.get_gripper_position(image_bytes)
            
            # Transform detected pixel to physical
            detected_physical = self.robot.transformer.gemini_to_physical(
                response["point"][0],
                response["point"][1],
                "low"
            )
            
            error = np.sqrt((detected_physical[0] - x)**2 + (detected_physical[1] - y)**2)
            errors.append(error)
        
        return {
            "mean_error_mm": float(np.mean(errors)),
            "max_error_mm": float(np.max(errors)),
            "verified_points": num_points
        }
