"""
Full coordinate and V-V distance analysis for both scenarios.
"""
import math
import json

# Load config
with open("servo_config.json", "r") as f:
    config = json.load(f)

def circle_intersection(c1, r1, c2, r2):
    x1, y1 = c1
    x2, y2 = c2
    d = math.sqrt((x2-x1)**2 + (y2-y1)**2)
    if d > r1 + r2 or d < abs(r1 - r2):
        return None
    a = (r1**2 - r2**2 + d**2) / (2*d)
    if r1**2 - a**2 < 0:
        return None
    h = math.sqrt(r1**2 - a**2)
    px = x1 + a*(x2-x1)/d
    py = y1 + a*(y2-y1)/d
    p1 = (px + h*(y2-y1)/d, py - h*(x2-x1)/d)
    p2 = (px - h*(y2-y1)/d, py + h*(x2-x1)/d)
    return p1, p2

def calc_vv_distances(vertices):
    """Calculate all V-V distances"""
    v_list = list(vertices.items())
    distances = {}
    for i in range(len(v_list)):
        for j in range(i+1, len(v_list)):
            v1_id, v1_pos = v_list[i]
            v2_id, v2_pos = v_list[j]
            dist = math.sqrt((v1_pos[0]-v2_pos[0])**2 + (v1_pos[1]-v2_pos[1])**2)
            distances[f"V{v1_id}-V{v2_id}"] = dist
    return distances

# Current coordinates from geometry
geo = config.get("geometry", {})
vertices_geo = geo.get("vertices", {})
bases_geo = geo.get("bases", {})

print("=" * 70)
print("CURRENT COORDINATES (from geometry)")
print("=" * 70)

# Extract current positions
current = {
    "left_base": (bases_geo.get("left_arm", {}).get("x", 0), bases_geo.get("left_arm", {}).get("y", 0)),
    "right_base": (bases_geo.get("right_arm", {}).get("x", 0), bases_geo.get("right_arm", {}).get("y", 0)),
}

print(f"Left Base:  ({current['left_base'][0]:.1f}, {current['left_base'][1]:.1f})")
print(f"Right Base: ({current['right_base'][0]:.1f}, {current['right_base'][1]:.1f})")
print()

current_vertices = {}
for vid, data in vertices_geo.items():
    current_vertices[vid] = (data["x"], data["y"])
    print(f"V{vid}: ({data['x']:.1f}, {data['y']:.1f}) - owner: {data.get('owner', 'N/A')}")

print()
print("CURRENT V-V DISTANCES:")
print("-" * 50)
curr_distances = calc_vv_distances(current_vertices)
for k, v in sorted(curr_distances.items()):
    print(f"  {k}: {v:.1f}mm")

# ============================================================
# SCENARIO 1: Fix V1 coordinates (Base stays)
# ============================================================
print()
print("=" * 70)
print("SCENARIO 1: Fix V1 (Base stays at (-253, -44))")
print("=" * 70)

# Known measured distances
share_to_v1 = 282  # measured
base_to_v1 = 250   # measured

left_base = (-253, -44)
v1_opts = circle_intersection((0, 0), share_to_v1, left_base, base_to_v1)

if v1_opts:
    # Choose the one in upper half (y > 0)
    v1_new = v1_opts[0] if v1_opts[0][1] > 0 else v1_opts[1]
    print(f"V1 corrected: ({v1_new[0]:.1f}, {v1_new[1]:.1f})")
    
    # Use corrected V1 for scenario 1
    scenario1_vertices = current_vertices.copy()
    scenario1_vertices["1"] = v1_new
    
    print()
    print("SCENARIO 1 V-V DISTANCES:")
    print("-" * 50)
    s1_distances = calc_vv_distances(scenario1_vertices)
    for k, v in sorted(s1_distances.items()):
        curr = curr_distances.get(k, 0)
        diff = v - curr
        print(f"  {k}: {v:.1f}mm (diff: {diff:+.1f})")

# ============================================================
# SCENARIO 2: Fix Base coordinates (V1 stays)
# ============================================================
print()
print("=" * 70)
print("SCENARIO 2: Fix Base (V1 stays at (-218, 178))")
print("=" * 70)

share_to_base = 257  # measured
v1_pos = (-218, 178)

base_opts = circle_intersection((0, 0), share_to_base, v1_pos, base_to_v1)

if base_opts:
    # Choose the one in lower half (y < 0)
    base_new = base_opts[1] if base_opts[1][1] < 0 else base_opts[0]
    print(f"Left Base corrected: ({base_new[0]:.1f}, {base_new[1]:.1f})")
    
    # Keep V1 same but note the base change would affect V2 too
    print()
    print("Note: Base change would affect V2 calculation as well")
    
    # For now, just show V1 with original position
    scenario2_vertices = current_vertices.copy()
    
    print()
    print("SCENARIO 2 V-V DISTANCES (V1 unchanged):")
    print("-" * 50)
    s2_distances = calc_vv_distances(scenario2_vertices)
    for k, v in sorted(s2_distances.items()):
        print(f"  {k}: {v:.1f}mm")

# ============================================================
# COMPARISON SUMMARY
# ============================================================
print()
print("=" * 70)
print("COMPARISON: V1-V2 Distance")
print("=" * 70)
print(f"MEASURED V1-V2:     390.0mm")
print(f"CURRENT:            {curr_distances.get('V1-V2', 0):.1f}mm (error: {curr_distances.get('V1-V2', 0) - 390:.1f}mm)")
print(f"SCENARIO 1 (V1 fix): {s1_distances.get('V1-V2', 0):.1f}mm (error: {s1_distances.get('V1-V2', 0) - 390:.1f}mm)")
