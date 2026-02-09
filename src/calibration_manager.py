# Calibration Manager Module
# Handles calibration data persistence (pixel coordinates, homography matrix)
# Independent from servo_config.json to prevent data loss

import json
import os

# Config file path (project root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALIBRATION_PATH = os.path.join(PROJECT_ROOT, "calibration_data.json")


def load_calibration():
    """Load all calibration data from file."""
    if not os.path.exists(CALIBRATION_PATH):
        return {"_meta": {"version": "1.0"}}
    
    with open(CALIBRATION_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_calibration(data):
    """Save calibration data to file."""
    with open(CALIBRATION_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_calibration_for_role(role_name):
    """
    Get calibration data for a specific role.
    Returns calibration dict or None if not found.
    """
    data = load_calibration()
    return data.get(role_name)


def save_calibration_for_role(role_name, calibration):
    """
    Save calibration data for a specific role.
    
    calibration: {
        timestamp: ISO string,
        resolution: {width, height},
        homography_matrix: [[...], [...], [...]],
        pixel_coords: {
            vertices: {"1": {x, y}, ...},
            share_point: {x, y},
            bases: {left_arm: {x, y}, right_arm: {x, y}}
        },
        reprojection_error: float,
        is_valid: bool
    }
    """
    data = load_calibration()
    data[role_name] = calibration
    save_calibration(data)
    return calibration


def delete_calibration_for_role(role_name):
    """
    Delete calibration data for a specific role.
    Returns True if deleted, False if not found.
    """
    data = load_calibration()
    if role_name in data:
        del data[role_name]
        save_calibration(data)
        return True
    return False


def get_gripper_offsets():
    """
    Get gripper-camera offset per arm (mm, in camera image coordinates).
    Returns dict: {"right": {"dx": 0, "dy": 0}, "left": {"dx": 0, "dy": 0}}
    """
    data = load_calibration()
    return data.get("gripper_offsets", {
        "right": {"dx": 0, "dy": 0},
        "left": {"dx": 0, "dy": 0}
    })

