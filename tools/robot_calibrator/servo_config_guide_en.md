# 🤖 Servo Configuration Guide

Standard for defining physical characteristics of robot joints in software.

---

## 1. Type (Joint Type)
Defines how the motor moves.

| Type | Meaning | Main Usage | Example |
| :--- | :--- | :--- | :--- |
| **`vertical`** | **Pitch** (Up/Down) | Elbow, Shoulder (Up/Down) | Nodding action |
| **`horizontal`**| **Yaw** (Left/Right) | Base, Shoulder (Left/Right) | Shaking head action |
| **`roll`** | **Roll** (Axis Rotation) | Wrist Rotation | Turning a screwdriver |
| **`gripper`** | **End Effector** | Grasping | Pinching fingers |

---

## 2. Min Pos (Zero Position Reference)
Defines the physical state of the robot when the servo angle is `0 degrees` (Minimum). Serves as the **reference for rotation direction**.

### A. For `vertical` Type
| Value | Meaning | As angle increases from 0 (`+`)? |
| :--- | :--- | :--- |
| **`bottom`** | 0° is **Bottom** (Ground) | **Moves Up** (Raise) |
| **`top`** | 0° is **Top** (Sky) | **Moves Down** (Lower) |

### B. For `horizontal` Type
| Value | Meaning | As angle increases from 0 (`+`)? |
| :--- | :--- | :--- |
| **`left`** | 0° is **Left** | **Rotates Right** |
| **`right`** | 0° is **Right** | **Rotates Left** |

### C. For `roll` Type (User Viewpoint)
| Value | Meaning | As angle increases from 0 (`+`)? |
| :--- | :--- | :--- |
| **`cw`** | 0° is **Max Clockwise** | **Unwinds Counter-Clockwise (CCW)** |
| **`ccw`** | 0° is **Max Counter-Clockwise** | **Winds Clockwise (CW)** |

### D. For `gripper` Type
| Value | Meaning | As angle increases from 0 (`+`)? |
| :--- | :--- | :--- |
| **`open`** | 0° is **Open** | **Closes** (Grasp object) |
| **`close`** | 0° is **Closed** | **Opens** (Release object) |

---

## 3. Length
The straight-line distance from the center of rotation of this joint to the **"center of rotation of the next joint"**. (Unit: mm)

*   **For Last Joint (Wrist, etc.)**: Distance from joint center to **TCP (Tool Center Point)**.
*   **Gripper**: Usually `0` if included in wrist length.

---

## 📝 Example Configuration

**Scenario: Base motor looks Left at 0°, rotates to Right up to 180°**
```json
{
  "slot_1": {
    "type": "horizontal",  // Rotates Left/Right
    "min_pos": "left",     // 0° is Left
    "length": 55.0         // Height to next joint (shoulder) is 55mm
  }
}
```

**Scenario: Elbow hangs down at 0°, lifts arm up as angle increases**
```json
{
  "slot_2": {
    "type": "vertical",    // Moves Up/Down
    "min_pos": "bottom",   // 0° is Bottom
    "length": 105.0        // Length to next joint (wrist) is 105mm
  }
}
```
