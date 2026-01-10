import cv2

def check_exposure_capabilities(cam_index):
    print(f"\n{'='*60}")
    print(f"  Camera {cam_index} Exposure Capabilities")
    print(f"{'='*60}\n")
    
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"Could not open camera {cam_index}")
        return None
    
    results = {
        "camera_index": cam_index,
        "auto_exposure": {"supported": False, "current": None, "can_disable": False},
        "exposure": {"supported": False, "current": None, "min": None, "max": None},
        "gain": {"supported": False, "current": None},
        "brightness": {"supported": False, "current": None}
    }
    
    # 1. Check Auto Exposure Support
    # Windows DirectShow: 0.25 = Manual, 0.75 = Auto (varies by camera/driver)
    # Some cameras: 1 = Manual, 3 = Auto
    print("[1] Auto Exposure (CAP_PROP_AUTO_EXPOSURE)")
    print("-" * 40)
    
    auto_exp_val = cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)
    print(f"  Current Value: {auto_exp_val}")
    results["auto_exposure"]["current"] = auto_exp_val
    
    if auto_exp_val != 0:
        results["auto_exposure"]["supported"] = True
        
        # Try disabling auto exposure (try common values)
        print("  Attempting to disable (set to 0.25)...")
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        new_val = cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)
        print(f"  Value after set 0.25: {new_val}")
        
        if new_val != auto_exp_val:
            results["auto_exposure"]["can_disable"] = True
            print("  ✓ Auto Exposure can be toggled")
        else:
            # Try alternate value
            print("  Attempting alternate (set to 1)...")
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
            new_val2 = cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)
            print(f"  Value after set 1: {new_val2}")
            if new_val2 != auto_exp_val:
                results["auto_exposure"]["can_disable"] = True
                print("  ✓ Auto Exposure can be toggled (using 1)")
    else:
        print("  ✗ Auto Exposure not readable (returned 0)")
    
    print()
    
    # 2. Check Manual Exposure Support
    # Windows: Usually 0 to -13 (logarithmic scale)
    print("[2] Exposure Value (CAP_PROP_EXPOSURE)")
    print("-" * 40)
    
    exp_val = cap.get(cv2.CAP_PROP_EXPOSURE)
    print(f"  Current Value: {exp_val}")
    results["exposure"]["current"] = exp_val
    
    if exp_val != 0 or results["auto_exposure"]["can_disable"]:
        results["exposure"]["supported"] = True
        
        # Test range by setting extreme values
        print("  Testing value range...")
        
        # Try setting to dark (short exposure)
        cap.set(cv2.CAP_PROP_EXPOSURE, -10)
        dark_val = cap.get(cv2.CAP_PROP_EXPOSURE)
        print(f"  After set -10: {dark_val}")
        
        # Try setting to bright (long exposure)
        cap.set(cv2.CAP_PROP_EXPOSURE, -3)
        bright_val = cap.get(cv2.CAP_PROP_EXPOSURE)
        print(f"  After set -3: {bright_val}")
        
        # Estimate range
        if dark_val != bright_val:
            results["exposure"]["min"] = -13
            results["exposure"]["max"] = 0
            print(f"  ✓ Exposure control working (estimated range: -13 to 0)")
        else:
            print("  △ Exposure readable but may not be controllable")
    else:
        print("  ✗ Exposure not readable")
    
    print()
    
    # 3. Check Gain Support
    print("[3] Gain (CAP_PROP_GAIN)")
    print("-" * 40)
    
    gain_val = cap.get(cv2.CAP_PROP_GAIN)
    print(f"  Current Value: {gain_val}")
    results["gain"]["current"] = gain_val
    
    if gain_val > 0 or gain_val == -1:
        # Try changing gain
        cap.set(cv2.CAP_PROP_GAIN, 50)
        new_gain = cap.get(cv2.CAP_PROP_GAIN)
        if new_gain != gain_val:
            results["gain"]["supported"] = True
            print(f"  ✓ Gain control supported (changed to {new_gain})")
        else:
            print("  ✗ Gain readable but not controllable")
    else:
        print("  ✗ Gain not supported")
    
    print()
    
    # 4. Check Brightness Support
    print("[4] Brightness (CAP_PROP_BRIGHTNESS)")
    print("-" * 40)
    
    brightness_val = cap.get(cv2.CAP_PROP_BRIGHTNESS)
    print(f"  Current Value: {brightness_val}")
    results["brightness"]["current"] = brightness_val
    
    if brightness_val >= 0:
        cap.set(cv2.CAP_PROP_BRIGHTNESS, 128)
        new_brightness = cap.get(cv2.CAP_PROP_BRIGHTNESS)
        if new_brightness == 128:
            results["brightness"]["supported"] = True
            print(f"  ✓ Brightness control supported")
        else:
            print(f"  △ Brightness readable but set to {new_brightness}")
    else:
        print("  ✗ Brightness not supported")
    
    print()
    
    # Summary
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Auto Exposure: {'✓ Supported' if results['auto_exposure']['supported'] else '✗ Not Supported'}")
    print(f"  Manual Exposure: {'✓ Supported' if results['exposure']['supported'] else '✗ Not Supported'}")
    print(f"  Gain: {'✓ Supported' if results['gain']['supported'] else '✗ Not Supported'}")
    print(f"  Brightness: {'✓ Supported' if results['brightness']['supported'] else '✗ Not Supported'}")
    print()
    
    cap.release()
    return results

if __name__ == "__main__":
    all_results = []
    
    for i in range(4):
        result = check_exposure_capabilities(i)
        if result:
            all_results.append(result)
    
    if not all_results:
        print("\nNo cameras found!")
    else:
        print("\n" + "=" * 60)
        print("  FINAL RECOMMENDATION")
        print("=" * 60)
        
        # Check if any camera supports exposure control
        any_exposure = any(r["exposure"]["supported"] for r in all_results)
        any_auto_exp = any(r["auto_exposure"]["can_disable"] for r in all_results)
        
        if any_exposure and any_auto_exp:
            print("  ✓ Manual exposure control can be implemented")
            print("  Recommended: Use CAP_PROP_AUTO_EXPOSURE + CAP_PROP_EXPOSURE")
        elif any_exposure:
            print("  △ Exposure readable but auto-exposure toggle may not work")
            print("  Try: Direct CAP_PROP_EXPOSURE manipulation")
        else:
            print("  ✗ Exposure control not available on detected cameras")
            print("  Alternative: Use CAP_PROP_BRIGHTNESS if supported")
