"""
Robotics Module

Business logic for robot kinematics and motion planning.
API handlers (server.py, robot_api.py) delegate to this module.
"""

from .ik_service import solve_ik, compute_pulses, compute_ik_detail, compute_ik_for_motion
from .config_cache import get_config

__all__ = [
    "solve_ik",
    "compute_pulses",
    "compute_ik_detail",
    "compute_ik_for_motion",
    "get_config",
]
