# 3D Robot Kinematics Prompt Validation Report

> Analysis Date: 2026-02-01  
> Target: "3D Robot Kinematics Calculation Expert" System Prompt

---

## 1. Accurate Points ✅

| Item | Prompt Content | Verification |
|------|---------------|--------------|
| Origin Definition | Share Point = (0, 0, 0) | ✅ `geometry.origin: "share_point"` |
| Coordinate System | +X=up, +Y=left | ✅ `geometry.coordinate_system` |
| Link Lengths | L1=105, L2=150 (mm) | ✅ slot_2.length, slot_3.length |
| Zero Pulse Reference | zero_pulse based calculation | ✅ Used in compute_reach() |
| Slot 4 Polarity | θ = zero_offset - physical | ✅ Confirmed in code and KI docs |

---

## 2. Missing Critical Points ⚠️

### 2.1 Dual Reach Protocol Not Included

The prompt presents only one Reach formula, but the actual system uses **two protocols**:

#### Vertex Protocol (Fixed 90° Approach)
```
When gripper is vertical (perpendicular to ground) - wrist contribution = 0
Reach = |a2 * cos(θ2) + a3 * cos(θ2 + θ3)|
```

#### Share Point Protocol (Variable Pose)
```
Full FK projection - includes wrist angle
Reach = a2*cos(θ2) + a3*cos(θ2+θ3) + (a4+a5+a6)*cos(θ2+θ3+θ4)
```

> **Issue**: The prompt's formula only applies to Vertex; Share Point requires more complex FK.

---

### 2.2 Wrist Section Omitted

Prompt mentions only L1=105, L2=150, but actual robot has:

| Slot | Length (mm) | Role |
|------|-------------|------|
| slot_1 | 107.0 | Base Height (d1) |
| slot_2 | 105.0 | Upper Arm |
| slot_3 | 150.0 | Forearm |
| slot_4 | 65.0 | Wrist |
| slot_5 | 30.0 | Roll |
| slot_6 | 82.0 | Gripper |

**Total Max Reach** = 105 + 150 + 65 + 30 + 82 = **432mm**

---

### 2.3 Incomplete min_pos Direction Rules

Prompt only mentions "determine CW/CCW sign", but exact rules are:

```
min_pos ∈ ["bottom", "right", "open", "ccw"] → θ_logical = (θ_physical - zero_offset)
min_pos ∈ ["top", "left", "closed", "cw"]   → θ_logical = -(θ_physical - zero_offset)
```

---

## 3. Errors ❌

### 3.1 Output Format Requests Z Coordinate

Prompt:
```json
"final_coordinates": { "x": "value", "y": "value", "z": "value" }
```

Current system:
```json
"vertices": { "1": { "x": 391.0, "y": 154.5, "owner": "left_arm" } }
```

**Reason**: Current system assumes Ground Plane (Z=0) and calculates **2D coordinates only**.

### 3.2 Base Z Coordinate = 0 Notation

Prompt shows Base Z=0, but actual Base Height (d1) = **107mm**.  
However, since current system calculates on 2D plane, Z is omitted.

---

## 4. Suggested Corrections

### 4.1 Add Dual Reach Protocol

```markdown
### Dual Reach Protocol
1. **Vertex Protocol (Fixed 90°)**:
   Formula: Reach = |a2·cos(θ2^log) + a3·cos(θ2^log + θ3^log)|
   
2. **Share Point Protocol (Variable Pose)**:
   Formula: Reach = a2·cos(θ2) + a3·cos(θ2+θ3) + (a4+a5+a6)·cos(θ2+θ3+θ4)
```

### 4.2 Clarify Logical Angle Conversion

```
θ_logical = zero_offset - θ_physical  (Slot 4 only)
θ_logical = θ_physical - zero_offset  (Other slots)
```

### 4.3 Remove Z from Output Format

Based on current system, output 2D coordinates only:
```json
"final_coordinates": { "x": "value", "y": "value" }
```

---

## 5. Current System Verification Results

`servo_config.json` geometry section:

```
Base-to-Base: 491.7mm (expected 512mm, 4% error)
Left reach: 229.9mm, yaw: -81.3°
Right reach: 261.9mm, yaw: 96.4°
```

---

## 6. Evaluation Summary

| Criteria | Score | Notes |
|----------|-------|-------|
| Structural Completeness | ★★★★☆ | Systematic step-by-step guide |
| Formula Accuracy | ★★★☆☆ | Dual Protocol not reflected |
| Codebase Alignment | ★★★☆☆ | 3D request vs 2D system |
| Practicality | ★★★★☆ | Past mistake warnings useful |

**Overall**: Conceptually correct, but needs modification to reflect Dual Reach Protocol and 2D coordinate system.
