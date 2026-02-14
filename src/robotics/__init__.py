"""
Robotics Module

Business logic for robot kinematics and motion planning.
API handlers (server.py, robot_api.py) delegate to this module.
"""

from .ik_service import solve_ik, compute_pulses, compute_ik_detail, compute_ik_for_motion
from .fk_service import compute_geometry, compute_reach, compute_yaw, compute_base
from .config_cache import get_config

__all__ = [
    "solve_ik",
    "compute_pulses",
    "compute_ik_detail",
    "compute_ik_for_motion",
    "compute_geometry",
    "compute_reach",
    "compute_yaw",
    "compute_base",
    "get_config",
]

