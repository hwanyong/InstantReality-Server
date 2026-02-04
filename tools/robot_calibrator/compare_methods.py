"""
Compare two methods for calculating Vertex positions.

Method A (Current): 3D Euclidean reach projected in yaw direction
Method B (Direct FK): Use FK (x, y) coordinates directly from Base

This script compares both methods to help identify which is more accurate.
"""

import json
import math
import os

# Load config
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "servo_config.json")

with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)


def get_slot_config(arm, slot_num):
    """Get slot configuration for an arm."""
    arm_config = config.get(arm, {})
    slot_key = f"slot_{slot_num}"
    return arm_config.get(slot_key)


def get_logical_angle(arm, point_data, slot_num):
    """Get logical angle for a slot based on min_pos abstraction."""
    slot_cfg = get_slot_config(arm, slot_num)
    if not slot_cfg:
        return 0
    
    angles = point_data.get("angles", {})
    slot_key = f"slot_{slot_num}"
    physical = angles.get(slot_key, slot_cfg.get("zero_offset", 0))
    zero_offset = slot_cfg.get("zero_offset", 0)
    min_pos = slot_cfg.get("min_pos", "")
    
    if min_pos in ["top", "left", "cw"]:
        logical = zero_offset - physical
    else:
        logical = physical - zero_offset
    
    return math.radians(logical)


def compute_yaw(arm, point_data):
    """Compute yaw angle from Slot 1."""
    slot_cfg = get_slot_config(arm, 1)
    if not slot_cfg:
        return 0
    
    angles = point_data.get("angles", {})
    physical = angles.get("slot_1", slot_cfg.get("zero_offset", 0))
    zero_offset = slot_cfg.get("zero_offset", 0)
    
    return math.radians(physical - zero_offset)


def method_a_current(arm, point_data, base_x, base_y):
    """
    Method A (Current): 3D Euclidean reach in yaw direction.
    reach = sqrt(x^2 + y^2) where x, y are FK coordinates.
    Vertex = Base + reach * yaw_direction
    """
    # Get link lengths
    a2 = get_slot_config(arm, 2).get("length", 0)
    a3 = get_slot_config(arm, 3).get("length", 0)
    a4 = get_slot_config(arm, 4).get("length", 0)
    a5 = get_slot_config(arm, 5).get("length", 0)
    a6 = get_slot_config(arm, 6).get("length", 0)
    
    # Get angles
    theta2 = get_logical_angle(arm, point_data, 2)
    theta3 = get_logical_angle(arm, point_data, 3)
    theta4 = get_logical_angle(arm, point_data, 4)
    
    # Cumulative angles
    angle_shoulder = theta2
    angle_elbow = theta2 + theta3
    angle_wrist = theta2 + theta3 + theta4
    
    # FK coordinates (relative to base)
    x = (a2 * math.cos(angle_shoulder) +
         a3 * math.cos(angle_elbow) +
         (a4 + a5 + a6) * math.cos(angle_wrist))
    
    y = (a2 * math.sin(angle_shoulder) +
         a3 * math.sin(angle_elbow) +
         (a4 + a5 + a6) * math.sin(angle_wrist))
    
    # 3D Euclidean reach
    reach = math.sqrt(x**2 + y**2)
    
    # Project in yaw direction
    yaw = compute_yaw(arm, point_data)
    vx = base_x + reach * (-math.sin(yaw))
    vy = base_y + reach * math.cos(yaw)
    
    return vx, vy, reach


def method_b_direct_fk(arm, point_data, base_x, base_y):
    """
    Method B (Direct FK): Use FK x, y coordinates directly.
    Vertex = Base + (FK_x rotated by yaw, FK_y rotated by yaw)
    """
    # Get link lengths
    a2 = get_slot_config(arm, 2).get("length", 0)
    a3 = get_slot_config(arm, 3).get("length", 0)
    a4 = get_slot_config(arm, 4).get("length", 0)
    a5 = get_slot_config(arm, 5).get("length", 0)
    a6 = get_slot_config(arm, 6).get("length", 0)
    
    # Get angles
    theta2 = get_logical_angle(arm, point_data, 2)
    theta3 = get_logical_angle(arm, point_data, 3)
    theta4 = get_logical_angle(arm, point_data, 4)
    
    # Cumulative angles
    angle_shoulder = theta2
    angle_elbow = theta2 + theta3
    angle_wrist = theta2 + theta3 + theta4
    
    # FK coordinates in arm's local frame
    # x = forward (in arm direction), y = vertical
    fk_x = (a2 * math.cos(angle_shoulder) +
            a3 * math.cos(angle_elbow) +
            (a4 + a5 + a6) * math.cos(angle_wrist))
    
    fk_y = (a2 * math.sin(angle_shoulder) +
            a3 * math.sin(angle_elbow) +
            (a4 + a5 + a6) * math.sin(angle_wrist))
    
    # Rotate by yaw and add to base
    yaw = compute_yaw(arm, point_data)
    
    # Transform local FK to world coordinates
    # fk_x is "forward" in arm direction, fk_y is "vertical" in arm plane
    # In world: forward direction rotated by yaw
    vx = base_x + fk_x * (-math.sin(yaw))
    vy = base_y + fk_x * math.cos(yaw)
    # Note: fk_y is the vertical component which we ignore for 2D top-view
    
    reach = abs(fk_x)  # Horizontal projection
    
    return vx, vy, reach


def compute_base_position(arm):
    """Compute base position using share_points."""
    share_point = config.get("share_points", {}).get(arm)
    if not share_point:
        return 0, 0
    
    # Get link lengths
    a2 = get_slot_config(arm, 2).get("length", 0)
    a3 = get_slot_config(arm, 3).get("length", 0)
    a4 = get_slot_config(arm, 4).get("length", 0)
    a5 = get_slot_config(arm, 5).get("length", 0)
    a6 = get_slot_config(arm, 6).get("length", 0)
    
    # Get angles
    theta2 = get_logical_angle(arm, share_point, 2)
    theta3 = get_logical_angle(arm, share_point, 3)
    theta4 = get_logical_angle(arm, share_point, 4)
    
    # Cumulative angles
    angle_shoulder = theta2
    angle_elbow = theta2 + theta3
    angle_wrist = theta2 + theta3 + theta4
    
    # FK coordinates
    x = (a2 * math.cos(angle_shoulder) +
         a3 * math.cos(angle_elbow) +
         (a4 + a5 + a6) * math.cos(angle_wrist))
    
    y = (a2 * math.sin(angle_shoulder) +
         a3 * math.sin(angle_elbow) +
         (a4 + a5 + a6) * math.sin(angle_wrist))
    
    reach = math.sqrt(x**2 + y**2)
    yaw = compute_yaw(arm, share_point)
    
    # Base = negative reach from origin in yaw direction
    base_x = -reach * (-math.sin(yaw))
    base_y = -reach * math.cos(yaw)
    
    return base_x, base_y


def main():
    print("=" * 80)
    print("VERTEX CALCULATION METHOD COMPARISON")
    print("=" * 80)
    print()
    print("Method A (Current): 3D Euclidean reach projected in yaw direction")
    print("Method B (Direct FK): Use FK x coordinate as horizontal reach")
    print()
    
    results = []
    
    for vid in range(1, 9):
        vertex = config.get("vertices", {}).get(str(vid))
        if not vertex:
            continue
        
        owner = vertex.get("owner")
        if not owner:
            continue
        
        base_x, base_y = compute_base_position(owner)
        
        # Calculate with both methods
        ax, ay, a_reach = method_a_current(owner, vertex, base_x, base_y)
        bx, by, b_reach = method_b_direct_fk(owner, vertex, base_x, base_y)
        
        # Distance from share point (origin)
        dist_a = math.sqrt(ax**2 + ay**2)
        dist_b = math.sqrt(bx**2 + by**2)
        
        results.append({
            'vid': vid,
            'owner': owner.split('_')[0],
            'base': (base_x, base_y),
            'a': (ax, ay, a_reach, dist_a),
            'b': (bx, by, b_reach, dist_b)
        })
    
    # Print comparison table
    print("-" * 80)
    print(f"{'V':<3} {'Arm':<6} {'Base':<16} | {'Method A':<24} | {'Method B':<24}")
    print(f"{'':3} {'':6} {'':16} | {'Coord':<14} {'SP Dist':<9} | {'Coord':<14} {'SP Dist':<9}")
    print("-" * 80)
    
    for r in results:
        base_str = f"({r['base'][0]:.0f}, {r['base'][1]:.0f})"
        a_coord = f"({r['a'][0]:.0f}, {r['a'][1]:.0f})"
        b_coord = f"({r['b'][0]:.0f}, {r['b'][1]:.0f})"
        
        print(f"V{r['vid']:<2} {r['owner']:<6} {base_str:<16} | "
              f"{a_coord:<14} {r['a'][3]:>7.1f}mm | "
              f"{b_coord:<14} {r['b'][3]:>7.1f}mm")
    
    print("-" * 80)
    print()
    
    # Print difference summary
    print("DIFFERENCE SUMMARY (Method A - Method B):")
    print("-" * 50)
    for r in results:
        diff_x = r['a'][0] - r['b'][0]
        diff_y = r['a'][1] - r['b'][1]
        diff_dist = r['a'][3] - r['b'][3]
        print(f"V{r['vid']}: dx={diff_x:+.1f}mm, dy={diff_y:+.1f}mm, dist_diff={diff_dist:+.1f}mm")
    
    print()
    print("=" * 80)
    print("NOTE: Compare these results with your physical measurements.")
    print("      Method A uses 3D reach, Method B uses horizontal projection only.")
    print("=" * 80)


if __name__ == "__main__":
    main()
