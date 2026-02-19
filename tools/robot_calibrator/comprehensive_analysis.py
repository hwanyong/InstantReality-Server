"""
Comprehensive Vertex Calculation Analysis.

Tests ALL possible calculation variations to find the correct method.

Variables tested:
1. Yaw offset: 0°, -90°, +90°, 180°
2. Yaw sign: normal, inverted
3. Coordinate transform: multiple options
4. Reach calculation: horizontal (fk_x), 3D (sqrt)
5. min_pos polarity: normal, inverted
"""

import json
import math
import os
from itertools import product

# Load config
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "servo_config.json")

with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)


def get_slot_config(arm, slot_num):
    arm_config = config.get(arm, {})
    slot_key = f"slot_{slot_num}"
    return arm_config.get(slot_key, {})


def get_logical_angle(arm, point_data, slot_num, invert_polarity=False):
    """Get logical angle with optional polarity inversion."""
    slot_cfg = get_slot_config(arm, slot_num)
    if not slot_cfg:
        return 0
    
    angles = point_data.get("angles", {})
    slot_key = f"slot_{slot_num}"
    physical = angles.get(slot_key, slot_cfg.get("zero_offset", 0))
    zero_offset = slot_cfg.get("zero_offset", 0)
    min_pos = slot_cfg.get("min_pos", "")
    
    # Normal polarity
    if min_pos in ["top", "left", "cw"]:
        logical = zero_offset - physical
    else:
        logical = physical - zero_offset
    
    # Optionally invert
    if invert_polarity:
        logical = -logical
    
    return math.radians(logical)


def compute_yaw(arm, point_data, offset_deg=0, invert_sign=False):
    """Compute yaw with configurable offset and sign."""
    slot_cfg = get_slot_config(arm, 1)
    if not slot_cfg:
        return 0
    
    angles = point_data.get("angles", {})
    physical = angles.get("slot_1", slot_cfg.get("zero_offset", 0))
    zero_offset = slot_cfg.get("zero_offset", 0)
    
    logical_angle = physical - zero_offset + offset_deg
    
    if invert_sign:
        logical_angle = -logical_angle
    
    return math.radians(logical_angle)


def compute_reach(arm, point_data, use_3d=False, invert_polarity=False):
    """Compute reach with options."""
    a2 = get_slot_config(arm, 2).get("length", 0)
    a3 = get_slot_config(arm, 3).get("length", 0)
    a4 = get_slot_config(arm, 4).get("length", 0)
    a5 = get_slot_config(arm, 5).get("length", 0)
    a6 = get_slot_config(arm, 6).get("length", 0)
    
    theta2 = get_logical_angle(arm, point_data, 2, invert_polarity)
    theta3 = get_logical_angle(arm, point_data, 3, invert_polarity)
    theta4 = get_logical_angle(arm, point_data, 4, invert_polarity)
    
    angle_shoulder = theta2
    angle_elbow = theta2 + theta3
    angle_wrist = theta2 + theta3 + theta4
    
    fk_x = (a2 * math.cos(angle_shoulder) +
            a3 * math.cos(angle_elbow) +
            (a4 + a5 + a6) * math.cos(angle_wrist))
    
    fk_y = (a2 * math.sin(angle_shoulder) +
            a3 * math.sin(angle_elbow) +
            (a4 + a5 + a6) * math.sin(angle_wrist))
    
    if use_3d:
        return math.sqrt(fk_x**2 + fk_y**2)
    else:
        return abs(fk_x)


def compute_base(arm):
    """Compute base position (fixed method)."""
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
    yaw = compute_yaw(arm, share_point)
    
    base_x = -reach * (-math.sin(yaw))
    base_y = -reach * math.cos(yaw)
    
    return base_x, base_y


# Coordinate transform functions
def transform_current(reach, yaw):
    """Current: (-sin, cos) - forward = +Y"""
    return reach * (-math.sin(yaw)), reach * math.cos(yaw)

def transform_standard(reach, yaw):
    """Standard math: (cos, sin) - 0° = +X"""
    return reach * math.cos(yaw), reach * math.sin(yaw)

def transform_inverted(reach, yaw):
    """Inverted: (sin, -cos)"""
    return reach * math.sin(yaw), -reach * math.cos(yaw)

def transform_neg_standard(reach, yaw):
    """Negative standard: (-cos, -sin)"""
    return -reach * math.cos(yaw), -reach * math.sin(yaw)

def transform_sin_cos(reach, yaw):
    """(sin, cos)"""
    return reach * math.sin(yaw), reach * math.cos(yaw)

def transform_neg_sin_neg_cos(reach, yaw):
    """(-sin, -cos)"""
    return -reach * math.sin(yaw), -reach * math.cos(yaw)


TRANSFORMS = {
    "(-sin,cos)": transform_current,
    "(cos,sin)": transform_standard,
    "(sin,-cos)": transform_inverted,
    "(-cos,-sin)": transform_neg_standard,
    "(sin,cos)": transform_sin_cos,
    "(-sin,-cos)": transform_neg_sin_neg_cos,
}


def calc_vertex(arm, vertex, base_x, base_y, 
                yaw_offset=0, yaw_invert=False, 
                use_3d_reach=False, invert_polarity=False,
                transform_func=transform_current):
    """Calculate vertex with all options."""
    reach = compute_reach(arm, vertex, use_3d_reach, invert_polarity)
    yaw = compute_yaw(arm, vertex, yaw_offset, yaw_invert)
    
    dx, dy = transform_func(reach, yaw)
    return base_x + dx, base_y + dy


def main():
    MEASURED_V1_V2 = 390.0
    
    print("=" * 80)
    print("COMPREHENSIVE VERTEX CALCULATION ANALYSIS")
    print("=" * 80)
    print(f"Target: V1-V2 distance = {MEASURED_V1_V2}mm")
    print()
    
    # Get vertices
    v1 = config.get("vertices", {}).get("1")
    v2 = config.get("vertices", {}).get("2")
    
    if not v1 or not v2:
        print("Error: V1 or V2 not found")
        return
    
    owner1 = v1.get("owner")
    owner2 = v2.get("owner")
    
    # Compute base positions
    base1 = compute_base(owner1)
    base2 = compute_base(owner2)
    
    print(f"V1 owner: {owner1}, Base: ({base1[0]:.1f}, {base1[1]:.1f})")
    print(f"V2 owner: {owner2}, Base: ({base2[0]:.1f}, {base2[1]:.1f})")
    print()
    
    # Test all combinations
    yaw_offsets = [0, -90, 90, 180]
    yaw_inverts = [False, True]
    reach_3d = [False, True]
    polarity_inverts = [False, True]
    
    results = []
    
    for yaw_off, yaw_inv, use_3d, pol_inv, (tf_name, tf_func) in product(
        yaw_offsets, yaw_inverts, reach_3d, polarity_inverts, TRANSFORMS.items()
    ):
        v1_pos = calc_vertex(owner1, v1, *base1, yaw_off, yaw_inv, use_3d, pol_inv, tf_func)
        v2_pos = calc_vertex(owner2, v2, *base2, yaw_off, yaw_inv, use_3d, pol_inv, tf_func)
        
        dist = math.sqrt((v1_pos[0]-v2_pos[0])**2 + (v1_pos[1]-v2_pos[1])**2)
        error = abs(dist - MEASURED_V1_V2)
        
        results.append({
            'yaw_offset': yaw_off,
            'yaw_invert': yaw_inv,
            'reach_3d': use_3d,
            'polarity_invert': pol_inv,
            'transform': tf_name,
            'v1': v1_pos,
            'v2': v2_pos,
            'distance': dist,
            'error': error
        })
    
    # Sort by error
    results.sort(key=lambda x: x['error'])
    
    # Print top 20 best results
    print("-" * 80)
    print("TOP 20 BEST MATCHES (sorted by error)")
    print("-" * 80)
    print(f"{'#':>2} {'YawOff':>6} {'YawInv':>6} {'3D':>4} {'PolInv':>6} {'Transform':<12} {'Distance':>10} {'Error':>10}")
    print("-" * 80)
    
    for i, r in enumerate(results[:20]):
        print(f"{i+1:>2} {r['yaw_offset']:>6}° {str(r['yaw_invert']):>6} "
              f"{str(r['reach_3d']):>4} {str(r['polarity_invert']):>6} "
              f"{r['transform']:<12} {r['distance']:>10.1f} {r['error']:>10.1f}")
    
    print("-" * 80)
    print()
    
    # Show best result details
    best = results[0]
    print("=" * 80)
    print("BEST MATCH DETAILS")
    print("=" * 80)
    print(f"Yaw Offset:      {best['yaw_offset']}°")
    print(f"Yaw Invert:      {best['yaw_invert']}")
    print(f"Use 3D Reach:    {best['reach_3d']}")
    print(f"Polarity Invert: {best['polarity_invert']}")
    print(f"Transform:       {best['transform']}")
    print()
    print(f"V1 Position: ({best['v1'][0]:.1f}, {best['v1'][1]:.1f})")
    print(f"V2 Position: ({best['v2'][0]:.1f}, {best['v2'][1]:.1f})")
    print(f"V1-V2 Distance: {best['distance']:.1f}mm")
    print(f"Error: {best['error']:.1f}mm ({best['error']/MEASURED_V1_V2*100:.2f}%)")
    print("=" * 80)


if __name__ == "__main__":
    main()
