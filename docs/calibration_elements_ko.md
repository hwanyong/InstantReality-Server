# 캘리브레이션 요소 및 검증 방법

> Gemini Robotics 모델과 로봇암 통합을 위한 소프트웨어 캘리브레이션 가이드

---

## 1. 좌표 변환 캘리브레이션

### 1.1 Gemini → Physical 변환
| 요소 | 공식 | 검증 방법 |
|------|------|----------|
| **Gemini 0-1000 정규화** | AI 반환 [y,x] | AI 응답 범위 확인 |
| **선형 스케일 변환** | `x_mm = (gemini_x/1000) * workspace_w` | 스케일 출력 로깅 |
| **Y축 반전** | `Y_robot = (1 - Y_gemini/1000) * H` | TopView 상단/하단 터치 테스트 |
| **Homography Matrix** | `cv2.getPerspectiveTransform()` | 9점 그리드 정확도 측정 |

### 1.2 축별 점진적 검증
```
1. X축 단독 테스트: Y=200mm, Z=100mm 고정, X를 -200mm → 0mm 이동
2. Y축 단독 테스트: X=-100mm, Z=100mm 고정, Y를 100mm → 300mm 이동
3. Z축 단독 테스트: X=-100mm, Y=200mm 고정, Z를 150mm → 50mm 이동
```

---

## 2. 4-Camera 통합 캘리브레이션

| 카메라 | 역할 | 검증 방법 |
|--------|------|----------|
| **TopView** | Homography Master | 그리드 포인트 매핑 오차 < 5mm |
| **QuarterView** | Z축 검증 | 높이별 그리퍼 위치 비교 |
| **RightRobot** | 그리퍼 팁 정밀 | 팁 좌표 vs 명령 좌표 오차 |
| **LeftRobot** | 그리퍼 팁 정밀 | 팁 좌표 vs 명령 좌표 오차 |

### 검증 절차
1. TopView에서 3x3 그리드 포인트 검출
2. 각 포인트로 그리퍼 이동
3. RobotCamera로 실제 팁 위치 확인
4. 오차 기록 및 Homography 재계산

---

## 3. 로봇 기구학 캘리브레이션

### 링크 길이 (servo_config.json)
| 링크 | 값 | 검증 방법 |
|------|-----|----------|
| d1 (Base) | 107mm | 실측 비교 |
| a2 (Shoulder→Elbow) | 105mm | 실측 비교 |
| a3 (Elbow→Wrist) | 150mm | 실측 비교 |
| a4 (Wrist→Roll) | 65mm | 실측 비교 |
| a6 (Gripper) | 70mm | 실측 비교 |

### IK 검증
```python
# ik_solver.py 테스트
result = ik_solver.solve(x=-100, y=200, z=100)
# 계산된 각도로 실제 이동 후 실측 위치 비교
assert abs(actual_x - target_x) < 5  # mm
```

---

## 4. 워크스페이스 캘리브레이션

### Reachable Area
| 축 | 범위 | 검증 방법 |
|----|------|----------|
| X | -280mm ~ +20mm | 극한점 도달 테스트 |
| Y | 80mm ~ 420mm | 극한점 도달 테스트 |
| Z | 0mm ~ 220mm | 극한점 도달 테스트 |

### 물리적 경계 터치 검증
```
1. (X_min, Y_min) 이동 → IK 성공/실패 기록
2. (X_max, Y_min) 이동 → IK 성공/실패 기록
3. (X_min, Y_max) 이동 → IK 성공/실패 기록
4. (X_max, Y_max) 이동 → IK 성공/실패 기록
5. 실패 시 범위 조정
```

---

## 5. Z-Height 캘리브레이션

| 레벨 | 높이 | 검증 방법 |
|------|------|----------|
| high | 150mm | QuarterView로 실측 |
| medium | 100mm | QuarterView로 실측 |
| low | 50mm | QuarterView로 실측 |
| ground | 10mm | 바닥 터치 확인 |

---

## 6. AI 전략 캘리브레이션

### 6.1 Thinking Budget 동적 튜닝
| 작업 유형 | Budget | 검증 |
|-----------|--------|------|
| 단순 위치 파악 | `0` | 응답 시간 < 2초 |
| 복잡한 공간 추론 | `1024` | 정확도 > 95% |

### 6.2 Visual Success Detection
```python
# 동작 후 검증 프롬프트
prompt = "물체가 목표 위치에 도착했나요? Yes/No로 답하세요."
response = gemini.generate(images=[after_image], prompt=prompt)
success = "yes" in response.lower()
```

### 6.3 Code Execution 자가 수정
```python
# Gemini 설정
config = {
    "tools": [{"code_execution": {}}],
    "thinking_budget": 1024
}
# AI가 좌표 오류 발견 시 스스로 수정
```

### 6.4 Stop-Capture-Act 시퀀스
```python
async def execute_with_capture():
    await robot.stop()           # 1. 정지
    await asyncio.sleep(0.3)     # 2. 안정화 대기
    frame = camera.capture()     # 3. 캡처
    result = await gemini.analyze(frame)  # 4. 분석
    await robot.move(result.target)       # 5. 이동
```

---

## 7. 검증 품질 지표

| 지표 | 목표값 | 측정 방법 |
|------|--------|----------|
| `mean_error_mm` | < 3mm | 10회 반복 평균 |
| `max_error_mm` | < 5mm | 10회 반복 최대 |
| `z_accuracy` | < 2mm | 높이별 측정 |
| `success_rate` | > 95% | 100회 파지 테스트 |

---

## 8. 관련 파일

| 파일 | 역할 |
|------|------|
| `calibration.json` | 캘리브레이션 데이터 저장 |
| `src/robotics/coord_transformer.py` | 좌표 변환 로직 |
| `src/robotics/ik_solver.py` | 역기구학 계산 |
| `src/ai_engine.py` | AI 통합 |
| `src/calibration_api.py` | 캘리브레이션 REST API |

---

*최종 업데이트: 2026-01-30*
