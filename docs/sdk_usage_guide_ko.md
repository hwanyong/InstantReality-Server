# InstantReality SDK 초기화 및 사용 가이드

`InstantReality` 클래스를 초기화하고 사용하는 방법을 다양한 환경별로 안내합니다.

## `InstantReality` 생성자 옵션

```javascript
new InstantReality({
    serverUrl: string,      // API 서버 주소 (기본값: '')
    maxCameras: number,     // 최대 수신 카메라 수 (기본값: 4)
    iceServers: object[]    // WebRTC STUN/TURN 서버 설정 (기본값: Google Public STUN)
})
```

## `connect()` 메서드 옵션 (`cameras`)

연결 시점에 특정 카메라(트랙)만 활성화하여 시작할 수 있습니다.

```javascript
await ir.connect({
    cameras: [0, 1] // 지정된 인덱스의 카메라만 활성화 (나머지는 mute 상태로 시작)
})
```


---

## 사용 케이스 (Use Cases)

### Case 1: 기본 사용 (로컬/단일 서버 환경)
가장 간단한 형태로, 프론트엔드와 백엔드가 같은 도메인에서 제공되거나 프록시가 설정된 경우에 사용합니다.

```javascript
// 옵션 없이 초기화하면 모든 기본값이 적용됩니다.
const ir = new InstantReality();

// 적용되는 기본값:
// serverUrl: '' (현재 도메인의 상대 경로 사용, 예: /offer)
// maxCameras: 4 (최대 4개의 비디오 트랙 수신 준비)
// iceServers: Google의 공용 STUN 서버 사용
```
**추천 환경:**
- 개발 단계에서 프론트엔드와 백엔드를 같이 실행할 때
- Webpack/Vite 프록시를 통해 API 요청을 백엔드로 우회할 때

---

### Case 2: API 서버 주소가 다른 경우 (CORS 환경)
프론트엔드와 백엔드 주소가 다를 때 `serverUrl`을 명시해야 합니다.
**주의:** URL 끝에 슬래시(`/`)를 포함하면 안 됩니다. SDK 내부에서 `/offer`를 붙여서 요청하기 때문입니다.

```javascript
const ir = new InstantReality({
    // ✅ 올바른 예시
    serverUrl: 'http://192.168.1.10:8000' 
    
    // ❌ 틀린 예시 (슬래시 포함 금지)
    // serverUrl: 'http://192.168.1.10:8000/'
});
```

---

### Case 3: 카메라 수량 최적화 (성능 튜닝)
불필요한 리소스 낭비를 막기 위해 사용할 카메라 개수를 제한할 수 있습니다. `maxCameras`는 WebRTC 연결 시 미리 생성할 비디오 트랙(Transceiver)의 개수를 결정합니다.

```javascript
const ir = new InstantReality({
    // 서버에 2대의 카메라만 연결되어 있다면 2로 설정
    maxCameras: 2
});
```
**효과:** `connect()` 호출 시 불필요한 빈 트랙을 생성하지 않아 초기 연결 속도가 미세하게 향상되고 클라이언트 리소스를 절약합니다.

---

### Case 4: 사설망/방화벽 환경 (커스텀 ICE 서버)
실제 서비스 환경이나 방화벽 뒤에 있는 사용자를 위해 커스텀 STUN/TURN 서버를 설정해야 할 때 사용합니다.

```javascript
const ir = new InstantReality({
    iceServers: [
        { 
            // 커스텀 STUN 서버
            urls: 'stun:stun.myserver.com:3478' 
        },
        { 
            // TURN 서버 (릴레이 필요 시 필수)
            urls: 'turn:turn.myserver.com:3478',
            username: 'myuser',
            credential: 'mypassword'
        }
    ]
});
```
**추천 환경:**
- 3G/LTE/5G 망 사용자가 접속할 때
- 기업 보안망 내부에서 접속할 때 (TURN 서버 필수)

---

### Case 5: 프로덕션 배포 (복합 설정)
실제 배포 시에는 보통 위 옵션들을 조합해서 사용합니다.

```javascript
const ir = new InstantReality({
    serverUrl: 'https://api.instant-reality.com', // 별도 API 서버
    maxCameras: 8,                                // 8채널 지원
    iceServers: [                                 // 안정적인 연결을 위한 TURN 서버
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'turn:turn.instant-reality.com:3478', username: 'user', credential: 'pw' }
    ]
});
```


---

### Case 6: 트랙 선택과 MaxCameras 조합 (`cameras` 옵션 활용)
`maxCameras`로 최대 연결 가능한 트랙(슬롯) 수를 확보해두되, 실제 화면에는 `connect` 시점의 `cameras` 옵션으로 지정한 카메라만 표시하고 싶을 때 사용합니다.

```javascript
// 1. 최대 4개의 비디오 트랙 수신 준비 (슬롯 확보)
const ir = new InstantReality({ maxCameras: 4 });

// 2. 초기 연결 시 0번 카메라만 활성화 상태로 시작
// (1, 2, 3번 카메라는 연결은 되지만 클라이언트 측에서 비활성/Mute 상태)
await ir.connect({ 
    cameras: [0] 
});

// 3. 이후 필요에 따라 다른 카메라 활성화
ir.setTrackEnabled(1, true);
```

## 옵션 요약표

| 옵션 | 기본값 | 설명 |
| :--- | :--- | :--- |
| `serverUrl` | `''` (빈 문자열) | API 요청을 보낼 기본 URL입니다. **반드시 마지막 슬래시를 제외**해야 합니다. |
| `maxCameras` | `4` | 수신할 비디오 스트림의 최대 개수입니다. 실제 카메라 수보다 적으면 일부만 보입니다. |
| `iceServers` | `[{ urls: 'stun:...' }]` | WebRTC 연결 경로(P2P/Relay)를 찾기 위한 STUN/TURN 서버 목록입니다. |

## `connect(options)` 파라미터
| 옵션 | 타입 | 설명 |
| :--- | :--- | :--- |
| `cameras` | `number[]` | 연결 직후 활성화할 카메라 인덱스 배열입니다. (예: `[0, 2]`) 지정하지 않으면 수신된 모든 트랙이 활성화됩니다. |

