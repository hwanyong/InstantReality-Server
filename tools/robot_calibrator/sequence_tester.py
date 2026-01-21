"""
Robot Arm Direction Verifier (Sequence Tester)
Tests each joint's movement direction to verify servo_config.json settings.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial.tools.list_ports
import threading
import time
import json
from datetime import datetime

from serial_driver import SerialDriver
from servo_manager import ServoManager


class SequenceTester:
    """
    GUI application for testing robot arm joint directions.
    Supports both manual (single joint) and auto (all joints) test modes.
    """

    # Direction expectations based on type and min_pos
    DIRECTION_MAP = {
        "vertical": {
            "bottom": ("UP", "DOWN"),      # +angle = up, -angle = down
            "top": ("DOWN", "UP")          # +angle = down, -angle = up
        },
        "horizontal": {
            "left": ("RIGHT", "LEFT"),     # +angle = right, -angle = left
            "right": ("LEFT", "RIGHT")     # +angle = left, -angle = right
        },
        "roll": {
            "ccw": ("CW", "CCW"),          # +angle = clockwise
            "cw": ("CCW", "CW")            # +angle = counter-clockwise
        },
        "gripper": {
            "open": ("CLOSE", "OPEN"),     # +angle = close
            "close": ("OPEN", "CLOSE")     # +angle = open
        }
    }

    # Korean translations for directions
    DIRECTION_KO = {
        "UP": "위로",
        "DOWN": "아래로",
        "LEFT": "왼쪽으로",
        "RIGHT": "오른쪽으로",
        "CW": "시계방향으로",
        "CCW": "반시계방향으로",
        "OPEN": "열림",
        "CLOSE": "닫힘"
    }

    # Joint role guesses based on slot number
    JOINT_ROLES = {
        1: "Base/Shoulder Yaw",
        2: "Shoulder Pitch",
        3: "Elbow Pitch",
        4: "Wrist Yaw",
        5: "Wrist Roll",
        6: "Gripper"
    }

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Robot Arm Direction Verifier")
        self.root.geometry("900x700")
        self.root.configure(bg="#2b2b2b")

        # Initialize components
        self.driver = SerialDriver()
        self.manager = ServoManager()

        # State variables
        self.is_connected = False
        self.test_running = False
        self.test_results = []

        # UI variables
        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Disconnected")
        self.action_var = tk.StringVar(value="Ready")

        # Build UI
        self._create_styles()
        self._create_connection_panel()
        self._create_main_area()
        self._create_control_panel()
        self._create_log_panel()

        # Load saved port
        saved_port = self.manager.get_saved_port()
        if saved_port:
            self.port_var.set(saved_port)

        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_styles(self):
        """Create custom styles for widgets."""
        style = ttk.Style()
        style.theme_use('clam')

        # Configure colors (dark theme)
        style.configure("TFrame", background="#2b2b2b")
        style.configure("TLabel", background="#2b2b2b", foreground="#ffffff")
        style.configure("TButton", padding=5)
        style.configure("TNotebook", background="#2b2b2b")
        style.configure("TNotebook.Tab", background="#3c3c3c", foreground="#ffffff", padding=[10, 5])
        style.map("TNotebook.Tab", background=[("selected", "#4a4a4a")])
        style.configure("Header.TLabel", font=("Arial", 14, "bold"))
        style.configure("Action.TLabel", font=("Arial", 18, "bold"), foreground="#00ff00")
        style.configure("Status.TLabel", font=("Arial", 10))

    def _create_connection_panel(self):
        """Create the connection status panel."""
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.X)

        # Status indicator
        self.status_canvas = tk.Canvas(frame, width=20, height=20, bg="#2b2b2b", highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.status_indicator = self.status_canvas.create_oval(2, 2, 18, 18, fill="#ff4444")

        # Status label
        ttk.Label(frame, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.LEFT)

        # Connect button
        self.connect_btn = ttk.Button(frame, text="Connect", command=self._on_connect)
        self.connect_btn.pack(side=tk.RIGHT, padx=5)

        # Port dropdown
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, width=15)
        self.port_combo.pack(side=tk.RIGHT, padx=5)
        self._refresh_ports()

        # Refresh ports button
        ttk.Button(frame, text="⟳", width=3, command=self._refresh_ports).pack(side=tk.RIGHT)

    def _create_main_area(self):
        """Create the main notebook area with arm tabs."""
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left Arm Tab
        left_frame = ttk.Frame(notebook, padding=10)
        notebook.add(left_frame, text="Left Arm (왼팔)")
        self._create_joint_list(left_frame, "left_arm")

        # Right Arm Tab
        right_frame = ttk.Frame(notebook, padding=10)
        notebook.add(right_frame, text="Right Arm (오른팔)")
        self._create_joint_list(right_frame, "right_arm")

    def _create_joint_list(self, parent, arm_key):
        """Create joint list for one arm."""
        for slot in range(1, 7):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=5)

            # Get config info
            joint_type = self.manager.get_type(arm_key, slot)
            min_pos = self.manager.get_min_pos(arm_key, slot)
            role = self.JOINT_ROLES.get(slot, "Unknown")

            # Joint label
            label_text = f"Slot {slot} ({joint_type}) - {role}"
            ttk.Label(row, text=label_text, width=35).pack(side=tk.LEFT)

            # Min pos indicator (use StringVar for dynamic updates)
            min_pos_var = tk.StringVar(value=f"[{min_pos}]")
            ttk.Label(row, textvariable=min_pos_var, width=8).pack(side=tk.LEFT, padx=5)
            setattr(self, f"min_pos_label_{arm_key}_{slot}", min_pos_var)

            # Test button
            ttk.Button(
                row, text="Test 🔬",
                command=lambda a=arm_key, s=slot: self._test_single_joint(a, s)
            ).pack(side=tk.LEFT, padx=10)

            # Result label (will be updated after test)
            result_var = tk.StringVar(value="—")
            result_label = ttk.Label(row, textvariable=result_var, width=10)
            result_label.pack(side=tk.LEFT)

            # Store reference for updating
            setattr(self, f"result_{arm_key}_{slot}", result_var)

    def _create_control_panel(self):
        """Create the control panel with action display and buttons."""
        frame = ttk.LabelFrame(self.root, text="Test Control", padding=10)
        frame.pack(fill=tk.X, padx=10, pady=5)

        # Action display (large text)
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill=tk.X, pady=10)

        ttk.Label(action_frame, text="Current Action:", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(action_frame, textvariable=self.action_var, style="Action.TLabel").pack(side=tk.LEFT, padx=20)

        # Control buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="▶ Test All Joints (Auto)", command=self._test_all_joints).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📄 Export Results", command=self._export_results).pack(side=tk.LEFT, padx=5)

        # E-STOP (prominent)
        estop_btn = tk.Button(
            btn_frame, text="E-STOP", bg="#ff4444", fg="white",
            font=("Arial", 12, "bold"), width=10,
            command=self._on_estop
        )
        estop_btn.pack(side=tk.RIGHT, padx=5)

    def _create_log_panel(self):
        """Create the result log panel."""
        frame = ttk.LabelFrame(self.root, text="Test Log", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Scrollable text area
        self.log_text = tk.Text(frame, height=8, bg="#1e1e1e", fg="#ffffff", font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def _refresh_ports(self):
        """Refresh available COM ports."""
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def _on_connect(self):
        """Handle connect/disconnect button click."""
        if self.is_connected:
            self.driver.disconnect()
            self.is_connected = False
            self.status_var.set("Disconnected")
            self.status_canvas.itemconfig(self.status_indicator, fill="#ff4444")
            self.connect_btn.config(text="Connect")
        else:
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "Please select a COM port")
                return

            self.status_var.set("Connecting...")
            self.root.update()

            if self.driver.connect(port):
                self.is_connected = True
                self.status_var.set(f"Connected: {port}")
                self.status_canvas.itemconfig(self.status_indicator, fill="#44ff44")
                self.connect_btn.config(text="Disconnect")
                self.manager.set_saved_port(port)
                self._log("Connected to " + port)
            else:
                self.status_var.set("Connection Failed")
                messagebox.showerror("Error", f"Failed to connect to {port}")

    def _log(self, message):
        """Add message to log panel."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

    def _get_expected_direction(self, joint_type, min_pos, positive=True):
        """Get expected movement direction based on config."""
        type_map = self.DIRECTION_MAP.get(joint_type, self.DIRECTION_MAP["vertical"])
        pos_map = type_map.get(min_pos, type_map.get("bottom", ("UP", "DOWN")))
        return pos_map[0] if positive else pos_map[1]

    def _test_single_joint(self, arm, slot):
        """Test a single joint's direction."""
        if not self.is_connected:
            messagebox.showwarning("Warning", "Not connected to hardware")
            return

        if self.test_running:
            messagebox.showwarning("Warning", "A test is already running")
            return

        # Run test in thread
        threading.Thread(target=self._run_joint_test, args=(arm, slot), daemon=True).start()

    def _run_joint_test(self, arm, slot):
        """Execute the joint test sequence."""
        self.test_running = True

        try:
            channel = self.manager.get_channel(arm, slot)
            joint_type = self.manager.get_type(arm, slot)
            min_pos = self.manager.get_min_pos(arm, slot)
            initial = self.manager.get_initial(arm, slot)
            limits = self.manager.get_limits(arm, slot)

            expected_dir = self._get_expected_direction(joint_type, min_pos, positive=True)
            expected_ko = self.DIRECTION_KO.get(expected_dir, expected_dir)

            # Step 1: Move to initial position
            initial_pulse = self.manager.get_initial_pulse(arm, slot)
            self.action_var.set(f"Moving to Home ({initial_pulse}µs)...")
            self._log(f"Testing {arm} Slot {slot}: Moving to initial position {initial_pulse}µs")
            self.driver.write_pulse(channel, initial_pulse)
            time.sleep(1)

            # Step 2: Smart direction probing - check available headroom
            delta = 150 # approx 15 degrees
            
            # Fetch pulse limits
            slot_key = f"slot_{slot}"
            slot_config = self.manager.config.get(arm, {}).get(slot_key, {})
            limit_min = slot_config.get("min_pulse", 500)
            limit_max = slot_config.get("max_pulse_limit", 2500)
            
            positive_headroom = limit_max - initial_pulse
            negative_headroom = initial_pulse - limit_min
            
            if positive_headroom >= delta:
                # Normal case: can move in positive direction
                test_pulse = initial_pulse + delta
                move_positive = True
            elif negative_headroom >= delta:
                # Blocked at max: move in negative direction instead
                test_pulse = initial_pulse - delta
                move_positive = False
                # Invert expected direction
                expected_dir = self._get_expected_direction(joint_type, min_pos, positive=False)
                expected_ko = self.DIRECTION_KO.get(expected_dir, expected_dir)
                self._log(f"Note: Initial at max, testing negative direction instead")
            else:
                # Both directions blocked (very small range) - Try anyway or limit?
                self._log(f"⚠ Warning: Joint has very small pulse range ({limit_min}-{limit_max}), testing with reduced delta")
                if positive_headroom > negative_headroom:
                    test_pulse = limit_max
                    move_positive = True
                else:
                    test_pulse = limit_min
                    move_positive = False
                    expected_dir = self._get_expected_direction(joint_type, min_pos, positive=False)
                    expected_ko = self.DIRECTION_KO.get(expected_dir, expected_dir)
            
            self.action_var.set(f"Moving {expected_dir} ({expected_ko})...")
            self._log(f"Moving to {test_pulse}µs (Expected: {expected_dir})")
            self.driver.write_pulse(channel, test_pulse)
            time.sleep(1.5)

            # Step 3: Return to initial
            self.driver.write_pulse(channel, initial_pulse)

            # Step 4: Ask user
            self.action_var.set("Waiting for feedback...")
            result = messagebox.askyesno(
                "Direction Check",
                f"Did the joint move {expected_dir} ({expected_ko})?\n\n"
                f"관절이 {expected_ko} 방향으로 움직였나요?"
            )

            # Record result
            result_var = getattr(self, f"result_{arm}_{slot}", None)
            if result:
                if result_var:
                    result_var.set("✓ PASS")
                self._log(f"✓ {arm} Slot {slot}: PASS")
                self.test_results.append({
                    "arm": arm,
                    "slot": slot,
                    "expected": expected_dir,
                    "result": "PASS"
                })
            else:
                if result_var:
                    result_var.set("✗ FAIL")
                # Suggest fix
                opposite_pos = self._get_opposite_min_pos(min_pos)
                suggestion = f"Consider changing min_pos from '{min_pos}' to '{opposite_pos}'"
                self._log(f"✗ {arm} Slot {slot}: FAIL - {suggestion}")
                self.test_results.append({
                    "arm": arm,
                    "slot": slot,
                    "expected": expected_dir,
                    "result": "FAIL",
                    "suggestion": suggestion
                })
                
                # Ask user if they want to auto-fix
                fix_result = messagebox.askyesnocancel(
                    "Direction Inverted",
                    f"The direction seems inverted.\n\n"
                    f"Do you want to AUTO-FIX?\n"
                    f"(Change `min_pos` from '{min_pos}' to '{opposite_pos}')\n\n"
                    f"방향이 반대인 것 같습니다. 자동 수정하시겠습니까?\n"
                    f"(`min_pos`를 '{min_pos}'에서 '{opposite_pos}'로 변경)"
                )
                
                if fix_result is True:
                    # Apply fix
                    self._apply_fix(arm, slot, opposite_pos)
                elif fix_result is False:
                    self._log(f"User skipped fix for {arm} Slot {slot}")
                # Cancel = do nothing

            self.action_var.set("Ready")

        except Exception as e:
            self._log(f"Error: {e}")
            self.action_var.set("Error")
        finally:
            self.test_running = False

    def _get_opposite_min_pos(self, min_pos):
        """Get the opposite min_pos value."""
        opposites = {
            "top": "bottom", "bottom": "top",
            "left": "right", "right": "left",
            "cw": "ccw", "ccw": "cw",
            "open": "close", "close": "open"
        }
        return opposites.get(min_pos, min_pos)

    def _apply_fix(self, arm, slot, new_min_pos):
        """Apply the fix to servo_config.json and update UI."""
        old_min_pos = self.manager.get_min_pos(arm, slot)
        
        # Update config
        self.manager.set_min_pos(arm, slot, new_min_pos)
        
        # Save to file
        if self.manager.save_config():
            self._log(f"✓ FIXED: {arm} Slot {slot}: min_pos '{old_min_pos}' → '{new_min_pos}'")
            
            # Update UI label if exists
            label_var = getattr(self, f"min_pos_label_{arm}_{slot}", None)
            if label_var:
                label_var.set(f"[{new_min_pos}]")
            
            # Update result to show it was fixed
            result_var = getattr(self, f"result_{arm}_{slot}", None)
            if result_var:
                result_var.set("⚡ FIXED")
            
            messagebox.showinfo(
                "Fixed",
                f"Config updated successfully!\n설정이 성공적으로 업데이트되었습니다!\n\n"
                f"min_pos: '{old_min_pos}' → '{new_min_pos}'"
            )
        else:
            self._log(f"✗ Failed to save config for {arm} Slot {slot}")
            messagebox.showerror("Error", "Failed to save config\n설정 저장 실패")

    def _test_all_joints(self):
        """Test all joints sequentially."""
        if not self.is_connected:
            messagebox.showwarning("Warning", "Not connected to hardware")
            return

        if self.test_running:
            messagebox.showwarning("Warning", "A test is already running")
            return

        # Confirm with user
        if not messagebox.askyesno("Auto Test", "This will test all 12 joints sequentially.\nContinue?"):
            return

        # Run in thread
        threading.Thread(target=self._run_all_tests, daemon=True).start()

    def _run_all_tests(self):
        """Execute auto test for all joints."""
        self.test_running = True
        self._log("=== Starting Auto Test ===")

        try:
            for arm in ["left_arm", "right_arm"]:
                for slot in range(1, 7):
                    self._log(f"--- Testing {arm} Slot {slot} ---")
                    self._run_joint_test(arm, slot)
                    time.sleep(0.5)  # Brief pause between joints

            self._log("=== Auto Test Complete ===")
            messagebox.showinfo("Complete", "All joints have been tested!\n모든 관절 테스트가 완료되었습니다!")

        except Exception as e:
            self._log(f"Auto test error: {e}")
        finally:
            self.test_running = False

    def _export_results(self):
        """Export test results to JSON file."""
        if not self.test_results:
            messagebox.showinfo("Info", "No test results to export")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_results_{timestamp}.json"

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": timestamp,
                    "results": self.test_results
                }, f, indent=2, ensure_ascii=False)

            self._log(f"Results exported to {filename}")
            messagebox.showinfo("Export", f"Results saved to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

    def _on_estop(self):
        """Emergency stop - release all servos."""
        if self.is_connected:
            self.driver.release_all()
        self.test_running = False
        self.action_var.set("E-STOP ACTIVATED")
        self._log("!!! E-STOP ACTIVATED !!!")
        messagebox.showinfo("E-STOP", "All servos released\n모든 서보가 해제되었습니다")

    def _on_close(self):
        """Handle window close event."""
        self.test_running = False
        if self.is_connected:
            self.driver.release_all()
            self.driver.disconnect()
        self.root.destroy()

    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()


if __name__ == "__main__":
    app = SequenceTester()
    app.run()
