import cv2

def check_focus_capabilities(cam_index):
    print(f"\n--- Checking Camera {cam_index} Focus Capabilities ---\n")
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"Could not open camera {cam_index}")
        return

    # 1. Check Auto Focus Support
    # 0 = Off, 1 = On (Typically)
    # Some backend might define it differently.
    
    # Try getting current value
    autofocus_val = cap.get(cv2.CAP_PROP_AUTOFOCUS)
    print(f"Current Auto Focus Value: {autofocus_val}")

    # Try setting to off
    print("Attempting to disable Auto Focus...")
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    new_af_val = cap.get(cv2.CAP_PROP_AUTOFOCUS)
    print(f"Auto Focus Value after disabling: {new_af_val}")

    # 2. Check Manual Focus Support
    # Usually ranges from 0 to 255 or 0 to 100 step 5.
    focus_val = cap.get(cv2.CAP_PROP_FOCUS)
    print(f"Current Focus Value: {focus_val}")
    
    # Try setting a specific focus value (e.g., near 0)
    if new_af_val == 0:
        print("Attempting to set Manual Focus to 0 (Near)...")
        cap.set(cv2.CAP_PROP_FOCUS, 0)
        print(f"Focus Value after set 0: {cap.get(cv2.CAP_PROP_FOCUS)}")
        
        print("Attempting to set Manual Focus to 255 (Far)...")
        cap.set(cv2.CAP_PROP_FOCUS, 255) # Value depends on camera
        print(f"Focus Value after set 255: {cap.get(cv2.CAP_PROP_FOCUS)}")
    else:
        print("Skipping manual focus test because Auto Focus could not be disabled.")

    cap.release()

if __name__ == "__main__":
    check_focus_capabilities(0)
    check_focus_capabilities(1)
