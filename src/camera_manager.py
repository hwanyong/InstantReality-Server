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


def stop_all():
    print("Stopping all cameras...")
    for cam in _cameras.values():
        cam.stop()
    _cameras.clear()
