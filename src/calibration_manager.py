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


def compute_mm_per_pixel(role_name):
    """
    Compute mm_per_pixel for a calibrated role using vertex diagonal distance.
    Returns float or None if calibration/geometry data is missing.
    """
    import math

    cal = get_calibration_for_role(role_name)
    if not cal:
        return None

    vertices_px = cal.get("pixel_coords", {}).get("vertices", {})
    if "1" not in vertices_px or "3" not in vertices_px:
        return None

    # Load geometry vertices (mm) from servo_config.json
    config_path = os.path.join(PROJECT_ROOT, "servo_config.json")
    if not os.path.exists(config_path):
        return None

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    vertices_mm = config.get("geometry", {}).get("vertices", {})
    if "1" not in vertices_mm or "3" not in vertices_mm:
        return None

    # Diagonal distance: vertex 1 → vertex 3
    v1_px = vertices_px["1"]
    v3_px = vertices_px["3"]
    px_dist = math.sqrt((v3_px["x"] - v1_px["x"])**2 + (v3_px["y"] - v1_px["y"])**2)

    v1_mm = vertices_mm["1"]
    v3_mm = vertices_mm["3"]
    mm_dist = math.sqrt((v3_mm["x"] - v1_mm["x"])**2 + (v3_mm["y"] - v1_mm["y"])**2)

    if px_dist == 0:
        return None

    return mm_dist / px_dist


def build_camera_metadata(role_name):
    """
    Build complete camera metadata dict for a role.
    Returns dict or None if calibration is missing.

    Result: {
        resolution: {width, height},
        mm_per_pixel: float,
        vertices_px: {"1": {x, y}, ...},
        vertices_mm: {"1": {x, y}, ...}
    }
    """
    cal = get_calibration_for_role(role_name)
    if not cal:
        return None

    mm_per_pixel = compute_mm_per_pixel(role_name)
    if mm_per_pixel is None:
        return None

    # Load geometry vertices (mm)
    config_path = os.path.join(PROJECT_ROOT, "servo_config.json")
    if not os.path.exists(config_path):
        return None

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    geo_vertices = config.get("geometry", {}).get("vertices", {})
    vertices_mm = {}
    for k, v in geo_vertices.items():
        if v is not None:
            vertices_mm[k] = {"x": v["x"], "y": v["y"]}

    return {
        "resolution": cal.get("resolution", {}),
        "mm_per_pixel": round(mm_per_pixel, 6),
        "vertices_px": cal.get("pixel_coords", {}).get("vertices", {}),
        "vertices_mm": vertices_mm
    }

