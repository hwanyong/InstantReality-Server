from aiortc import VideoStreamTrack
from av import VideoFrame
import time
import numpy as np
from src.camera_manager import get_camera

class OpenCVVideoCapture(VideoStreamTrack):
    """
    A VideoStreamTrack that yields frames from the CameraManager.
    """
    def __init__(self, camera_index=0, options=None):
        super().__init__()
        self.camera_index = camera_index
        # We don't need options here as Manager handles it, but keeping arg for compatibility
        self.cam_thread = get_camera(camera_index)
        self.paused = False
    
    def set_paused(self, paused):
        self.paused = paused
        
    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        if self.paused:
            # Send black frame when paused (saves bandwidth)
            frame_rgb = self._create_black_frame(16, 16)
        else:
            # Normal: fetch from camera manager
            high_res, frame_rgb = self.cam_thread.get_frames()
            if frame_rgb is None:
                frame_rgb = self._create_black_frame(16, 16)
        
        video_frame = VideoFrame.from_ndarray(frame_rgb, format="rgb24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        
        return video_frame

    def get_latest_frame(self):
        """Returns the latest high-resolution frame (BGR) or None."""
        high_res, _ = self.cam_thread.get_frames()
        return high_res

    def _create_black_frame(self, width, height):
        return np.zeros((height, width, 3), dtype=np.uint8)

    def stop(self):
        # We generally don't stop the global camera thread here because multiple clients might share it.
        # But per current architecture, we can leave it running.
        super().stop()


class BlackVideoTrack(VideoStreamTrack):
    """
    A minimal VideoStreamTrack that yields tiny black frames.
    Used for per-client pause to save bandwidth.
    """
    def __init__(self):
        super().__init__()
        self._black_frame = np.zeros((16, 16, 3), dtype=np.uint8)
    
    async def recv(self):
        pts, time_base = await self.next_timestamp()
        video_frame = VideoFrame.from_ndarray(self._black_frame, format="rgb24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame
