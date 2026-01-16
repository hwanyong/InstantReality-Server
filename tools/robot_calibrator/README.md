# Robot Calibration Tool

서보모터 캘리브레이션 및 하드웨어 진단을 위한 독립형 GUI 도구입니다.

## 설치 (Installation)

```powershell
cd tools/robot_calibrator
pip install -r requirements.txt
```

## 실행 (Run)

```powershell
python calibrator_gui.py
```

## 기능 (Features)

- **연결 관리**: Arduino COM 포트 자동 탐지 및 연결
- **서보 제어**: 12개 서보 슬롯 (Left Arm 6개, Right Arm 6개)
- **핀 매핑**: 각 슬롯에 PCA9685 채널(0~15) 지정 가능
- **한계값 설정**: 각 서보의 Min/Max 각도 저장
- **E-STOP**: 프로그램 종료 시 모든 서보 PWM Off

## 하드웨어 연결 (Hardware Wiring)

```
LattePanda Arduino → PCA9685
  D2 (SDA) → SDA
  D3 (SCL) → SCL
  5V → VCC
  GND → GND
```

## 설정 파일 (Config File)

`servo_config.json`에 캘리브레이션 데이터가 저장됩니다.
