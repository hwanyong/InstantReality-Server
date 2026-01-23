# servo_config.json Analysis Document

## 1. Zero Point (0°) Definition

**0 degrees represents the posture where the arm is extended horizontally toward the table (scene).**

---

## 2. File Structure Overview

```json
{
  "right_arm": { "slot_1" ~ "slot_6" },
  "left_arm":  { "slot_1" ~ "slot_6" },
  "connection": { "port": "COM7" }
}
```

---

## 3. Parameter Definitions (Complete)

| Parameter | Type | Description |
|---|---|---|
| `channel` | int | PCA9685 PWM board channel number (0~15) |
| `min` | float | Software-allowed minimum angle |
| `max` | float | Software-allowed maximum angle |
| `type` | string | Joint type (`horizontal`, `roll`, `gripper`, or omitted for vertical joints) |
| `min_pos` | string | **Physical position at minimum angle (min)** → Determines motion polarity |
| `initial` | float | Initial angle to move to at startup (°) |
| `length` | float | Physical length of the link (mm) - for IK calculations |
| `zero_offset` | float | **Raw servo angle corresponding to zero point (0°)** |
| `actuation_range` | int | Servo's physical actuation range (180° or 270°) |
| `pulse_min` | int | Servo spec minimum pulse (μs) |
| `pulse_max` | int | Servo spec maximum pulse (μs) |
| `device_name` | string | Servo model name (DS3225, MG996R, etc.) |
| `initial_pulse` | int | Actual pulse value to output at startup (μs) |
| `zero_pulse` | int | **Pulse value corresponding to 0° posture** (μs) - Core calibration value |
| `min_pulse` | int | Software-allowed minimum pulse (safety limit) |
| `max_pulse_limit` | int | Software-allowed maximum pulse (safety limit) |

---

## 4. Right Arm Detailed Slot Analysis

### Slot 1 - Base Rotation (Base Yaw)

| Property | Value | Meaning |
|---|---|---|
| `channel` | 0 | PWM Channel 0 |
| `type` | `horizontal` | Horizontal plane rotation |
| `min_pos` | `right` | min(0°) → Right side |
| `min` → `max` | 0° → 180° | Right → Left rotation |
| `zero_offset` | 2.7° | Forward (horizontal extend) = Servo 2.7° |
| `length` | 107mm | Shoulder height/base offset |
| `actuation_range` | 180° | 180-degree servo |
| `zero_pulse` | 530μs | 0° position pulse |
| `device_name` | DS3225 | Servo model |

**Motion Direction**: Angle increase → **Counter-Clockwise (CCW) / Left**

---

### Slot 2 - Shoulder (Shoulder Pitch)

| Property | Value | Meaning |
|---|---|---|
| `channel` | 1 | PWM Channel 1 |
| `type` | (none) | Vertical joint |
| `min_pos` | `bottom` | min(86.7°) → Downward direction |
| `min` → `max` | 86.7° → 270° | Physical range of motion |
| `zero_offset` | 126° | Forward horizontal = Servo 126° |
| `actuation_range` | 270° | 270-degree servo |
| `length` | 105mm | Upper arm length |
| `zero_pulse` | 1433μs | 0° position pulse |
| `device_name` | DS3225 | Servo model |

**Motion Direction**: Angle increase → **Down** / Angle decrease → **Up**

> ⚠️ Since `min_pos: bottom`, decreasing the software angle moves the arm **upward**.

---

### Slot 3 - Elbow (Elbow Pitch)

| Property | Value | Meaning |
|---|---|---|
| `channel` | 2 | PWM Channel 2 |
| `type` | (none) | Vertical joint |
| `min_pos` | `top` | min(0°) → Upward direction (folded) |
| `min` → `max` | 0° → 259.9° | Folded → Extended |
| `zero_offset` | 108.7° | Forward horizontal = Servo 108.7° |
| `actuation_range` | 270° | 270-degree servo |
| `length` | 150mm | Forearm length |
| `zero_pulse` | 1305μs | 0° position pulse |
| `device_name` | DS3225 | Servo model |

**Motion Direction**: Angle increase → **Elbow Extension**

---

### Slot 4 - Wrist Horizontal Rotation (Wrist Yaw)

| Property | Value | Meaning |
|---|---|---|
| `channel` | 3 | PWM Channel 3 |
| `type` | `horizontal` | Horizontal plane rotation |
| `min_pos` | `left` | min(0°) → Left side |
| `min` → `max` | 0° → 180° | Left → Right |
| `zero_offset` | 110° | Neutral (straight) = Servo 110° |
| `length` | 65mm | Wrist offset |
| `zero_pulse` | 1722μs | 0° position pulse |
| `device_name` | DS3225 | Servo model |

**Motion Direction**: Angle increase → **Clockwise (CW) / Right**

---

### Slot 5 - Wrist Roll

| Property | Value | Meaning |
|---|---|---|
| `channel` | 4 | PWM Channel 4 |
| `type` | `roll` | Roll rotation |
| `min_pos` | `ccw` | min(0°) → Counter-clockwise direction |
| `min` → `max` | 0° → 180° | CCW → CW |
| `zero_offset` | 85° | Neutral = Servo 85° |
| `length` | 30mm | Wrist roll segment |
| `zero_pulse` | 1444μs | 0° position pulse |
| `device_name` | MG996R | Servo model |

**Motion Direction**: Angle increase → **Clockwise Roll (CW Roll)**

---

### Slot 6 - Gripper

| Property | Value | Meaning |
|---|---|---|
| `channel` | 5 | PWM Channel 5 |
| `type` | `gripper` | Gripper |
| `min_pos` | `open` | min(0°) → Fully open |
| `min` → `max` | 0° → 55.7° | Open → Closed |
| `zero_offset` | 0° | Open state = 0° |
| `length` | 70mm | Gripper length |
| `zero_pulse` | 500μs | 0° position pulse |
| `device_name` | MG996R | Servo model |

**Motion Direction**: Angle increase → **Close**

---

## 5. Left Arm Detailed Slot Analysis

### Slot 1 - Base Rotation (Base Yaw)

| Property | Value | Meaning |
|---|---|---|
| `channel` | 6 | PWM Channel 6 |
| `type` | `horizontal` | Horizontal plane rotation |
| `min_pos` | `right` | min(0°) → Right side |
| `min` → `max` | 0° → 180° | Right → Left rotation |
| `zero_offset` | 171° | Forward horizontal = Servo 171° |
| `length` | 107mm | Shoulder height/base offset |
| `zero_pulse` | 2400μs | 0° position pulse |
| `device_name` | DS3225 | Servo model |

---

### Slot 2 - Shoulder (Shoulder Pitch)

| Property | Value | Meaning |
|---|---|---|
| `channel` | 7 | PWM Channel 7 |
| `min_pos` | `bottom` | min(107.6°) → Downward direction |
| `min` → `max` | 107.6° → 270° | Physical range of motion |
| `zero_offset` | 139.1° | Forward horizontal = Servo 139.1° |
| `actuation_range` | 270° | 270-degree servo |
| `length` | 105mm | Upper arm length |
| `zero_pulse` | 1530μs | 0° position pulse |
| `device_name` | DS3225 | Servo model |

---

### Slot 3 - Elbow (Elbow Pitch)

| Property | Value | Meaning |
|---|---|---|
| `channel` | 8 | PWM Channel 8 |
| `min_pos` | `top` | min(0°) → Upward direction |
| `min` → `max` | 0° → 270° | Folded → Extended |
| `zero_offset` | 121° | Forward horizontal = Servo 121° |
| `actuation_range` | 270° | 270-degree servo |
| `length` | 150mm | Forearm length |
| `zero_pulse` | 1396μs | 0° position pulse |
| `device_name` | DS3225 | Servo model |

---

### Slot 4 - Wrist Horizontal Rotation (Wrist Yaw)

| Property | Value | Meaning |
|---|---|---|
| `channel` | 9 | PWM Channel 9 |
| `type` | `horizontal` | Horizontal plane rotation |
| `min_pos` | `left` | min(0°) → Left side |
| `min` → `max` | 0° → 180° | Left → Right |
| `zero_offset` | 91.2° | Neutral = Servo 91.2° |
| `length` | 65mm | Wrist offset |
| `zero_pulse` | 1513μs | 0° position pulse |
| `device_name` | DS3225 | Servo model |

---

### Slot 5 - Wrist Roll

| Property | Value | Meaning |
|---|---|---|
| `channel` | 10 | PWM Channel 10 |
| `type` | `roll` | Roll rotation |
| `min_pos` | `ccw` | min(0°) → Counter-clockwise direction |
| `min` → `max` | 0° → 180° | CCW → CW |
| `zero_offset` | 90° | Neutral = Servo 90° |
| `length` | 30mm | Wrist roll segment |
| `zero_pulse` | 1500μs | 0° position pulse |
| `device_name` | MG996R | Servo model |

---

### Slot 6 - Gripper

| Property | Value | Meaning |
|---|---|---|
| `channel` | 11 | PWM Channel 11 |
| `type` | `gripper` | Gripper |
| `min_pos` | `open` | min(126.4°) → Open |
| `min` → `max` | 126.4° → 180° | Open → Closed |
| `zero_offset` | 126.4° | Open state = 126.4° |
| `length` | 70mm | Gripper length |
| `zero_pulse` | 1904μs | 0° position pulse |
| `device_name` | MG996R | Servo model |

---

## 6. Motion Polarity Summary

### Right Arm

| Slot | Joint | `min_pos` | Motion Direction on Angle Increase |
|---|---|---|---|
| 1 | Base Yaw | `right` | → **Left (CCW)** |
| 2 | Shoulder | `bottom` | → **Down** |
| 3 | Elbow | `top` | → **Extension** |
| 4 | Wrist Yaw | `left` | → **Right (CW)** |
| 5 | Wrist Roll | `ccw` | → **CW Roll** |
| 6 | Gripper | `open` | → **Close** |

### Left Arm

| Slot | Joint | `min_pos` | Motion Direction on Angle Increase |
|---|---|---|---|
| 1 | Base Yaw | `right` | → **Left (CCW)** |
| 2 | Shoulder | `bottom` | → **Down** |
| 3 | Elbow | `top` | → **Extension** |
| 4 | Wrist Yaw | `left` | → **Right (CW)** |
| 5 | Wrist Roll | `ccw` | → **CW Roll** |
| 6 | Gripper | `open` | → **Close** |

---

## 7. Core Calibration Formula

```
pulse = zero_pulse + (software_angle × pulse_per_degree × polarity)
```

Components:
- **`zero_pulse`**: Reference pulse for 0° posture
- **`polarity`**: +1 or -1 depending on `min_pos`
- **`pulse_per_degree`**: `(pulse_max - pulse_min) / actuation_range`

---

## 8. Left Arm vs Right Arm Key Differences

Left Arm is structurally **mirrored** from Right Arm:

| Property | Right Arm | Left Arm |
|---|---|---|
| Slot 1 `initial` | 0° | 171° (facing opposite side) |
| Slot 1 `zero_offset` | 2.7° | 171° |
| Slot 2 `zero_offset` | 126° | 139.1° |
| Slot 3 `zero_offset` | 108.7° | 121° |
| Slot 4 `zero_offset` | 110° | 91.2° |
| Slot 6 `min` | 0° | 126.4° (gripper direction inverted) |

---

## 9. Connection Settings

```json
"connection": {
  "port": "COM7"
}
```

The robot arm is connected via **COM7** serial port.
