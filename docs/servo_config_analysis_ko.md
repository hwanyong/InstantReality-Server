# servo_config.json 분석 보고서

> **분석 대상**: `ik_tester_gui.py`의 마지막 탭 (Tab 5: Full Slot) 기능과 `servo_config.json` 해석 방법
> **분석 일시**: 2026-02-01

## 1. 개요

`servo_config.json`은 Gemini 로봇 제어 시스템의 **마스터 설정 파일**입니다. 이 파일은:
- 독립 실행 `calibrator_gui.py`
- `ik_tester_gui.py` (역기구학 테스터)
- 메인 Gemini 서버

세 가지 도구에서 공유됩니다.

---

## 2. 파일 구조

### 2.1 최상위 구조

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

| 섹션 | 설명 |
|------|------|
| `left_arm`, `right_arm` | 각 팔의 6개 슬롯(관절) 설정 |
| `connection` | 시리얼 포트 연결 정보 (데스크톱 도구용) |
| `vertices` | 작업 영역 꼭짓점 8개 (캘리브레이션 포인트) |
| `share_points` | 양팔이 공유하는 중심점 좌표 |
| `geometry` | 사전 계산된 3D 좌표 및 거리 데이터 |

---

## 3. 슬롯(관절) 프로퍼티 분석

### 3.1 하드웨어 식별 속성

| 프로퍼티 | 타입 | 설명 | 예시 |
|----------|------|------|------|
| `channel` | int | PCA9685 I2C 채널 (0-15) | `0`, `7` |
| `device_name` | string | 모터 모델명 | `"DS3225"`, `"MG996R"` |
| `type` | string | 운동학적 역할 | `"horizontal"`, `"vertical"`, `"roll"`, `"gripper"` |
| `actuation_range` | int | 물리적 회전 범위 (도) | `180`, `270` |
| `length` | float | 다음 관절까지의 링크 길이 (mm) | `107.0`, `150.0` |
| `min_pos` | string | 최소 위치 방향 표시 | `"right"`, `"top"`, `"bottom"`, `"ccw"`, `"open"` |

### 3.2 펄스 기반 속성 (Master Truth)

> [!IMPORTANT]
> **핵심 원칙**: 시스템은 **펄스 폭(µs)**을 **마스터 소스**로 취급합니다.
> 모든 각도 값은 펄스에서 파생됩니다.

| 프로퍼티 | 타입 | 설명 |
|----------|------|------|
| `pulse_min` | int | 0° 기준점의 PWM 펄스 |
| `pulse_max` | int | 하드웨어 최대값의 이론적 펄스 |
| `min_pulse` | int | **소프트웨어 안전 한계** (최소) |
| `max_pulse_limit` | int | **소프트웨어 안전 한계** (최대) |
| `zero_pulse` | int | "Zero" (수직 자세) 위치의 펄스 |
| `initial_pulse` | int | "Home" (접힌 자세) 위치의 펄스 |

### 3.3 파생 각도 속성 (View Projection)

| 프로퍼티 | 타입 | 설명 |
|----------|------|------|
| `initial` | float | Home 위치의 물리적 각도 (°) |
| `zero_offset` | float | 0° 기준점으로부터의 오프셋 각도 (°) |
| `min` | float | 물리적 최소 한계 (°) |
| `max` | float | 물리적 최대 한계 (°) |

---

## 4. Full Slot 탭 (Tab 5) 기능 분석

### 4.1 UI 구성

```
┌─────────────────┬─────────────────┬─────────────┐
│  Top-Down View  │   Side View     │  Gripper    │
│   (X/Y 입력)    │  (IK: R,Z→θ2,θ3)│   State     │
│                 │                 │             │
│  • Y 슬라이더   │  • Z 슬라이더   │  • 그리퍼   │
│  • X 슬라이더   │  • S2-S6 상태   │    시각화   │
│  • θ1 자동계산 │  • θ4 접근각도  │             │
└─────────────────┴─────────────────┴─────────────┘
```

### 4.2 설정 로딩 워크플로우

```python
# _refresh_config() 에서 설정 로딩
p1 = self.context.get_slot_params(1)  # Slot 1 파라미터
p2 = self.context.get_slot_params(2)  # Slot 2 파라미터
# ... p3 ~ p6

# Side View 위젯에 링크 길이 전달
self.side_widget.cfg['d1'] = p1.get('length', 107.0)  # Base 높이
self.side_widget.cfg['a2'] = p2.get('length', 105.0)  # 상완
self.side_widget.cfg['a3'] = p3.get('length', 150.0)  # 전완
self.side_widget.cfg['a4'] = p4.get('length', 65.0)   # 손목
```

### 4.3 get_slot_params() 반환 구조

```python
{
    'channel': 0,           # PCA9685 채널
    'zero_offset': 137.6,   # Zero 위치 오프셋
    'min': 107.3,           # 물리적 최소 한계
    'max': 270.0,           # 물리적 최대 한계
    'actuation_range': 270, # 모터 회전 범위
    'type': 'vertical',     # 운동 유형
    'min_pos': 'bottom',    # 최소 위치 방향
    'polarity': 1,          # 극성 (+1 또는 -1)
    'math_min': -30.0,      # 수학적 최소 (IK용)
    'math_max': 132.4,      # 수학적 최대 (IK용)
    'motor_config': {       # PulseMapper용
        'actuation_range': 270,
        'pulse_min': 500,
        'pulse_max': 2500
    },
    'length': 105.0         # 링크 길이 (mm)
}
```

---

## 5. 극성(Polarity) 규칙

### 5.1 극성 결정 로직

```python
polarity = 1

# Horizontal 타입: left → -1
if typ == "horizontal" and min_pos == "left":
    polarity = -1

# Vertical 타입: top → -1, bottom → 1
if typ == "vertical":
    polarity = -1 if min_pos == "top" else 1
```

### 5.2 수학적 범위 계산

```python
# 물리적 한계를 수학적 프레임으로 변환
bound_a = (limits["min"] - zero_offset) * polarity
bound_b = (limits["max"] - zero_offset) * polarity

math_min = min(bound_a, bound_b)
math_max = max(bound_a, bound_b)
```

---

## 6. 펄스-각도 변환 (PulseMapper)

### 6.1 물리 각도 → 펄스 변환

```python
def physical_to_pulse(target_physical_deg, motor_config):
    actuation_range = motor_config.get("actuation_range", 180)
    pulse_min = motor_config.get("pulse_min", 500)
    pulse_max = motor_config.get("pulse_max", 2500)
    
    # 비율 계산
    ratio = target_physical_deg / actuation_range
    pulse_us = pulse_min + (ratio * (pulse_max - pulse_min))
    
    return int(pulse_us)
```

### 6.2 예시: DS3225 (270° 모터)

| 물리 각도 | 비율 | 펄스 (µs) |
|-----------|------|-----------|
| 0° | 0.0 | 500 |
| 90° | 0.333 | 1166 |
| 135° | 0.5 | 1500 |
| 270° | 1.0 | 2500 |

---

## 7. IK 계산 흐름 (update_visualization)

### 7.1 Step 1: θ1 계산 (Base Yaw)

```python
# Top-Down View에서 X, Y 입력
theta1 = math.degrees(math.atan2(y, x))
R = math.sqrt(x**2 + y**2)  # 수평 거리
```

### 7.2 Step 2: θ2, θ3 계산 (2-Link IK)

```python
# 손목 Z 높이 계산 (그리퍼가 -90°로 하향)
wrist_z = z + a4 + a6

# 2-Link IK 풀이
theta2, theta3, is_reachable, config_name = _solve_2link_ik(R, wrist_z, d1, a2, a3)

# Slot 3 반전 (min_pos: top)
theta3 = -theta3
```

### 7.3 Step 3: θ4 계산 (접근 각도)

```python
# 그리퍼가 지면에 수직으로 유지되도록
theta4 = -90.0 - theta2 + theta3
```

### 7.4 Step 4: 물리 각도 변환

각 슬롯마다 다른 변환 규칙:

| 슬롯 | 변환 공식 | 설명 |
|------|-----------|------|
| S1 | `phy = theta + zero_offset` | 단순 오프셋 |
| S2 | `phy = theta + zero_offset` | 어깨 |
| S3 | `phy = zero_offset + theta` | 팔꿈치 (반전 후) |
| S4 | `phy = zero_offset - theta` | 손목 (top → 반전) |
| S5 | `phy = theta + zero_offset` | 롤 (수동 입력) |
| S6 | `phy = theta + zero_offset` | 그리퍼 (수동 입력) |

---

## 8. Vertices & Share Points 구조

### 8.1 Vertex (작업 영역 꼭짓점)

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

### 8.2 Share Point (공유 중심점)

```json
"share_points": {
  "left_arm": {
    "pulses": { "slot_1": 1664, ... },
    "angles": { "slot_1": 98.7, ... }
  }
}
```

---

## 9. Geometry 블록

### 9.1 좌표계 정의

```json
"geometry": {
  "coordinate_system": "+X=up, +Y=left",
  "origin": "share_point"
}
```

| 축 | 방향 | 설명 |
|----|------|------|
| +X | Up (위) | 로봇에서 멀어지는 방향 |
| +Y | Left (좌) | TopView 기준 왼쪽 |
| Z | 0 | 지면 (모든 랜드마크 Z=0) |

### 9.2 사전 계산된 데이터

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

## 10. 슬롯별 역할 요약

| 슬롯 | 역할 | 타입 | 모터 | 범위 | 링크 길이 |
|------|------|------|------|------|-----------|
| **S1** | Base Yaw (수평 회전) | horizontal | DS3225 | 180° | 107mm |
| **S2** | Shoulder (어깨) | vertical | DS3225 | 270° | 105mm |
| **S3** | Elbow (팔꿈치) | vertical | DS3225 | 270° | 150mm |
| **S4** | Wrist Pitch (손목) | vertical | DS3225 | 180° | 65mm |
| **S5** | Roll (롤) | roll | MG996R | 180° | 30mm |
| **S6** | Gripper (그리퍼) | gripper | MG996R | 180° | 82mm |

---

## 11. 핵심 설계 원칙

1. **펄스 우선 (Pulse-First)**: 모든 위치 데이터는 펄스로 저장되고, 각도는 파생값
2. **독점 소유권 (Exclusive Ownership)**: 각 vertex는 하나의 팔에만 귀속
3. **사전 계산 (Precomputed)**: FK/IK 결과를 geometry에 저장하여 런타임 계산 최소화
4. **양팔 일관성 (Dual-Arm Consensus)**: `base_to_base` 거리로 캘리브레이션 검증
5. **안전 한계 (Safety Limits)**: `min_pulse`/`max_pulse_limit`으로 물리적 충돌 방지

---

## 12. 참조 파일 목록

| 파일 | 경로 | 역할 |
|------|------|------|
| `servo_config.json` | 루트 | 마스터 설정 |
| `servo_manager.py` | `tools/robot_calibrator/` | 설정 로드/저장/API |
| `pulse_mapper.py` | `tools/robot_calibrator/` | 펄스-각도 변환 |
| `full_slot2_view.py` | `tools/robot_calibrator/ik_tester/tabs/` | Tab 5 구현 |
| `app.py` | `tools/robot_calibrator/ik_tester/` | 메인 앱 및 get_slot_params() |
