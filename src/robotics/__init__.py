"""
Robotics Module for Gemini Robotics ER-1.5 Integration

This module provides:
- IKSolver: 5-Link Inverse Kinematics solver
- GeminiRoboticsClient: Gemini API client for vision-based robot control
- CoordinateTransformer: Gemini 0-1000 to physical mm conversion
- ServoController: Serial communication with Arduino PCA9685
- RobotCoordinator: End-to-end robot control orchestration
- AutoCalibrator: AI-powered auto-calibration system
"""

# Lazy imports to avoid loading all dependencies
def __getattr__(name):
    if name == 'IKSolver':
        from .ik_solver import IKSolver
        return IKSolver
    if name == 'IKSolution':
        from .ik_solver import IKSolution
        return IKSolution
    if name == 'IKResult':
        from .ik_solver import IKResult
        return IKResult
    if name == 'CoordinateTransformer':
        from .coord_transformer import CoordinateTransformer
        return CoordinateTransformer
    if name == 'GeminiRoboticsClient':
        from .gemini_robotics import GeminiRoboticsClient
        return GeminiRoboticsClient
    if name == 'ServoController':
        from .servo_controller import ServoController
        return ServoController
    if name == 'RobotCoordinator':
        from .coordinator import RobotCoordinator
        return RobotCoordinator
    if name == 'AutoCalibrator':
        from .auto_calibrator import AutoCalibrator
        return AutoCalibrator
    raise AttributeError(f"module 'robotics' has no attribute '{name}'")

__all__ = [
    'IKSolver',
    'IKSolution',
    'IKResult',
    'CoordinateTransformer',
    'GeminiRoboticsClient',
    'ServoController',
    'RobotCoordinator',
    'AutoCalibrator',
]
