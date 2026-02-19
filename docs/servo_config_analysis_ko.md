# servo_config.json 분석 문서

## 1. 제로 포인트(0°) 정의

**0도는 팔을 테이블(장면) 방향으로 수평으로 뻗은 자세**를 의미합니다.

---

## 2. 파일 구조 개요

```json
{
  "right_arm": { "slot_1" ~ "slot_6" },
  "left_arm":  { "slot_1" ~ "slot_6" },
  "connection": { "port": "COM7" }
}
```

---

## 3. 파라미터 정의 (전체)

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `channel` | int | PCA9685 PWM 보드의 채널 번호 (0~15) |
| `min` | float | 소프트웨어 허용 최소 각도 |
| `max` | float | 소프트웨어 허용 최대 각도 |
| `type` | string | 관절 유형 (`horizontal`, `roll`, `gripper`, 또는 생략 시 수직 관절) |
| `min_pos` | string | **최소 각도(min)일 때 물리적 위치** → 운동 극성 결정 |
| `initial` | float | 시동 시 이동할 초기 각도 (°) |
| `length` | float | 해당 링크의 물리적 길이 (mm) - IK 계산용 |
| `zero_offset` | float | **제로 포인트(0°)에 해당하는 서보 원시 각도** |
| `actuation_range` | int | 서보의 물리적 가동 범위 (180° 또는 270°) |
| `pulse_min` | int | 서보 스펙상 최소 펄스 (μs) |
| `pulse_max` | int | 서보 스펙상 최대 펄스 (μs) |
| `device_name` | string | 서보 모델명 (DS3225, MG996R 등) |
| `initial_pulse` | int | 시동 시 실제 출력할 펄스 값 (μs) |
| `zero_pulse` | int | **0° 자세에 해당하는 펄스 값** (μs) - 캘리브레이션 핵심 |
| `min_pulse` | int | 소프트웨어 허용 최소 펄스 (안전 제한) |
| `max_pulse_limit` | int | 소프트웨어 허용 최대 펄스 (안전 제한) |

---

## 4. Right Arm 각 Slot별 상세 분석

### Slot 1 - 베이스 회전 (Base Yaw)

| 속성 | 값 | 의미 |
|---|---|---|
| `channel` | 0 | PWM 채널 0 |
| `type` | `horizontal` | 수평면 회전 |
| `min_pos` | `right` | min(0°) → 오른쪽 |
| `min` → `max` | 0° → 180° | 오른쪽 → 왼쪽 회전 |
| `zero_offset` | 2.7° | 전방(수평 뻗음) = 서보 2.7° |
| `length` | 107mm | 어깨 높이/베이스 오프셋 |
| `actuation_range` | 180° | 180도 서보 |
| `zero_pulse` | 530μs | 0° 위치 펄스 |
| `device_name` | DS3225 | 서보 모델 |

**운동 방향**: 각도 증가 → **좌회전 (CCW)**

---

### Slot 2 - 어깨 (Shoulder Pitch)

| 속성 | 값 | 의미 |
|---|---|---|
| `channel` | 1 | PWM 채널 1 |
| `type` | (없음) | 수직 관절 |
| `min_pos` | `bottom` | min(86.7°) → 아래 방향 |
| `min` → `max` | 86.7° → 270° | 물리적 가동 범위 |
| `zero_offset` | 126° | 전방 수평 = 서보 126° |
| `actuation_range` | 270° | 270도 서보 사용 |
| `length` | 105mm | 상완 길이 |
| `zero_pulse` | 1433μs | 0° 위치 펄스 |
| `device_name` | DS3225 | 서보 모델 |

**운동 방향**: 각도 증가 → **아래로 (Down)** / 각도 감소 → **위로 (Up)**

> ⚠️ `min_pos: bottom`이므로, 소프트웨어 각도가 감소하면 팔이 **위**로 올라갑니다.

---

### Slot 3 - 팔꿈치 (Elbow Pitch)

| 속성 | 값 | 의미 |
|---|---|---|
| `channel` | 2 | PWM 채널 2 |
| `type` | (없음) | 수직 관절 |
| `min_pos` | `top` | min(0°) → 위 방향 (접힘) |
| `min` → `max` | 0° → 259.9° | 접힘 → 펴짐 |
| `zero_offset` | 108.7° | 전방 수평 = 서보 108.7° |
| `actuation_range` | 270° | 270도 서보 |
| `length` | 150mm | 전완 길이 |
| `zero_pulse` | 1305μs | 0° 위치 펄스 |
| `device_name` | DS3225 | 서보 모델 |

**운동 방향**: 각도 증가 → **팔꿈치 펼침 (Extension)**

---

### Slot 4 - 손목 수평 회전 (Wrist Yaw)

| 속성 | 값 | 의미 |
|---|---|---|
| `channel` | 3 | PWM 채널 3 |
| `type` | `horizontal` | 수평면 회전 |
| `min_pos` | `left` | min(0°) → 왼쪽 |
| `min` → `max` | 0° → 180° | 왼쪽 → 오른쪽 |
| `zero_offset` | 110° | 중립(직진) = 서보 110° |
| `length` | 65mm | 손목 오프셋 |
| `zero_pulse` | 1722μs | 0° 위치 펄스 |
| `device_name` | DS3225 | 서보 모델 |

**운동 방향**: 각도 증가 → **우회전 (CW)**

---

### Slot 5 - 손목 롤 (Wrist Roll)

| 속성 | 값 | 의미 |
|---|---|---|
| `channel` | 4 | PWM 채널 4 |
| `type` | `roll` | 롤 회전 |
| `min_pos` | `ccw` | min(0°) → 반시계 방향 |
| `min` → `max` | 0° → 180° | CCW → CW |
| `zero_offset` | 85° | 중립 = 서보 85° |
| `length` | 30mm | 손목 롤 세그먼트 |
| `zero_pulse` | 1444μs | 0° 위치 펄스 |
| `device_name` | MG996R | 서보 모델 |

**운동 방향**: 각도 증가 → **시계방향 롤 (CW Roll)**

---

### Slot 6 - 그리퍼 (Gripper)

| 속성 | 값 | 의미 |
|---|---|---|
| `channel` | 5 | PWM 채널 5 |
| `type` | `gripper` | 그리퍼 |
| `min_pos` | `open` | min(0°) → 완전 열림 |
| `min` → `max` | 0° → 55.7° | 열림 → 닫힘 |
| `zero_offset` | 0° | 열린 상태 = 0° |
| `length` | 70mm | 그리퍼 길이 |
| `zero_pulse` | 500μs | 0° 위치 펄스 |
| `device_name` | MG996R | 서보 모델 |

**운동 방향**: 각도 증가 → **닫힘 (Close)**

---

## 5. Left Arm 각 Slot별 상세 분석

### Slot 1 - 베이스 회전 (Base Yaw)

| 속성 | 값 | 의미 |
|---|---|---|
| `channel` | 6 | PWM 채널 6 |
| `type` | `horizontal` | 수평면 회전 |
| `min_pos` | `right` | min(0°) → 오른쪽 |
| `min` → `max` | 0° → 180° | 오른쪽 → 왼쪽 회전 |
| `zero_offset` | 171° | 전방 수평 = 서보 171° |
| `length` | 107mm | 어깨 높이/베이스 오프셋 |
| `zero_pulse` | 2400μs | 0° 위치 펄스 |
| `device_name` | DS3225 | 서보 모델 |

---

### Slot 2 - 어깨 (Shoulder Pitch)

| 속성 | 값 | 의미 |
|---|---|---|
| `channel` | 7 | PWM 채널 7 |
| `min_pos` | `bottom` | min(107.6°) → 아래 방향 |
| `min` → `max` | 107.6° → 270° | 물리적 가동 범위 |
| `zero_offset` | 139.1° | 전방 수평 = 서보 139.1° |
| `actuation_range` | 270° | 270도 서보 |
| `length` | 105mm | 상완 길이 |
| `zero_pulse` | 1530μs | 0° 위치 펄스 |
| `device_name` | DS3225 | 서보 모델 |

---

### Slot 3 - 팔꿈치 (Elbow Pitch)

| 속성 | 값 | 의미 |
|---|---|---|
| `channel` | 8 | PWM 채널 8 |
| `min_pos` | `top` | min(0°) → 위 방향 |
| `min` → `max` | 0° → 270° | 접힘 → 펴짐 |
| `zero_offset` | 121° | 전방 수평 = 서보 121° |
| `actuation_range` | 270° | 270도 서보 |
| `length` | 150mm | 전완 길이 |
| `zero_pulse` | 1396μs | 0° 위치 펄스 |
| `device_name` | DS3225 | 서보 모델 |

---

### Slot 4 - 손목 수평 회전 (Wrist Yaw)

| 속성 | 값 | 의미 |
|---|---|---|
| `channel` | 9 | PWM 채널 9 |
| `type` | `horizontal` | 수평면 회전 |
| `min_pos` | `left` | min(0°) → 왼쪽 |
| `min` → `max` | 0° → 180° | 왼쪽 → 오른쪽 |
| `zero_offset` | 91.2° | 중립 = 서보 91.2° |
| `length` | 65mm | 손목 오프셋 |
| `zero_pulse` | 1513μs | 0° 위치 펄스 |
| `device_name` | DS3225 | 서보 모델 |

---

### Slot 5 - 손목 롤 (Wrist Roll)

| 속성 | 값 | 의미 |
|---|---|---|
| `channel` | 10 | PWM 채널 10 |
| `type` | `roll` | 롤 회전 |
| `min_pos` | `ccw` | min(0°) → 반시계 방향 |
| `min` → `max` | 0° → 180° | CCW → CW |
| `zero_offset` | 90° | 중립 = 서보 90° |
| `length` | 30mm | 손목 롤 세그먼트 |
| `zero_pulse` | 1500μs | 0° 위치 펄스 |
| `device_name` | MG996R | 서보 모델 |

---

### Slot 6 - 그리퍼 (Gripper)

| 속성 | 값 | 의미 |
|---|---|---|
| `channel` | 11 | PWM 채널 11 |
| `type` | `gripper` | 그리퍼 |
| `min_pos` | `open` | min(126.4°) → 열림 |
| `min` → `max` | 126.4° → 180° | 열림 → 닫힘 |
| `zero_offset` | 126.4° | 열린 상태 = 126.4° |
| `length` | 70mm | 그리퍼 길이 |
| `zero_pulse` | 1904μs | 0° 위치 펄스 |
| `device_name` | MG996R | 서보 모델 |

---

## 6. 운동 극성 요약

### Right Arm

| Slot | 관절 | `min_pos` | 각도 증가 시 운동 방향 |
|---|---|---|---|
| 1 | Base Yaw | `right` | → **Left (CCW)** |
| 2 | Shoulder | `bottom` | → **Down** |
| 3 | Elbow | `top` | → **Extension (펼침)** |
| 4 | Wrist Yaw | `left` | → **Right (CW)** |
| 5 | Wrist Roll | `ccw` | → **CW Roll** |
| 6 | Gripper | `open` | → **Close** |

### Left Arm

| Slot | 관절 | `min_pos` | 각도 증가 시 운동 방향 |
|---|---|---|---|
| 1 | Base Yaw | `right` | → **Left (CCW)** |
| 2 | Shoulder | `bottom` | → **Down** |
| 3 | Elbow | `top` | → **Extension (펼침)** |
| 4 | Wrist Yaw | `left` | → **Right (CW)** |
| 5 | Wrist Roll | `ccw` | → **CW Roll** |
| 6 | Gripper | `open` | → **Close** |

---

## 7. 핵심 캘리브레이션 관계식

```
펄스 = zero_pulse + (소프트웨어_각도 × 펄스_per_degree × polarity)
```

구성 요소:
- **`zero_pulse`**: 0° 자세의 기준 펄스
- **`polarity`**: `min_pos`에 따라 +1 또는 -1
- **`펄스_per_degree`**: `(pulse_max - pulse_min) / actuation_range`

---

## 8. Left Arm vs Right Arm 주요 차이점

Left Arm은 구조적으로 Right Arm과 **미러링**되어 있습니다:

| 속성 | Right Arm | Left Arm |
|---|---|---|
| Slot 1 `initial` | 0° | 171° (반대쪽 향함) |
| Slot 1 `zero_offset` | 2.7° | 171° |
| Slot 2 `zero_offset` | 126° | 139.1° |
| Slot 3 `zero_offset` | 108.7° | 121° |
| Slot 4 `zero_offset` | 110° | 91.2° |
| Slot 6 `min` | 0° | 126.4° (그리퍼 방향 반전) |

---

## 9. 연결 설정

```json
"connection": {
  "port": "COM7"
}
```

로봇 암은 **COM7** 시리얼 포트를 통해 연결됩니다.
