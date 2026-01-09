from aiortc import VideoStreamTrack
from av import VideoFrame
import time
import numpy as np
from camera_manager import get_camera

class OpenCVVideoCapture(VideoStreamTrack):
    """
    A VideoStreamTrack that yields frames from the CameraManager.
    """
    def __init__(self, camera_index=0, options=None):
        super().__init__()
        self.camera_index = camera_index
        # We don't need options here as Manager handles it, but keeping arg for compatibility
        self.cam_thread = get_camera(camera_index)
        
    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        # 1. Non-blocking fetch from manager
        high_res, processed_rgb = self.cam_thread.get_frames()
        
        if processed_rgb is None:
            # Camera hasn't started or is failing, send black frame
            processed_rgb = self._create_black_frame(640, 360)
        
        # 2. Wrap in VideoFrame (Zero-copy ideally, extremely fast)
        video_frame = VideoFrame.from_ndarray(processed_rgb, format="rgb24")
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
