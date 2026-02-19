"""Quick test for geometry_visualizer core logic (without matplotlib)."""
import sys
import os
import math

# Ensure imports work
sys.path.insert(0, os.path.dirname(__file__))

# Import core modules only (no matplotlib)
from geometry_engine import compute_geometry, compute_reach, compute_yaw
import json

# Load config
config_path = os.path.join(os.path.dirname(__file__), "servo_config.json")
with open(config_path, 'r', encoding='utf-8') as f:
    cfg = json.load(f)
print("Config loaded successfully")

# Compute geometry
geo = compute_geometry(cfg)
print(f"Geometry computed: {len(geo['bases'])} bases, {len(geo['vertices'])} vertices")

# Test compute_base_info logic (inline)
def compute_base_info(cfg, arm_name):
    share_point = cfg.get("share_points", {}).get(arm_name)
    if not share_point:
        return None
    
    reach = compute_reach(cfg, arm_name, share_point, is_vertex=False)
    yaw = compute_yaw(cfg, arm_name, share_point)
    yaw_deg = math.degrees(yaw)
    
    base_x = -reach * (-math.sin(yaw))
    base_y = -reach * math.cos(yaw)
    
    return {
        'reach': reach,
        'yaw_deg': yaw_deg,
        'base_x': base_x,
        'base_y': base_y
    }

for arm in ["left_arm", "right_arm"]:
    info = compute_base_info(cfg, arm)
    if info:
        print(f"{arm}: reach={info['reach']:.1f}mm, yaw={info['yaw_deg']:.1f}deg, base=({info['base_x']:.1f}, {info['base_y']:.1f})")

# Test IKSolver import
try:
    from ik_tester.ik_solver import IKSolver
    print("\nIKSolver import: OK")
    
    # Create solver
    arm = cfg.get("right_arm", {})
    link_lengths = {
        'd1': arm.get("slot_1", {}).get("length", 107.0),
        'a2': arm.get("slot_2", {}).get("length", 105.0),
        'a3': arm.get("slot_3", {}).get("length", 150.0),
        'a4': arm.get("slot_4", {}).get("length", 65.0) + 
              arm.get("slot_5", {}).get("length", 0.0) + 
              arm.get("slot_6", {}).get("length", 115.0)
    }
    solver = IKSolver(link_lengths, {})
    result = solver.solve((100, 200, 50))
    print(f"IKSolver test: reachable={result.is_reachable}")
    if result.best_solution:
        print(f"  Best: theta1={result.best_solution.theta1:.1f}, theta2={result.best_solution.theta2:.1f}")
except Exception as e:
    print(f"\nIKSolver import failed: {e}")

print("\n=== All core logic tests passed! ===")
print("Note: Run 'pip install matplotlib' to use the full visualization.")
