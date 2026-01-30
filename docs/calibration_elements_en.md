# Calibration Elements and Verification Methods

> Software calibration guide for Gemini Robotics model and robot arm integration

---

## 1. Coordinate Transform Calibration

### 1.1 Gemini → Physical Conversion
| Element | Formula | Verification |
|---------|---------|--------------|
| **Gemini 0-1000 Normalization** | AI returns [y,x] | Verify AI response range |
| **Linear Scale Transform** | `x_mm = (gemini_x/1000) * workspace_w` | Log scale output |
| **Y-Axis Inversion** | `Y_robot = (1 - Y_gemini/1000) * H` | TopView top/bottom touch test |
| **Homography Matrix** | `cv2.getPerspectiveTransform()` | Measure 9-point grid accuracy |

### 1.2 Axis-Independent Verification
```
1. X-axis test: Fix Y=200mm, Z=100mm, move X from -200mm → 0mm
2. Y-axis test: Fix X=-100mm, Z=100mm, move Y from 100mm → 300mm
3. Z-axis test: Fix X=-100mm, Y=200mm, move Z from 150mm → 50mm
```

---

## 2. 4-Camera Integration Calibration

| Camera | Role | Verification |
|--------|------|--------------|
| **TopView** | Homography Master | Grid point mapping error < 5mm |
| **QuarterView** | Z-axis verify | Compare gripper position by height |
| **RightRobot** | Gripper tip precision | Tip coord vs command coord error |
| **LeftRobot** | Gripper tip precision | Tip coord vs command coord error |

### Verification Procedure
1. Detect 3x3 grid points from TopView
2. Move gripper to each point
3. Verify actual tip position with RobotCamera
4. Record error and recalculate Homography

---

## 3. Robot Kinematics Calibration

### Link Lengths (servo_config.json)
| Link | Value | Verification |
|------|-------|--------------|
| d1 (Base) | 107mm | Physical measurement |
| a2 (Shoulder→Elbow) | 105mm | Physical measurement |
| a3 (Elbow→Wrist) | 150mm | Physical measurement |
| a4 (Wrist→Roll) | 65mm | Physical measurement |
| a6 (Gripper) | 70mm | Physical measurement |

### IK Verification
```python
# ik_solver.py test
result = ik_solver.solve(x=-100, y=200, z=100)
# Compare actual position after movement
assert abs(actual_x - target_x) < 5  # mm
```

---

## 4. Workspace Calibration

### Reachable Area
| Axis | Range | Verification |
|------|-------|--------------|
| X | -280mm ~ +20mm | Extreme point reach test |
| Y | 80mm ~ 420mm | Extreme point reach test |
| Z | 0mm ~ 220mm | Extreme point reach test |

### Physical Boundary Touch Verification
```
1. Move to (X_min, Y_min) → Record IK success/failure
2. Move to (X_max, Y_min) → Record IK success/failure
3. Move to (X_min, Y_max) → Record IK success/failure
4. Move to (X_max, Y_max) → Record IK success/failure
5. Adjust range on failure
```

---

## 5. Z-Height Calibration

| Level | Height | Verification |
|-------|--------|--------------|
| high | 150mm | Measure with QuarterView |
| medium | 100mm | Measure with QuarterView |
| low | 50mm | Measure with QuarterView |
| ground | 10mm | Confirm surface touch |

---

## 6. AI Strategy Calibration

### 6.1 Dynamic Thinking Budget Tuning
| Task Type | Budget | Verification |
|-----------|--------|--------------|
| Simple positioning | `0` | Response time < 2s |
| Complex spatial reasoning | `1024` | Accuracy > 95% |

### 6.2 Visual Success Detection
```python
# Post-action verification prompt
prompt = "Did the object arrive at the target location? Answer Yes/No."
response = gemini.generate(images=[after_image], prompt=prompt)
success = "yes" in response.lower()
```

### 6.3 Code Execution Self-Correction
```python
# Gemini configuration
config = {
    "tools": [{"code_execution": {}}],
    "thinking_budget": 1024
}
# AI self-corrects when coordinate error detected
```

### 6.4 Stop-Capture-Act Sequence
```python
async def execute_with_capture():
    await robot.stop()           # 1. Stop
    await asyncio.sleep(0.3)     # 2. Stabilization wait
    frame = camera.capture()     # 3. Capture
    result = await gemini.analyze(frame)  # 4. Analyze
    await robot.move(result.target)       # 5. Move
```

---

## 7. Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| `mean_error_mm` | < 3mm | 10-trial average |
| `max_error_mm` | < 5mm | 10-trial maximum |
| `z_accuracy` | < 2mm | Per-height measurement |
| `success_rate` | > 95% | 100 grasp tests |

---

## 8. Related Files

| File | Role |
|------|------|
| `calibration.json` | Calibration data storage |
| `src/robotics/coord_transformer.py` | Coordinate transform logic |
| `src/robotics/ik_solver.py` | Inverse kinematics |
| `src/ai_engine.py` | AI integration |
| `src/calibration_api.py` | Calibration REST API |

---

*Last Updated: 2026-01-30*
