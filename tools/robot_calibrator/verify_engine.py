"""
Comprehensive verification: Geometry Engine vs Measured vs Trilateration.
All comparisons in one place.
"""
import sys
sys.path.insert(0, ".")

import json
import math
from itertools import product
from geometry_engine import compute_geometry, compute_reach


def run_verification(config, measured=None, threshold=50):
    """
    Run verification on the given configuration.
    
    Args:
        config: Servo configuration dict
        measured: Optional measured values dict (uses defaults if None)
        threshold: Error threshold in mm for is_valid check
    
    Returns:
        dict with keys:
            - total_error: float
            - largest_error: str (e.g., "v4_v1: 67.0mm")
            - bad_items: list of {"name": str, "error": float}
            - ok_items: list of {"name": str, "error": float}
            - is_valid: bool (total_error < threshold)
            - engine_calc: dict of calculated distances
    """
    # Default measured values
    if measured is None:
        measured = {
            "share_to_base_left": 256.5,
            "share_to_base_right": 268.0,
            "base_left_to_v1": 250,
            "base_left_to_v2": 185,
            "base_right_to_v3": 198,
            "base_right_to_v4": 225,
            "share_to_v1": 282,
            "share_to_v2": 268,
            "share_to_v3": 268,
            "share_to_v4": 296,
            "v1_v2": 390,
            "v2_v3": 380,
            "v3_v4": 390,
            "v4_v1": 284,
            "v1_v3": 546,
            "v2_v4": 546,
        }
    
    def dist(p1, p2):
        return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
    
    # Compute geometry from config
    geometry = compute_geometry(config)
    bases = geometry.get("bases", {})
    vertices = geometry.get("vertices", {})
    
    lb = (bases.get("left_arm", {}).get("x", 0), bases.get("left_arm", {}).get("y", 0))
    rb = (bases.get("right_arm", {}).get("x", 0), bases.get("right_arm", {}).get("y", 0))
    
    v = {}
    v_reach = {}
    for vid in ["1", "2", "3", "4"]:
        vdata = vertices.get(vid, {})
        v[vid] = (vdata.get("x", 0), vdata.get("y", 0))
        v_reach[vid] = vdata.get("reach", 0)
    
    # Calculate distances
    engine_calc = {
        "share_to_base_left": dist((0, 0), lb),
        "share_to_base_right": dist((0, 0), rb),
        "base_left_to_v1": v_reach["1"],
        "base_left_to_v2": v_reach["2"],
        "base_right_to_v3": v_reach["3"],
        "base_right_to_v4": v_reach["4"],
        "share_to_v1": dist((0, 0), v["1"]),
        "share_to_v2": dist((0, 0), v["2"]),
        "share_to_v3": dist((0, 0), v["3"]),
        "share_to_v4": dist((0, 0), v["4"]),
        "v1_v2": dist(v["1"], v["2"]),
        "v2_v3": dist(v["2"], v["3"]),
        "v3_v4": dist(v["3"], v["4"]),
        "v4_v1": dist(v["4"], v["1"]),
        "v1_v3": dist(v["1"], v["3"]),
        "v2_v4": dist(v["2"], v["4"]),
    }
    
    # Calculate errors
    bad_items = []
    ok_items = []
    total_error = 0
    largest_error_name = ""
    largest_error_val = 0
    
    for key in measured:
        m = measured[key]
        e = engine_calc[key]
        err = abs(e - m)
        total_error += err
        
        item = {"name": key, "error": err, "measured": m, "calculated": e}
        if err >= 10:
            bad_items.append(item)
        else:
            ok_items.append(item)
        
        if err > largest_error_val:
            largest_error_val = err
            largest_error_name = key
    
    return {
        "total_error": total_error,
        "largest_error": f"{largest_error_name}: {largest_error_val:.1f}mm",
        "bad_items": bad_items,
        "ok_items": ok_items,
        "is_valid": total_error < threshold,
        "engine_calc": engine_calc,
    }




def dist(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


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
    return ((px + h * (y2 - y1) / d, py - h * (x2 - x1) / d),
            (px - h * (y2 - y1) / d, py + h * (x2 - x1) / d))


# ============================================================
# SCRIPT MODE: Run when executed directly
# ============================================================
if __name__ == "__main__":
    with open("servo_config.json", "r") as f:
        config = json.load(f)

    # ============================================================
    # ALL MEASURED VALUES (from user)
    # ============================================================
    MEASURED = {
        # Base distances
        "share_to_base_left": 256.5,
        "share_to_base_right": 268.0,
        # Base to Vertex (reach)
        "base_left_to_v1": 250,
        "base_left_to_v2": 185,
        "base_right_to_v3": 198,
        "base_right_to_v4": 225,
        # Share to Vertex
        "share_to_v1": 282,
        "share_to_v2": 268,
        "share_to_v3": 268,
        "share_to_v4": 296,
        # Vertex to Vertex
        "v1_v2": 390,
        "v2_v3": 380,
        "v3_v4": 390,
        "v4_v1": 284,
        "v1_v3": 546,
        "v2_v4": 546,
    }

    # ============================================================
    # METHOD 1: GEOMETRY ENGINE (current implementation)
    # ============================================================
    geometry = compute_geometry(config)
    bases_engine = geometry.get("bases", {})
    vertices_engine = geometry.get("vertices", {})

    lb_engine = (bases_engine["left_arm"]["x"], bases_engine["left_arm"]["y"])
    rb_engine = (bases_engine["right_arm"]["x"], bases_engine["right_arm"]["y"])

    v_engine = {}
    v_reach_engine = {}
    for vid in ["1", "2", "3", "4"]:
        v = vertices_engine.get(vid, {})
        v_engine[vid] = (v.get("x", 0), v.get("y", 0))
        v_reach_engine[vid] = v.get("reach", 0)

    # Engine calculated distances
    engine_calc = {
        "share_to_base_left": dist((0, 0), lb_engine),
        "share_to_base_right": dist((0, 0), rb_engine),
        "base_left_to_v1": v_reach_engine["1"],
        "base_left_to_v2": v_reach_engine["2"],
        "base_right_to_v3": v_reach_engine["3"],
        "base_right_to_v4": v_reach_engine["4"],
        "share_to_v1": dist((0, 0), v_engine["1"]),
        "share_to_v2": dist((0, 0), v_engine["2"]),
        "share_to_v3": dist((0, 0), v_engine["3"]),
        "share_to_v4": dist((0, 0), v_engine["4"]),
        "v1_v2": dist(v_engine["1"], v_engine["2"]),
        "v2_v3": dist(v_engine["2"], v_engine["3"]),
        "v3_v4": dist(v_engine["3"], v_engine["4"]),
        "v4_v1": dist(v_engine["4"], v_engine["1"]),
        "v1_v3": dist(v_engine["1"], v_engine["3"]),
        "v2_v4": dist(v_engine["2"], v_engine["4"]),
    }


    # ============================================================
    # METHOD 2: TRILATERATION (using MEASURED distances)
    # ============================================================
    share = (0, 0)
    v_owners = {"1": "left", "2": "left", "3": "right", "4": "right"}

    # Use engine base positions
    lb_tri = lb_engine
    rb_tri = rb_engine

    # Get vertex candidates using MEASURED distances
    candidates = {}
    for vid in ["1", "2", "3", "4"]:
        base = lb_tri if v_owners[vid] == "left" else rb_tri
        r1 = MEASURED[f"share_to_v{vid}"]
        r2 = MEASURED[f"base_{'left' if v_owners[vid] == 'left' else 'right'}_to_v{vid}"]
        pts = circle_intersection(share, r1, base, r2)
        if pts:
            candidates[vid] = pts

    # Find best combination
    best_err = float("inf")
    best_v_tri = None

    for combo in product([0, 1], repeat=4):
        if any(vid not in candidates for vid in ["1", "2", "3", "4"]):
            break
        v = {vid: candidates[vid][combo[i]] for i, vid in enumerate(["1", "2", "3", "4"])}
        calc = {
            "v1_v2": dist(v["1"], v["2"]), "v2_v3": dist(v["2"], v["3"]),
            "v3_v4": dist(v["3"], v["4"]), "v4_v1": dist(v["4"], v["1"]),
            "v1_v3": dist(v["1"], v["3"]), "v2_v4": dist(v["2"], v["4"]),
        }
        err = sum(abs(calc[k] - MEASURED[k]) for k in ["v1_v2", "v2_v3", "v3_v4", "v4_v1", "v1_v3", "v2_v4"])
        if err < best_err:
            best_err = err
            best_v_tri = v

    # Trilateration calculated distances
    tri_calc = {
        "share_to_base_left": dist(share, lb_tri),
        "share_to_base_right": dist(share, rb_tri),
        "base_left_to_v1": dist(lb_tri, best_v_tri["1"]),
        "base_left_to_v2": dist(lb_tri, best_v_tri["2"]),
        "base_right_to_v3": dist(rb_tri, best_v_tri["3"]),
        "base_right_to_v4": dist(rb_tri, best_v_tri["4"]),
        "share_to_v1": dist(share, best_v_tri["1"]),
        "share_to_v2": dist(share, best_v_tri["2"]),
        "share_to_v3": dist(share, best_v_tri["3"]),
        "share_to_v4": dist(share, best_v_tri["4"]),
        "v1_v2": dist(best_v_tri["1"], best_v_tri["2"]),
        "v2_v3": dist(best_v_tri["2"], best_v_tri["3"]),
        "v3_v4": dist(best_v_tri["3"], best_v_tri["4"]),
        "v4_v1": dist(best_v_tri["4"], best_v_tri["1"]),
        "v1_v3": dist(best_v_tri["1"], best_v_tri["3"]),
        "v2_v4": dist(best_v_tri["2"], best_v_tri["4"]),
    }


    # ============================================================
    # OUTPUT: COMPREHENSIVE COMPARISON
    # ============================================================
    print("=" * 90)
    print("COMPREHENSIVE COMPARISON: MEASURED vs ENGINE vs TRILATERATION")
    print("=" * 90)
    print()

    # Coordinates
    print("COORDINATES:")
    print("-" * 60)
    print(f"{'Point':<15} {'Engine':<25} {'Trilateration':<25}")
    print("-" * 60)
    print(f"{'Left Base':<15} ({lb_engine[0]:>7.1f}, {lb_engine[1]:>7.1f})       ({lb_tri[0]:>7.1f}, {lb_tri[1]:>7.1f})")
    print(f"{'Right Base':<15} ({rb_engine[0]:>7.1f}, {rb_engine[1]:>7.1f})       ({rb_tri[0]:>7.1f}, {rb_tri[1]:>7.1f})")
    for vid in ["1", "2", "3", "4"]:
        e = v_engine[vid]
        t = best_v_tri[vid]
        print(f"{'V' + vid:<15} ({e[0]:>7.1f}, {e[1]:>7.1f})       ({t[0]:>7.1f}, {t[1]:>7.1f})")
    print()

    # Distances
    print("DISTANCES COMPARISON:")
    print("-" * 90)
    header = f"{'Item':<22} {'Measured':>10} {'Engine':>10} {'Eng Err':>10} {'Trilat':>10} {'Tri Err':>10}"
    print(header)
    print("-" * 90)

    categories = [
        ("=== Share to Base ===", ["share_to_base_left", "share_to_base_right"]),
        ("=== Base to Vertex ===", ["base_left_to_v1", "base_left_to_v2", "base_right_to_v3", "base_right_to_v4"]),
        ("=== Share to Vertex ===", ["share_to_v1", "share_to_v2", "share_to_v3", "share_to_v4"]),
        ("=== Vertex to Vertex ===", ["v1_v2", "v2_v3", "v3_v4", "v4_v1", "v1_v3", "v2_v4"]),
    ]

    total_eng_err = 0
    total_tri_err = 0

    for cat_name, keys in categories:
        print(cat_name)
        for key in keys:
            m = MEASURED[key]
            e = engine_calc[key]
            t = tri_calc[key]
            e_err = e - m
            t_err = t - m
            e_status = "[OK]" if abs(e_err) < 10 else "[BAD]"
            t_status = "[OK]" if abs(t_err) < 10 else "[BAD]"
            total_eng_err += abs(e_err)
            total_tri_err += abs(t_err)
            print(f"  {key:<20} {m:>10.1f} {e:>10.1f} {e_err:>+9.1f} {t:>10.1f} {t_err:>+9.1f}  {e_status} {t_status}")

    print("-" * 90)
    print(f"{'TOTAL ERROR':<22} {'':<10} {'':<10} {total_eng_err:>10.1f} {'':<10} {total_tri_err:>10.1f}")
    print()
    print(f"Engine total error:       {total_eng_err:.1f}mm")
    print(f"Trilateration total error: {total_tri_err:.1f}mm")
    print()
    if total_tri_err < total_eng_err:
        print(">> TRILATERATION IS BETTER")
    else:
        print(">> ENGINE IS BETTER")


    # ============================================================
    # TRIANGLE VERIFICATION (역검산)
    # Verify that coordinates form valid triangles with measured distances
    # ============================================================
    print()
    print("=" * 90)
    print("TRIANGLE VERIFICATION (Share-Base-Vertex)")
    print("=" * 90)
    print()
    print("For each vertex, check if the triangle (Share, Base, Vertex) has consistent side lengths.")
    print()

    triangles = [
        ("V1", "left", lb_engine, v_engine["1"], "1"),
        ("V2", "left", lb_engine, v_engine["2"], "2"),
        ("V3", "right", rb_engine, v_engine["3"], "3"),
        ("V4", "right", rb_engine, v_engine["4"], "4"),
    ]

    print(f"{'Triangle':<12} {'S->B':<12} {'B->V':<12} {'S->V':<12} {'Status':<10}")
    print("-" * 60)

    for name, arm, base, vertex, vid in triangles:
        # From coordinates
        s_to_b = dist((0, 0), base)
        b_to_v = dist(base, vertex)
        s_to_v = dist((0, 0), vertex)
    
        # From measured
        m_s_to_b = MEASURED[f"share_to_base_{arm}"]
        m_b_to_v = MEASURED[f"base_{arm}_to_v{vid}"]
        m_s_to_v = MEASURED[f"share_to_v{vid}"]
    
        # Check triangle inequality and side consistency
        # Using law of cosines: c^2 = a^2 + b^2 - 2ab*cos(C)
        # If consistent, all sides should match measured values
        err_sb = abs(s_to_b - m_s_to_b)
        err_bv = abs(b_to_v - m_b_to_v)
        err_sv = abs(s_to_v - m_s_to_v)
        total_tri_err_check = err_sb + err_bv + err_sv
    
        status = "[OK]" if total_tri_err_check < 15 else "[BAD]"
    
        print(f"{name:<12} {s_to_b:>5.1f}({err_sb:+.1f})  {b_to_v:>5.1f}({err_bv:+.1f})  {s_to_v:>5.1f}({err_sv:+.1f})  {status}")

    print()
    print("Legend: Calculated(Error vs Measured)")
    print()

    # Detailed triangle angle verification
    print("=" * 90)
    print("TRIANGLE ANGLE VERIFICATION (Law of Cosines)")
    print("=" * 90)
    print()

    for name, arm, base, vertex, vid in triangles:
        s_to_b = dist((0, 0), base)
        b_to_v = dist(base, vertex)
        s_to_v = dist((0, 0), vertex)
    
        # Law of cosines to find angle at Base: cos(B) = (a^2 + c^2 - b^2) / (2ac)
        # where a = S->B, b = S->V, c = B->V
        a, b, c = s_to_b, s_to_v, b_to_v
    
        # Check if triangle is valid
        if a + c > b and a + b > c and b + c > a:
            cos_B = (a**2 + c**2 - b**2) / (2 * a * c)
            cos_B = max(-1, min(1, cos_B))  # Clamp for numerical stability
            angle_B = math.degrees(math.acos(cos_B))
        
            # Measured values
            m_a = MEASURED[f"share_to_base_{arm}"]
            m_b = MEASURED[f"share_to_v{vid}"]
            m_c = MEASURED[f"base_{arm}_to_v{vid}"]
        
            if m_a + m_c > m_b and m_a + m_b > m_c and m_b + m_c > m_a:
                cos_B_m = (m_a**2 + m_c**2 - m_b**2) / (2 * m_a * m_c)
                cos_B_m = max(-1, min(1, cos_B_m))
                angle_B_m = math.degrees(math.acos(cos_B_m))
                angle_diff = angle_B - angle_B_m
                status = "[OK]" if abs(angle_diff) < 5 else "[BAD]"
                print(f"{name}: Angle at Base = {angle_B:.1f} deg (measured: {angle_B_m:.1f} deg, diff: {angle_diff:+.1f}) {status}")
            else:
                print(f"{name}: Invalid measured triangle")
        else:
            print(f"{name}: Invalid calculated triangle")


    # ============================================================
    # MEASURED DATA CONSISTENCY CHECK
    # Can all measured distances be satisfied simultaneously?
    # ============================================================
    print()
    print("=" * 90)
    print("MEASURED DATA CONSISTENCY CHECK")
    print("=" * 90)
    print()
    print("Testing if measured distances are mathematically consistent...")
    print()

    # Use brute force trilateration with all 16 combinations
    # to find the best possible fit

    def calc_all_distances(lb, rb, v1, v2, v3, v4):
        share = (0, 0)
        return {
            "share_to_base_left": dist(share, lb),
            "share_to_base_right": dist(share, rb),
            "base_left_to_v1": dist(lb, v1),
            "base_left_to_v2": dist(lb, v2),
            "base_right_to_v3": dist(rb, v3),
            "base_right_to_v4": dist(rb, v4),
            "share_to_v1": dist(share, v1),
            "share_to_v2": dist(share, v2),
            "share_to_v3": dist(share, v3),
            "share_to_v4": dist(share, v4),
            "v1_v2": dist(v1, v2),
            "v2_v3": dist(v2, v3),
            "v3_v4": dist(v3, v4),
            "v4_v1": dist(v4, v1),
            "v1_v3": dist(v1, v3),
            "v2_v4": dist(v2, v4),
        }

    def calc_total_error(distances):
        return sum(abs(distances[k] - MEASURED[k]) for k in MEASURED)

    # Best result from trilateration (already computed)
    print("Using trilateration-optimized positions:")
    print("-" * 60)
    print(f"  Left Base:  ({lb_tri[0]:.1f}, {lb_tri[1]:.1f})")
    print(f"  Right Base: ({rb_tri[0]:.1f}, {rb_tri[1]:.1f})")
    print(f"  V1:         ({best_v_tri['1'][0]:.1f}, {best_v_tri['1'][1]:.1f})")
    print(f"  V2:         ({best_v_tri['2'][0]:.1f}, {best_v_tri['2'][1]:.1f})")
    print(f"  V3:         ({best_v_tri['3'][0]:.1f}, {best_v_tri['3'][1]:.1f})")
    print(f"  V4:         ({best_v_tri['4'][0]:.1f}, {best_v_tri['4'][1]:.1f})")
    print()

    # Calculate distances for trilateration result
    tri_distances = calc_all_distances(
        lb_tri, rb_tri,
        best_v_tri["1"], best_v_tri["2"], best_v_tri["3"], best_v_tri["4"]
    )

    print("TRILATERATION DISTANCES vs MEASURED:")
    print("-" * 70)
    print(f"{'Item':<22} {'Measured':>10} {'Trilat':>10} {'Error':>10}")
    print("-" * 55)

    for key in MEASURED:
        m = MEASURED[key]
        t = tri_distances[key]
        err = t - m
        status = "[OK]" if abs(err) < 5 else "[BAD]"
        print(f"  {key:<20} {m:>10.1f} {t:>10.1f} {err:>+9.1f} {status}")

    print("-" * 55)
    print(f"Total trilateration error: {calc_total_error(tri_distances):.1f}mm")
    print()

    # Check which measurements have the most error
    errors = [(k, abs(tri_distances[k] - MEASURED[k])) for k in MEASURED]
    errors.sort(key=lambda x: x[1], reverse=True)

    print("LARGEST MEASUREMENT DISCREPANCIES:")
    print("-" * 40)
    for k, e in errors[:5]:
        print(f"  {k}: {e:.1f}mm error")
    print()

    if calc_total_error(tri_distances) < 50:
        print(">> MEASURED DATA IS ROUGHLY CONSISTENT")
    else:
        print(">> MEASURED DATA HAS SIGNIFICANT INCONSISTENCIES")
        print("   Some vertex measurements may be incorrect")
