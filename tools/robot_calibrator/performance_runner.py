"""
Robot Performance Runner (Victory Dance)
Executes a synchronized choreography to demonstrate perfect robot setup.
Features: Keyframe animation, Smooth interpolation (Easing), Safety checks.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial.tools.list_ports
import threading
import time
import math
from datetime import datetime

from serial_driver import SerialDriver
from servo_manager import ServoManager
from pulse_mapper import PulseMapper

class AnimationEngine:
    """
    Handles smooth transition between keyframes.
    """
    def __init__(self, driver, manager, mapper):
        self.driver = driver
        self.manager = manager
        self.mapper = mapper
        self.running = False
        self.paused = False
        
        # Current state of all servos {channel: angle}
        self.current_state = {}
        self._init_state()

    def _init_state(self):
        """Initialize state with 'initial' positions from config."""
        for arm in ["left_arm", "right_arm"]:
            for slot in range(1, 7):
                channel = self.manager.get_channel(arm, slot)
                initial_pulse = self.manager.get_initial_pulse(arm, slot)
                self.current_state[channel] = initial_pulse

    def stop(self):
        """Stop animation."""
        self.running = False

    def ease_in_out_sine(self, x):
        """Sine easing function (0.0 to 1.0)."""
        return -(math.cos(math.pi * x) - 1) / 2

    def move_to(self, target_keyframe, duration_sec=1.0, steps=30):
        """
        Smoothly move to target keyframe.
        target_keyframe: { (arm, slot): target_angle }
        """
        if not self.running: return

        # Identify changes
        start_positions = {}
        changes = {}
        
        valid_targets = {}
        
        # Pre-validate and calculating deltas
        for (arm, slot), target_angle in target_keyframe.items():
            channel = self.manager.get_channel(arm, slot)
            start_pulse = self.current_state.get(channel, 1500)
            
            # Convert Target Angle -> Target Pulse
            slot_key = f"slot_{slot}"
            motor_config = self.manager.config.get(arm, {}).get(slot_key, {})
            target_pulse = self.mapper.physical_to_pulse(target_angle, motor_config)
            
            # Clamp target to pulse limits
            min_pulse = motor_config.get("min_pulse", 500)
            max_pulse_limit = motor_config.get("max_pulse_limit", 2500)
            clamped_target = max(min_pulse, min(max_pulse_limit, target_pulse))
            
            start_positions[channel] = start_pulse
            changes[channel] = clamped_target - start_pulse
            valid_targets[channel] = clamped_target

        # Animation Loop
        start_time = time.time()
        while self.running:
            elapsed = time.time() - start_time
            if elapsed >= duration_sec:
                break
            
            progress = min(1.0, elapsed / duration_sec)
            eased_progress = self.ease_in_out_sine(progress)
            
            for channel, delta in changes.items():
                start_pulse = start_positions[channel]
                current_pulse = int(start_pulse + (delta * eased_progress))
                self.driver.write_pulse(channel, current_pulse)
                self.current_state[channel] = current_pulse # Update state tracker
            
            time.sleep(1.0 / steps)

        # Ensure final position is exact
        if self.running:
            for channel, target_pulse in valid_targets.items():
                self.driver.write_pulse(channel, int(target_pulse))
                self.current_state[channel] = target_pulse

class PerformanceRunner:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Robot Performance Runner (Victory Dance)")
        self.root.geometry("600x500")
        self.root.configure(bg="#2b2b2b")
        
        self.driver = SerialDriver()
        self.manager = ServoManager()
        self.mapper = PulseMapper()
        self.engine = AnimationEngine(self.driver, self.manager, self.mapper)
        
        self.is_connected = False
        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Disconnected")
        self.current_move_var = tk.StringVar(value="Ready")
        
        self._build_ui()
        self._check_saved_port()

    def _build_ui(self):
        self._create_styles()
        
        # Main Container
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Connection Panel
        conn_frame = ttk.LabelFrame(main_frame, text="Connection", padding=10)
        conn_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Combobox(conn_frame, textvariable=self.port_var, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(conn_frame, text="Connect", command=self._toggle_connect).pack(side=tk.LEFT, padx=5)
        ttk.Label(conn_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=10)

        # Performance Control Panel
        perf_frame = ttk.LabelFrame(main_frame, text="The Victory Dance", padding=20)
        perf_frame.pack(fill=tk.BOTH, expand=True)
        
        # Status Display
        ttk.Label(perf_frame, textvariable=self.current_move_var, style="Big.TLabel", anchor="center").pack(pady=20)
        
        # Play Button
        self.play_btn = tk.Button(
            perf_frame, text="▶ START PERFORMANCE", 
            command=self._start_performance,
            font=("Arial", 16, "bold"), bg="#4caf50", fg="white",
            height=2, state="disabled"
        )
        self.play_btn.pack(fill=tk.X, pady=10)
        
        # Reset Button
        tk.Button(
            perf_frame, text="⏮ RESET TO HOME", 
            command=self._reset_home,
            font=("Arial", 12), bg="#2196f3", fg="white"
        ).pack(fill=tk.X, pady=5)
        
        # E-STOP
        tk.Button(
            perf_frame, text="⚠ E-STOP", 
            command=self._estop,
            font=("Arial", 12, "bold"), bg="#f44336", fg="white"
        ).pack(fill=tk.X, pady=(20, 0))

    def _create_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#2b2b2b")
        style.configure("TLabel", background="#2b2b2b", foreground="#ffffff")
        style.configure("Big.TLabel", font=("Arial", 24, "bold"), foreground="#00e676")
        style.configure("TLabelframe", background="#2b2b2b", foreground="#ffffff")
        style.configure("TLabelframe.Label", background="#2b2b2b", foreground="#ffffff")

    def _check_saved_port(self):
        try:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            if ports: self.port_var.set(ports[0])
            
            saved = self.manager.get_saved_port()
            if saved in ports: self.port_var.set(saved)
        except: pass

    def _toggle_connect(self):
        if not self.is_connected:
            port = self.port_var.get()
            if self.driver.connect(port):
                self.is_connected = True
                self.status_var.set(f"Connected: {port}")
                self.play_btn.config(state="normal", bg="#4caf50")
            else:
                self.status_var.set("Connection Failed")
        else:
            self.driver.disconnect()
            self.is_connected = False
            self.status_var.set("Disconnected")
            self.play_btn.config(state="disabled", bg="#555")

    def _start_performance(self):
        if not self.is_connected: return
        threading.Thread(target=self._run_choreography, daemon=True).start()

    def _run_choreography(self):
        self.engine.running = True
        self.play_btn.config(state="disabled")
        
        try:
            # 1. Awake
            self.current_move_var.set("Phase 1: The Awakening 🌅")
            self._pose_wake_up()
            time.sleep(1.0)
            
            # 2. Wings
            self.current_move_var.set("Phase 2: The Wings 🦅")
            self._pose_wings()
            time.sleep(1.0)
            
            # 3. Twist
            self.current_move_var.set("Phase 3: The Twist 🌪️")
            self._pose_twist()
            time.sleep(1.0)
            
            # 4. Reach
            self.current_move_var.set("Phase 4: The Reach 🔭")
            self._pose_reach()
            time.sleep(1.0)
            
            # 5. Grasp
            self.current_move_var.set("Phase 5: The Grasp ✊")
            self._pose_grasp()
            time.sleep(1.0)
            
            # 6. Cross
            self.current_move_var.set("Phase 6: The Cross ⚔️")
            self._pose_cross()
            time.sleep(1.5)
            
            # 7. Bow
            self.current_move_var.set("Phase 7: The Bow 🙇")
            self._pose_bow()
            time.sleep(2.0)
            
            self.current_move_var.set("✨ SYMPHONY COMPLETE ✨")
            
        except Exception as e:
            self.current_move_var.set(f"Error: {e}")
            print(f"Animation Error: {e}")
        finally:
            self.engine.running = False
            self.play_btn.config(state="normal")
            
    # --- Choreography Poses ---
    
    def _pose_wake_up(self):
        """Phase 1: Slow rise to Home position"""
        home_frame = {}
        for arm in ["left_arm", "right_arm"]:
            for slot in range(1, 7):
                home_frame[(arm, slot)] = self.manager.get_initial(arm, slot)
        # Slow ease-in
        self.engine.move_to(home_frame, duration_sec=3.0)

    def _pose_wings(self):
        """Phase 2: T-Pose then Up"""
        # T-Pose (Approx 90 deg for Shoulder Pitch)
        t_frame = {
            ("left_arm", 2): 90, ("left_arm", 3): 90,  # Extend Left
            ("right_arm", 2): 90, ("right_arm", 3): 90 # Extend Right
        }
        self.engine.move_to(t_frame, duration_sec=2.0)
        
        # Raise Arms (Shoulder Pitch to Min/Max)
        # Note: Check config for "Up" direction. Usually smaller angle for servo?
        # Let's try lifting 30 degrees more from T-Pose
        up_frame = {
            ("left_arm", 2): 60,   # Up?
            ("right_arm", 2): 60
        }
        self.engine.move_to(up_frame, duration_sec=1.5)
        
        # Return to T-Pose
        self.engine.move_to(t_frame, duration_sec=1.5)

    def _pose_twist(self):
        """Phase 3: Wrist Rotate (Slot 5)"""
        # Roll CW
        cw_frame = {
            ("left_arm", 5): 10,
            ("right_arm", 5): 10
        }
        self.engine.move_to(cw_frame, duration_sec=1.0)
        
        # Roll CCW
        ccw_frame = {
            ("left_arm", 5): 140,
            ("right_arm", 5): 140
        }
        self.engine.move_to(ccw_frame, duration_sec=1.0)
        
        # Center
        center_frame = {
            ("left_arm", 5): 75,
            ("right_arm", 5): 75
        }
        self.engine.move_to(center_frame, duration_sec=0.5)

    def _pose_reach(self):
        """Phase 4: Elbow Pitch (Slot 3) Extend/Contract"""
        # Extend Elbows (0 degrees usually straight?)
        # Checking limits: Left Slot 3 min 0, max 142.
        straight_frame = {
            ("left_arm", 3): 10,
            ("right_arm", 3): 10
        }
        self.engine.move_to(straight_frame, duration_sec=1.5)
        
        # Contract Elbows
        bent_frame = {
            ("left_arm", 3): 100,
            ("right_arm", 3): 100
        }
        self.engine.move_to(bent_frame, duration_sec=1.0)

    def _pose_grasp(self):
        """Phase 5: Gripper (Slot 6) Pulse"""
        # Forward arms first
        forward_frame = {
             ("left_arm", 2): 90, ("left_arm", 3): 45,
             ("right_arm", 2): 90, ("right_arm", 3): 45
        }
        self.engine.move_to(forward_frame, duration_sec=1.0)
        
        # Fast Open/Close
        for target in [10, 80, 10, 80]: # Check limits: Left max 35?
            # Safe clamping is handled by engine, so we send ideal targets
            frame = {
                ("left_arm", 6): target,
                ("right_arm", 6): target
            }
            self.engine.move_to(frame, duration_sec=0.2)

    def _pose_cross(self):
        """Phase 6: Multi-Axis Crossing"""
        # Left Up-Right, Right Down-Left
        cross_frame = {
            # Left Arm: Shoulder Yaw Right (0?), Pitch Up (60)
            ("left_arm", 1): 10, # Right
            ("left_arm", 2): 60, # Up
            
            # Right Arm: Shoulder Yaw Left (180?), Pitch Down (120)
            ("right_arm", 1): 170, # Left
            ("right_arm", 2): 120  # Down
        }
        self.engine.move_to(cross_frame, duration_sec=2.0)
        
        # Switch!
        uncross_frame = {
            # Left Arm: Shoulder Yaw Left (140?), Pitch Down
            ("left_arm", 1): 140, 
            ("left_arm", 2): 120,
            
            # Right Arm: Shoulder Yaw Right (10?), Pitch Up
            ("right_arm", 1): 10, 
            ("right_arm", 2): 60
        }
        self.engine.move_to(uncross_frame, duration_sec=2.0)
        
        # Return Center
        center_frame = {
            ("left_arm", 1): 57,
            ("right_arm", 1): 131
        }
        self.engine.move_to(center_frame, duration_sec=1.0)

    def _pose_bow(self):
        """Phase 7: Graceful Shutdown"""
        frame = {
             # Arms down/in
            ("left_arm", 2): 145, ("left_arm", 3): 145,
            ("right_arm", 2): 145, ("right_arm", 3): 145
        }
        self.engine.move_to(frame, duration_sec=3.0)

    def _reset_home(self):
        if not self.is_connected: return
        self.engine.running = True
        self._pose_wake_up()
        self.engine.running = False

    def _estop(self):
        self.engine.stop()
        if self.is_connected:
            self.driver.release_all()
        self.current_move_var.set("⚠ E-STOP ACTIVATED")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = PerformanceRunner()
    app.run()
