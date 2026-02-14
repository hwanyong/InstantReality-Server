# IK Service — 3-Layer Inverse Kinematics
# Layer 1: solve_ik() — Pure IK math
# Layer 2: compute_pulses() — Angle-to-pulse conversion
# Layer 3: Facade functions for different API consumers

import math
from dataclasses import dataclass
from robotics.config_cache import get_config


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class IKResult:
    theta1: float
    theta2: float
    theta3: float
    theta4: float
    theta5: float
    theta6: float
    local_x: float
    local_y: float
    reach: float
    valid: bool
    config_name: str


@dataclass
class PulseResult:
    physical: dict  # {1: 90.0, 2: 135.0, ...}
    pulses: dict    # {1: 1500, 2: 1200, ...}


# ─────────────────────────────────────────────────────────────────────────────
# Layer 1: Pure IK Math
# ─────────────────────────────────────────────────────────────────────────────

def solve_ik(world_x, world_y, z, base_x, base_y, link_lengths):
    """
    Pure 5-Link IK math function.
    Does NOT know about z_offset or orientation — caller applies those.

    Args:
        world_x, world_y: Share Point origin coordinates (mm)
        z: Z height (mm) — z_offset already applied by caller
        base_x, base_y: Arm base coordinates (mm)
        link_lengths: dict with keys d1, a2, a3, a4, a5, a6

    Returns:
        IKResult dataclass
    """
    d1 = link_lengths["d1"]
    a2 = link_lengths["a2"]
    a3 = link_lengths["a3"]
    a4 = link_lengths["a4"]
    a5 = link_lengths["a5"]
    a6 = link_lengths["a6"]

    # Local coordinates
    local_x = world_x - base_x
    local_y = world_y - base_y

    # θ1 (Base Yaw) — Y=forward, CCW positive
    if local_x == 0 and local_y == 0:
        theta1 = 0.0
    else:
        theta1 = math.degrees(math.atan2(-local_x, local_y))

    reach = math.sqrt(local_x**2 + local_y**2)

    # 5-Link IK: Gripper tip at -90° (pointing down)
    wrist_z = z + a4 + a5 + a6
    s = wrist_z - d1
    dist_sq = reach**2 + s**2
    dist = math.sqrt(dist_sq)
    max_reach = a2 + a3
    min_reach = abs(a2 - a3)

    valid = True
    config_name = "Elbow Up"

    if dist > max_reach or dist < min_reach or dist < 0.001:
        # Pointing fallback
        if reach > 0:
            theta2 = math.degrees(math.atan2(s, reach))
        else:
            theta2 = 90.0 if s >= 0 else -90.0
        theta3 = 0.0
        theta4 = -90.0 - theta2
        valid = False
        config_name = "Pointing"
    else:
        # Law of Cosines for elbow angle (θ3)
        cos_theta3 = (dist_sq - a2**2 - a3**2) / (2 * a2 * a3)
        cos_theta3 = max(-1.0, min(1.0, cos_theta3))
        theta3_rad = math.acos(cos_theta3)

        # Shoulder angle components
        beta = math.atan2(s, reach)
        cos_alpha = (a2**2 + dist_sq - a3**2) / (2 * a2 * dist)
        cos_alpha = max(-1.0, min(1.0, cos_alpha))
        alpha = math.acos(cos_alpha)

        # Elbow Up solution
        theta2 = math.degrees(beta + alpha)
        theta3 = math.degrees(theta3_rad)

        # θ4: keep gripper pointing down
        theta4 = -90.0 - theta2 + theta3

    return IKResult(
        theta1=theta1, theta2=theta2, theta3=theta3,
        theta4=theta4, theta5=0.0, theta6=0.0,
        local_x=local_x, local_y=local_y,
        reach=reach, valid=valid, config_name=config_name
    )


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2: Angle → Pulse Conversion
# ─────────────────────────────────────────────────────────────────────────────

# Polarity mapping: slot 4 is inverted (wrist pitch)
SLOT_POLARITY = {1: 1, 2: 1, 3: 1, 4: -1, 5: 1, 6: 1}


def compute_pulses(ik_result, slots):
    """
    Convert IK angles to physical angles and pulse widths.

    Args:
        ik_result: IKResult dataclass
        slots: dict {1: slot1_config, 2: slot2_config, ...}

    Returns:
        PulseResult dataclass
    """
    from lib.robot.pulse_mapper import PulseMapper

    mapper = PulseMapper()
    angles = {
        1: ik_result.theta1, 2: ik_result.theta2, 3: ik_result.theta3,
        4: ik_result.theta4, 5: ik_result.theta5, 6: ik_result.theta6
    }

    physical = {}
    pulses = {}

    for slot_num in range(1, 7):
        slot_config = slots[slot_num]
        polarity = SLOT_POLARITY[slot_num]
        ik_angle = angles[slot_num]

        zero_offset = slot_config.get("zero_offset", 90)
        act_range = slot_config.get("actuation_range", 180)
        phy = zero_offset + (polarity * ik_angle)
        phy = max(0, min(act_range, phy))

        motor_config = {
            "actuation_range": act_range,
            "pulse_min": slot_config.get("pulse_min", 500),
            "pulse_max": slot_config.get("pulse_max", 2500)
        }
        pulse = mapper.physical_to_pulse(phy, motor_config)

        physical[slot_num] = round(phy, 2)
        pulses[slot_num] = pulse

    return PulseResult(physical=physical, pulses=pulses)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Load arm data from ConfigCache
# ─────────────────────────────────────────────────────────────────────────────

def _load_arm_data(arm):
    """Load arm configuration from cached servo_config.json."""
    cache = get_config()
    config = cache.get()

    arm_config = config.get(arm, {})
    geometry = config.get("geometry", {})
    bases = geometry.get("bases", {})
    base = bases.get(arm, {"x": 0, "y": 0})

    slots = {}
    for i in range(1, 7):
        slots[i] = arm_config.get(f"slot_{i}", {})

    link_lengths = {
        "d1": slots[1].get("length", 107.0),
        "a2": slots[2].get("length", 105.0),
        "a3": slots[3].get("length", 150.0),
        "a4": slots[4].get("length", 65.0),
        "a5": slots[5].get("length", 0.0),
        "a6": slots[6].get("length", 115.0),
    }

    return arm_config, slots, base, link_lengths


# ─────────────────────────────────────────────────────────────────────────────
# Layer 3: API Facades
# ─────────────────────────────────────────────────────────────────────────────

def compute_ik_detail(world_x, world_y, z, arm="right_arm"):
    """
    Facade for server.py (calibration UI).
    Returns full IK detail: angles, physical, pulses.
    Does NOT apply z_offset (shows theoretical position).
    """
    arm_config, slots, base, link_lengths = _load_arm_data(arm)
    base_x = float(base.get("x", 0))
    base_y = float(base.get("y", 0))

    ik = solve_ik(world_x, world_y, z, base_x, base_y, link_lengths)
    pr = compute_pulses(ik, slots)

    return {
        "success": True,
        "local": {"x": round(ik.local_x, 2), "y": round(ik.local_y, 2)},
        "reach": round(ik.reach, 2),
        "ik": {
            "theta1": round(ik.theta1, 2), "theta2": round(ik.theta2, 2),
            "theta3": round(ik.theta3, 2), "theta4": round(ik.theta4, 2),
            "theta5": round(ik.theta5, 2), "theta6": round(ik.theta6, 2),
        },
        "physical": {
            "slot1": pr.physical[1], "slot2": pr.physical[2], "slot3": pr.physical[3],
            "slot4": pr.physical[4], "slot5": pr.physical[5], "slot6": pr.physical[6],
        },
        "pulse": {
            "slot1": pr.pulses[1], "slot2": pr.pulses[2], "slot3": pr.pulses[3],
            "slot4": pr.pulses[4], "slot5": pr.pulses[5], "slot6": pr.pulses[6],
        },
        "config_name": ik.config_name,
        "valid": ik.valid,
    }


def compute_ik_for_motion(x, y, z, arm="right_arm", orientation=None):
    """
    Facade for robot_api.py (robot motion).
    Returns minimal data for motor execution.
    Applies z_offset (safety margin) and orientation.
    """
    arm_config, slots, base, link_lengths = _load_arm_data(arm)
    base_x = float(base.get("x", 0))
    base_y = float(base.get("y", 0))

    # Apply per-arm z_offset (safety margin for calibration errors)
    z_offset = arm_config.get("z_offset", 0)
    z = z + z_offset

    ik = solve_ik(x, y, z, base_x, base_y, link_lengths)

    # Apply orientation if provided (gripper world direction = θ1 + θ5)
    if orientation is not None:
        ik.theta5 = float(orientation) - ik.theta1

    pr = compute_pulses(ik, slots)

    # Build channel→pulse targets for slot 1~5 (exclude slot 6 = gripper)
    targets = []
    for i in range(1, 6):
        channel = slots[i].get("channel", i - 1)
        targets.append((channel, pr.pulses[i]))

    return {
        "success": ik.valid,
        "targets": targets,
        "yaw_deg": round(ik.theta1, 2),
        "valid": ik.valid,
    }
