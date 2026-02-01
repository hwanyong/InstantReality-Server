# 3D Robot Kinematics 프롬프트 유효성 분석

> 분석일: 2026-02-01  
> 대상: "3D Robot Kinematics Calculation Expert" 시스템 프롬프트

---

## 1. 정확한 부분 ✅

| 항목 | 프롬프트 내용 | 검증 결과 |
|------|-------------|----------|
| 원점 정의 | Share Point = (0, 0, 0) | ✅ `geometry.origin: "share_point"` |
| 좌표계 | +X=up, +Y=left | ✅ `geometry.coordinate_system` |
| 링크 길이 | L1=105, L2=150 (mm) | ✅ slot_2.length, slot_3.length |
| Zero Pulse 기준 | zero_pulse 기반 계산 | ✅ compute_reach()에서 사용 |
| Slot 4 극성 | θ = zero_offset - physical | ✅ 코드 및 KI 문서 확인 |

---

## 2. 누락된 핵심 사항 ⚠️

### 2.1 Dual Reach Protocol 미반영

프롬프트는 하나의 Reach 공식만 제시하지만, 실제 시스템은 **두 가지 프로토콜**을 사용합니다:

#### Vertex Protocol (Fixed 90° Approach)
```
그리퍼가 수직(바닥에 수직)일 때 - wrist 기여도 = 0
Reach = |a2 * cos(θ2) + a3 * cos(θ2 + θ3)|
```

#### Share Point Protocol (Variable Pose)
```
완전 FK 투영 - wrist 각도까지 포함
Reach = a2*cos(θ2) + a3*cos(θ2+θ3) + (a4+a5+a6)*cos(θ2+θ3+θ4)
```

> **문제점**: 프롬프트의 공식은 Vertex만 해당하며, Share Point에서는 더 복잡한 FK가 필요합니다.

---

### 2.2 Wrist 섹션 누락

프롬프트에서 링크 길이로 L1=105, L2=150만 언급했으나, 실제 로봇은:

| Slot | Length (mm) | 역할 |
|------|-------------|------|
| slot_1 | 107.0 | Base Height (d1) |
| slot_2 | 105.0 | Upper Arm |
| slot_3 | 150.0 | Forearm |
| slot_4 | 65.0 | Wrist |
| slot_5 | 30.0 | Roll |
| slot_6 | 82.0 | Gripper |

**전체 Max Reach** = 105 + 150 + 65 + 30 + 82 = **432mm**

---

### 2.3 min_pos 방향성 규칙 불완전

프롬프트는 단순히 "CW/CCW 부호 결정"만 언급했으나, 정확한 규칙:

```
min_pos ∈ ["bottom", "right", "open", "ccw"] → θ_logical = (θ_physical - zero_offset)
min_pos ∈ ["top", "left", "closed", "cw"]   → θ_logical = -(θ_physical - zero_offset)
```

---

## 3. 오류 ❌

### 3.1 출력 형식에 Z 좌표 요청

프롬프트:
```json
"final_coordinates": { "x": "값", "y": "값", "z": "값" }
```

현재 시스템:
```json
"vertices": { "1": { "x": 391.0, "y": 154.5, "owner": "left_arm" } }
```

**원인**: 현재 시스템은 Ground Plane (Z=0) 가정으로 **2D 좌표만** 계산합니다.

### 3.2 Base Z 좌표 = 0 표기

프롬프트에서 Base Z=0으로 표기했으나, 실제 Base Height (d1) = **107mm**입니다.  
다만 현재 시스템이 2D 평면으로 계산하므로 Z는 생략됩니다.

---

## 4. 수정 제안

### 4.1 Dual Reach Protocol 추가

```markdown
### Dual Reach Protocol
1. **Vertex Protocol (Fixed 90°)**:
   공식: Reach = |a2·cos(θ2^log) + a3·cos(θ2^log + θ3^log)|
   
2. **Share Point Protocol (Variable Pose)**:
   공식: Reach = a2·cos(θ2) + a3·cos(θ2+θ3) + (a4+a5+a6)·cos(θ2+θ3+θ4)
```

### 4.2 논리각 변환 공식 명확화

```
θ_logical = zero_offset - θ_physical  (Slot 4 only)
θ_logical = θ_physical - zero_offset  (Other slots)
```

### 4.3 출력 형식에서 Z 제거

현재 시스템 기준으로 2D 좌표만 출력:
```json
"final_coordinates": { "x": "값", "y": "값" }
```

---

## 5. 현재 시스템 검증 결과

`servo_config.json` geometry 섹션:

```
Base-to-Base: 491.7mm (예상 512mm, 4% 오차)
Left reach: 229.9mm, yaw: -81.3°
Right reach: 261.9mm, yaw: 96.4°
```

---

## 6. 평가 요약

| 평가 항목 | 점수 | 비고 |
|----------|------|------|
| 구조적 완성도 | ★★★★☆ | 체계적인 단계별 가이드 |
| 공식 정확도 | ★★★☆☆ | Dual Protocol 미반영 |
| 코드베이스 일치 | ★★★☆☆ | 3D 요청 vs 2D 시스템 |
| 실용성 | ★★★★☆ | 과거 실수 경고 유용함 |

**종합**: 개념적으로 올바르나, Dual Reach Protocol과 2D 좌표계를 반영하도록 수정 필요.
