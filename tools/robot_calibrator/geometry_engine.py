"""
Geometry Engine
Standalone module for robot geometry calculations.
Extracted from ServoManager for external reuse.
"""

import math
from pulse_mapper import PulseMapper


# ========== Constants ==========

KINEMATICS_CONSTANTS = {
    "d1": 107.0,   # Base height (mm)
    "L1": 105.0,   # Upper arm length - Slot 2 (mm)
    "L2": 150.0,   # Forearm length - Slot 3 (mm)
    "L_wrist": 147.0,  # Wrist + Gripper effective length (mm)
    "stance_threshold": 60.0  # Yaw delta threshold for stance determination (degrees)
}


# ========== Helper Functions ==========

def compute_delta_angle(config, arm, slot_num, point_data):
    """
    Calculate delta angle from Zero reference.
    
    Formula: |physical_angle - zero_offset|
    
    Args:
        config: Full servo configuration dict
        arm: 'left_arm' or 'right_arm'
        slot_num: Slot number (1-6)
        point_data: dict with 'angles' key
        
    Returns:
        float: Delta angle in degrees (always positive)
    """
    slot_key = f"slot_{slot_num}"
    angles = point_data.get("angles", {})
    
    physical_angle = angles.get(slot_key, 0)
    slot_config = config.get(arm, {}).get(slot_key, {})
    zero_offset = slot_config.get("zero_offset", 0)
    
    return abs(physical_angle - zero_offset)


def determine_stance(yaw_delta):
    """
    Determine robot stance based on yaw delta angle.
    
    Open Stance: |yaw_delta| < 60° → Extended arms for side/forward work
    Closed Stance: |yaw_delta| >= 60° → Folded arms for back/inner work
    
    Args:
        yaw_delta: Yaw delta angle in degrees
        
    Returns:
        str: 'open' or 'closed'
    """
    threshold = KINEMATICS_CONSTANTS["stance_threshold"]
    if abs(yaw_delta) < threshold:
        return "open"
    return "closed"


def compute_internal_angle(config, arm, point_data):
    """
    Compute the internal angle between L1 and L2 links.
    
    Open Stance (Compensation Logic):
        θ_int = 180° - |θ_E_delta - θ_S_delta|
        Shoulder rotation is compensated by elbow, keeping arm extended.
        
    Closed Stance (Folded Logic):
        θ_int = θ_E_delta
        No compensation, elbow delta directly becomes fold angle.
        
    Args:
        config: Full servo configuration dict
        arm: 'left_arm' or 'right_arm'
        point_data: dict with 'angles' key
        
    Returns:
        dict: {
            'yaw_delta': float,
            'shoulder_delta': float,
            'elbow_delta': float,
            'stance': str,
            'internal_angle': float
        }
    """
    # Calculate delta angles
    yaw_delta = compute_delta_angle(config, arm, 1, point_data)
    shoulder_delta = compute_delta_angle(config, arm, 2, point_data)
    elbow_delta = compute_delta_angle(config, arm, 3, point_data)
    
    # Determine stance
    stance = determine_stance(yaw_delta)
    
    # Calculate internal angle based on stance
    if stance == "open":
        # Open Stance: Compensation logic
        # θ_int = 180° - |θ_E_delta - θ_S_delta|
        internal_angle = 180.0 - abs(elbow_delta - shoulder_delta)
    else:
        # Closed Stance: Folded logic
        # θ_int = θ_E_delta
        internal_angle = elbow_delta
    
    return {
        "yaw_delta": yaw_delta,
        "shoulder_delta": shoulder_delta,
        "elbow_delta": elbow_delta,
        "stance": stance,
        "internal_angle": internal_angle
    }


def compute_3d_reach(config, arm, point_data):
    """
    Compute 3D reach using Law of Cosines (Dual Reach Protocol).
    
    R_3d = √(L1² + L2² - 2·L1·L2·cos(θ_int))
    Z_drop = R_3d × sin(θ_S_delta)
    Z_final = d1 - Z_drop
    r_xy = R_3d × cos(θ_S_delta)
    
    Args:
        config: Full servo configuration dict
        arm: 'left_arm' or 'right_arm'
        point_data: dict with 'angles' key
        
    Returns:
        dict: {
            'angles': {yaw_delta, shoulder_delta, elbow_delta, internal_angle},
            'stance': str,
            'r_3d': float (mm),
            'r_xy': float (mm),
            'z_drop': float (mm),
            'z_final': float (mm)
        }
    """
    # Get internal angle data
    angle_data = compute_internal_angle(config, arm, point_data)
    
    # Hardware constants
    L1 = KINEMATICS_CONSTANTS["L1"]
    L2 = KINEMATICS_CONSTANTS["L2"]
    d1 = KINEMATICS_CONSTANTS["d1"]
    
    # Convert internal angle to radians
    theta_int_rad = math.radians(angle_data["internal_angle"])
    
    # Law of Cosines: R_3d = √(L1² + L2² - 2·L1·L2·cos(θ_int))
    r_3d = math.sqrt(L1**2 + L2**2 - 2 * L1 * L2 * math.cos(theta_int_rad))
    
    # Convert shoulder delta to radians for projection
    theta_s_rad = math.radians(angle_data["shoulder_delta"])
    
    # Height calculation (assuming pitch down)
    z_drop = r_3d * math.sin(theta_s_rad)
    z_final = d1 - z_drop
    
    # Horizontal reach
    r_xy = r_3d * math.cos(theta_s_rad)
    
    return {
        "angles": {
            "yaw_delta": angle_data["yaw_delta"],
            "shoulder_delta": angle_data["shoulder_delta"],
            "elbow_delta": angle_data["elbow_delta"],
            "internal_angle": angle_data["internal_angle"]
        },
        "stance": angle_data["stance"],
        "r_3d": r_3d,
        "r_xy": r_xy,
        "z_drop": z_drop,
        "z_final": z_final
    }


def compute_reach(config, arm, point_data, is_vertex=True):
    """
    Compute reach distance from base to gripper (Euclidean distance).

    Uses min_pos-based abstraction for angle direction:
    - min_pos in [top, left, cw]: θ = zero_offset - physical (inverted)
    - min_pos in [bottom, right, ccw]: θ = physical - zero_offset (normal)

    Args:
        config: Full servo configuration dict
        arm: 'left_arm' or 'right_arm'
        point_data: dict with 'pulses' and 'angles'
        is_vertex: True for vertex (approach 90°), False for share point

    Returns:
        float: reach distance in mm (Euclidean distance from base to end effector)
    """
    angles = point_data.get("angles", {})

    def get_logical_angle(slot_num):
        """
        Get logical angle based on min_pos abstraction.
        Returns angle in radians.
        """
        slot_key = f"slot_{slot_num}"
        slot_cfg = config.get(arm, {}).get(slot_key, {})
        physical = angles.get(slot_key, 0)
        zero_offset = slot_cfg.get("zero_offset", 0)
        min_pos = slot_cfg.get("min_pos", "")

        # Abstracted polarity based on min_pos
        # Inverted direction: top, left, cw
        # Normal direction: bottom, right, ccw, open
        if min_pos in ["top", "left", "cw"]:
            logical = zero_offset - physical
        else:
            logical = physical - zero_offset

        return math.radians(logical)

    if is_vertex:
        # Vertex: Full FK with Slots 2-6 (Euclidean distance)
        # Same as Share Point - include all arm segments to gripper tip
        slot2_cfg = config.get(arm, {}).get("slot_2", {})
        slot3_cfg = config.get(arm, {}).get("slot_3", {})
        slot4_cfg = config.get(arm, {}).get("slot_4", {})
        slot6_cfg = config.get(arm, {}).get("slot_6", {})

        a2 = slot2_cfg.get("length", 105.0)
        a3 = slot3_cfg.get("length", 150.0)
        a4 = slot4_cfg.get("length", 65.0)
        a5 = config.get(arm, {}).get("slot_5", {}).get("length", 0.0)
        a6 = slot6_cfg.get("length", 115.0)

        theta2 = get_logical_angle(2)
        theta3 = get_logical_angle(3)
        theta4 = get_logical_angle(4)

        # Cumulative angles for each joint
        angle_shoulder = theta2
        angle_elbow = theta2 + theta3
        angle_wrist = theta2 + theta3 + theta4

        # FK: (x, y) coordinates relative to base
        x = (a2 * math.cos(angle_shoulder) +
             a3 * math.cos(angle_elbow) +
             (a4 + a5 + a6) * math.cos(angle_wrist))

        y = (a2 * math.sin(angle_shoulder) +
             a3 * math.sin(angle_elbow) +
             (a4 + a5 + a6) * math.sin(angle_wrist))

        return math.sqrt(x**2 + y**2)
    else:
        # Share Point: Full FK with Slots 2-6 (Euclidean distance)
        slot2_cfg = config.get(arm, {}).get("slot_2", {})
        slot3_cfg = config.get(arm, {}).get("slot_3", {})
        slot4_cfg = config.get(arm, {}).get("slot_4", {})
        slot6_cfg = config.get(arm, {}).get("slot_6", {})

        a2 = slot2_cfg.get("length", 105.0)
        a3 = slot3_cfg.get("length", 150.0)
        a4 = slot4_cfg.get("length", 65.0)
        a5 = config.get(arm, {}).get("slot_5", {}).get("length", 0.0)
        a6 = slot6_cfg.get("length", 115.0)

        theta2 = get_logical_angle(2)
        theta3 = get_logical_angle(3)
        theta4 = get_logical_angle(4)

        # Cumulative angles for each joint
        angle_shoulder = theta2
        angle_elbow = theta2 + theta3
        angle_wrist = theta2 + theta3 + theta4

        # FK: (x, y) coordinates relative to base
        # x = horizontal distance, y = vertical distance
        x = (a2 * math.cos(angle_shoulder) +
             a3 * math.cos(angle_elbow) +
             (a4 + a5 + a6) * math.cos(angle_wrist))

        y = (a2 * math.sin(angle_shoulder) +
             a3 * math.sin(angle_elbow) +
             (a4 + a5 + a6) * math.sin(angle_wrist))

        # Euclidean distance
        return math.sqrt(x**2 + y**2)


def compute_yaw(config, arm, point_data):
    """
    Compute yaw angle (slot 1 logical angle) in world coordinate.
    
    World coordinate system: +X=right, +Y=up
    - yaw=0° points to +X (right)
    - yaw=90° points to +Y (up)
    
    Args:
        config: Full servo configuration dict
        arm: 'left_arm' or 'right_arm'
        point_data: dict with 'angles'

    Returns:
        float: yaw angle in radians (world coordinate: +X=right, +Y=up)
    """
    angles = point_data.get("angles", {})
    slot_1_angle = angles.get("slot_1", 0)

    slot_1_config = config.get(arm, {}).get("slot_1", {})
    zero_offset = slot_1_config.get("zero_offset", 0)

    # Logical angle = IK yaw (forward = 0°)
    logical_angle = slot_1_angle - zero_offset

    return math.radians(logical_angle)


def compute_base_direct(point_x, point_y, reach, yaw):
    """
    Compute base position by reversing reach + yaw from point.

    Args:
        point_x, point_y: Point position (relative to origin)
        reach: Distance from base to point
        yaw: Direction angle in radians

    Returns:
        tuple: (base_x, base_y)
    """
    # IK coordinate system: yaw=0° = forward (+Y), yaw=90° = left (-X)
    base_x = point_x - reach * (-math.sin(yaw))  # -sin for +X=right
    base_y = point_y - reach * math.cos(yaw)
    return (base_x, base_y)


# ========== Main Entry Point ==========

def compute_geometry(config):
    """
    Compute geometry section: bases, vertices, share points positions.
    Uses Share Point as origin (0, 0).
    
    Args:
        config: Full servo configuration dict
        
    Returns:
        dict: Geometry data with bases, vertices, distances
    """
    geometry = {
        "coordinate_system": "+X=right, +Y=up",
        "origin": "share_point",
        "share_points": {},
        "bases": {},
        "vertices": {}
    }

    # 1. Add Share Points as origin (0, 0)
    for arm in ["left_arm", "right_arm"]:
        share_point = config.get("share_points", {}).get(arm)
        if share_point:
            geometry["share_points"][arm] = {"x": 0.0, "y": 0.0}

    # 2. Compute Base positions from Share Points only
    for arm in ["left_arm", "right_arm"]:
        share_point = config.get("share_points", {}).get(arm)
        if not share_point:
            continue

        reach = compute_reach(config, arm, share_point, is_vertex=False)
        yaw = compute_yaw(config, arm, share_point)

        # Share Point is origin (0, 0), compute base relative to origin
        base_x, base_y = compute_base_direct(0, 0, reach, yaw)

        geometry["bases"][arm] = {
            "x": round(base_x, 1),
            "y": round(base_y, 1),
            "sources": 1
        }

    # 3. Compute Vertex positions relative to origin (1-8) using FK planar projection
    for vid in range(1, 9):
        vertex = config.get("vertices", {}).get(str(vid))
        if not vertex:
            continue

        owner = vertex.get("owner")
        if not owner or owner not in geometry["bases"]:
            continue

        base = geometry["bases"][owner]
        
        # Use FK planar projection (approach angle = 90° for vertices)
        reach = compute_reach(config, owner, vertex, is_vertex=True)
        yaw = compute_yaw(config, owner, vertex)

        # Vertex position = base + reach in yaw direction
        vx = base["x"] + reach * (-math.sin(yaw))  # -sin for +X=right
        vy = base["y"] + reach * math.cos(yaw)

        geometry["vertices"][str(vid)] = {
            "x": round(vx, 1),
            "y": round(vy, 1),
            "owner": owner,
            "reach": round(reach, 1)
        }


    # 4. Compute distance matrix
    distances = {
        "vertex_to_vertex": {},
        "base_to_vertex": {},
        "share_point_to_vertex": {},
        "base_to_base": None
    }

    # Vertex to Vertex distances
    vertex_ids = list(geometry["vertices"].keys())
    for i, v1 in enumerate(vertex_ids):
        for v2 in vertex_ids[i+1:]:
            p1 = geometry["vertices"][v1]
            p2 = geometry["vertices"][v2]
            dist = math.sqrt((p1["x"] - p2["x"])**2 + (p1["y"] - p2["y"])**2)
            distances["vertex_to_vertex"][f"{v1}_{v2}"] = round(dist, 1)

    # Base to Vertex distances
    for arm, base in geometry["bases"].items():
        arm_distances = {}
        for vid, vertex in geometry["vertices"].items():
            dist = math.sqrt((base["x"] - vertex["x"])**2 + (base["y"] - vertex["y"])**2)
            arm_distances[vid] = round(dist, 1)
        distances["base_to_vertex"][arm] = arm_distances

    # Share Point to Vertex distances (from origin 0,0)
    for vid, vertex in geometry["vertices"].items():
        dist = math.sqrt(vertex["x"]**2 + vertex["y"]**2)
        distances["share_point_to_vertex"][vid] = round(dist, 1)

    # Base to Base distance
    if "left_arm" in geometry["bases"] and "right_arm" in geometry["bases"]:
        left = geometry["bases"]["left_arm"]
        right = geometry["bases"]["right_arm"]
        dist = math.sqrt((left["x"] - right["x"])**2 + (left["y"] - right["y"])**2)
        distances["base_to_base"] = round(dist, 1)

    geometry["distances"] = distances

    return geometry


# ========== Standalone Test ==========

if __name__ == "__main__":
    import json
    import os
    
    # Load config from same directory
    config_path = os.path.join(os.path.dirname(__file__), "servo_config.json")
    
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print("=== Geometry Engine Test ===")
        result = compute_geometry(config)
        print(json.dumps(result, indent=2))
    else:
        print(f"Config not found: {config_path}")
