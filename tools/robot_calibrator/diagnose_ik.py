
import math
import json
import os

# Mock Config (from current file view)
LEFT_ARM_CONFIG = {
    "slot_1": {"min": 0, "max": 180, "zero_offset": 60.0, "min_pos": "right", "type": "horizontal"},
    "slot_2": {"min": 42, "max": 144, "zero_offset": 108.0, "min_pos": "bottom", "type": "vertical"},
    "slot_3": {"min": 0, "max": 144, "zero_offset": 55.0, "min_pos": "top", "type": "vertical"}
}

D1 = 107.0
A2 = 105.0
A3 = 150.0

def get_direction(slot_cfg):
    min_pos = slot_cfg.get("min_pos", "bottom")
    t = slot_cfg.get("type", "vertical")
    if t == "vertical": return 1 if min_pos == "bottom" else -1
    if t == "horizontal": return 1 if min_pos == "left" else -1
    return 1

def solve_ik_debug(x, y, z, elbow_up=True):
    r = math.sqrt(x**2 + y**2)
    s = z - D1
    D = math.sqrt(r**2 + s**2)
    
    print(f"Target: ({x}, {y}, {z}) -> r={r:.1f}, s={s:.1f}, D={D:.1f}")
    
    if D > A2 + A3: return "Unreachable (Far)"
    
    # Theta 1
    th1 = math.degrees(math.atan2(x, y))
    
    # Theta 3
    cos_th3 = (D**2 - A2**2 - A3**2) / (2 * A2 * A3)
    th3_mag = math.degrees(math.acos(max(-1, min(1, cos_th3))))
    
    # Elbow Up/Down Logic
    # Elbow Up: Theta3 usually negative (relative to straight line) if we define up as positive?
    # Let's stick to standard geometric:
    # Beta always positive.
    # Elbow Down: th2 = alpha - beta, th3 = +mag
    # Elbow Up:   th2 = alpha + beta, th3 = -mag
    
    alpha = math.degrees(math.atan2(s, r))
    beta = math.degrees(math.atan2(A3 * math.sin(math.radians(th3_mag)),
                                   A2 + A3 * math.cos(math.radians(th3_mag))))
    
    if elbow_up:
        th2 = alpha + beta
        th3 = -th3_mag
        mode = "UP"
    else:
        th2 = alpha - beta
        th3 = th3_mag
        mode = "DOWN"
        
    print(f"Solution ({mode}): th1={th1:.1f}, th2={th2:.1f}, th3={th3:.1f}")
    
    # Physical Mapping (Left Arm)
    phys = []
    for i, angle in enumerate([th1, th2, th3], 1):
        key = f"slot_{i}"
        cfg = LEFT_ARM_CONFIG[key]
        offset = cfg["zero_offset"]
        direction = get_direction(cfg)
        
        p = offset + (direction * angle)
        
        limit_min = cfg["min"]
        limit_max = cfg["max"]
        status = "OK"
        if not (limit_min <= p <= limit_max):
            status = f"FAIL ({limit_min}-{limit_max})"
            
        print(f"  Slot {i}: Math={angle:.1f} -> Phys={p:.1f} [{status}] (Dir={direction}, Off={offset})")
        phys.append(p)
        
    return phys

print("--- Testing Left Arm IK ---")
# Test Point 1: Forward and slightly up (Standard reach)
# Local X=0 (Straight ahead for Left arm?), Y=200, Z=150
solve_ik_debug(0, 200, 150, elbow_up=False) # Current implementation
solve_ik_debug(0, 200, 150, elbow_up=True)  # Proposed

print("\n--- Test Point 2: Low reach (Table) ---")
solve_ik_debug(0, 200, 50, elbow_up=False)
solve_ik_debug(0, 200, 50, elbow_up=True)

