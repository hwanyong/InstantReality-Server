# InstantReality Camera System and Gemini Robotics Integration

## 1. Camera System Architecture

### 1.1 Core Components

#### CameraThread (camera_manager.py)
```python
class CameraThread:
    def __init__(self, camera_index, width=1920, height=1080):
        # Thread-safe frame buffers with Lock
        self.latest_high_res_frame = None  # Raw BGR 1080p for AI
        self.latest_processed_frame = None  # RGB 360p for streaming
        
        # Auto Exposure P-Controller
        self.auto_exposure_enabled = False
        self.current_exposure = -5
        self.target_brightness = 128
```

**Dual Data Path Architecture:**
- **High-Resolution Path**: Raw BGR 1080p/720p for Gemini AI analysis
- **Low-Resolution Path**: RGB 360p (640x360) for WebRTC streaming

### 1.2 Camera Role System

**Predefined Roles (camera_mapping.py):**
```python
VALID_ROLES = ["TopView", "QuarterView", "LeftRobot", "RightRobot"]
```

- **TopView**: Overhead camera for workspace observation
- **QuarterView**: Angled perspective for depth perception
- **LeftRobot**: Left arm working area
- **RightRobot**: Right arm working area

**Device-Path Mapping:**
- Uses USB device path (not index) for stable identification across reboots
- Stored in `camera_config.json`

### 1.3 Multi-Threaded Capture

```
┌────────────────────────────────────────────────────────────┐
│                     Main Server Thread                     │
│  (aiohttp async event loop - handles HTTP/WebSocket)       │
└────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │ CameraThread│   │ CameraThread│   │ CameraThread│
    │   Index 0   │   │   Index 1   │   │   Index 2   │
    │  (TopView)  │   │ (QuarterView)│  │ (LeftRobot) │
    └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
           │                 │                 │
           ▼                 ▼                 ▼
      cv2.read()        cv2.read()        cv2.read()
           │                 │                 │
           └────────┬────────┴────────┬────────┘
                    ▼                 ▼
           High-Res Buffer    Low-Res Buffer
           (for AI analysis)  (for streaming)
```

---

## 2. Server V2 Structure (server_v2.py)

### 2.1 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/config` | GET | Robot configuration |
| `/api/capture` | GET | Capture current camera frame |
| `/api/prompt` | POST | Process natural language with Gemini |
| `/api/execute` | POST | Send pulse commands to hardware |
| `/api/estop` | POST | Emergency stop |
| `/api/ik/test` | POST | Test IK calculation |

### 2.2 Global Instances

```python
robot: RobotController = None
transformer: CoordinateTransformer = None
brain: GeminiBrain = None
```

### 2.3 Capture Flow for Gemini

```python
# From handle_capture()
cam = get_camera(camera_index)
high_res, _ = cam.get_frames()

# Resize for Gemini (800px width)
h, w = high_res.shape[:2]
target_width = 800
new_h = int(target_width * h / w)
resized = cv2.resize(high_res, (target_width, new_h))

# Encode to base64
_, buffer = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
b64_image = base64.b64encode(buffer).decode('utf-8')
```

---

## 3. Fixed Camera Position Considerations

### 3.1 Fixed Position Advantages

1. **Consistent Coordinate Mapping**: Camera position never changes → stable pixel-to-world coordinate transformation
2. **Pre-calibrated Lens Distortion**: One-time calibration is sufficient
3. **Known Field of View**: Workspace boundaries are fixed and known

### 3.2 Position-Aware Integration Points

```
Camera Position Matrix (Conceptual):
┌─────────────────────────────────────────────┐
│                 TopView                      │
│           (Straight Down, Z-axis)            │
│                                             │
│   ┌─────────────────────────────────────┐   │
│   │         Workspace (600×400mm)        │   │
│   │                                     │   │
│   │  LeftRobot ◄──────────► RightRobot  │   │
│   │                                     │   │
│   └─────────────────────────────────────┘   │
│                                             │
│           QuarterView (45° angle)            │
└─────────────────────────────────────────────┘
```

### 3.3 Coordinate Transformation

**CoordinateTransformer Configuration:**
```python
transformer = CoordinateTransformer(WorkspaceConfig(
    width_mm=600,
    height_mm=400,
    robot_base_height=107,
    default_target_z=10
))
```

**Gemini → Robot Coordinate Flow:**
```
Gemini Output: [y, x] (0-1000 normalized)
        │
        ▼
gemini_to_robot(gemini_x, gemini_y, target_z, arm_name)
        │
        ▼
Local Robot Coords: (local_x, local_y, local_z) in mm
```

---

## 4. Gemini Robotics ER 1.5 Integration

### 4.1 Model Characteristics

- **Model ID**: `gemini-robotics-er-1.5-preview`
- **Capabilities**: Visual understanding, spatial reasoning, action planning
- **Coordinate Output**: [y, x] normalized to 0-1000

### 4.2 Current Integration (ai_engine.py)

```python
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class GeminiBrain:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = os.environ.get("GEMINI_MODEL", "gemini-robotics-er-1.5-preview")
    
    def analyze_frame(self, frame_bgr, instruction):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        _, buffer = cv2.imencode(".jpg", frame_rgb)
        image_bytes = buffer.tobytes()
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
```

### 4.3 Prompt Structure for Robot Control

```python
prompt = f'''You are a dual-arm robot controller.
User instruction: "{instruction}"

Analyze the image and return:
1. target_arm: "right_arm" or "left_arm"
2. coordinates: [y, x] (0-1000 normalized)
3. approach_strategy: "straight" | "hook_left" | "hook_right"
4. target_z: estimated object height in mm
5. description: brief reasoning

Output in JSON format:
{{
    "target_arm": "right_arm",
    "coordinates": [y, x],
    "approach_strategy": "straight",
    "target_z": 10,
    "description": "..."
}}'''
```

---

## 5. Research Questions for NotebookLM

### 5.1 Fixed Camera Position Integration
- How should fixed camera positions be communicated to Gemini Robotics ER 1.5?
- Should camera intrinsics/extrinsics be included in system prompts?
- How to leverage "always-known" FOV for more accurate spatial reasoning?

### 5.2 Code Structure Design
- Should CameraProvider abstraction wrap different camera sources?
- How to design a VisionPipeline that decouples capture from analysis?
- What interfaces should exist between Camera → Image Processing → Gemini?

### 5.3 Abstraction for Stability
- How to handle camera disconnection gracefully?
- Should there be a FrameBuffer abstraction for temporal queries?
- How to design retry/fallback logic for Gemini API failures?

---

## 6. Proposed Architecture Improvements

### 6.1 Abstract Camera Provider

```python
class ICameraProvider(ABC):
    @abstractmethod
    def get_latest_frame(self, role: str) -> Optional[np.ndarray]:
        pass
    
    @abstractmethod
    def get_frame_with_metadata(self, role: str) -> CapturedFrame:
        pass

@dataclass
class CapturedFrame:
    image: np.ndarray
    timestamp: float
    camera_role: str
    resolution: Tuple[int, int]
```

### 6.2 Vision Pipeline Design

```
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│   Camera   │───►│  Preprocessor│───►│   Gemini   │───►│  Executor  │
│  Provider  │    │  (resize,   │    │    Brain   │    │  (IK+Serial)│
│            │    │   encode)   │    │            │    │            │
└────────────┘    └────────────┘    └────────────┘    └────────────┘
       │                │                 │                 │
       └────────────────┴─────────────────┴─────────────────┘
                              │
                    ┌────────────────┐
                    │ VisionContext  │
                    │ (camera_role,  │
                    │  workspace,    │
                    │  calibration)  │
                    └────────────────┘
```

### 6.3 Error Handling Strategy

```python
class VisionResult:
    success: bool
    data: Optional[dict]
    error: Optional[str]
    retry_suggested: bool
    
class RetryPolicy:
    max_retries: int = 3
    backoff_seconds: float = 1.0
    fallback_camera_role: Optional[str] = None
```
