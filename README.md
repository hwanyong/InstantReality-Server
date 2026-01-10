# InstantReality Server

## 서버 재시작 방법 (How to Restart Server)

서버 코드가 수정되었거나 재설정이 필요할 때 다음 명령어로 서버를 재시작할 수 있습니다.

### 1. 실행 중인 서버 종료 (PowerShell)
기존에 8080 포트를 점유하고 있는 프로세스를 강제로 종료합니다.
```powershell
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8080).OwningProcess -Force
```

### 2. 서버 시작
프로젝트 루트 경로에서 가상 환경의 Python을 사용하여 서버를 실행합니다.
```powershell
.\.venv\Scripts\python.exe src/server.py
```
