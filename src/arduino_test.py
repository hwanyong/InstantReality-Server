import serial
import serial.tools.list_ports
import time
import sys

def list_ports():
    ports = serial.tools.list_ports.comports()
    print("Available ports:")
    result = []
    for port, desc, hwid in ports:
        print(f" - {port}: {desc} [{hwid}]")
        result.append(port)
    if not ports:
        print(" - No ports found")
    print("-" * 30)
    return result

def main():
    print("Arduino Serial Tester")
    available_ports = list_ports()
    
    # Simple default or selection logic could go here.
    # For this test script, we will try to use the first available port or COM3 if nothing found (as a fallback guess).
    target_port = "COM3"
    if available_ports:
        # Heuristic: try to find 'Arduino' in description? For now, just pick the last one as it's often the plugged device.
        # But safer to just ask or default.
        # Let's use the first one for now.
        target_port = available_ports[0]

    if len(sys.argv) > 1:
        target_port = sys.argv[1]
    
    print(f"Attempting to connect to: {target_port}")
    print("Press Ctrl+C to exit.")

    try:
        ser = serial.Serial(target_port, 9600, timeout=1)
        time.sleep(2) # Wait for connection to settle (Arduino reset)
        print(f"Successfully connected to {target_port} @ 9600bps")
        
        while True:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        print(f"[RX] {line}")
                except UnicodeDecodeError:
                    print(f"[RX-Error] Decode failed")
            time.sleep(0.01)

    except serial.SerialException as e:
        print(f"Error: Could not open port {target_port}.")
        print(f"Details: {e}")
        print("\nTip: Usage: python src/arduino_test.py [COM_PORT]")
    except KeyboardInterrupt:
        print("\nExiting...")
        if 'ser' in locals() and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
