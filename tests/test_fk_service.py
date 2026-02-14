"""FK Service unit tests — validate geometry computation"""
import sys
import os
import json
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from robotics.fk_service import (
    get_logical_angle,
    compute_yaw,
    compute_reach,
    compute_base,
    circle_intersection,
    compute_geometry,
)


# ── Load real config for integration tests ──

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'servo_config.json')

def _load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


# ── Unit Tests: get_logical_angle ──

def test_logical_angle_inverted():
    """min_pos='top' → inverted: logical = zero_offset - physical"""
    config = {"left_arm": {"slot_3": {"zero_offset": 137.2, "min_pos": "top"}}}
    angles = {"slot_3": 200.0}
    result = get_logical_angle(config, "left_arm", 3, angles)
    expected = math.radians(137.2 - 200.0)
    assert abs(result - expected) < 0.001


def test_logical_angle_normal():
    """min_pos='bottom' → normal: logical = physical - zero_offset"""
    config = {"left_arm": {"slot_2": {"zero_offset": 149.3, "min_pos": "bottom"}}}
    angles = {"slot_2": 174.6}
    result = get_logical_angle(config, "left_arm", 2, angles)
    expected = math.radians(174.6 - 149.3)
    assert abs(result - expected) < 0.001


# ── Unit Tests: compute_yaw ──

def test_compute_yaw_zero():
    """physical == zero_offset → yaw = 0"""
    config = {"left_arm": {"slot_1": {"zero_offset": 180.0}}}
    point_data = {"angles": {"slot_1": 180.0}}
    result = compute_yaw(config, "left_arm", point_data)
    assert abs(result) < 0.001


def test_compute_yaw_positive():
    """physical > zero_offset → positive yaw"""
    config = {"right_arm": {"slot_1": {"zero_offset": 0.0}}}
    point_data = {"angles": {"slot_1": 45.0}}
    result = compute_yaw(config, "right_arm", point_data)
    assert abs(result - math.radians(45.0)) < 0.001


# ── Unit Tests: circle_intersection ──

def test_circle_intersection_basic():
    """Two circles with known intersection"""
    result = circle_intersection((0, 0), 5, (6, 0), 5)
    assert result is not None
    p1, p2 = result
    # Both points at x=3, y=±4
    assert abs(p1[0] - 3.0) < 0.1
    assert abs(p2[0] - 3.0) < 0.1


def test_circle_intersection_no_overlap():
    """Circles too far apart → None"""
    result = circle_intersection((0, 0), 1, (10, 0), 1)
    assert result is None


# ── Unit Tests: compute_base ──

def test_compute_base_reversible():
    """base → point → base should be consistent"""
    base_x, base_y = compute_base(0, 0, 100.0, math.radians(45.0))
    # Reversing: point at (0,0), reach=100, yaw=45°
    # base_x = 0 - 100*(-sin(45°)) = 100*sin(45°) ≈ 70.7
    # base_y = 0 - 100*cos(45°) = -100*cos(45°) ≈ -70.7
    assert abs(base_x - 70.7) < 1.0
    assert abs(base_y - (-70.7)) < 1.0


# ── Integration Test: compute_geometry ──

def test_compute_geometry_structure():
    """compute_geometry returns correct top-level structure"""
    config = _load_config()
    geometry = compute_geometry(config)

    assert "coordinate_system" in geometry
    assert "origin" in geometry
    assert "share_points" in geometry
    assert "bases" in geometry
    assert "vertices" in geometry
    assert "distances" in geometry


def test_compute_geometry_bases():
    """Both arm bases computed"""
    config = _load_config()
    geometry = compute_geometry(config)
    bases = geometry["bases"]

    assert "left_arm" in bases
    assert "right_arm" in bases
    for arm in ["left_arm", "right_arm"]:
        assert "x" in bases[arm]
        assert "y" in bases[arm]


def test_compute_geometry_vertices():
    """Vertices 1-4 computed with owner and reach"""
    config = _load_config()
    geometry = compute_geometry(config)
    vertices = geometry["vertices"]

    for vid in ["1", "2", "3", "4"]:
        assert vid in vertices
        assert "x" in vertices[vid]
        assert "y" in vertices[vid]
        assert "owner" in vertices[vid]
        assert "reach" in vertices[vid]


def test_compute_geometry_distances():
    """Distance matrix has all required sections"""
    config = _load_config()
    geometry = compute_geometry(config)
    distances = geometry["distances"]

    assert "vertex_to_vertex" in distances
    assert "base_to_vertex" in distances
    assert "share_point_to_vertex" in distances
    assert "base_to_base" in distances
    assert distances["base_to_base"] is not None
    assert distances["base_to_base"] > 0


def test_compute_geometry_matches_existing():
    """FK results should match pre-computed values in servo_config.json"""
    config = _load_config()

    existing = config.get("geometry", {})
    if not existing:
        return  # No pre-existing geometry to compare

    computed = compute_geometry(config)

    # Compare base positions (within 1mm tolerance)
    for arm in ["left_arm", "right_arm"]:
        if arm not in existing.get("bases", {}):
            continue
        ex = existing["bases"][arm]
        co = computed["bases"][arm]
        assert abs(ex["x"] - co["x"]) < 1.0, f"{arm} base X: expected {ex['x']}, got {co['x']}"
        assert abs(ex["y"] - co["y"]) < 1.0, f"{arm} base Y: expected {ex['y']}, got {co['y']}"

    # Compare vertex positions (within 2mm tolerance)
    for vid in ["1", "2", "3", "4"]:
        if vid not in existing.get("vertices", {}):
            continue
        ex = existing["vertices"][vid]
        co = computed["vertices"][vid]
        assert abs(ex["x"] - co["x"]) < 2.0, f"Vertex {vid} X: expected {ex['x']}, got {co['x']}"
        assert abs(ex["y"] - co["y"]) < 2.0, f"Vertex {vid} Y: expected {ex['y']}, got {co['y']}"
