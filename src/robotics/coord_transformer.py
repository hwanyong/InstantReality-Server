"""
Coordinate Transformer for Gemini Robotics

Converts between:
- Gemini normalized coordinates (0-1000)
- Physical robot coordinates (mm)

Also handles:
- Z-height mapping (high/medium/low/ground)
- Calibration data loading/saving
"""

import json
from dataclasses import dataclass
from typing import Optional, Dict, Tuple
import numpy as np


@dataclass
class CalibrationData:
    """Calibration data structure."""
    version: str
    homography: Optional[np.ndarray]
    workspace_width: float
    workspace_height: float
    robot_base_pixel: Tuple[int, int]
    robot_base_physical: Tuple[float, float]
    z_height_map: Dict[str, float]
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CalibrationData':
        return cls(
            version=data.get("version", "1.0"),
            homography=np.array(data["transform"]["homography"]) if data.get("transform", {}).get("homography") else None,
            workspace_width=data.get("workspace", {}).get("width_mm", 600.0),
            workspace_height=data.get("workspace", {}).get("height_mm", 500.0),
            robot_base_pixel=tuple(data.get("robot", {}).get("base_pixel", [850, 950])),
            robot_base_physical=tuple(data.get("robot", {}).get("base_physical_mm", [0, 0])),
            z_height_map=data.get("transform", {}).get("z_height_map", {
                "high": 150.0, "medium": 100.0, "low": 50.0, "ground": 10.0
            })
        )


class CoordinateTransformer:
    """
    Transform between Gemini vision coordinates and physical robot coordinates.
    
    Gemini returns normalized [y, x] coordinates in 0-1000 range.
    Physical coordinates are in mm with robot base as origin.
    
    Coordinate System (Bottom-Mount, Right Arm):
    - Physical X: Negative is right (towards arm)
    - Physical Y: Positive is forward (away from base)
    - Physical Z: Height above ground
    """
    
    # Default Z-Height mapping
    Z_HEIGHT_MAP = {
        "high": 150.0,    # Safe movement height
        "medium": 100.0,  # Intermediate height
        "low": 50.0,      # Grasping height
        "ground": 10.0    # Near ground
    }
    
    def __init__(self, 
                 workspace_w: float = 600.0, 
                 workspace_h: float = 500.0,
                 base_height: float = 107.0,
                 calibration_path: str = None):
        """
        Initialize coordinate transformer.
        
        Args:
            workspace_w: Workspace width in mm
            workspace_h: Workspace height in mm
            base_height: Robot base height (d1) in mm
            calibration_path: Path to calibration.json
        """
        self.workspace_w = workspace_w
        self.workspace_h = workspace_h
        self.base_height = base_height
        self.homography = None
        self.calibration = None
        
        if calibration_path:
            self.load_calibration(calibration_path)
    
    def load_calibration(self, path: str) -> bool:
        """Load calibration data from JSON file."""
        try:
            with open(path) as f:
                data = json.load(f)
            
            self.calibration = CalibrationData.from_dict(data)
            self.workspace_w = self.calibration.workspace_width
            self.workspace_h = self.calibration.workspace_height
            self.homography = self.calibration.homography
            
            if self.calibration.z_height_map:
                self.Z_HEIGHT_MAP = self.calibration.z_height_map
            
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"Error loading calibration: {e}")
            return False
    
    def gemini_to_physical(self, y_gemini: int, x_gemini: int, z_level: str = "low") -> Tuple[float, float, float]:
        """
        Convert Gemini 0-1000 coordinates to physical mm coordinates.
        
        Args:
            y_gemini: Gemini Y coordinate (0-1000, top to bottom)
            x_gemini: Gemini X coordinate (0-1000, left to right)
            z_level: "high", "medium", "low", "ground" or direct mm value
        
        Returns:
            (x_mm, y_mm, z_mm) in physical robot coordinates
        """
        # If homography calibration is available, use it
        if self.homography is not None:
            return self._apply_homography(y_gemini, x_gemini, z_level)
        
        # Otherwise use linear transformation
        # Bottom-Mount, Right Arm configuration:
        # - Camera top-left (0,0) maps to workspace top-left
        # - Robot base is at bottom-right
        
        x_mm = (x_gemini / 1000.0 * self.workspace_w) - self.workspace_w  # Right is negative
        y_mm = (1.0 - y_gemini / 1000.0) * self.workspace_h  # Y-axis inverted! Forward is positive
        
        # Z height determination
        if isinstance(z_level, str):
            z_mm = self.Z_HEIGHT_MAP.get(z_level, 50.0)
        else:
            z_mm = float(z_level)
        
        return (x_mm, y_mm, z_mm)
    
    def _apply_homography(self, y_gemini: int, x_gemini: int, z_level: str) -> Tuple[float, float, float]:
        """Apply homography transformation."""
        cv2 = _get_cv2()
        if cv2 is None:
            raise ImportError("OpenCV (cv2) required for homography transformation")
        
        # Convert to pixel coordinates (assuming 1000 = image size)
        point = np.array([[x_gemini, y_gemini]], dtype=np.float32).reshape(-1, 1, 2)
        
        # Apply homography
        transformed = cv2.perspectiveTransform(point, self.homography)
        x_mm, y_mm = transformed[0][0]
        
        # Z height
        if isinstance(z_level, str):
            z_mm = self.Z_HEIGHT_MAP.get(z_level, 50.0)
        else:
            z_mm = float(z_level)
        
        return (float(x_mm), float(y_mm), z_mm)
    
    def physical_to_gemini(self, x_mm: float, y_mm: float) -> Tuple[int, int]:
        """
        Convert physical mm coordinates to Gemini 0-1000 coordinates.
        
        Args:
            x_mm: Physical X coordinate (mm)
            y_mm: Physical Y coordinate (mm)
        
        Returns:
            (y_gemini, x_gemini) in 0-1000 range
        """
        # Inverse of gemini_to_physical
        x_gemini = int((x_mm + self.workspace_w) / self.workspace_w * 1000)
        y_gemini = int((1.0 - y_mm / self.workspace_h) * 1000)
        
        # Clamp to valid range
        x_gemini = max(0, min(1000, x_gemini))
        y_gemini = max(0, min(1000, y_gemini))
        
        return (y_gemini, x_gemini)
    
    def get_z_height(self, level: str) -> float:
        """Get Z height in mm for a given level."""
        return self.Z_HEIGHT_MAP.get(level, 50.0)
    
    def save_calibration(self, path: str, calibration_data: dict) -> bool:
        """
        Save calibration data to JSON file.
        
        Args:
            path: Path to save calibration.json
            calibration_data: Full calibration data dict
        
        Returns:
            True if successful
        """
        try:
            # Ensure numpy arrays are converted to lists
            def convert_numpy(obj):
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                if isinstance(obj, (np.floating, np.integer)):
                    return float(obj) if isinstance(obj, np.floating) else int(obj)
                return obj
            
            # Deep convert
            import copy
            data = copy.deepcopy(calibration_data)
            
            def recursive_convert(d):
                if isinstance(d, dict):
                    return {k: recursive_convert(v) for k, v in d.items()}
                elif isinstance(d, list):
                    return [recursive_convert(v) for v in d]
                else:
                    return convert_numpy(d)
            
            data = recursive_convert(data)
            
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving calibration: {e}")
            return False
    
    def update_from_calibration(self, calibration_data: dict) -> None:
        """
        Update transformer settings from calibration data dict.
        
        Args:
            calibration_data: Calibration data dict (from auto_calibrator)
        """
        self.calibration = CalibrationData.from_dict(calibration_data)
        self.workspace_w = self.calibration.workspace_width
        self.workspace_h = self.calibration.workspace_height
        self.homography = self.calibration.homography
        
        if self.calibration.z_height_map:
            self.Z_HEIGHT_MAP = self.calibration.z_height_map


# Import cv2 lazily to avoid import errors
def _get_cv2():
    try:
        import cv2
        return cv2
    except ImportError:
        return None

