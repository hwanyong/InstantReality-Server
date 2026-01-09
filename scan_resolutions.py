import cv2

def scan_resolutions():
    # List of resolutions to check
    resolutions = [
        (320, 240),
        (640, 480),
        (800, 600),
        (1024, 768),
        (1280, 720),
        (1280, 960),
        (1920, 1080),
        (3840, 2160)
    ]
    
    print("Scanning supported resolutions for Camera 0...")
    
    # Open camera 0 with CAP_DSHOW for Windows
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    
    if not cap.isOpened():
        print("Error: Could not open camera 0.")
        return

    supported_resolutions = []

    for width, height in resolutions:
        # Try to set the resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        # Read back the actual resolution set
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # If the read back matches the request, it's supported
        if actual_width == width and actual_height == height:
            supported_resolutions.append(f"{width}x{height}")
            print(f"Supported: {width}x{height}")
        else:
            print(f"Not supported: {width}x{height} (Got {actual_width}x{actual_height})")

    cap.release()
    print("\nFinal Supported Resolutions:")
    for res in supported_resolutions:
        print(res)

if __name__ == "__main__":
    scan_resolutions()
