# InstantReality SDK Initialization and Usage Guide

This guide explains how to initialize and use the `InstantReality` class across various environments.

## `InstantReality` Constructor Options

```javascript
new InstantReality({
    serverUrl: string,      // API Server URL (Default: '')
    maxCameras: number,     // Max cameras to receive (Default: 4)
    iceServers: object[]    // WebRTC STUN/TURN servers (Default: Google Public STUN)
})
```

## `connect()` Method Options (`cameras`)

You can specify which cameras (tracks) should be enabled initially upon connection.

```javascript
await ir.connect({
    cameras: [0, 1] // Only enable cameras at these indices (others start muted)
})
```


---

## Use Cases

### Case 1: Basic Usage (Local/Single Server)
This is the simplest form, used when the frontend and backend are served from the same domain or a proxy is configured.

```javascript
// Initializing without options uses all defaults.
const ir = new InstantReality();

// Defaults applied:
// serverUrl: '' (Relative path, e.g., /offer)
// maxCameras: 4 ( Prepares 4 video tracks)
// iceServers: Uses Google's public STUN server
```
**Recommended for:**
- Development where frontend and backend run together.
- When using Webpack/Vite proxy to route API requests to the backend.

---

### Case 2: Different API Server URL (CORS Environment)
You must specify `serverUrl` if the frontend and backend addresses differ.
**Note:** Do NOT include a trailing slash (`/`) at the end of the URL. The SDK appends `/offer` internally.

```javascript
const ir = new InstantReality({
    // ✅ Correct Example
    serverUrl: 'http://192.168.1.10:8000' 
    
    // ❌ Incorrect Example (Do not include trailing slash)
    // serverUrl: 'http://192.168.1.10:8000/'
});
```

---

### Case 3: Camera Optimization (Performance Tuning)
You can limit the number of cameras to prevent unnecessary resource usage. `maxCameras` determines the number of video tracks (Transceivers) created during the WebRTC connection.

```javascript
const ir = new InstantReality({
    // Set to 2 if only 2 cameras are connected to the server
    maxCameras: 2
});
```
**Effect:** Prevents creating empty tracks during `connect()`, slightly improving initial connection speed and saving client resources.

---

### Case 4: Private Network/Firewall (Custom ICE Servers)
Use this when you need to configure custom STUN/TURN servers for production environments or users behind firewalls.

```javascript
const ir = new InstantReality({
    iceServers: [
        { 
            // Custom STUN server
            urls: 'stun:stun.myserver.com:3478' 
        },
        { 
            // TURN server (Required for relay)
            urls: 'turn:turn.myserver.com:3478',
            username: 'myuser',
            credential: 'mypassword'
        }
    ]
});
```
**Recommended for:**
- Users on 3G/LTE/5G networks.
- Users inside corporate security networks (TURN server required).

---

### Case 5: Production Deployment (Combined Settings)
In production, you typically combine these options.

```javascript
const ir = new InstantReality({
    serverUrl: 'https://api.instant-reality.com', // Dedicated API server
    maxCameras: 8,                                // Support 8 channels
    iceServers: [                                 // TURN server for reliable connection
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'turn:turn.instant-reality.com:3478', username: 'user', credential: 'pw' }
    ]
});
```


---

### Case 6: Track Selection with MaxCameras (Using `cameras` option)
Use this combination when you want to reserve slots for multiple cameras using `maxCameras`, but only want to display specific cameras initially.

```javascript
// 1. Prepare slots for up to 4 video tracks
const ir = new InstantReality({ maxCameras: 4 });

// 2. Start with only Camera 0 enabled
// (Cameras 1, 2, 3 are connected but start locally disabled/muted)
await ir.connect({ 
    cameras: [0] 
});

// 3. Enable other cameras later as needed
ir.setTrackEnabled(1, true);
```

## Options Summary Table

| Option | Default | Description |
| :--- | :--- | :--- |
| `serverUrl` | `''` (Empty String) | Base URL for API requests. **Must NOT denote a trailing slash.** |
| `maxCameras` | `4` | Maximum number of video streams to receive. If actual cameras are fewer, only available ones are shown. |
| `iceServers` | `[{ urls: 'stun:...' }]` | List of STUN/TURN servers to find WebRTC connection paths (P2P/Relay). |

## `connect(options)` Parameters
| Option | Type | Description |
| :--- | :--- | :--- |
| `cameras` | `number[]` | Array of camera indices to enable immediately after connection (e.g., `[0, 2]`). If omitted, all received tracks are enabled. |

