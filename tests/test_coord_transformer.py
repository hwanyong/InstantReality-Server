"""
Unit Tests for Coordinate Transformer

Tests the coordinate transformation between:
- Gemini normalized coordinates (0-1000)
- Physical robot coordinates (mm)
"""

import sys
import os
import json
import unittest
import tempfile

# Check for numpy availability
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

@unittest.skipUnless(HAS_NUMPY, "numpy not available")
class TestCoordinateTransformer(unittest.TestCase):
    """Test coordinate transformation."""
    
    @classmethod
    def setUpClass(cls):
        """Import and initialize transformer."""
        from src.robotics.coord_transformer import CoordinateTransformer, CalibrationData
        cls.CoordinateTransformer = CoordinateTransformer
        cls.CalibrationData = CalibrationData
    
    def setUp(self):
        """Create fresh transformer for each test."""
        self.transformer = self.CoordinateTransformer(
            workspace_w=600.0,
            workspace_h=500.0
        )
    
    def test_init_defaults(self):
        """Test default initialization."""
        t = CoordinateTransformer()
        self.assertEqual(t.workspace_w, 600.0)
        self.assertEqual(t.workspace_h, 500.0)
        self.assertIsNone(t.homography)
    
    def test_gemini_to_physical_origin(self):
        """Test converting Gemini origin (0,0) to physical."""
        x, y, z = self.transformer.gemini_to_physical(0, 0, "low")
        
        # Top-left should map to far-left, far-forward
        self.assertEqual(x, -600.0)  # Far left
        self.assertEqual(y, 500.0)   # Far forward
    
    def test_gemini_to_physical_bottom_right(self):
        """Test converting Gemini (1000, 1000) to physical."""
        x, y, z = self.transformer.gemini_to_physical(1000, 1000, "low")
        
        # Bottom-right should map to robot base area
        self.assertEqual(x, 0.0)
        self.assertEqual(y, 0.0)
    
    def test_gemini_to_physical_center(self):
        """Test converting Gemini center to physical."""
        x, y, z = self.transformer.gemini_to_physical(500, 500, "low")
        
        self.assertAlmostEqual(x, -300.0, delta=1.0)
        self.assertAlmostEqual(y, 250.0, delta=1.0)
    
    def test_z_height_levels(self):
        """Test Z height mapping for different levels."""
        _, _, z_high = self.transformer.gemini_to_physical(500, 500, "high")
        _, _, z_med = self.transformer.gemini_to_physical(500, 500, "medium")
        _, _, z_low = self.transformer.gemini_to_physical(500, 500, "low")
        _, _, z_ground = self.transformer.gemini_to_physical(500, 500, "ground")
        
        self.assertEqual(z_high, 150.0)
        self.assertEqual(z_med, 100.0)
        self.assertEqual(z_low, 50.0)
        self.assertEqual(z_ground, 10.0)
    
    def test_z_height_direct_mm(self):
        """Test passing direct mm value for Z."""
        _, _, z = self.transformer.gemini_to_physical(500, 500, 75.5)
        self.assertEqual(z, 75.5)
    
    def test_physical_to_gemini_roundtrip(self):
        """Test converting back from physical to Gemini."""
        # Original Gemini coords
        y_g, x_g = 400, 600
        
        # To physical
        x_mm, y_mm, _ = self.transformer.gemini_to_physical(y_g, x_g, "low")
        
        # Back to Gemini
        y_back, x_back = self.transformer.physical_to_gemini(x_mm, y_mm)
        
        self.assertAlmostEqual(y_back, y_g, delta=1)
        self.assertAlmostEqual(x_back, x_g, delta=1)
    
    def test_get_z_height(self):
        """Test get_z_height helper."""
        self.assertEqual(self.transformer.get_z_height("high"), 150.0)
        self.assertEqual(self.transformer.get_z_height("invalid"), 50.0)  # Default


class TestCalibrationLoading(unittest.TestCase):
    """Test calibration file loading."""
    
    def test_load_missing_file(self):
        """Test loading non-existent file."""
        t = CoordinateTransformer()
        result = t.load_calibration("/nonexistent/path.json")
        self.assertFalse(result)
    
    def test_load_valid_calibration(self):
        """Test loading valid calibration file."""
        # Create temp calibration file
        cal_data = {
            "version": "1.0",
            "workspace": {"width_mm": 400.0, "height_mm": 300.0},
            "robot": {"base_pixel": [500, 800], "base_physical_mm": [0, 0]},
            "transform": {
                "homography": None,
                "z_height_map": {"high": 200.0, "low": 30.0}
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(cal_data, f)
            temp_path = f.name
        
        try:
            t = CoordinateTransformer()
            result = t.load_calibration(temp_path)
            
            self.assertTrue(result)
            self.assertEqual(t.workspace_w, 400.0)
            self.assertEqual(t.workspace_h, 300.0)
            self.assertEqual(t.Z_HEIGHT_MAP["high"], 200.0)
        finally:
            os.unlink(temp_path)
    
    def test_save_calibration(self):
        """Test saving calibration data."""
        t = CoordinateTransformer()
        
        cal_data = {
            "version": "1.0",
            "workspace": {"width_mm": 500.0, "height_mm": 400.0},
            "quality": {"mean_error_mm": 5.5}
        }
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            result = t.save_calibration(temp_path, cal_data)
            self.assertTrue(result)
            
            # Verify saved data
            with open(temp_path) as f:
                saved = json.load(f)
            
            self.assertEqual(saved["version"], "1.0")
            self.assertEqual(saved["workspace"]["width_mm"], 500.0)
        finally:
            os.unlink(temp_path)


class TestCalibrationData(unittest.TestCase):
    """Test CalibrationData dataclass."""
    
    def test_from_dict_minimal(self):
        """Test creating CalibrationData from minimal dict."""
        data = {"version": "1.0"}
        cal = CalibrationData.from_dict(data)
        
        self.assertEqual(cal.version, "1.0")
        self.assertIsNone(cal.homography)
        self.assertEqual(cal.workspace_width, 600.0)  # Default
    
    def test_from_dict_full(self):
        """Test creating CalibrationData from full dict."""
        data = {
            "version": "2.0",
            "workspace": {"width_mm": 800.0, "height_mm": 600.0},
            "robot": {
                "base_pixel": [400, 700],
                "base_physical_mm": [10, 20]
            },
            "transform": {
                "homography": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "z_height_map": {"custom": 75.0}
            }
        }
        cal = CalibrationData.from_dict(data)
        
        self.assertEqual(cal.version, "2.0")
        self.assertEqual(cal.workspace_width, 800.0)
        self.assertEqual(cal.robot_base_pixel, (400, 700))
        self.assertIsNotNone(cal.homography)
        self.assertEqual(cal.z_height_map["custom"], 75.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
