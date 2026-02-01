# servo_config.json Analysis Report

> **Analysis Target**: `ik_tester_gui.py` last tab (Tab 5: Full Slot) functionality and `servo_config.json` interpretation
> **Analysis Date**: 2026-02-01

## 1. Overview

`servo_config.json` is the **master configuration file** for the Gemini Robot Control System. It is shared across:
- Standalone `calibrator_gui.py`
- `ik_tester_gui.py` (Inverse Kinematics Tester)
- Main Gemini Server

---

## 2. File Structure

### 2.1 Top-Level Structure

```json
{
  "left_arm": { "slot_1": {...}, "slot_2": {...}, ... "slot_6": {...} },
  "right_arm": { "slot_1": {...}, "slot_2": {...}, ... "slot_6": {...} },
  "connection": { "port": "COM7" },
  "vertices": { "1": {...}, "2": {...}, ... "8": {...} },
  "share_points": { "left_arm": {...}, "right_arm": {...} },
  "geometry": { ... }
}
```

| Section | Description |
|---------|-------------|
| `left_arm`, `right_arm` | 6 slot (joint) configurations per arm |
| `connection` | Serial port connection info (desktop tools) |
| `vertices` | 8 workspace vertices (calibration points) |
| `share_points` | Central point shared by both arms |
| `geometry` | Precomputed 3D coordinates and distances |

---

## 3. Slot (Joint) Property Analysis

### 3.1 Hardware Identification Properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `channel` | int | PCA9685 I2C channel (0-15) | `0`, `7` |
| `device_name` | string | Motor model name | `"DS3225"`, `"MG996R"` |
| `type` | string | Kinematic role | `"horizontal"`, `"vertical"`, `"roll"`, `"gripper"` |
| `actuation_range` | int | Physical rotation range (degrees) | `180`, `270` |
| `length` | float | Link length to next joint (mm) | `107.0`, `150.0` |
| `min_pos` | string | Minimum position direction indicator | `"right"`, `"top"`, `"bottom"`, `"ccw"`, `"open"` |

### 3.2 Pulse-Based Properties (Master Truth)

> [!IMPORTANT]
> **Core Principle**: The system treats **Pulse Width (µs)** as the **Master Source of Truth**.
> All angle values are derived from pulses.

| Property | Type | Description |
|----------|------|-------------|
| `pulse_min` | int | PWM pulse at 0° reference |
| `pulse_max` | int | Theoretical pulse at hardware maximum |
| `min_pulse` | int | **Software safety limit** (minimum) |
| `max_pulse_limit` | int | **Software safety limit** (maximum) |
| `zero_pulse` | int | Pulse at "Zero" (vertical pose) position |
| `initial_pulse` | int | Pulse at "Home" (retracted pose) position |

### 3.3 Derived Angle Properties (View Projection)

| Property | Type | Description |
|----------|------|-------------|
| `initial` | float | Physical angle at Home position (°) |
| `zero_offset` | float | Offset angle from 0° reference (°) |
| `min` | float | Physical minimum limit (°) |
| `max` | float | Physical maximum limit (°) |

---

## 4. Full Slot Tab (Tab 5) Functional Analysis

### 4.1 UI Layout

```
┌─────────────────┬─────────────────┬─────────────┐
│  Top-Down View  │   Side View     │  Gripper    │
│   (X/Y Input)   │  (IK: R,Z→θ2,θ3)│   State     │
│                 │                 │             │
│  • Y Slider     │  • Z Slider     │  • Gripper  │
│  • X Slider     │  • S2-S6 Status │    Visual   │
│  • θ1 Auto-calc │  • θ4 Approach  │             │
└─────────────────┴─────────────────┴─────────────┘
```

### 4.2 Configuration Loading Workflow

```python
# Configuration loading in _refresh_config()
p1 = self.context.get_slot_params(1)  # Slot 1 parameters
p2 = self.context.get_slot_params(2)  # Slot 2 parameters
# ... p3 ~ p6

# Pass link lengths to Side View Widget
self.side_widget.cfg['d1'] = p1.get('length', 107.0)  # Base height
self.side_widget.cfg['a2'] = p2.get('length', 105.0)  # Upper arm
self.side_widget.cfg['a3'] = p3.get('length', 150.0)  # Forearm
self.side_widget.cfg['a4'] = p4.get('length', 65.0)   # Wrist
```

### 4.3 get_slot_params() Return Structure

```python
{
    'channel': 0,           # PCA9685 channel
    'zero_offset': 137.6,   # Zero position offset
    'min': 107.3,           # Physical minimum limit
    'max': 270.0,           # Physical maximum limit
    'actuation_range': 270, # Motor rotation range
    'type': 'vertical',     # Motion type
    'min_pos': 'bottom',    # Minimum position direction
    'polarity': 1,          # Polarity (+1 or -1)
    'math_min': -30.0,      # Mathematical minimum (for IK)
    'math_max': 132.4,      # Mathematical maximum (for IK)
    'motor_config': {       # For PulseMapper
        'actuation_range': 270,
        'pulse_min': 500,
        'pulse_max': 2500
    },
    'length': 105.0         # Link length (mm)
}
```

---

## 5. Polarity Rules

### 5.1 Polarity Determination Logic

```python
polarity = 1

# Horizontal type: left → -1
if typ == "horizontal" and min_pos == "left":
    polarity = -1

# Vertical type: top → -1, bottom → 1
if typ == "vertical":
    polarity = -1 if min_pos == "top" else 1
```

### 5.2 Mathematical Range Calculation

```python
# Convert physical limits to mathematical frame
bound_a = (limits["min"] - zero_offset) * polarity
bound_b = (limits["max"] - zero_offset) * polarity

math_min = min(bound_a, bound_b)
math_max = max(bound_a, bound_b)
```

---

## 6. Pulse-Angle Conversion (PulseMapper)

### 6.1 Physical Angle → Pulse Conversion

```python
def physical_to_pulse(target_physical_deg, motor_config):
    actuation_range = motor_config.get("actuation_range", 180)
    pulse_min = motor_config.get("pulse_min", 500)
    pulse_max = motor_config.get("pulse_max", 2500)
    
    # Calculate ratio
    ratio = target_physical_deg / actuation_range
    pulse_us = pulse_min + (ratio * (pulse_max - pulse_min))
    
    return int(pulse_us)
```

### 6.2 Example: DS3225 (270° Motor)

| Physical Angle | Ratio | Pulse (µs) |
|----------------|-------|------------|
| 0° | 0.0 | 500 |
| 90° | 0.333 | 1166 |
| 135° | 0.5 | 1500 |
| 270° | 1.0 | 2500 |

---

## 7. IK Calculation Flow (update_visualization)

### 7.1 Step 1: θ1 Calculation (Base Yaw)

```python
# X, Y input from Top-Down View
theta1 = math.degrees(math.atan2(y, x))
R = math.sqrt(x**2 + y**2)  # Horizontal distance
```

### 7.2 Step 2: θ2, θ3 Calculation (2-Link IK)

```python
# Calculate wrist Z height (gripper pointing down at -90°)
wrist_z = z + a4 + a6

# 2-Link IK solution
theta2, theta3, is_reachable, config_name = _solve_2link_ik(R, wrist_z, d1, a2, a3)

# Invert θ3 for Slot 3 (min_pos: top)
theta3 = -theta3
```

### 7.3 Step 3: θ4 Calculation (Approach Angle)

```python
# Keep gripper perpendicular to ground
theta4 = -90.0 - theta2 + theta3
```

### 7.4 Step 4: Physical Angle Conversion

Different conversion rules per slot:

| Slot | Conversion Formula | Description |
|------|--------------------|-------------|
| S1 | `phy = theta + zero_offset` | Simple offset |
| S2 | `phy = theta + zero_offset` | Shoulder |
| S3 | `phy = zero_offset + theta` | Elbow (after inversion) |
| S4 | `phy = zero_offset - theta` | Wrist (top → inverted) |
| S5 | `phy = theta + zero_offset` | Roll (manual input) |
| S6 | `phy = theta + zero_offset` | Gripper (manual input) |

---

## 8. Vertices & Share Points Structure

### 8.1 Vertex (Workspace Vertices)

```json
"vertices": {
  "1": {
    "owner": "left_arm",
    "pulses": {
      "slot_1": 2459,
      "slot_2": 1803,
      "slot_3": 1666,
      "slot_4": 1918,
      "slot_5": 580,
      "slot_6": 2720
    },
    "angles": {
      "slot_1": 170.3,
      "slot_2": 175.9,
      "slot_3": 157.4,
      "slot_4": 127.6,
      "slot_5": 7.2,
      "slot_6": 180
    }
  }
}
```

### 8.2 Share Point (Shared Center Point)

```json
"share_points": {
  "left_arm": {
    "pulses": { "slot_1": 1664, ... },
    "angles": { "slot_1": 98.7, ... }
  }
}
```

---

## 9. Geometry Block

### 9.1 Coordinate System Definition

```json
"geometry": {
  "coordinate_system": "+X=up, +Y=left",
  "origin": "share_point"
}
```

| Axis | Direction | Description |
|------|-----------|-------------|
| +X | Up | Away from robot base |
| +Y | Left | Left side in TopView |
| Z | 0 | Ground level (all landmarks at Z=0) |

### 9.2 Precomputed Data

```json
"bases": {
  "left_arm": { "x": -34.8, "y": 227.3, "sources": 1 }
},
"vertices": {
  "1": { "x": 391.0, "y": 154.5, "owner": "left_arm" }
},
"distances": {
  "vertex_to_vertex": { "1_2": 834.7 },
  "base_to_vertex": { "left_arm": { "1": 432.0 } },
  "share_point_to_vertex": { "1": 420.4 },
  "base_to_base": 491.7
}
```

---

## 10. Slot-by-Slot Role Summary

| Slot | Role | Type | Motor | Range | Link Length |
|------|------|------|-------|-------|-------------|
| **S1** | Base Yaw (horizontal rotation) | horizontal | DS3225 | 180° | 107mm |
| **S2** | Shoulder | vertical | DS3225 | 270° | 105mm |
| **S3** | Elbow | vertical | DS3225 | 270° | 150mm |
| **S4** | Wrist Pitch | vertical | DS3225 | 180° | 65mm |
| **S5** | Roll | roll | MG996R | 180° | 30mm |
| **S6** | Gripper | gripper | MG996R | 180° | 82mm |

---

## 11. Core Design Principles

1. **Pulse-First**: All position data stored as pulses; angles are derived values
2. **Exclusive Ownership**: Each vertex belongs to only one arm
3. **Precomputed**: FK/IK results stored in geometry to minimize runtime calculations
4. **Dual-Arm Consensus**: `base_to_base` distance validates calibration
5. **Safety Limits**: `min_pulse`/`max_pulse_limit` prevent physical collisions

---

## 12. Reference File List

| File | Path | Role |
|------|------|------|
| `servo_config.json` | Root | Master configuration |
| `servo_manager.py` | `tools/robot_calibrator/` | Config load/save/API |
| `pulse_mapper.py` | `tools/robot_calibrator/` | Pulse-angle conversion |
| `full_slot2_view.py` | `tools/robot_calibrator/ik_tester/tabs/` | Tab 5 implementation |
| `app.py` | `tools/robot_calibrator/ik_tester/` | Main app & get_slot_params() |
