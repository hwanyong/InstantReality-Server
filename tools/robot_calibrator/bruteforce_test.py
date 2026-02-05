"""
Brute force test all intersection point combinations.
"""
import sys
sys.path.insert(0, ".")

import json
import math
from itertools import product
from geometry_engine import compute_geometry, compute_reach

with open("servo_config.json", "r") as f:
    config = json.load(f)


def circle_intersection(c1, r1, c2, r2):
    x1, y1 = c1
    x2, y2 = c2
    d = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
        return None
    a = (r1 ** 2 - r2 ** 2 + d ** 2) / (2 * d)
    h_sq = r1 ** 2 - a ** 2
    if h_sq < 0:
        return None
    h = math.sqrt(h_sq)
    px = x1 + a * (x2 - x1) / d
    py = y1 + a * (y2 - y1) / d
    p1 = (px + h * (y2 - y1) / d, py - h * (x2 - x1) / d)
    p2 = (px - h * (y2 - y1) / d, py + h * (x2 - x1) / d)
    return p1, p2


def compute_share_to_vertex(config, arm, vertex):
    a2 = config.get(arm, {}).get("slot_2", {}).get("length", 0)
    a3 = config.get(arm, {}).get("slot_3", {}).get("length", 0)
    a4 = config.get(arm, {}).get("slot_4", {}).get("length", 0)
    a5 = config.get(arm, {}).get("slot_5", {}).get("length", 0)
    a6 = config.get(arm, {}).get("slot_6", {}).get("length", 0)
    angles = vertex.get("angles", {})
    
    def get_angle(slot_num):
        slot_cfg = config.get(arm, {}).get(f"slot_{slot_num}", {})
        physical = angles.get(f"slot_{slot_num}", slot_cfg.get("zero_offset", 0))
        zero_offset = slot_cfg.get("zero_offset", 0)
        min_pos = slot_cfg.get("min_pos", "")
        if min_pos in ["top", "left", "cw"]:
            return math.radians(zero_offset - physical)
        else:
            return math.radians(physical - zero_offset)
    
    t2, t3, t4 = get_angle(2), get_angle(3), get_angle(4)
    fk_x = a2*math.cos(t2) + a3*math.cos(t2+t3) + (a4+a5+a6)*math.cos(t2+t3+t4)
    fk_y = a2*math.sin(t2) + a3*math.sin(t2+t3) + (a4+a5+a6)*math.sin(t2+t3+t4)
    return math.sqrt(fk_x**2 + fk_y**2)


def dist(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)


# Measured V-V distances
measured = {
    "v1_v2": 390, "v2_v3": 380, "v3_v4": 390,
    "v4_v1": 284, "v1_v3": 546, "v2_v4": 546,
}

# Get bases
geometry = compute_geometry(config)
bases = geometry.get("bases", {})
lb = (bases["left_arm"]["x"], bases["left_arm"]["y"])
rb = (bases["right_arm"]["x"], bases["right_arm"]["y"])

# Get vertex intersection candidates
vertices_config = config.get("vertices", {})
candidates = {}

for vid in ["1", "2", "3", "4"]:
    v_data = vertices_config.get(vid, {})
    owner = v_data.get("owner")
    base = lb if owner == "left_arm" else rb
    
    reach_h, reach_3d = compute_reach(config, owner, v_data, is_vertex=True)
    share_to_v = compute_share_to_vertex(config, owner, v_data)
    
    pts = circle_intersection((0, 0), share_to_v, base, reach_3d)
    if pts:
        candidates[vid] = pts
    else:
        # Fallback
        candidates[vid] = ((0, 0), (0, 0))

print("Candidate positions:")
for vid, pts in candidates.items():
    print(f"  V{vid}: A=({pts[0][0]:.1f}, {pts[0][1]:.1f}), B=({pts[1][0]:.1f}, {pts[1][1]:.1f})")

# Test all 16 combinations (2^4)
print()
print("Testing all 16 combinations...")
print("=" * 80)

best_error = float('inf')
best_combo = None
best_vertices = None

for combo in product([0, 1], repeat=4):
    v1 = candidates["1"][combo[0]]
    v2 = candidates["2"][combo[1]]
    v3 = candidates["3"][combo[2]]
    v4 = candidates["4"][combo[3]]
    
    calc = {
        "v1_v2": dist(v1, v2), "v2_v3": dist(v2, v3), "v3_v4": dist(v3, v4),
        "v4_v1": dist(v4, v1), "v1_v3": dist(v1, v3), "v2_v4": dist(v2, v4),
    }
    
    total_error = sum(abs(calc[k] - measured[k]) for k in measured)
    
    if total_error < best_error:
        best_error = total_error
        best_combo = combo
        best_vertices = {"1": v1, "2": v2, "3": v3, "4": v4}

print()
print(f"BEST COMBINATION: {best_combo}")
print(f"Total error: {best_error:.1f}mm")
print()
print("Vertex positions:")
for vid, pos in best_vertices.items():
    print(f"  V{vid}: ({pos[0]:.1f}, {pos[1]:.1f})")
print()
print("V-V Distance comparison:")
print("-" * 60)
pairs = [("1", "2"), ("2", "3"), ("3", "4"), ("4", "1"), ("1", "3"), ("2", "4")]
keys = ["v1_v2", "v2_v3", "v3_v4", "v4_v1", "v1_v3", "v2_v4"]
for (v1_id, v2_id), key in zip(pairs, keys):
    calc_dist = dist(best_vertices[v1_id], best_vertices[v2_id])
    err = calc_dist - measured[key]
    status = "[OK]" if abs(err) < 15 else "[BAD]"
    print(f"  {key}: measured={measured[key]:.0f}, calc={calc_dist:.1f}, err={err:+.1f} {status}")
