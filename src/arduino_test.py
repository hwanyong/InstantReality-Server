import serial
import serial.tools.list_ports
import time
import sys
from config_manager import ConfigManager

def list_ports():
    ports = serial.tools.list_ports.comports()
    print("Available ports:")
    result = []
    for port, desc, hwid in ports:
        print(f" - {port}: {desc} [{hwid}]")
        result.append({'port': port, 'desc': desc, 'hwid': hwid})
    if not ports:
        print(" - No ports found")
    print("-" * 30)
    return result

def try_connect(port):
    print(f"Attempting to connect to: {port}")
    try:
        ser = serial.Serial(port, 9600, timeout=1)
        time.sleep(2) # Wait for Arduino reset
        if ser.is_open:
            print(f"Successfully connected to {port} @ 9600bps")
            return ser
    except serial.SerialException as e:
        print(f"Failed to connect to {port}: {e}")
    return None

def main():
    print("Arduino Serial Tester (with Auto-Discovery)")
    
    config = ConfigManager()
    saved_port = config.get("arduino_port")
    
    ser = None
    
    # 1. Try saved port first
    if saved_port:
        print(f"Found saved port in config: {saved_port}")
        ser = try_connect(saved_port)
    
    # 2. If failed (or no saved port), discover and try others
    if ser is None:
        print("Scanning for Arduino...")
        available_ports = list_ports()
        
        # Priority: Ports with "Arduino" in description
        candidates = [p['port'] for p in available_ports if "Arduino" in p['desc']]
        # Remaining ports
        others = [p['port'] for p in available_ports if "Arduino" not in p['desc']]
        
        all_candidates = candidates + others
        
        for port in all_candidates:
            ser = try_connect(port)
            if ser:
                # 3. Save successful port
                print(f"Saving new port {port} to config.json")
                config.set("arduino_port", port)
                break
                
    if ser is None:
        print("Error: Could not connect to any Arduino.")
        return

    print("Listening for data... (Press Ctrl+C to exit)")
    try:
        while True:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        print(f"[RX] {line}")
                except UnicodeDecodeError:
                    print(f"[RX-Error] Decode failed")
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting...")
        ser.close()
    except Exception as e:
        print(f"\nRuntime Error: {e}")
        if ser and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
