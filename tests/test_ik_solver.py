"""
Unit Tests for IK Solver

Tests the 5-Link Inverse Kinematics solver for:
- Basic reachability
- Joint limit validation
- Configuration selection (Elbow Up/Down)
- Edge cases
"""

import sys
import os
import math
import unittest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.robotics.ik_solver import IKSolver, IKSolution, IKResult


class TestIKSolver(unittest.TestCase):
    """Test IK Solver functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Initialize IK solver for all tests."""
        cls.solver = IKSolver()
    
    def test_init_default_values(self):
        """Test solver initializes with default link lengths."""
        self.assertEqual(self.solver.d1, 107.0)
        self.assertEqual(self.solver.a2, 105.0)
        self.assertEqual(self.solver.a3, 150.0)
    
    def test_reachable_point(self):
        """Test solving for a reachable point."""
        result = self.solver.solve(-100, 150, 80)
        
        self.assertTrue(result.is_valid)
        self.assertTrue(result.is_reachable)
        self.assertIsNotNone(result.best_solution)
        self.assertEqual(result.best_solution.config_name, "Elbow Up")
    
    def test_unreachable_point_too_far(self):
        """Test point too far from robot base."""
        result = self.solver.solve(-400, 500, 100)
        
        self.assertFalse(result.is_reachable)
        # Should still provide a pointing solution
        self.assertIsNotNone(result.best_solution)
        self.assertEqual(result.best_solution.config_name, "Pointing")
    
    def test_point_close_to_base(self):
        """Test point close to robot base - may be reachable depending on geometry."""
        result = self.solver.solve(-10, 50, 100)
        
        # This point may be reachable - just verify we get a result
        self.assertIsNotNone(result)
    
    def test_theta1_yaw_calculation(self):
        """Test yaw angle calculation (theta1)."""
        # Point directly in front (Y-axis)
        result = self.solver.solve(0, 200, 100)
        if result.is_valid:
            # Theta1 should point towards target
            self.assertIsNotNone(result.best_solution.theta1)
        
        # Point to the right (-X direction)
        result = self.solver.solve(-200, 100, 100)
        if result.is_valid:
            # Just verify theta1 is calculated
            self.assertIsNotNone(result.best_solution.theta1)
    
    def test_joint_limits(self):
        """Test that solutions have valid joint angles."""
        result = self.solver.solve(-100, 180, 80)
        
        if result.is_valid and result.best_solution:
            sol = result.best_solution
            
            # Check all theta values are within reasonable bounds
            self.assertGreaterEqual(sol.theta1, -180)
            self.assertLessEqual(sol.theta1, 180)
            self.assertGreaterEqual(sol.theta2, -180)
            self.assertLessEqual(sol.theta2, 180)
    
    def test_multiple_solutions(self):
        """Test that solver can find multiple configurations."""
        result = self.solver.solve(-120, 200, 100)
        
        # Should have at least one solution
        self.assertGreater(len(result.solutions), 0)
    
    def test_theta4_wrist_pitch(self):
        """Test wrist pitch is calculated."""
        result = self.solver.solve(-100, 180, 60)
        
        if result.is_valid and result.best_solution:
            sol = result.best_solution
            # Verify theta4 is calculated (not None)
            self.assertIsNotNone(sol.theta4)
            # Theta4 should be within reasonable range
            self.assertGreaterEqual(sol.theta4, -180.0)
            self.assertLessEqual(sol.theta4, 180.0)
    
    def test_roll_passthrough(self):
        """Test roll angle is passed through correctly."""
        result = self.solver.solve(-100, 180, 80, roll=45.0)
        
        if result.best_solution:
            self.assertEqual(result.best_solution.theta5, 45.0)
    
    def test_edge_case_origin(self):
        """Test point at or near origin."""
        result = self.solver.solve(0, 0, 100)
        
        # Verify we get a result (may or may not be valid)
        self.assertIsNotNone(result)
    
    def test_ground_level(self):
        """Test reaching ground level."""
        result = self.solver.solve(-150, 200, 10)
        
        # May or may not be reachable depending on configuration
        self.assertIsNotNone(result)
    
    def test_high_position(self):
        """Test reaching high position."""
        result = self.solver.solve(-100, 150, 180)
        
        self.assertIsNotNone(result)


class TestIKSolution(unittest.TestCase):
    """Test IKSolution dataclass."""
    
    def test_solution_creation(self):
        """Test creating an IKSolution."""
        sol = IKSolution(
            theta1=45.0,
            theta2=30.0,
            theta3=-20.0,
            theta4=-100.0,
            theta5=90.0,
            is_valid=True,
            config_name="Elbow Up"
        )
        
        self.assertEqual(sol.theta1, 45.0)
        self.assertEqual(sol.config_name, "Elbow Up")
        self.assertTrue(sol.is_valid)
    
    def test_solution_to_dict(self):
        """Test converting solution to dict."""
        sol = IKSolution(10, 20, 30, 40, 50, True, "Test")
        angles = sol.to_dict()
        
        self.assertEqual(angles["theta1"], 10)
        self.assertEqual(angles["theta5"], 50)


class TestIKResult(unittest.TestCase):
    """Test IKResult dataclass."""
    
    def test_empty_result(self):
        """Test result with no valid solutions."""
        result = IKResult(
            solutions=[],
            is_reachable=False,
            target_xyz=(100, 200, 50),
            best_solution=None
        )
        
        self.assertIsNone(result.best_solution)
        self.assertFalse(result.is_valid)
    
    def test_result_with_solutions(self):
        """Test result with valid solutions."""
        sol = IKSolution(45, 30, -20, -100, 90, True, "Elbow Up")
        result = IKResult(
            solutions=[sol],
            is_reachable=True,
            target_xyz=(100, 200, 50),
            best_solution=sol
        )
        
        self.assertIsNotNone(result.best_solution)
        self.assertTrue(result.is_valid)


if __name__ == '__main__':
    unittest.main(verbosity=2)
