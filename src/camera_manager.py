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
        
    def start(self):
        if self.running:
            return
            
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        
        if not self.cap.isOpened():
            print(f"Error: Could not open camera {self.camera_index}")
            return

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print(f"Camera {self.camera_index} thread started.")

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

def get_camera(index):
    if index not in _cameras:
        _cameras[index] = CameraThread(index)
        _cameras[index].start()
    return _cameras[index]

def stop_all():
    print("Stopping all cameras...")
    for cam in _cameras.values():
        cam.stop()
    _cameras.clear()
