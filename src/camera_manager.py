import cv2
import threading
import time
import numpy as np

class CameraThread:
    def __init__(self, camera_index, width=1920, height=1080):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.running = False
        self.thread = None
        self.cap = None
        
        # Buffers (Thread-safe assignment is atomic in Python for single vars, but locking is safer)
        self.lock = threading.Lock()
        self.latest_high_res_frame = None # Raw BGR 1080p
        self.latest_processed_frame = None # RGB 360p (Ready for sending)
        
        # Auto Exposure State
        self.auto_exposure_enabled = False
        self.current_exposure = -5
        self.target_brightness = 128
        self.frame_counter = 0
        
    def start(self):
        if self.running:
            return
            
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer for low latency
        
        # Default Focus Strategy: Auto Focus ON initially
        # self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

        if not self.cap.isOpened():
            print(f"Error: Could not open camera {self.camera_index}")
            return

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print(f"Camera {self.camera_index} thread started.")

    def set_focus(self, auto_focus=True, value=0):
        """
        Control camera focus.
        :param auto_focus: True for Auto Focus, False for Manual Focus
        :param value: Focus value (0-255), used only if auto_focus is False
        """
        if not self.cap or not self.cap.isOpened():
            return

        # Note: CAP_PROP_AUTOFOCUS values can vary by backend. 
        # Typically 1=On, 0=Off. Some backends use boolean.
        
        print(f"Camera {self.camera_index}: Setting Focus Auto={auto_focus}, Value={value}")
        
        if auto_focus:
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        else:
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            self.cap.set(cv2.CAP_PROP_FOCUS, value)

    def set_exposure(self, value=-5):
        """
        Control camera exposure.
        :param value: Exposure value (-13 to 0, where -13 is darkest, 0 is brightest)
        Note: CAP_PROP_AUTO_EXPOSURE toggle doesn't work on DirectShow backend,
        so we directly manipulate CAP_PROP_EXPOSURE value.
        """
        if not self.cap or not self.cap.isOpened():
            return
        
        # Clamp value to valid range
        value = max(-13, min(0, value))
        
        print(f"Camera {self.camera_index}: Setting Exposure={value}")
        self.current_exposure = value
        self.cap.set(cv2.CAP_PROP_EXPOSURE, value)

    def set_auto_exposure(self, enabled, target_brightness=128):
        """
        Enable/disable auto exposure mode.
        :param enabled: True for auto, False for manual
        :param target_brightness: Target brightness (0-255), used only if enabled
        """
        self.auto_exposure_enabled = enabled
        self.target_brightness = max(0, min(255, target_brightness))
        print(f"Camera {self.camera_index}: Auto Exposure={enabled}, Target={self.target_brightness}")

    def _analyze_brightness(self, frame):
        """Analyze frame brightness using LAB L-channel mean."""
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0]
        return np.mean(l_channel)

    def _auto_adjust_exposure(self, brightness):
        """P-controller for auto exposure adjustment."""
        if not self.auto_exposure_enabled:
            return
        
        error = self.target_brightness - brightness
        
        # Deadband: skip adjustment if close enough to target
        if abs(error) < 10:
            return
        
        # Proportional control: Kp = 0.05
        # Scale error to exposure range (-13 to 0)
        adjustment = error * 0.05
        new_exposure = self.current_exposure + adjustment
        
        # Clamp to valid range
        new_exposure = max(-13, min(0, new_exposure))
        
        # Only apply if changed meaningfully (avoid excessive API calls)
        if abs(new_exposure - self.current_exposure) >= 0.5:
            self.current_exposure = int(new_exposure)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, self.current_exposure)
            print(f"Camera {self.camera_index}: Auto adjusted exposure to {self.current_exposure} (brightness={brightness:.1f})")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        if self.cap:
            self.cap.release()
        print(f"Camera {self.camera_index} thread stopped.")

    def _capture_loop(self):
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                # Auto exposure adjustment every 10 frames
                self.frame_counter += 1
                if self.frame_counter % 10 == 0 and self.auto_exposure_enabled:
                    brightness = self._analyze_brightness(frame)
                    self._auto_adjust_exposure(brightness)

                # 1. Store High-Res (BGR) for AI
                # Copying might be needed if we modify it, but we strictly read it elsewhere.
                high_res = frame 
                
                # 2. Process for Streaming (Resize + Color Convert)
                # Resize to 360p (640x360) directly here to save main thread CPU
                resized = cv2.resize(frame, (640, 360))
                
                # Convert to RGB here (aiortc expects RGB)
                frame_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

                with self.lock:
                    self.latest_high_res_frame = high_res
                    self.latest_processed_frame = frame_rgb
                    
                # Small sleep to yield CPU if pulling faster than camera FPS (though read is blocking usually)
                # But read() blocks to camera fps, so this is minimal overhead.
                
            except Exception as e:
                print(f"Error in camera {self.camera_index}: {e}")
                time.sleep(0.1)

    def get_frames(self):
        """Returns (high_res_bgr, low_res_rgb)"""
        with self.lock:
            return self.latest_high_res_frame, self.latest_processed_frame

# Global Manager Pattern
_cameras = {}

def init_cameras(indices, width=1280, height=720):
    """Initialize multiple cameras at startup. Called once when server starts."""
    print(f"Initializing cameras: {indices}")
    for idx in indices:
        if idx not in _cameras:
            cam = CameraThread(idx, width, height)
            cam.start()
            _cameras[idx] = cam
    print(f"Cameras initialized: {list(_cameras.keys())}")

def get_active_cameras():
    """Return list of camera indices that are currently running."""
    return list(_cameras.keys())

def get_camera(index):
    if index not in _cameras:
        _cameras[index] = CameraThread(index)
        _cameras[index].start()
    return _cameras[index]

def set_camera_focus(index, auto_focus, value):
    if index in _cameras:
        _cameras[index].set_focus(auto_focus, value)
    else:
        # If camera not initialized, we initialize it temporarily or just warn
        print(f"Warning: Camera {index} not running, cannot set focus.")

def set_camera_exposure(index, value):
    if index in _cameras:
        _cameras[index].set_exposure(value)
    else:
        print(f"Warning: Camera {index} not running, cannot set exposure.")

def set_camera_auto_exposure(index, enabled, target_brightness=128):
    if index in _cameras:
        _cameras[index].set_auto_exposure(enabled, target_brightness)
    else:
        print(f"Warning: Camera {index} not running, cannot set auto exposure.")


def refresh_cameras(width=1920, height=1080):
    """
    Full restart approach: Stop all cameras, discover fresh, reinitialize.
    Filters out virtual devices (e.g., Logi Capture).
    Returns list of {role, index, name, connected} for all physical cameras.
    """
    from camera_mapping import get_available_devices, match_roles
    
    # 1. Stop ALL existing cameras (clean slate)
    print("Stopping all cameras for refresh...")
    for cam in _cameras.values():
        try:
            cam.stop()
        except Exception as e:
            print(f"Error stopping camera: {e}")
    _cameras.clear()
    print("All cameras stopped and cleared")
    
    # 2. Discover currently connected devices
    devices = get_available_devices()
    print(f"Found {len(devices)} USB video devices")
    
    # 3. Filter out virtual devices (e.g., Logi Capture, OBS Virtual Camera)
    VIRTUAL_DEVICE_KEYWORDS = ["capture", "virtual", "obs"]
    physical_devices = []
    for device in devices:
        name_lower = device["name"].lower()
        is_virtual = any(keyword in name_lower for keyword in VIRTUAL_DEVICE_KEYWORDS)
        if is_virtual:
            print(f"Skipping virtual device: {device['name']} (index {device['index']})")
        else:
            physical_devices.append(device)
    
    print(f"Physical cameras: {len(physical_devices)}")
    
    # 4. Initialize all physical cameras fresh
    for device in physical_devices:
        idx = device["index"]
        print(f"Starting camera at index {idx} ({device['name']})")
        try:
            cam = CameraThread(idx, width, height)
            cam.start()
            _cameras[idx] = cam
        except Exception as e:
            print(f"Failed to start camera {idx}: {e}")
    
    print(f"Cameras initialized: {list(_cameras.keys())}")
    
    # 5. Build result with role info
    roles = match_roles(physical_devices)
    
    # Create index-to-role mapping
    index_to_role = {}
    for role, info in roles.items():
        if info["connected"] and info["index"] is not None:
            index_to_role[info["index"]] = role
    
    result = []
    for device in physical_devices:
        idx = device["index"]
        result.append({
            "role": index_to_role.get(idx),
            "index": idx,
            "name": device["name"],
            "connected": idx in _cameras
        })
    
    return result


def get_camera_by_role(role_name):
    """
    Get CameraThread by role name.
    Returns CameraThread or None if role not mapped/connected.
    """
    from camera_mapping import get_index_by_role
    
    index = get_index_by_role(role_name)
    if index is not None and index in _cameras:
        return _cameras[index]
    return None


def stop_all():
    print("Stopping all cameras...")
    for cam in _cameras.values():
        cam.stop()
    _cameras.clear()


# ────────────────────────────────────────────────────────────────────────────
# Background Polling for Hot-Plug Detection
# ────────────────────────────────────────────────────────────────────────────

_previous_device_paths = set()

def detect_camera_changes():
    """
    Detect added/removed cameras by comparing current devices to previous state.
    Returns (added_paths, removed_paths, current_cameras)
    """
    global _previous_device_paths
    from camera_mapping import get_available_devices
    
    devices = get_available_devices()
    current_paths = {d["path"] for d in devices}
    
    added = current_paths - _previous_device_paths
    removed = _previous_device_paths - current_paths
    
    _previous_device_paths = current_paths
    
    return added, removed, devices


async def start_polling(on_change_callback, interval=3):
    """
    Start background polling for camera changes.
    Calls on_change_callback(added, removed, cameras) when changes detected.
    """
    import asyncio
    global _previous_device_paths
    from camera_mapping import get_available_devices
    
    # Initialize state
    devices = get_available_devices()
    _previous_device_paths = {d["path"] for d in devices}
    print(f"Polling started. Initial devices: {len(_previous_device_paths)}")
    
    while True:
        await asyncio.sleep(interval)
        
        added, removed, devices = detect_camera_changes()
        
        if added or removed:
            print(f"Camera change detected! Added: {len(added)}, Removed: {len(removed)}")
            
            # Refresh camera connections
            cameras = refresh_cameras()
            
            # Notify callback
            await on_change_callback(added, removed, cameras)

