# Camera Mapping Module
# Maps device paths to role names for stable camera identification

import json
import os
from pyusbcameraindex import enumerate_usb_video_devices_windows

# Config file path (project root)
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "camera_config.json")

# Predefined role names
VALID_ROLES = ["TopView", "QuarterView", "LeftRobot", "RightRobot"]


def load_mapping():
    """Load device-to-role mapping from config file."""
    if not os.path.exists(CONFIG_PATH):
        return {"device_mappings": {}}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_mapping(config):
    """Save device-to-role mapping to config file."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_available_devices():
    """
    Enumerate all connected USB video devices.
    Returns list of dicts: {index, name, vid, pid, path}
    """
    devices = enumerate_usb_video_devices_windows()
    return [
        {
            "index": d.index,
            "name": d.name,
            "vid": d.vid,
            "pid": d.pid,
            "path": d.path
        }
        for d in devices
    ]


def match_roles(devices=None):
    """
    Match connected devices to saved roles.
    Returns: {role: {index, name, path, connected}} for each mapped role
    """
    if devices is None:
        devices = get_available_devices()
    
    config = load_mapping()
    mappings = config.get("device_mappings", {})
    
    # Build path -> device lookup
    path_to_device = {d["path"]: d for d in devices}
    
    result = {}
    for path, role in mappings.items():
        if path in path_to_device:
            device = path_to_device[path]
            result[role] = {
                "index": device["index"],
                "name": device["name"],
                "path": path,
                "connected": True
            }
        else:
            result[role] = {
                "index": None,
                "name": None,
                "path": path,
                "connected": False
            }
    
    return result


def assign_role(device_path, role_name):
    """
    Assign a role to a device path.
    Returns True on success, raises ValueError on invalid role.
    """
    if role_name not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role_name}. Valid roles: {VALID_ROLES}")
    
    config = load_mapping()
    mappings = config.get("device_mappings", {})
    
    # Remove any existing mapping for this role
    mappings = {p: r for p, r in mappings.items() if r != role_name}
    
    # Add new mapping
    mappings[device_path] = role_name
    config["device_mappings"] = mappings
    save_mapping(config)
    
    return True


def get_index_by_role(role_name):
    """
    Get the current OpenCV index for a given role.
    Returns index (int) or None if not connected.
    """
    roles = match_roles()
    if role_name in roles and roles[role_name]["connected"]:
        return roles[role_name]["index"]
    return None
