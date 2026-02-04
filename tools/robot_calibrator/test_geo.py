"""Test geometry engine module directly."""

from servo_manager import ServoManager
from geometry_engine import compute_reach, compute_geometry
import math


# Load config via ServoManager
m = ServoManager()

# Check V1 and V3 reach using geometry_engine functions
v1 = m.config['vertices']['1']
v3 = m.config['vertices']['3']

print("=== V1 (left_arm) ===")
print("Angles:", v1.get('angles'))
r1 = compute_reach(m.config, 'left_arm', v1, True)
print("Reach:", r1)

print("\n=== V3 (right_arm) ===")
print("Angles:", v3.get('angles'))
r3 = compute_reach(m.config, 'right_arm', v3, True)
print("Reach:", r3)

# Debug FK calculation for V3
angles = v3.get('angles', {})
arm = 'right_arm'

# Get logical angles
slot2_cfg = m.config[arm]['slot_2']
slot3_cfg = m.config[arm]['slot_3']

phy2 = angles.get('slot_2', 0)
phy3 = angles.get('slot_3', 0)
zero2 = slot2_cfg.get('zero_offset', 0)
zero3 = slot3_cfg.get('zero_offset', 0)

theta2 = phy2 - zero2
theta3 = phy3 - zero3

print("\n=== V3 FK Debug ===")
print(f"Physical: slot_2={phy2}, slot_3={phy3}")
print(f"Zero offset: slot_2={zero2}, slot_3={zero3}")
print(f"Logical: theta2={theta2}, theta3={theta3}")
print(f"cos(theta2)={math.cos(math.radians(theta2)):.4f}")
print(f"cos(theta2+theta3)={math.cos(math.radians(theta2+theta3)):.4f}")

a2 = slot2_cfg.get('length', 0)
a3 = slot3_cfg.get('length', 0)
r = a2 * math.cos(math.radians(theta2)) + a3 * math.cos(math.radians(theta2 + theta3))
print(f"Calculated reach: {a2}*{math.cos(math.radians(theta2)):.4f} + {a3}*{math.cos(math.radians(theta2+theta3)):.4f} = {r:.1f}")

# Test compute_geometry through ServoManager wrapper
print("\n=== Testing ServoManager.compute_geometry() wrapper ===")
result = m.compute_geometry()
print(f"Bases: {list(result['bases'].keys())}")
print(f"Vertices: {list(result['vertices'].keys())}")
print(f"Base to base distance: {result['distances']['base_to_base']}")
