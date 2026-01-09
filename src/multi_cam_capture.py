import cv2
import threading
import time
import os
import datetime
from concurrent.futures import ThreadPoolExecutor

class CameraCapture:
    def __init__(self, index):
        self.index = index
        # cv2.CAP_DSHOW is generally faster/more stable on Windows for basic webcams
        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        self.frame = None
        
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera {index}")
        
        # Set resolution to a standard safe value (VGA) for prototype reliability
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def warmup(self, frame_count=60):
        print(f"[Cam {self.index}] Warming up ({frame_count} frames)...")
        for _ in range(frame_count):
            ret, frame = self.cap.read()
            if ret:
                self.frame = frame
            else:
                print(f"[Cam {self.index}] Warning: Failed to read frame during warmup")
                time.sleep(0.01)
        print(f"[Cam {self.index}] Warmup complete")

    def save_snapshot(self, output_dir):
        # Ensure we have a frame. If warmup failed to keep one, try reading now.
        if self.frame is None:
            ret, self.frame = self.cap.read()
        
        if self.frame is not None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cam_{self.index}_{timestamp}.jpg"
            filepath = os.path.join(output_dir, filename)
            
            # Using cv2.imwrite in the thread to avoid blocking main thread
            cv2.imwrite(filepath, self.frame)
            print(f"[Cam {self.index}] Saved: {filepath}")
            return filepath
        else:
            print(f"[Cam {self.index}] Error: No frame to save")
            return None

    def release(self):
        if self.cap.isOpened():
            self.cap.release()

def discover_cameras(max_indices=4):
    """
    Check first N indices.
    Note: On some systems, checking invalid indices involves a delay.
    """
    print("Discovering cameras (checking indices 0-3)...")
    working_indices = []
    for i in range(max_indices):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            print(f" - Found camera at index {i}")
            working_indices.append(i)
            cap.release()
    return working_indices

def worker_routine(index, output_dir):
    cam = None
    try:
        cam = CameraCapture(index)
        # Warmup for ~2 seconds (assuming 30fps)
        cam.warmup(60)
        cam.save_snapshot(output_dir)
        return True
    except Exception as e:
        print(f"[Cam {index}] Error: {e}")
        return False
    finally:
        if cam:
            cam.release()

def main():
    output_dir = "captures"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # Step 1: Discover
    indices = discover_cameras()
    if not indices:
        print("No cameras found. Please check connections.")
        return

    print(f"\nStarting concurrent capture for {len(indices)} cameras...")
    print("This will take approx 3-4 seconds (warmup + save)...\n")
    
    # Step 2: Execute in parallel
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=len(indices)) as executor:
        futures = [executor.submit(worker_routine, idx, output_dir) for idx in indices]
        
        # Wait for all to complete
        for future in futures:
            future.result()
            
    elapsed = time.time() - start_time
    print(f"\nAll tasks completed in {elapsed:.2f} seconds.")
    print(f"Check the '{output_dir}' folder for images.")

if __name__ == "__main__":
    main()
