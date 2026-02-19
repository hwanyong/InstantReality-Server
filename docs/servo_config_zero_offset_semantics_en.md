# servo_config.json - zero_offset Semantic Definition

> ⚠️ **CRITICAL**: This document defines the **correct interpretation** of `zero_offset` values.
> Misinterpretation will break geometry calculations, IK transformations, and coordinate mappings entirely.

---

## 🔴 What is zero_offset?

### ❌ WRONG Interpretations (NEVER think this way)

- "The reference for 0 degrees"
- "Where mathematical 0° is located"
- "An offset for coordinate system conversion"

### ✅ CORRECT Definition

> **`zero_offset` = The motor's physical angle when the robot arm points FORWARD (+Y direction)**

In other words:
- **When the robot arm is extended forward** (θ1 = 0° in IK coordinate system)
- **The motor's physical angle at that moment** = `zero_offset`

---

## 📋 Real Value Examples

### Right Arm - Slot 1
```json
{
  "zero_offset": 0.0,
  "min_pos": "right",
  "type": "horizontal"
}
```
- When arm points forward → Motor physical angle = **0°**

### Left Arm - Slot 1
```json
{
  "zero_offset": 180.0,
  "min_pos": "right",
  "type": "horizontal"
}
```
- When arm points forward → Motor physical angle = **180°**

**Both arms point forward, but physical motor angles differ!**

---

## 🧮 Conversion Formulas

### World Yaw (IK Angle) → Physical Angle

```
physical_angle = zero_offset + world_yaw
```

| Example | world_yaw | zero_offset | physical_angle |
|---------|-----------|-------------|----------------|
| Right Arm forward | 0° | 0° | 0° |
| Left Arm forward | 0° | 180° | 180° |
| Right Arm right | -90° | 0° | -90° (out of range) |
| Left Arm right | -90° | 180° | 90° ✅ |

### Physical Angle → World Yaw (IK Angle)

```
world_yaw = physical_angle - zero_offset
```

| Example | physical_angle | zero_offset | world_yaw |
|---------|----------------|-------------|-----------|
| Right Arm 96.4° | 96.4° | 0° | 96.4° |
| Left Arm 98.7° | 98.7° | 180° | -81.3° |

---

## 🎯 IK Coordinate System Definition

```
      +Y (Forward)
         ↑
         │
   -X ←──┼──→ +X (Right)
         │
         ↓
      -Y (Backward)
```

- **θ1 = 0°**: Forward (+Y direction)
- **θ1 = 90°**: Left (-X direction)
- **θ1 = -90°**: Right (+X direction)

### θ1 Calculation (using atan2)
```python
theta1 = math.degrees(math.atan2(-x, y))
```

---

## 🔧 Per-Slot Interpretation and Conversion (Based on IK Tester)

> This section is based on the actual implementation in `ik_tester/tabs/full_slot3_view.py` and `ik_tester/app.py`.

### Slot 1 (Base Yaw) - Horizontal Rotation

| Property | Right Arm | Left Arm |
|----------|-----------|----------|
| Type | `horizontal` | `horizontal` |
| min_pos | `right` | `right` |
| zero_offset | 0 | 180 |
| actuation_range | 180 | 180 |

**Polarity Determination (app.py:312-317):**
```python
polarity = 1
if typ == "horizontal" and min_pos == "left": polarity = -1
if typ == "vertical":
    polarity = -1 if min_pos == "top" else 1
```

**Slot 1 Polarity:**
- `type = "horizontal"`, `min_pos = "right"` → **polarity = +1** (same for both arms)
- If `min_pos = "left"`, polarity would be -1

**min_pos: "right" Meaning:**
- When motor is at minimum angle (0°) → robot arm points **right**
- Both arms use the same convention

**Math Range Calculation (app.py:319-324):**
```python
bound_a = (limits["min"] - zero) * polarity
bound_b = (limits["max"] - zero) * polarity
math_min = min(bound_a, bound_b)
math_max = max(bound_a, bound_b)
```

| Arm | limits | zero | polarity | bound_a | bound_b | math_min | math_max |
|-----|--------|------|----------|---------|---------|----------|----------|
| Right | 0~180 | 0 | +1 | (0-0)*1=0 | (180-0)*1=180 | 0 | 180 |
| Left | 0~180 | 180 | +1 | (0-180)*1=-180 | (180-180)*1=0 | -180 | 0 |

**IMPORTANT**: Left Arm's IK θ1 range is **-180° ~ 0°**

**IK Angle Calculation (full_slot3_view.py:297-298):**
```python
# Calculate θ1 from X, Y input
theta1 = math.degrees(math.atan2(-x, y))  # forward=0°, left=+90°, right=-90°
```

**Physical Angle Conversion (full_slot3_view.py:330-332):**
```python
# Unified physical angle calculation: phy = zero_offset + theta1
phy_angle_s1 = zero_offset + theta1
phy_angle_s1 = max(0, min(actuation_range, phy_angle_s1))
```

**Example Calculation - Arm Forward (θ1=0°):**
| Arm | zero_offset | theta1 | physical |
|-----|-------------|--------|----------|
| Right | 0 | 0 | 0 + 0 = **0°** |
| Left | 180 | 0 | 180 + 0 = **180°** |

**Example Calculation - Arm Right 30° (θ1=-30°):**
| Arm | zero_offset | theta1 | physical (raw) | physical (clamped) |
|-----|-------------|--------|----------------|-------------------|
| Right | 0 | -30 | 0 + (-30) = -30° | **0°** (out of range) |
| Left | 180 | -30 | 180 + (-30) = 150° | **150°** ✅ |

**Why Left Arm and Right Arm Cover Different Directions:**
- Right Arm: physical 0°~180° → IK 0°~180° (forward~left)
- Left Arm: physical 0°~180° → IK -180°~0° (forward~right)
- This is the **mirroring encoded by zero_offset**

---

### Slot 2 (Shoulder) - Upper Arm Rotation

| Property | Right Arm | Left Arm |
|----------|-----------|----------|
| Type | `vertical` | `vertical` |
| min_pos | `bottom` | `bottom` |
| zero_offset | 137.6 | 149.3 |
| actuation_range | 270 | 270 |

**Polarity:**
- `type = "vertical"`, `min_pos = "bottom"` → **polarity = +1**

**IK and Physical Conversion:**
```python
# Calculate θ2 via 2-Link IK (shoulder angle)
theta2, theta3, is_reachable, config = _solve_2link_ik(R, wrist_z, d1, a2, a3)

# Physical conversion: forward direction (polarity = +1)
physical = zero_offset + theta2
physical = max(0, min(actuation_range, physical))
```

**min_pos: "bottom" Meaning:**
- Motor 0° → arm points down (bottom)
- Motor angle increase → arm rises up

---

### Slot 3 (Elbow) - Forearm Rotation

| Property | Right Arm | Left Arm |
|----------|-----------|----------|
| Type | `vertical` | `vertical` |
| min_pos | `top` | `top` |
| zero_offset | 125.0 | 137.2 |
| actuation_range | 270 | 270 |

**Polarity:**
- `type = "vertical"`, `min_pos = "top"` → **polarity = -1**

**‼️ IMPORTANT: θ3 Inversion Required (full_slot3_view.py:316)**

```python
# Invert θ3 from IK result
theta3 = -theta3  # min_pos: top compensation

# Physical conversion (add AFTER inversion)
physical = zero_offset + theta3
physical = max(0, min(actuation_range, physical))
```

**min_pos: "top" Meaning:**
- Motor 0° → arm **folded up** (top)
- IK calculation direction is opposite to motor → θ3 inversion needed

**Why Invert?**
- IK elbow angle: θ3 positive = arm extending
- Motor physical: angle increase = arm folding (based on top)
- Therefore sign inversion required

---

### Slot 4 (Wrist Pitch) - Wrist Vertical Rotation

| Property | Right Arm | Left Arm |
|----------|-----------|----------|
| Type | `vertical` | `vertical` |
| min_pos | `top` | `top` |
| zero_offset | 51.0 | 24.6 |
| actuation_range | 180 | 180 |

**Polarity:**
- `type = "vertical"`, `min_pos = "top"` → **polarity = -1**

**θ4 Auto-Calculation - Keep Gripper Vertical (full_slot3_view.py:387):**
```python
# Keep gripper always pointing -90° (downward)
theta4 = -90.0 - theta2 + theta3
```

**Physical Conversion - Sign Inversion! (full_slot3_view.py:397-399):**
```python
# ❗ min_pos: top → polarity = -1 applied
physical = zero_offset - theta4  # MINUS!
physical = max(0, min(actuation_range, physical))
```

**Why Subtraction?**
- General formula: `physical = zero_offset + (theta × polarity)`
- polarity = -1, so: `physical = zero_offset + theta × (-1) = zero_offset - theta`

---

### Slot 5 (Roll) - Wrist Rotation

| Property | Right Arm | Left Arm |
|----------|-----------|----------|
| Type | `roll` | `roll` |
| min_pos | `ccw` | `ccw` |
| zero_offset | 3.6 | 7.2 |
| actuation_range | 180 | 180 |

**Polarity:**
- `type = "roll"` → not covered by polarity rules → **polarity = +1**

**Conversion (Manual Input, full_slot3_view.py:420-422):**
```python
theta5 = roll_var.get()  # User slider input

# Physical conversion: forward direction
physical = zero_offset + theta5
physical = max(0, min(actuation_range, physical))
```

---

### Slot 6 (Gripper) - Gripper

| Property | Right Arm | Left Arm |
|----------|-----------|----------|
| Type | `gripper` | `gripper` |
| min_pos | `open` | `open` |
| zero_offset | 0 | 126.4 |
| actuation_range | 180 | 180 |

**Polarity:**
- `type = "gripper"` → not covered by polarity rules → **polarity = +1**

**Conversion (Manual Input, full_slot3_view.py:443-445):**
```python
theta6 = gripper_var.get()  # User slider input

# Physical conversion: forward direction
physical = zero_offset + theta6
physical = max(0, min(actuation_range, physical))
```

---

## 📊 Per-Slot Conversion Formula Summary

| Slot | Type | min_pos | Polarity | Conversion Formula | Notes |
|------|------|---------|----------|-------------------|-------|
| 1 | horizontal | right | +1 | `phy = zero + θ1` | Unified for both arms |
| 2 | vertical | bottom | +1 | `phy = zero + θ2` | Forward direction |
| 3 | vertical | top | -1 | `phy = zero + θ3` | **θ3 inverted first** |
| 4 | vertical | top | -1 | `phy = zero - θ4` | **Sign inversion in formula** |
| 5 | roll | ccw | +1 | `phy = zero + θ5` | Manual |
| 6 | gripper | open | +1 | `phy = zero + θ6` | Manual |

---

## 🔢 Polarity Determination Rules (app.py:312-317)

```python
# Polarity logic in get_slot_params() function
polarity = 1

if typ == "horizontal" and min_pos == "left":
    polarity = -1

if typ == "vertical":
    polarity = -1 if min_pos == "top" else 1
```

| Type | min_pos | Polarity | Currently Used Slot |
|------|---------|----------|---------------------|
| horizontal | right | +1 | Slot 1 (both arms) |
| horizontal | left | -1 | (unused) |
| vertical | bottom | +1 | Slot 2 (both arms) |
| vertical | top | **-1** | Slot 3, 4 (both arms) |
| roll | ccw | +1 | Slot 5 (both arms) |
| gripper | open | +1 | Slot 6 (both arms) |

---

## 🔄 Left Arm vs Right Arm Differences Summary

### Slot 1 (Base Yaw)
| Item | Right Arm | Left Arm |
|------|-----------|----------|
| zero_offset | 0 | 180 |
| min_pos | right | right |
| polarity | +1 | +1 |
| IK valid range | 0° ~ 180° | -180° ~ 0° |
| Physical coverage | forward ~ left | right ~ forward |

**Key Point**: `min_pos` is same for both arms → **difference is ONLY in `zero_offset`**

### Slot 2-6
- min_pos and type are same for both arms
- polarity is same for both arms
- **Difference is ONLY in `zero_offset` and some `limits`**

---

## ⚠️ Common Mistakes

### 1. Adding Left Arm Mirroring
```python
# ❌ WRONG - DO NOT DO THIS!
if arm == "left_arm":
    world_yaw = 180.0 - logical_angle
```

**Reason**: `zero_offset` already encodes the arm direction difference.
Additional mirroring is **double compensation** and produces completely wrong results.

### 2. Misunderstanding zero_offset as "mathematical 0°"
```python
# ❌ WRONG interpretation
# "zero_offset=180 means mathematical 0° is at physical 180°?"
```

**CORRECT interpretation**:
```
"zero_offset=180 means the motor reads 180° when pointing forward"
```

### 3. Ignoring Slot 1 min_pos
```python
# ❌ WRONG thinking
# "Slot 1 doesn't use min_pos based interpretation?"
```

**FACT**: Slot 1 DOES use min_pos for polarity determination.
Both arms have `min_pos: "right"` so polarity = +1 for both.

### 4. Missing Slot 3 Inversion
```python
# ❌ WRONG
physical = zero_offset + theta3_from_ik  # Using IK result directly

# ✅ CORRECT
theta3 = -theta3_from_ik  # Invert first!
physical = zero_offset + theta3
```

### 5. Wrong Sign Direction for Slot 4
```python
# ❌ WRONG
physical = zero_offset + theta4

# ✅ CORRECT (min_pos: top → polarity = -1)
physical = zero_offset - theta4
```

---

## 📐 Notes for cos/sin Usage

### World Coordinate System: +X=right, +Y=up

```python
# If world_yaw is correctly calculated:
# cos(world_yaw) → X direction component
# sin(world_yaw) → Y direction component

x = base_x + reach * math.cos(world_yaw)  # Right direction
y = base_y + reach * math.sin(world_yaw)  # Up/Forward direction
```

### Caution: Verify world_yaw 0° Direction

Current IK:
- **θ1 = 0°** = Forward (+Y)
- **cos(0°) = 1, sin(0°) = 0** → (1, 0) = +X direction?!

**Mismatch exists!** → World coordinate system and IK θ1 reference differ by 90°

---

## 📜 Final Summary

| Concept | Definition |
|---------|------------|
| `zero_offset` | Motor physical angle when pointing forward |
| `min_pos` | Direction when motor is at minimum angle (used for polarity) |
| `polarity` | Sign direction for IK→Physical conversion (+1 or -1) |
| `world_yaw` | Rotation angle in IK coords (forward=0°) |
| `physical_angle` | Actual motor angle |
| Conversion | `physical = zero_offset + (theta × polarity)` |

---

*Document created: 2026-02-03*
*Ignoring this document and misinterpreting will break geometry calculations.*
