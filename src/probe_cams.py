import cv2

def check_resolutions(cam_index):
    print(f"\n--- Checking Camera {cam_index} ---\n")
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"Could not open camera {cam_index}")
        return

    common_resolutions = [
        (160, 120), (320, 240), (640, 480), (800, 600), 
        (1024, 768), (1280, 720), (1920, 1080)
    ]

    for w, h in common_resolutions:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        
        actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        if int(actual_w) == w and int(actual_h) == h:
            print(f"Supported: {w}x{h} -> {int(actual_w)}x{int(actual_h)}")
        else:
             # Sometimes it snaps to nearest supported
            print(f"Requested {w}x{h}, got {int(actual_w)}x{int(actual_h)}")

    cap.release()

if __name__ == "__main__":
    # Check both cameras used in the project
    check_resolutions(0)
    check_resolutions(1)
