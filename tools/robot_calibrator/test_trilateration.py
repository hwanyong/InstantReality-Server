"""
Test trilateration approach for vertex coordinate calculation.
Uses circle intersection instead of yaw-based transform.
"""
import sys
sys.path.insert(0, ".")

import json
import math
from geometry_engine import compute_reach, compute_yaw

with open("servo_config.json", "r") as f:
    config = json.load(f)


def circle_intersection(c1, r1, c2, r2):
    """
    Find intersection points of two circles.
    Returns tuple of two points or None if no intersection.
    """
    x1, y1 = c1
    x2, y2 = c2
    d = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    
    # Check if circles intersect
    if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
        return None
    
    a = (r1 ** 2 - r2 ** 2 + d ** 2) / (2 * d)
    h_sq = r1 ** 2 - a ** 2
    if h_sq < 0:
        return None
    h = math.sqrt(h_sq)
    
    # Point on line between centers
    px = x1 + a * (x2 - x1) / d
    py = y1 + a * (y2 - y1) / d
    
    # Two intersection points
    p1 = (px + h * (y2 - y1) / d, py - h * (x2 - x1) / d)
    p2 = (px - h * (y2 - y1) / d, py + h * (x2 - x1) / d)
    
    return p1, p2


def select_by_yaw(p1, p2, base, yaw, share_point=(0, 0)):
    """
    Select the point that matches the expected position.
    Use the old yaw-based calculation as reference.
    """
    # Calculate expected position using old method (for reference only)
    # Old method: vx = base_x + reach * (-sin(yaw)), vy = base_y + reach * cos(yaw)
    reach = math.sqrt((p1[0] - base[0])**2 + (p1[1] - base[1])**2)
    expected_x = base[0] + reach * (-math.sin(yaw))
    expected_y = base[1] + reach * math.cos(yaw)
    
    # Choose the point closer to expected position
    dist1 = math.sqrt((p1[0] - expected_x)**2 + (p1[1] - expected_y)**2)
    dist2 = math.sqrt((p2[0] - expected_x)**2 + (p2[1] - expected_y)**2)
    
    return p1 if dist1 < dist2 else p2


def compute_share_to_vertex_distance(config, arm, vertex):
    """
    Compute distance from Share Point (origin) to Vertex using FK.
    This is the full 3D reach from share point.
    """
    # Get slot configs
    a2 = config.get(arm, {}).get("slot_2", {}).get("length", 0)
    a3 = config.get(arm, {}).get("slot_3", {}).get("length", 0)
    a4 = config.get(arm, {}).get("slot_4", {}).get("length", 0)
    a5 = config.get(arm, {}).get("slot_5", {}).get("length", 0)
    a6 = config.get(arm, {}).get("slot_6", {}).get("length", 0)
    
    # Get angles
    angles = vertex.get("angles", {})
    
    def get_logical_angle(slot_num):
        slot_cfg = config.get(arm, {}).get(f"slot_{slot_num}", {})
        physical = angles.get(f"slot_{slot_num}", slot_cfg.get("zero_offset", 0))
        zero_offset = slot_cfg.get("zero_offset", 0)
        min_pos = slot_cfg.get("min_pos", "")
        
        if min_pos in ["top", "left", "cw"]:
            return math.radians(zero_offset - physical)
        else:
            return math.radians(physical - zero_offset)
    
    theta2 = get_logical_angle(2)
    theta3 = get_logical_angle(3)
    theta4 = get_logical_angle(4)
    
    angle_shoulder = theta2
    angle_elbow = theta2 + theta3
    angle_wrist = theta2 + theta3 + theta4
    
    fk_x = (a2 * math.cos(angle_shoulder) +
            a3 * math.cos(angle_elbow) +
            (a4 + a5 + a6) * math.cos(angle_wrist))
    
    fk_y = (a2 * math.sin(angle_shoulder) +
            a3 * math.sin(angle_elbow) +
            (a4 + a5 + a6) * math.sin(angle_wrist))
    
    return math.sqrt(fk_x ** 2 + fk_y ** 2)


def compute_vertex_trilateration(config, base_pos, vertex_data, arm):
    """
    Compute vertex position using trilateration.
    
    Uses:
    - Share Point (origin) to Vertex distance
    - Base to Vertex distance (reach)
    - Yaw only for selecting correct intersection point
    """
    # Get reach (Base->Vertex distance)
    reach_horiz, reach_3d = compute_reach(config, arm, vertex_data, is_vertex=True)
    
    # Get Share->Vertex distance
    share_to_vertex = compute_share_to_vertex_distance(config, arm, vertex_data)
    
    # Get yaw for direction selection only
    yaw = compute_yaw(config, arm, vertex_data)
    
    # Find circle intersections
    share_point = (0, 0)
    intersections = circle_intersection(share_point, share_to_vertex, base_pos, reach_3d)
    
    if intersections is None:
        # Fallback to old method if no intersection
        vx = base_pos[0] + reach_horiz * (-math.sin(yaw))
        vy = base_pos[1] + reach_horiz * math.cos(yaw)
        return (vx, vy), reach_3d, "fallback"
    
    # Select correct intersection based on yaw direction
    vertex_pos = select_by_yaw(intersections[0], intersections[1], base_pos, yaw)
    
    return vertex_pos, reach_3d, "trilateration"


# Test the new approach
print("=" * 75)
print("TRILATERATION APPROACH TEST")
print("=" * 75)
print()

# Get base positions (using existing geometry_engine logic)
from geometry_engine import compute_geometry

geometry = compute_geometry(config)
bases = geometry.get("bases", {})

lb = (bases.get("left_arm", {}).get("x", 0), bases.get("left_arm", {}).get("y", 0))
rb = (bases.get("right_arm", {}).get("x", 0), bases.get("right_arm", {}).get("y", 0))

print(f"Left Base:  ({lb[0]:.1f}, {lb[1]:.1f})")
print(f"Right Base: ({rb[0]:.1f}, {rb[1]:.1f})")
print()

# Compute vertices with trilateration
vertices_config = config.get("vertices", {})
new_vertices = {}

for vid in ["1", "2", "3", "4"]:
    v_data = vertices_config.get(vid, {})
    owner = v_data.get("owner")
    base = lb if owner == "left_arm" else rb
    
    pos, reach, method = compute_vertex_trilateration(config, base, v_data, owner)
    new_vertices[vid] = {"pos": pos, "reach": reach, "method": method}
    
    print(f"V{vid}: ({pos[0]:.1f}, {pos[1]:.1f}) - reach: {reach:.1f}mm - method: {method}")

print()

# Compare V-V distances
measured = {
    "v1_v2": 390,
    "v2_v3": 380,
    "v3_v4": 390,
    "v4_v1": 284,
    "v1_v3": 546,
    "v2_v4": 546,
}


def dist(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


calculated = {
    "v1_v2": dist(new_vertices["1"]["pos"], new_vertices["2"]["pos"]),
    "v2_v3": dist(new_vertices["2"]["pos"], new_vertices["3"]["pos"]),
    "v3_v4": dist(new_vertices["3"]["pos"], new_vertices["4"]["pos"]),
    "v4_v1": dist(new_vertices["4"]["pos"], new_vertices["1"]["pos"]),
    "v1_v3": dist(new_vertices["1"]["pos"], new_vertices["3"]["pos"]),
    "v2_v4": dist(new_vertices["2"]["pos"], new_vertices["4"]["pos"]),
}

print("=" * 75)
print("V-V DISTANCE COMPARISON (Trilateration)")
print("=" * 75)
print()
print(f"{'Item':<15} {'Measured':>10} {'Calculated':>12} {'Error':>10} {'Status':>8}")
print("-" * 60)

for key in measured:
    m = measured[key]
    c = calculated[key]
    err = c - m
    status = "[OK]" if abs(err) < 15 else "[BAD]"
    print(f"{key:<15} {m:>10.1f} {c:>12.1f} {err:>+10.1f} {status:>8}")
