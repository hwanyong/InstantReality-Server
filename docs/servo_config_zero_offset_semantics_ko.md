# servo_config.json - zero_offset 시맨틱 정의서

> ⚠️ **중요**: 이 문서는 `zero_offset` 값의 **올바른 해석 방법**을 정의합니다.
> 잘못된 해석은 geometry 계산, IK 변환, 좌표계 매핑 전체를 망칩니다.

---

## 🔴 zero_offset은 무엇인가?

### ❌ 잘못된 해석 (절대 이렇게 생각하지 마라)

- "0도의 기준"
- "수학적 0도가 어디인지 나타내는 값"
- "좌표계 변환용 오프셋"

### ✅ 올바른 정의

> **`zero_offset` = 로봇팔이 정면(forward, +Y 방향)을 향할 때 해당 모터의 물리 각도**

다시 말해:
- **로봇팔을 정면으로 뻗었을 때** (IK 좌표계에서 θ1 = 0°)
- **그 순간 모터가 가리키는 물리 각도** = `zero_offset`

---

## 📋 실제 값 예시

### Right Arm - Slot 1
```json
{
  "zero_offset": 0.0,
  "min_pos": "right",
  "type": "horizontal"
}
```
- 로봇팔이 정면을 향할 때 → 모터 물리 각도 = **0°**

### Left Arm - Slot 1
```json
{
  "zero_offset": 180.0,
  "min_pos": "right",
  "type": "horizontal"
}
```
- 로봇팔이 정면을 향할 때 → 모터 물리 각도 = **180°**

**두 팔 모두 정면을 향하고 있지만, 물리적 모터 각도는 다르다!**

---

## 🧮 변환 공식

### World Yaw (IK 각도) → Physical Angle

```
physical_angle = zero_offset + world_yaw
```

| 예시 | world_yaw | zero_offset | physical_angle |
|------|-----------|-------------|----------------|
| Right Arm 정면 | 0° | 0° | 0° |
| Left Arm 정면 | 0° | 180° | 180° |
| Right Arm 우측 | -90° | 0° | -90° (범위초과) |
| Left Arm 우측 | -90° | 180° | 90° ✅ |

### Physical Angle → World Yaw (IK 각도)

```
world_yaw = physical_angle - zero_offset
```

| 예시 | physical_angle | zero_offset | world_yaw |
|------|----------------|-------------|-----------|
| Right Arm 96.4° | 96.4° | 0° | 96.4° |
| Left Arm 98.7° | 98.7° | 180° | -81.3° |

---

## 🎯 IK 좌표계 정의

```
      +Y (Forward)
         ↑
         │
   -X ←──┼──→ +X (Right)
         │
         ↓
      -Y (Backward)
```

- **θ1 = 0°**: 정면 (+Y 방향)
- **θ1 = 90°**: 왼쪽 (-X 방향)
- **θ1 = -90°**: 오른쪽 (+X 방향)

### θ1 계산 (atan2 사용)
```python
theta1 = math.degrees(math.atan2(-x, y))
```

---

## 🔧 Slot별 해석 및 변환 (IK Tester 기준)

> 이 섹션은 `ik_tester/tabs/full_slot3_view.py`와 `ik_tester/app.py`의 실제 구현을 기반으로 작성되었습니다.

### Slot 1 (Base Yaw) - 수평 회전

| 속성 | Right Arm | Left Arm |
|------|-----------|----------|
| Type | `horizontal` | `horizontal` |
| min_pos | `right` | `right` |
| zero_offset | 0 | 180 |
| actuation_range | 180 | 180 |

**Polarity 결정 (app.py:312-317):**
```python
polarity = 1
if typ == "horizontal" and min_pos == "left": polarity = -1
if typ == "vertical":
    polarity = -1 if min_pos == "top" else 1
```

**Slot 1의 Polarity:**
- `type = "horizontal"`, `min_pos = "right"` → **polarity = +1** (양팔 동일)
- 만약 `min_pos = "left"`였다면 polarity = -1이 됨

**min_pos: "right"의 의미:**
- 모터가 최소 각도(0°)일 때 →로봇팔이 **오른쪽**을 향함
- 양팔 모두 동일한 규약 사용

**Math 범위 계산 (app.py:319-324):**
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

**중요**: Left Arm의 IK θ1 범위는 **-180° ~ 0°**

**IK 각도 계산 (full_slot3_view.py:297-298):**
```python
# X, Y 입력으로부터 θ1 계산
theta1 = math.degrees(math.atan2(-x, y))  # 정면=0°, 좌=+90°, 우=-90°
```

**Physical 각도 변환 (full_slot3_view.py:330-332):**
```python
# 통일된 physical 각도 계산: phy = zero_offset + theta1
phy_angle_s1 = zero_offset + theta1
phy_angle_s1 = max(0, min(actuation_range, phy_angle_s1))
```

**예시 계산 - 로봇팔 정면 (θ1=0°):**
| Arm | zero_offset | theta1 | physical |
|-----|-------------|--------|----------|
| Right | 0 | 0 | 0 + 0 = **0°** |
| Left | 180 | 0 | 180 + 0 = **180°** |

**예시 계산 - 로봇팔 우측 30° (θ1=-30°):**
| Arm | zero_offset | theta1 | physical (raw) | physical (clamped) |
|-----|-------------|--------|----------------|-------------------|
| Right | 0 | -30 | 0 + (-30) = -30° | **0°** (범위초과) |
| Left | 180 | -30 | 180 + (-30) = 150° | **150°** ✅ |

**왜 Left Arm과 Right Arm이 다른 방향을 커버하는가:**
- Right Arm: physical 0°~180° → IK 0°~180° (정면~좌측)
- Left Arm: physical 0°~180° → IK -180°~0° (정면~우측)
- 이것이 **zero_offset으로 인코딩된 미러링**

---

### Slot 2 (Shoulder) - 상완 회전

| 속성 | Right Arm | Left Arm |
|------|-----------|----------|
| Type | `vertical` | `vertical` |
| min_pos | `bottom` | `bottom` |
| zero_offset | 137.6 | 149.3 |
| actuation_range | 270 | 270 |

**Polarity:**
- `type = "vertical"`, `min_pos = "bottom"` → **polarity = +1**

**IK 및 Physical 변환:**
```python
# 2-Link IK로 θ2 계산 (어깨 각도)
theta2, theta3, is_reachable, config = _solve_2link_ik(R, wrist_z, d1, a2, a3)

# Physical 변환: 정방향 (polarity = +1)
physical = zero_offset + theta2
physical = max(0, min(actuation_range, physical))
```

**min_pos: "bottom"의 의미:**
- 모터 0° → 팔이 아래로 향함 (bottom)
- 모터 각도 증가 → 팔이 위로 올라감

---

### Slot 3 (Elbow) - 전완 회전

| 속성 | Right Arm | Left Arm |
|------|-----------|----------|
| Type | `vertical` | `vertical` |
| min_pos | `top` | `top` |
| zero_offset | 125.0 | 137.2 |
| actuation_range | 270 | 270 |

**Polarity:**
- `type = "vertical"`, `min_pos = "top"` → **polarity = -1**

**‼️ 중요: θ3 반전 처리 (full_slot3_view.py:316)**

```python
# IK에서 계산된 θ3를 반전
theta3 = -theta3  # min_pos: top 보정

# Physical 변환 (반전 후에 더하기)
physical = zero_offset + theta3
physical = max(0, min(actuation_range, physical))
```

**min_pos: "top"의 의미:**
- 모터 0° → 팔이 **위로 접힘** (top)
- IK 계산과 모터 방향이 반대 → θ3 반전 필요

**왜 반전하는가?**
- IK의 elbow angle: θ3 양수 = 팔 펴짐
- 모터 물리: angle 증가 = 팔 접힘 (top 기준)
- 따라서 부호 반전 필요

---

### Slot 4 (Wrist Pitch) - 손목 상하 회전

| 속성 | Right Arm | Left Arm |
|------|-----------|----------|
| Type | `vertical` | `vertical` |
| min_pos | `top` | `top` |
| zero_offset | 51.0 | 24.6 |
| actuation_range | 180 | 180 |

**Polarity:**
- `type = "vertical"`, `min_pos = "top"` → **polarity = -1**

**θ4 자동 계산 - 그리퍼 수직 유지 (full_slot3_view.py:387):**
```python
# 그리퍼가 항상 -90° (아래 방향)를 유지하도록
theta4 = -90.0 - theta2 + theta3
```

**Physical 변환 - 부호 반전! (full_slot3_view.py:397-399):**
```python
# ❗ min_pos: top → polarity = -1 적용
physical = zero_offset - theta4  # 마이너스!
physical = max(0, min(actuation_range, physical))
```

**왜 빼기인가?**
- 일반 공식: `physical = zero_offset + (theta × polarity)`
- polarity = -1 이므로: `physical = zero_offset + theta × (-1) = zero_offset - theta`

---

### Slot 5 (Roll) - 손목 회전

| 속성 | Right Arm | Left Arm |
|------|-----------|----------|
| Type | `roll` | `roll` |
| min_pos | `ccw` | `ccw` |
| zero_offset | 3.6 | 7.2 |
| actuation_range | 180 | 180 |

**Polarity:**
- `type = "roll"` → polarity 규칙에 해당 없음 → **polarity = +1**

**변환 (수동 입력, full_slot3_view.py:420-422):**
```python
theta5 = roll_var.get()  # 사용자 슬라이더 입력

# Physical 변환: 정방향
physical = zero_offset + theta5
physical = max(0, min(actuation_range, physical))
```

---

### Slot 6 (Gripper) - 집게

| 속성 | Right Arm | Left Arm |
|------|-----------|----------|
| Type | `gripper` | `gripper` |
| min_pos | `open` | `open` |
| zero_offset | 0 | 126.4 |
| actuation_range | 180 | 180 |

**Polarity:**
- `type = "gripper"` → polarity 규칙에 해당 없음 → **polarity = +1**

**변환 (수동 입력, full_slot3_view.py:443-445):**
```python
theta6 = gripper_var.get()  # 사용자 슬라이더 입력

# Physical 변환: 정방향
physical = zero_offset + theta6
physical = max(0, min(actuation_range, physical))
```

---

## 📊 Slot별 변환 공식 요약표

| Slot | Type | min_pos | Polarity | 변환 공식 | 비고 |
|------|------|---------|----------|----------|------|
| 1 | horizontal | right | +1 | `phy = zero + θ1` | 양팔 통일 |
| 2 | vertical | bottom | +1 | `phy = zero + θ2` | 정방향 |
| 3 | vertical | top | -1 | `phy = zero + θ3` | **θ3 먼저 반전** |
| 4 | vertical | top | -1 | `phy = zero - θ4` | **공식에서 부호 반전** |
| 5 | roll | ccw | +1 | `phy = zero + θ5` | 수동 |
| 6 | gripper | open | +1 | `phy = zero + θ6` | 수동 |

---

## 🔢 Polarity 결정 규칙 (app.py:312-317)

```python
# get_slot_params() 함수 내 polarity 결정 로직
polarity = 1

if typ == "horizontal" and min_pos == "left":
    polarity = -1

if typ == "vertical":
    polarity = -1 if min_pos == "top" else 1
```

| Type | min_pos | Polarity | 현재 사용 Slot |
|------|---------|----------|---------------|
| horizontal | right | +1 | Slot 1 (양팔) |
| horizontal | left | -1 | (미사용) |
| vertical | bottom | +1 | Slot 2 (양팔) |
| vertical | top | **-1** | Slot 3, 4 (양팔) |
| roll | ccw | +1 | Slot 5 (양팔) |
| gripper | open | +1 | Slot 6 (양팔) |

---

## 🔄 Left Arm vs Right Arm 차이점 정리

### Slot 1 (Base Yaw)
| 항목 | Right Arm | Left Arm |
|------|-----------|----------|
| zero_offset | 0 | 180 |
| min_pos | right | right |
| polarity | +1 | +1 |
| IK 유효 범위 | 0° ~ 180° | -180° ~ 0° |
| 물리적 커버 영역 | 정면 ~ 좌측 | 우측 ~ 정면 |

**핵심**: `min_pos`는 양팔 동일 → **차이는 오직 `zero_offset`**

### Slot 2-6
- min_pos와 type이 양팔 동일
- polarity도 양팔 동일
- **차이는 오직 `zero_offset`과 일부 `limits`**

---

## ⚠️ 흔한 실수

### 1. Left Arm 미러링 추가 시도
```python
# ❌ 잘못됨 - 하지 마라!
if arm == "left_arm":
    world_yaw = 180.0 - logical_angle
```

**이유**: `zero_offset`이 이미 팔 방향 차이를 인코딩하고 있다.
추가 미러링은 **이중 보정**이며 완전히 잘못된 결과를 낳는다.

### 2. zero_offset을 "수학적 0도"로 오해
```python
# ❌ 잘못된 해석
# "zero_offset=180이니까 수학적 0도는 물리 180도겠지?"
```

**올바른 해석**:
```
"zero_offset=180이니까 정면 방향일 때 모터가 180도에 있다"
```

### 3. Slot 1 min_pos 무시
```python
# ❌ 잘못된 생각
# "Slot 1은 min_pos 기반으로 해석 안 하네?"
```

**사실**: Slot 1도 min_pos 기반으로 polarity 결정함.
다만 양팔 모두 `min_pos: "right"`이라 polarity = +1로 동일할 뿐.

### 4. Slot 3 반전 누락
```python
# ❌ 잘못됨
physical = zero_offset + theta3_from_ik  # IK 결과 직접 사용

# ✅ 올바름
theta3 = -theta3_from_ik  # 먼저 반전!
physical = zero_offset + theta3
```

### 5. Slot 4 부호 방향 착각
```python
# ❌ 잘못됨
physical = zero_offset + theta4

# ✅ 올바름 (min_pos: top → polarity = -1)
physical = zero_offset - theta4
```

---

## 📐 cos/sin 사용 시 주의사항

### World 좌표계: +X=right, +Y=up

```python
# world_yaw가 올바르게 계산되었다면:
# cos(world_yaw) → X 방향 성분
# sin(world_yaw) → Y 방향 성분

x = base_x + reach * math.cos(world_yaw)  # Right 방향
y = base_y + reach * math.sin(world_yaw)  # Up/Forward 방향
```

### 주의: world_yaw의 0° 방향 확인

현재 IK:
- **θ1 = 0°** = Forward (+Y)
- **cos(0°) = 1, sin(0°) = 0** → (1, 0) = +X 방향?!

**불일치 존재!** → world 좌표계와 IK θ1 기준이 90° 어긋남

---

## 📜 최종 정리

| 개념 | 정의 |
|------|------|
| `zero_offset` | 정면 방향일 때 모터 물리 각도 |
| `min_pos` | 모터 최소 각도일 때 방향 (polarity 결정에 사용) |
| `polarity` | IK→Physical 변환 시 부호 방향 (+1 또는 -1) |
| `world_yaw` | IK 좌표계에서의 회전각 (정면=0°) |
| `physical_angle` | 모터 실제 각도 |
| 변환 공식 | `physical = zero_offset + (theta × polarity)` |

---

*문서 작성: 2026-02-03*
*이 문서를 무시하고 잘못 해석하면 geometry 계산이 망가집니다.*
