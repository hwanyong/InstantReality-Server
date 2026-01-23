
"""
Wrapper/Entry point for the Modular IK Tester GUI.
Redirects to ik_tester.app.IKTesterApp.
"""
import sys
import os

# Ensure the current directory is in sys.path so we can import 'ik_tester' package
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from ik_tester.app import IKTesterApp
except ImportError as e:
    print("Failed to import IKTesterApp.")
    print(f"Error: {e}")
    print("Ensure 'ik_tester' package directory exists and has __init__.py")
    sys.exit(1)

if __name__ == "__main__":
    app = IKTesterApp()
    app.run()
