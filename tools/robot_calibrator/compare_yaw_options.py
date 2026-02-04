"""
Compare Yaw Correction Options for Vertex Coordinate Calculation.

This script simulates two correction approaches and compares results with measured values.

Option A: Apply -90° correction in compute_yaw
Option B: Change coordinate transform formula (cos/sin swap)
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


def compute_yaw_current(arm, point_data):
    """Current yaw calculation (no correction)."""
    slot_cfg = get_slot_config(arm, 1)
    if not slot_cfg:
        return 0
    
    angles = point_data.get("angles", {})
    physical = angles.get("slot_1", slot_cfg.get("zero_offset", 0))
    zero_offset = slot_cfg.get("zero_offset", 0)
    
    logical_angle = physical - zero_offset
    return math.radians(logical_angle)


def compute_yaw_option_a(arm, point_data):
    """Option A: Apply -90° correction to yaw."""
    slot_cfg = get_slot_config(arm, 1)
    if not slot_cfg:
        return 0
    
    angles = point_data.get("angles", {})
    physical = angles.get("slot_1", slot_cfg.get("zero_offset", 0))
    zero_offset = slot_cfg.get("zero_offset", 0)
    
    logical_angle = physical - zero_offset
    # Apply -90° correction for world coordinate
    world_yaw = logical_angle - 90
    return math.radians(world_yaw)


def compute_reach(arm, point_data):
    """Compute horizontal reach for vertex."""
    a2 = get_slot_config(arm, 2).get("length", 0)
    a3 = get_slot_config(arm, 3).get("length", 0)
    a4 = get_slot_config(arm, 4).get("length", 0)
    a5 = get_slot_config(arm, 5).get("length", 0)
    a6 = get_slot_config(arm, 6).get("length", 0)
    
    theta2 = get_logical_angle(arm, point_data, 2)
    theta3 = get_logical_angle(arm, point_data, 3)
    theta4 = get_logical_angle(arm, point_data, 4)
    
    angle_shoulder = theta2
    angle_elbow = theta2 + theta3
    angle_wrist = theta2 + theta3 + theta4
    
    fk_x = (a2 * math.cos(angle_shoulder) +
            a3 * math.cos(angle_elbow) +
            (a4 + a5 + a6) * math.cos(angle_wrist))
    
    return abs(fk_x)


def compute_base_position(arm):
    """Compute base position from share point."""
    share_point = config.get("share_points", {}).get(arm)
    if not share_point:
        return 0, 0
    
    a2 = get_slot_config(arm, 2).get("length", 0)
    a3 = get_slot_config(arm, 3).get("length", 0)
    a4 = get_slot_config(arm, 4).get("length", 0)
    a5 = get_slot_config(arm, 5).get("length", 0)
    a6 = get_slot_config(arm, 6).get("length", 0)
    
    theta2 = get_logical_angle(arm, share_point, 2)
    theta3 = get_logical_angle(arm, share_point, 3)
    theta4 = get_logical_angle(arm, share_point, 4)
    
    angle_shoulder = theta2
    angle_elbow = theta2 + theta3
    angle_wrist = theta2 + theta3 + theta4
    
    x = (a2 * math.cos(angle_shoulder) +
         a3 * math.cos(angle_elbow) +
         (a4 + a5 + a6) * math.cos(angle_wrist))
    
    y = (a2 * math.sin(angle_shoulder) +
         a3 * math.sin(angle_elbow) +
         (a4 + a5 + a6) * math.sin(angle_wrist))
    
    reach = math.sqrt(x**2 + y**2)
    yaw = compute_yaw_current(arm, share_point)
    
    base_x = -reach * (-math.sin(yaw))
    base_y = -reach * math.cos(yaw)
    
    return base_x, base_y


def calc_vertex_current(arm, vertex, base_x, base_y):
    """Current method: -sin(yaw), cos(yaw)."""
    reach = compute_reach(arm, vertex)
    yaw = compute_yaw_current(arm, vertex)
    
    vx = base_x + reach * (-math.sin(yaw))
    vy = base_y + reach * math.cos(yaw)
    return vx, vy


def calc_vertex_option_a(arm, vertex, base_x, base_y):
    """Option A: -90° correction in yaw, same transform."""
    reach = compute_reach(arm, vertex)
    yaw = compute_yaw_option_a(arm, vertex)
    
    vx = base_x + reach * (-math.sin(yaw))
    vy = base_y + reach * math.cos(yaw)
    return vx, vy


def calc_vertex_option_b(arm, vertex, base_x, base_y):
    """Option B: No yaw correction, different transform (cos, sin)."""
    reach = compute_reach(arm, vertex)
    yaw = compute_yaw_current(arm, vertex)
    
    # Standard math convention: yaw=0 -> +X, yaw=90 -> +Y
    vx = base_x + reach * math.cos(yaw)
    vy = base_y + reach * math.sin(yaw)
    return vx, vy


def main():
    # Measured V1-V2 distance
    MEASURED_V1_V2 = 390.0
    
    print("=" * 70)
    print("YAW CORRECTION OPTIONS COMPARISON")
    print("=" * 70)
    print()
    
    # Get vertices
    v1 = config.get("vertices", {}).get("1")
    v2 = config.get("vertices", {}).get("2")
    
    if not v1 or not v2:
        print("Error: V1 or V2 not found in config")
        return
    
    # Get base positions for each arm
    bases = {}
    for arm in ["left_arm", "right_arm"]:
        bases[arm] = compute_base_position(arm)
    
    print(f"Base Positions:")
    print(f"  left_arm:  ({bases['left_arm'][0]:.1f}, {bases['left_arm'][1]:.1f})")
    print(f"  right_arm: ({bases['right_arm'][0]:.1f}, {bases['right_arm'][1]:.1f})")
    print()
    
    # Calculate vertices with each method
    owner1 = v1.get("owner")
    owner2 = v2.get("owner")
    
    print(f"V1 owner: {owner1}, V2 owner: {owner2}")
    print()
    
    # Current method
    v1_curr = calc_vertex_current(owner1, v1, *bases[owner1])
    v2_curr = calc_vertex_current(owner2, v2, *bases[owner2])
    dist_curr = math.sqrt((v1_curr[0]-v2_curr[0])**2 + (v1_curr[1]-v2_curr[1])**2)
    
    # Option A
    v1_a = calc_vertex_option_a(owner1, v1, *bases[owner1])
    v2_a = calc_vertex_option_a(owner2, v2, *bases[owner2])
    dist_a = math.sqrt((v1_a[0]-v2_a[0])**2 + (v1_a[1]-v2_a[1])**2)
    
    # Option B
    v1_b = calc_vertex_option_b(owner1, v1, *bases[owner1])
    v2_b = calc_vertex_option_b(owner2, v2, *bases[owner2])
    dist_b = math.sqrt((v1_b[0]-v2_b[0])**2 + (v1_b[1]-v2_b[1])**2)
    
    print("-" * 70)
    print(f"{'Method':<15} {'V1 Coord':<20} {'V2 Coord':<20} {'V1-V2 Dist':>10}")
    print("-" * 70)
    print(f"{'Current':<15} ({v1_curr[0]:>7.1f}, {v1_curr[1]:>7.1f}) ({v2_curr[0]:>7.1f}, {v2_curr[1]:>7.1f}) {dist_curr:>10.1f}mm")
    print(f"{'Option A':<15} ({v1_a[0]:>7.1f}, {v1_a[1]:>7.1f}) ({v2_a[0]:>7.1f}, {v2_a[1]:>7.1f}) {dist_a:>10.1f}mm")
    print(f"{'Option B':<15} ({v1_b[0]:>7.1f}, {v1_b[1]:>7.1f}) ({v2_b[0]:>7.1f}, {v2_b[1]:>7.1f}) {dist_b:>10.1f}mm")
    print("-" * 70)
    print()
    
    print(f"MEASURED V1-V2: {MEASURED_V1_V2:.1f}mm")
    print()
    print("ERROR COMPARISON:")
    print("-" * 40)
    print(f"  Current:  {dist_curr - MEASURED_V1_V2:+.1f}mm ({abs(dist_curr - MEASURED_V1_V2)/MEASURED_V1_V2*100:.1f}% error)")
    print(f"  Option A: {dist_a - MEASURED_V1_V2:+.1f}mm ({abs(dist_a - MEASURED_V1_V2)/MEASURED_V1_V2*100:.1f}% error)")
    print(f"  Option B: {dist_b - MEASURED_V1_V2:+.1f}mm ({abs(dist_b - MEASURED_V1_V2)/MEASURED_V1_V2*100:.1f}% error)")
    print()
    
    # Recommend best option
    errors = [
        ("Current", abs(dist_curr - MEASURED_V1_V2)),
        ("Option A", abs(dist_a - MEASURED_V1_V2)),
        ("Option B", abs(dist_b - MEASURED_V1_V2))
    ]
    best = min(errors, key=lambda x: x[1])
    print(f"RECOMMENDATION: {best[0]} (lowest error: {best[1]:.1f}mm)")
    print("=" * 70)


if __name__ == "__main__":
    main()
