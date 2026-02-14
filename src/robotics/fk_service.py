# FK Service — Forward Kinematics for Geometry Generation
# Computes robot geometry (bases, vertices, distances) from servo angles.
# Coordinate System: +X=right, +Y=up, Share Point as origin (0, 0).
#
# Ported from tools/robot_calibrator/geometry_engine.py
# Uses same link model as IK: a4 + a5 + a6

import math


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Logical Angle Extraction
# ─────────────────────────────────────────────────────────────────────────────

def get_logical_angle(config, arm, slot_num, angles):
    """
    Get logical angle for a slot based on min_pos polarity.

    Polarity rule (min_pos-based):
    - Inverted: top, left, cw    → logical = zero_offset - physical
    - Normal:   bottom, right, ccw, open → logical = physical - zero_offset

    Args:
        config: Full servo configuration dict
        arm: 'left_arm' or 'right_arm'
        slot_num: Slot number (1-6)
        angles: dict with 'slot_N' keys → physical angle values

    Returns:
        float: Logical angle in radians
    """
    slot_key = f"slot_{slot_num}"
    slot_cfg = config.get(arm, {}).get(slot_key, {})
    physical = angles.get(slot_key, slot_cfg.get("zero_offset", 0))
    zero_offset = slot_cfg.get("zero_offset", 0)
    min_pos = slot_cfg.get("min_pos", "")

    if min_pos in ["top", "left", "cw"]:
        logical = zero_offset - physical
    else:
        logical = physical - zero_offset

    return math.radians(logical)


# ─────────────────────────────────────────────────────────────────────────────
# FK Computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_yaw(config, arm, point_data):
    """
    Compute yaw angle (slot 1 logical angle) in world coordinate.

    World coordinate: +X=right, +Y=up
    - yaw=0° → +X (right)
    - yaw=90° → +Y (up)

    Args:
        config: Full servo configuration dict
        arm: 'left_arm' or 'right_arm'
        point_data: dict with 'angles'

    Returns:
        float: Yaw angle in radians
    """
    angles = point_data.get("angles", {})
    slot_1_angle = angles.get("slot_1", 0)

    slot_1_config = config.get(arm, {}).get("slot_1", {})
    zero_offset = slot_1_config.get("zero_offset", 0)

    logical_angle = slot_1_angle - zero_offset

    return math.radians(logical_angle)


def _get_link_lengths(config, arm):
    """Extract link lengths from config for an arm."""
    get = lambda slot, default: config.get(arm, {}).get(f"slot_{slot}", {}).get("length", default)
    return get(2, 105.0), get(3, 150.0), get(4, 65.0), get(5, 0.0), get(6, 115.0)


def _compute_fk_components(config, arm, angles):
    """
    Core 3-Link planar FK computation.

    Returns:
        tuple: (fk_x, fk_y) — horizontal and vertical FK components
    """
    a2, a3, a4, a5, a6 = _get_link_lengths(config, arm)

    theta2 = get_logical_angle(config, arm, 2, angles)
    theta3 = get_logical_angle(config, arm, 3, angles)
    theta4 = get_logical_angle(config, arm, 4, angles)

    angle_shoulder = theta2
    angle_elbow = theta2 + theta3
    angle_wrist = theta2 + theta3 + theta4

    fk_x = (a2 * math.cos(angle_shoulder) +
            a3 * math.cos(angle_elbow) +
            (a4 + a5 + a6) * math.cos(angle_wrist))

    fk_y = (a2 * math.sin(angle_shoulder) +
            a3 * math.sin(angle_elbow) +
            (a4 + a5 + a6) * math.sin(angle_wrist))

    return fk_x, fk_y


def compute_reach(config, arm, point_data, is_vertex=True):
    """
    Compute reach distance from base to end effector using FK.

    Args:
        config: Full servo configuration dict
        arm: 'left_arm' or 'right_arm'
        point_data: dict with 'angles'
        is_vertex: True → return (horizontal_reach, 3d_reach) tuple
                   False → return scalar Euclidean distance

    Returns:
        tuple or float: See is_vertex
    """
    angles = point_data.get("angles", {})
    fk_x, fk_y = _compute_fk_components(config, arm, angles)

    if is_vertex:
        return (abs(fk_x), math.sqrt(fk_x**2 + fk_y**2))

    return math.sqrt(fk_x**2 + fk_y**2)


# ─────────────────────────────────────────────────────────────────────────────
# Base & Vertex Position Computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_base(point_x, point_y, reach, yaw):
    """
    Compute base position by reversing reach + yaw from a known point.

    IK coordinate: yaw=0° = forward (+Y), yaw=90° = left (-X)

    Args:
        point_x, point_y: Known point position (relative to origin)
        reach: Distance from base to point
        yaw: Direction angle in radians

    Returns:
        tuple: (base_x, base_y)
    """
    base_x = point_x - reach * (-math.sin(yaw))
    base_y = point_y - reach * math.cos(yaw)
    return (base_x, base_y)


def compute_share_to_vertex(config, arm, vertex, base_pos):
    """
    Compute distance from Share Point (origin) to a Vertex.

    Uses FK + yaw to estimate vertex position, then measures distance to origin.

    Args:
        config: Full servo configuration dict
        arm: 'left_arm' or 'right_arm'
        vertex: Vertex data dict with 'angles'
        base_pos: Base position tuple (x, y)

    Returns:
        float: Distance from share point (0,0) to vertex
    """
    angles = vertex.get("angles", {})
    fk_x, _ = _compute_fk_components(config, arm, angles)
    reach_horiz = abs(fk_x)

    # Get yaw
    slot1_cfg = config.get(arm, {}).get("slot_1", {})
    physical_yaw = angles.get("slot_1", slot1_cfg.get("zero_offset", 0))
    zero_offset = slot1_cfg.get("zero_offset", 0)
    min_pos = slot1_cfg.get("min_pos", "")

    if min_pos in ["left", "cw"]:
        yaw = math.radians(zero_offset - physical_yaw)
    else:
        yaw = math.radians(physical_yaw - zero_offset)

    # Vertex position = base + reach in yaw direction
    vx = base_pos[0] + reach_horiz * (-math.sin(yaw))
    vy = base_pos[1] + reach_horiz * math.cos(yaw)

    return math.sqrt(vx**2 + vy**2)


# ─────────────────────────────────────────────────────────────────────────────
# Trilateration
# ─────────────────────────────────────────────────────────────────────────────

def circle_intersection(c1, r1, c2, r2):
    """
    Find intersection points of two circles.

    Args:
        c1: Center of first circle (x, y)
        r1: Radius of first circle
        c2: Center of second circle (x, y)
        r2: Radius of second circle

    Returns:
        Tuple of two points ((x1, y1), (x2, y2)) or None if no intersection
    """
    x1, y1 = c1
    x2, y2 = c2
    d = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
        return None

    a = (r1**2 - r2**2 + d**2) / (2 * d)
    h_sq = r1**2 - a**2
    if h_sq < 0:
        return None
    h = math.sqrt(h_sq)

    px = x1 + a * (x2 - x1) / d
    py = y1 + a * (y2 - y1) / d

    p1 = (px + h * (y2 - y1) / d, py - h * (x2 - x1) / d)
    p2 = (px - h * (y2 - y1) / d, py + h * (x2 - x1) / d)

    return p1, p2


def select_vertex_by_yaw(p1, p2, base, yaw):
    """
    Select the correct intersection point based on yaw direction.

    Args:
        p1, p2: Two candidate points from circle intersection
        base: Base position (x, y)
        yaw: Yaw angle in radians

    Returns:
        The point that best matches the yaw direction
    """
    reach = math.sqrt((p1[0] - base[0])**2 + (p1[1] - base[1])**2)
    expected_x = base[0] + reach * (-math.sin(yaw))
    expected_y = base[1] + reach * math.cos(yaw)

    dist1 = math.sqrt((p1[0] - expected_x)**2 + (p1[1] - expected_y)**2)
    dist2 = math.sqrt((p2[0] - expected_x)**2 + (p2[1] - expected_y)**2)

    return p1 if dist1 < dist2 else p2


# ─────────────────────────────────────────────────────────────────────────────
# Main Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def compute_geometry(config):
    """
    Compute geometry section: bases, vertices, distances.
    Uses Share Point as origin (0, 0).

    Args:
        config: Full servo configuration dict

    Returns:
        dict: Geometry data ready to be written to servo_config.json["geometry"]
    """
    geometry = {
        "coordinate_system": "+X=right, +Y=up",
        "origin": "share_point",
        "share_points": {},
        "bases": {},
        "vertices": {}
    }

    # Step 1: Share Points → origin (0, 0)
    for arm in ["left_arm", "right_arm"]:
        share_point = config.get("share_points", {}).get(arm)
        if share_point:
            geometry["share_points"][arm] = {"x": 0.0, "y": 0.0}

    # Step 2: Compute Base positions from Share Points
    for arm in ["left_arm", "right_arm"]:
        share_point = config.get("share_points", {}).get(arm)
        if not share_point:
            continue

        reach = compute_reach(config, arm, share_point, is_vertex=False)
        yaw = compute_yaw(config, arm, share_point)
        base_x, base_y = compute_base(0, 0, reach, yaw)

        geometry["bases"][arm] = {
            "x": round(base_x, 1),
            "y": round(base_y, 1),
            "sources": 1
        }

    # Step 3: Compute Vertex positions using Trilateration
    share_point = (0, 0)

    for vid in range(1, 9):
        vertex = config.get("vertices", {}).get(str(vid))
        if not vertex:
            continue

        owner = vertex.get("owner")
        if not owner or owner not in geometry["bases"]:
            continue

        base = geometry["bases"][owner]
        base_pos = (base["x"], base["y"])

        reach_horiz, reach_3d = compute_reach(config, owner, vertex, is_vertex=True)
        share_to_v = compute_share_to_vertex(config, owner, vertex, base_pos)
        yaw = compute_yaw(config, owner, vertex)

        intersections = circle_intersection(share_point, share_to_v, base_pos, reach_horiz)

        if intersections:
            vx, vy = select_vertex_by_yaw(intersections[0], intersections[1], base_pos, yaw)
        else:
            # Fallback: yaw-based estimation
            vx = base["x"] + reach_horiz * (-math.sin(yaw))
            vy = base["y"] + reach_horiz * math.cos(yaw)

        geometry["vertices"][str(vid)] = {
            "x": round(vx, 1),
            "y": round(vy, 1),
            "owner": owner,
            "reach": round(reach_horiz, 1)
        }

    # Step 4: Distance matrix
    distances = {
        "vertex_to_vertex": {},
        "base_to_vertex": {},
        "share_point_to_vertex": {},
        "base_to_base": None
    }

    vertex_ids = list(geometry["vertices"].keys())
    for i, v1 in enumerate(vertex_ids):
        for v2 in vertex_ids[i+1:]:
            p1 = geometry["vertices"][v1]
            p2 = geometry["vertices"][v2]
            dist = math.sqrt((p1["x"] - p2["x"])**2 + (p1["y"] - p2["y"])**2)
            distances["vertex_to_vertex"][f"{v1}_{v2}"] = round(dist, 1)

    for arm, base in geometry["bases"].items():
        arm_distances = {}
        for vid, vertex in geometry["vertices"].items():
            dist = math.sqrt((base["x"] - vertex["x"])**2 + (base["y"] - vertex["y"])**2)
            arm_distances[vid] = round(dist, 1)
        distances["base_to_vertex"][arm] = arm_distances

    for vid, vertex in geometry["vertices"].items():
        dist = math.sqrt(vertex["x"]**2 + vertex["y"]**2)
        distances["share_point_to_vertex"][vid] = round(dist, 1)

    if "left_arm" in geometry["bases"] and "right_arm" in geometry["bases"]:
        left = geometry["bases"]["left_arm"]
        right = geometry["bases"]["right_arm"]
        dist = math.sqrt((left["x"] - right["x"])**2 + (left["y"] - right["y"])**2)
        distances["base_to_base"] = round(dist, 1)

    geometry["distances"] = distances

    return geometry
