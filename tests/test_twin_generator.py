"""
Unit Tests for Twin Generator Module

Tests the VR JSON and GLB generation pipeline.
"""

import sys
import os
import json
import unittest

# Add project src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

# Check for trimesh availability
try:
    import trimesh
    HAS_TRIMESH = True
except ImportError:
    HAS_TRIMESH = False


class TestColorMapping(unittest.TestCase):
    """Test get_color_rgba utility."""

    @classmethod
    def setUpClass(cls):
        from twin_generator import get_color_rgba
        cls.get_color_rgba = staticmethod(get_color_rgba)

    def test_known_colors(self):
        """Known colors return correct RGBA."""
        red = self.get_color_rgba('red')
        self.assertEqual(red, [255, 0, 0, 255])

        blue = self.get_color_rgba('Blue')
        self.assertEqual(blue, [0, 0, 255, 255])

    def test_unknown_color_returns_gray(self):
        """Unknown colors return default gray."""
        gray = self.get_color_rgba('magenta')
        self.assertEqual(gray, [128, 128, 128, 255])

    def test_case_insensitive(self):
        """Color lookup is case-insensitive."""
        upper = self.get_color_rgba('RED')
        lower = self.get_color_rgba('red')
        self.assertEqual(upper, lower)


class TestBuildTwinJson(unittest.TestCase):
    """Test VR JSON generation from scan results."""

    @classmethod
    def setUpClass(cls):
        from twin_generator import build_twin_json, _box2d_center, _extract_color_from_label
        cls.build_twin_json = staticmethod(build_twin_json)
        cls.box2d_center = staticmethod(_box2d_center)
        cls.extract_color = staticmethod(_extract_color_from_label)

    def test_box2d_center(self):
        """Center calculated correctly from box_2d."""
        center = self.box2d_center([100, 200, 300, 400])
        self.assertAlmostEqual(center['gx'], 300.0)
        self.assertAlmostEqual(center['gy'], 200.0)

    def test_extract_color_from_label(self):
        """Color extracted from various label formats."""
        self.assertEqual(self.extract_color('red cup'), 'red')
        self.assertEqual(self.extract_color('Blue_Dice'), 'blue')
        self.assertEqual(self.extract_color('mystery object'), 'gray')

    def test_build_json_basic(self):
        """Basic JSON generation structure."""
        scan_result = {
            'objects': [
                {'label': 'red cube', 'box_2d': [400, 300, 600, 500]},
                {'label': 'blue marker', 'box_2d': [100, 100, 200, 200]},
            ]
        }
        # No Homography — uses fallback coordinates
        cal = {}

        result = self.build_twin_json(scan_result, cal)

        self.assertIn('timestamp', result)
        self.assertIn('objects', result)
        self.assertEqual(len(result['objects']), 2)

        obj0 = result['objects'][0]
        self.assertIn('id', obj0)
        self.assertIn('transform', obj0)
        self.assertIn('position', obj0['transform'])
        self.assertIn('rotation', obj0['transform'])
        self.assertIn('scale', obj0['transform'])
        self.assertEqual(obj0['properties']['color'], 'red')

    def test_build_json_skips_invalid_box(self):
        """Objects without valid box_2d are skipped."""
        scan_result = {
            'objects': [
                {'label': 'no box'},
                {'label': 'bad box', 'box_2d': [100]},
                {'label': 'good box', 'box_2d': [0, 0, 100, 100]},
            ]
        }
        result = self.build_twin_json(scan_result, {})
        self.assertEqual(len(result['objects']), 1)

    def test_build_json_empty_scan(self):
        """Empty scan result produces empty objects list."""
        result = self.build_twin_json({'objects': []}, {})
        self.assertEqual(len(result['objects']), 0)


@unittest.skipUnless(HAS_TRIMESH, "trimesh not available")
class TestBuildTwinGlb(unittest.TestCase):
    """Test GLB binary generation."""

    @classmethod
    def setUpClass(cls):
        from twin_generator import build_twin_json, build_twin_glb
        cls.build_twin_json = staticmethod(build_twin_json)
        cls.build_twin_glb = staticmethod(build_twin_glb)

    def _make_sample_json(self):
        """Create a sample twin JSON for testing."""
        scan = {
            'objects': [
                {'label': 'red dice', 'box_2d': [400, 300, 500, 400]},
                {'label': 'blue dice', 'box_2d': [200, 600, 300, 700]},
            ]
        }
        return self.build_twin_json(scan, {})

    def test_glb_output_bytes(self):
        """GLB output is bytes of at least minimal size."""
        twin_json = self._make_sample_json()
        glb = self.build_twin_glb(twin_json)

        self.assertIsInstance(glb, bytes)
        self.assertGreater(len(glb), 100)

    def test_glb_magic_bytes(self):
        """GLB starts with glTF magic bytes."""
        twin_json = self._make_sample_json()
        glb = self.build_twin_glb(twin_json)

        # glTF magic: 0x46546C67 = "glTF" in ASCII
        self.assertEqual(glb[:4], b'glTF')

    def test_glb_empty_scene(self):
        """Empty scene still produces valid GLB."""
        twin_json = {'objects': [], 'dice_size_mm': 20.0}
        glb = self.build_twin_glb(twin_json)
        self.assertIsInstance(glb, bytes)

    def test_glb_validates_with_trimesh(self):
        """Generated GLB can be re-loaded by trimesh."""
        twin_json = self._make_sample_json()
        glb = self.build_twin_glb(twin_json)

        import io
        loaded = trimesh.load(io.BytesIO(glb), file_type='glb')
        self.assertIsNotNone(loaded)


if __name__ == '__main__':
    unittest.main(verbosity=2)
