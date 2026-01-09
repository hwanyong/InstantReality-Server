import cv2
import asyncio
from aiortc import VideoStreamTrack
from av import VideoFrame
import time

class OpenCVVideoCapture(VideoStreamTrack):
    """
    A VideoStreamTrack that yields frames from an OpenCV capture.
    """
    def __init__(self, camera_index=0, options={"width": 640, "height": 480}):
        super().__init__()
        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        
        # Configure Resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, options["width"])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, options["height"])
        
        self.latest_high_res_frame = None
        
        if not self.cap.isOpened():
            print(f"Warning: Could not open camera {camera_index}")
            
    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        # Read frame (blocking call, but fast enough for usb cam typically)
        ret, frame = self.cap.read()
        
        if not ret:
            # Create a dummy black frame if failed
            frame = self._create_black_frame(640, 360) # 360p (16:9)
            self.latest_high_res_frame = None
        else:
            # Store the raw high-res frame (e.g. 1920x1080) for AI
            self.latest_high_res_frame = frame
            
            # Resize for WebRTC Streaming (Low Latency) -> 640x360 (16:9)
            frame = cv2.resize(frame, (640, 360))
            
        # Convert BGR (OpenCV) to RGB (aiortc/av expects YUV or RGB)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        video_frame = VideoFrame.from_ndarray(frame_rgb, format="rgb24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        
        return video_frame

    def get_latest_frame(self):
        """Returns the latest high-resolution frame (BGR) or None."""
        return self.latest_high_res_frame

    def _create_black_frame(self, width, height):
        import numpy as np
        return np.zeros((height, width, 3), dtype=np.uint8)

    def stop(self):
        if self.cap.isOpened():
            self.cap.release()
        super().stop()
