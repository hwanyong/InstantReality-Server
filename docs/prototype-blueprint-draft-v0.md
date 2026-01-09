[프롬프트] Gemini Robotics-ER 1.5 기반 지능형 서버 개발 기획/설계서
1. 프로젝트 개요 (Project Overview)
• 목표: LattePanda 2 Alpha를 서버로 사용하여 2~4개의 웹캠 영상을 실시간 스트리밍(WebRTC)하고, Gemini Robotics-ER 1.5 모델을 통해 자연어 명령을 로봇팔의 물리적 동작으로 변환하는 통합 에이전트 시스템 구축.
• 핵심 기술: Python 3.10+, Gemini Robotics-ER 1.5 (VLM), WebRTC (aiortc), Arduino (ATMEL 32U4).
2. 시스템 아키텍처 설계 (System Architecture)
• 서버 환경: LattePanda 2 Alpha 864s (Windows 10 Pro 기반 Python 서버).
• 통신 구조:
    ◦ External (N:1): 복수의 클라이언트에게 WebRTC를 통해 초저지연 영상 전송 및 JSON 명령 수신.
    ◦ Internal: Python 서버에서 Gemini API로 이미지/동영상 데이터를 전송하고 궤적 좌표를 수신.
    ◦ Hardware: 시리얼 통신을 통해 내장 아두이노 및 PCA9685 PWM 드라이버 제어.
3. 주요 모듈 설계 (Core Modules)
• A. 동적 카메라 관리 모듈 (Dynamic Vision Module):
    ◦ USB 3.0 포트를 통해 연결된 2~4개의 웹캠(Logitech C920x 등)을 자동 감지.
    ◦ 다중 뷰 대응(Multi-view correspondence)을 위해 각 카메라의 프레임을 동기화하여 캡처.
• B. WebRTC 스트리밍 모듈 (Broadcasting Module):
    ◦ Server-to-Client 방식으로 N개의 클라이언트에게 실시간 영상 송출.
    ◦ DataChannel을 통해 클라이언트의 자연어 명령 및 제어 신호 수신.
• C. Gemini AI 추론 모듈 (AI Reasoning Module):
    ◦ google-genai SDK를 사용하여 이미지와 프롬프트를 전송.
    ◦ 기능: 객체 감지, 경계 상자(Bounding Box) 생성, 15개 이상의 중간 지점을 포함한 궤적 계획.
    ◦ 성공 감지: 작업 전후 이미지를 비교하여 임무 완료 여부 판단.
• D. 로봇팔 제어 모듈 (Hardware Control Module):
    ◦ Gemini가 반환한 0~1000 정규화 좌표를 실제 관절 각도로 매핑.
    ◦ move(x, y, high), setGripperState(opened) 등 API 함수 구현 및 실행.
4. Gemini API 통합 프롬프트 설계 (Prompt Engineering)
• 시스템 역할 정의: "너는 6자유도를 가진 로봇팔 에이전트이며, 주어진 다중 뷰 이미지를 분석하여 장애물을 피하고 물체를 조작해야 한다.".
• 좌표계 설정: 베이스 위치를 원점(robot_origin)으로 설정하고 상대 좌표를 계산하도록 지시.
• 사고 예산(Thinking Budget) 최적화: 지연 시간을 줄이기 위해 공간 추론 시에는 thinking_budget=0으로 설정하고, 복잡한 단계 계획 시에는 예산을 높여 정확도 확보.
5. 단계별 구현 가이드 (Implementation Steps)
1. 환경 구축: LattePanda에 Python 환경 설정 및 google-genai, aiortc, pyserial 설치.
2. 카메라 및 WebRTC 연동: 다중 웹캠 캡처 레이턴시 최적화 및 클라이언트 접속 테스트.
3. VLA(Vision-Language-Action) 구현: 자연어 명령을 입력받아 Gemini가 로봇 제어 함수 호출 시퀀스(JSON)를 반환하도록 프롬프트 튜닝.
4. 하드웨어 테스트: PCA9685를 통해 실제 로봇팔 관절의 가동 범위(Yaw/Pitch) 보정 및 매핑.
5. 통합 시나리오 실행: "파란색 블록을 집어 주황색 그릇에 넣어줘"와 같은 복잡한 작업 오케스트레이션 테스트.