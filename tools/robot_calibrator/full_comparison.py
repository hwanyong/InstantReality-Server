"""
Compare all measured vs calculated distances.
"""
import math
import json

with open("servo_config.json", "r") as f:
    config = json.load(f)

# Measured values (from user)
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

# Current geometry
geo = config.get("geometry", {})
bases = geo.get("bases", {})
vertices = geo.get("vertices", {})

lb = (bases.get("left_arm", {}).get("x", 0), bases.get("left_arm", {}).get("y", 0))
rb = (bases.get("right_arm", {}).get("x", 0), bases.get("right_arm", {}).get("y", 0))
v1 = (vertices.get("1", {}).get("x", 0), vertices.get("1", {}).get("y", 0))
v2 = (vertices.get("2", {}).get("x", 0), vertices.get("2", {}).get("y", 0))
v3 = (vertices.get("3", {}).get("x", 0), vertices.get("3", {}).get("y", 0))
v4 = (vertices.get("4", {}).get("x", 0), vertices.get("4", {}).get("y", 0))


def dist(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


# Calculated values
calculated = {
    "share_to_base_left": dist((0, 0), lb),
    "share_to_base_right": dist((0, 0), rb),
    "base_left_to_v1": dist(lb, v1),
    "base_left_to_v2": dist(lb, v2),
    "base_right_to_v3": dist(rb, v3),
    "base_right_to_v4": dist(rb, v4),
    "v1_v2": dist(v1, v2),
    "v2_v3": dist(v2, v3),
    "v3_v4": dist(v3, v4),
    "v4_v1": dist(v4, v1),
    "v1_v3": dist(v1, v3),
    "v2_v4": dist(v2, v4),
}

print("=" * 75)
print("MEASURED vs CALCULATED COMPARISON")
print("=" * 75)
print()
header = f"{'Item':<25} {'Measured':>10} {'Calculated':>12} {'Error':>10} {'Error%':>8}"
print(header)
print("-" * 75)

total_error = 0
for key in measured:
    m = measured[key]
    c = calculated[key]
    err = c - m
    err_pct = (err / m) * 100
    status = "[OK]" if abs(err) < 10 else "[BAD]"
    total_error += abs(err)
    print(f"{key:<25} {m:>10.1f} {c:>12.1f} {err:>+10.1f} {err_pct:>+7.1f}% {status}")

print("-" * 75)
print(f"Total absolute error: {total_error:.1f}mm")
print()
print("Coordinates used:")
print(f"  Share Point: (0, 0)")
print(f"  Left Base:   ({lb[0]:.1f}, {lb[1]:.1f})")
print(f"  Right Base:  ({rb[0]:.1f}, {rb[1]:.1f})")
print(f"  V1:          ({v1[0]:.1f}, {v1[1]:.1f})")
print(f"  V2:          ({v2[0]:.1f}, {v2[1]:.1f})")
print(f"  V3:          ({v3[0]:.1f}, {v3[1]:.1f})")
print(f"  V4:          ({v4[0]:.1f}, {v4[1]:.1f})")
