"""
Verify using geometry_engine logic - CORRECTED.
Base->Vertex uses stored 3D reach, not coordinate distance.
"""
import sys
sys.path.insert(0, ".")

from geometry_engine import compute_geometry
import json
import math

with open("servo_config.json", "r") as f:
    config = json.load(f)

# Compute geometry using the engine
geometry = compute_geometry(config)

print("=" * 75)
print("GEOMETRY ENGINE OUTPUT (CORRECTED)")
print("=" * 75)
print()

# Extract computed values
bases = geometry.get("bases", {})
vertices = geometry.get("vertices", {})

lb = (bases.get("left_arm", {}).get("x", 0), bases.get("left_arm", {}).get("y", 0))
rb = (bases.get("right_arm", {}).get("x", 0), bases.get("right_arm", {}).get("y", 0))

print("Bases from geometry_engine:")
print(f"  Left Base:  ({lb[0]:.1f}, {lb[1]:.1f})")
print(f"  Right Base: ({rb[0]:.1f}, {rb[1]:.1f})")
print()

print("Vertices from geometry_engine:")
v_coords = {}
v_reach = {}
for vid in ["1", "2", "3", "4"]:
    v = vertices.get(vid, {})
    v_coords[vid] = (v.get("x", 0), v.get("y", 0))
    v_reach[vid] = v.get("reach", 0)
    print(f"  V{vid}: ({v.get('x', 0):.1f}, {v.get('y', 0):.1f}) - reach: {v.get('reach', 0):.1f}mm")

# Measured values
measured = {
    "share_to_base_left": 256.5,
    "share_to_base_right": 268.0,
    "base_left_to_v1": 250,
    "base_left_to_v2": 185,
    "base_right_to_v3": 198,
    "base_right_to_v4": 225,
    "v1_v2": 390,
    "v2_v3": 380,
    "v3_v4": 390,
    "v4_v1": 284,
    "v1_v3": 546,
    "v2_v4": 546,
}


def dist(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


# Calculated values - USE STORED REACH for Base->Vertex!
calculated = {
    "share_to_base_left": dist((0, 0), lb),
    "share_to_base_right": dist((0, 0), rb),
    # Base->Vertex uses 3D reach stored in vertex data
    "base_left_to_v1": v_reach["1"],
    "base_left_to_v2": v_reach["2"],
    "base_right_to_v3": v_reach["3"],
    "base_right_to_v4": v_reach["4"],
    # V-V distances from coordinates
    "v1_v2": dist(v_coords["1"], v_coords["2"]),
    "v2_v3": dist(v_coords["2"], v_coords["3"]),
    "v3_v4": dist(v_coords["3"], v_coords["4"]),
    "v4_v1": dist(v_coords["4"], v_coords["1"]),
    "v1_v3": dist(v_coords["1"], v_coords["3"]),
    "v2_v4": dist(v_coords["2"], v_coords["4"]),
}

print()
print("=" * 75)
print("MEASURED vs GEOMETRY_ENGINE COMPARISON (CORRECTED)")
print("=" * 75)
print()
header = f"{'Item':<25} {'Measured':>10} {'Engine':>12} {'Error':>10} {'Error%':>8}"
print(header)
print("-" * 75)

ok_count = 0
bad_count = 0
for key in measured:
    m = measured[key]
    c = calculated[key]
    err = c - m
    err_pct = (err / m) * 100
    status = "[OK]" if abs(err) < 10 else "[BAD]"
    if abs(err) < 10:
        ok_count += 1
    else:
        bad_count += 1
    print(f"{key:<25} {m:>10.1f} {c:>12.1f} {err:>+10.1f} {err_pct:>+7.1f}% {status}")

print("-" * 75)
print(f"Results: {ok_count} OK, {bad_count} BAD")
