"""
Robot Calibration GUI
Tkinter-based GUI for servo calibration and hardware diagnostics.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial.tools.list_ports
import threading
import math
import time
import shutil
import os

from serial_driver import SerialDriver as PCA9685Driver
from servo_manager import ServoManager
from motion_planner import MotionPlanner
from pulse_mapper import PulseMapper


# ============ Constants ============
# Hardware
NUM_SLOTS = 6                    # Servo slots per arm
NUM_CHANNELS = 16                # PCA9685 channel count
ARM_NAMES = ["left_arm", "right_arm"]

# UI Theme
THEME = {
    "bg": "#2b2b2b",
    "fg": "#ffffff",
    "success": "#44ff44",
    "error": "#ff4444",
    "warning": "#ffaa00"
}

# Thread Timing (seconds)
SENDER_LOOP_INTERVAL = 0.033     # ~30Hz
SENDER_CMD_DELAY = 0.002         # Delay between commands
SINE_TEST_INTERVAL = 0.05        # Sine wave update interval


class ServoState:
    """
    Manages the state of servo angles for threaded communication.
    """
    def __init__(self):
        self._lock = threading.Lock()
        # Key: channel (0-15), Value: target angle (0-180)
        self.target_angles = {}
        # Key: channel (0-15), Value: last sent angle
        self.last_sent_angles = {}

    def update_angle(self, channel, angle):
        """Update the target angle for a channel."""
        with self._lock:
            self.target_angles[channel] = angle

    def get_pending_updates(self):
        """
        Get list of (channel, angle) for channels that need updating.
        Returns: list of tuples (channel, angle)
        """
        updates = []
        with self._lock:
            for channel, angle in self.target_angles.items():
                last = self.last_sent_angles.get(channel, -1)
                if angle != last:
                    updates.append((channel, angle))
        return updates

    def mark_as_sent(self, channel, angle):
        """Mark a channel's angle as successfully sent."""
        with self._lock:
            self.last_sent_angles[channel] = angle

    def clear_history(self):
        """Clear sent history to force updates on next command."""
        with self._lock:
            self.last_sent_angles.clear()

    def get_angle(self, channel):
        """Get current target angle for a channel."""
        with self._lock:
            return self.target_angles.get(channel, None)


class CalibratorGUI:
    """
    Main GUI application for robot calibration.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Robot Calibration Tool")
        self.root.geometry("800x700")
        self.root.configure(bg=THEME["bg"])

        # Initialize components
        self.driver = PCA9685Driver()
        self.manager = ServoManager()
        self.servo_state = ServoState()
        self.motion_planner = MotionPlanner(self.servo_state)
        self.pulse_mapper = PulseMapper()  # For heterogeneous motor support

        # State variables
        self.is_connected = False
        self.sine_test_running = False
        self.sine_test_thread = None
        
        # Sender thread variables
        self.sender_running = True
        self.sender_thread = threading.Thread(target=self._sender_thread_loop, daemon=True)
        self.sender_thread.start()

        # UI variables
        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Disconnected")
        self.sliders = {}
        self.channel_vars = {}
        self.angle_vars = {}
        self.min_labels = {}
        self.max_labels = {}
        # Kinematics UI variables
        self.type_vars = {}
        self.min_pos_vars = {}
        self.min_pos_combos = {}  # Store ComboBox references for dynamic update
        self.length_vars = {}
        self.actuation_range_vars = {}  # Motor actuation range (180/270)
        self.constrain_var = None  # Slider constraint toggle

        # Build UI
        self._create_styles()
        self._create_connection_panel()
        self._create_servo_panels()
        self._create_diagnostics_panel()
        self._create_footer()

        # Load saved port
        saved_port = self.manager.get_saved_port()
        if saved_port:
            self.port_var.set(saved_port)

        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _deploy_config(self):
        """Deploy current servo_config.json to project root."""
        if not messagebox.askyesno("Deploy Config", 
            "This will overwrite the main server's servo configuration.\n"
            "Proceed?\n\n"
            "이 작업은 메인 서버의 서보 설정을 덮어씁니다.\n"
            "진행하시겠습니까?"):
            return

        try:
            # Save current state first
            self.manager.save_config()
            
            # Define paths
            # Assuming script is in tools/robot_calibrator
            # Project root is ../../
            current_dir = os.path.dirname(os.path.abspath(__file__))
            src_file = os.path.join(current_dir, "servo_config.json")
            
            # Destination: Project Root
            root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
            dest_file = os.path.join(root_dir, "servo_config.json")
            
            if not os.path.exists(src_file):
                messagebox.showerror("Error", "Source config not found!")
                return
                
            # Backup if exists
            if os.path.exists(dest_file):
                shutil.copy2(dest_file, dest_file + ".bak")
                
            # Copy
            shutil.copy2(src_file, dest_file)
            
            messagebox.showinfo("Success", 
                f"Configuration deployed successfully!\n\n"
                f"From: {src_file}\n"
                f"To:   {dest_file}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Deployment failed: {e}")

    def _create_styles(self):
        """Create custom styles for widgets."""
        style = ttk.Style()
        style.theme_use('clam')

        # Configure colors
        style.configure("TFrame", background=THEME["bg"])
        style.configure("TLabel", background=THEME["bg"], foreground=THEME["fg"])
        style.configure("TButton", padding=5)
        style.configure("Header.TLabel", font=("Arial", 12, "bold"))
        style.configure("Status.TLabel", font=("Arial", 10))

    def _create_connection_panel(self):
        """Create the connection status panel."""
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.X)

        # Status indicator
        self.status_canvas = tk.Canvas(frame, width=20, height=20, bg=THEME["bg"], highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.status_indicator = self.status_canvas.create_oval(2, 2, 18, 18, fill=THEME["error"])

        # Status label
        ttk.Label(frame, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.LEFT)

        # Connect button
        self.connect_btn = ttk.Button(frame, text="Connect", command=self._on_connect)
        self.connect_btn.pack(side=tk.RIGHT, padx=5)

        # Deploy button
        ttk.Button(frame, text="Deploy Config", command=self._deploy_config).pack(side=tk.RIGHT, padx=5)

        # Port dropdown
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, width=15)
        self.port_combo.pack(side=tk.RIGHT, padx=5)
        self._refresh_ports()

        # Refresh ports button
        ttk.Button(frame, text="⟳", width=3, command=self._refresh_ports).pack(side=tk.RIGHT)

    def _create_servo_panels(self):
        """Create Left/Right arm servo control panels."""
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left Arm Tab
        left_frame = ttk.Frame(notebook, padding=10)
        notebook.add(left_frame, text="Left Arm")
        self._create_arm_controls(left_frame, "left_arm", range(1, NUM_SLOTS + 1))

        # Right Arm Tab
        right_frame = ttk.Frame(notebook, padding=10)
        notebook.add(right_frame, text="Right Arm")
        self._create_arm_controls(right_frame, "right_arm", range(1, NUM_SLOTS + 1))

    def _create_arm_controls(self, parent, arm_key, slots):
        """Create control widgets for one arm with kinematics settings."""
        for i, slot in enumerate(slots):
            # Container for 2-row layout
            slot_container = ttk.Frame(parent)
            slot_container.pack(fill=tk.X, pady=3)

            # === Row 1: Servo Control ===
            row1 = ttk.Frame(slot_container)
            row1.pack(fill=tk.X)

            # Slot label
            ttk.Label(row1, text=f"Slot {slot}:", width=8).pack(side=tk.LEFT)

            # Channel dropdown
            ch_var = tk.IntVar(value=self.manager.get_channel(arm_key, slot))
            self.channel_vars[(arm_key, slot)] = ch_var

            ch_combo = ttk.Combobox(row1, textvariable=ch_var, values=list(range(NUM_CHANNELS)), width=5)
            ch_combo.pack(side=tk.LEFT, padx=5)
            ch_combo.bind("<<ComboboxSelected>>", lambda e, a=arm_key, s=slot: self._on_channel_change(a, s))

            # Angle slider
            angle_var = tk.DoubleVar(value=90.0)
            self.angle_vars[(arm_key, slot)] = angle_var

            # [-] Button
            ttk.Button(row1, text="-", width=2, 
                command=lambda a=arm_key, s=slot: self._adjust_angle(a, s, -0.1)
            ).pack(side=tk.LEFT, padx=2)

            # Angle slider - range based on motor actuation_range
            current_range = self.manager.get_actuation_range(arm_key, slot)
            slider = ttk.Scale(
                row1, from_=0, to=current_range, variable=angle_var, orient=tk.HORIZONTAL, length=200,
                command=lambda v, a=arm_key, s=slot: self._on_slider_change(a, s, float(v))
            )
            slider.pack(side=tk.LEFT, padx=5)
            self.sliders[(arm_key, slot)] = slider

            # [+] Button
            ttk.Button(row1, text="+", width=2, 
                command=lambda a=arm_key, s=slot: self._adjust_angle(a, s, 0.1)
            ).pack(side=tk.LEFT, padx=2)

            # Angle display
            ttk.Label(row1, textvariable=angle_var, width=4).pack(side=tk.LEFT)
            ttk.Label(row1, text="°").pack(side=tk.LEFT)

            # Min/Max buttons and labels
            limits = self.manager.get_limits(arm_key, slot)

            min_label = tk.StringVar(value=str(limits["min"]))
            max_label = tk.StringVar(value=str(limits["max"]))
            self.min_labels[(arm_key, slot)] = min_label
            self.max_labels[(arm_key, slot)] = max_label

            ttk.Button(row1, text="Set Min", width=8,
                       command=lambda a=arm_key, s=slot: self._on_set_min(a, s)).pack(side=tk.LEFT, padx=2)
            ttk.Label(row1, textvariable=min_label, width=4).pack(side=tk.LEFT)

            ttk.Button(row1, text="Set Max", width=8,
                       command=lambda a=arm_key, s=slot: self._on_set_max(a, s)).pack(side=tk.LEFT, padx=2)
            ttk.Label(row1, textvariable=max_label, width=4).pack(side=tk.LEFT)

            # === Row 2: Kinematics Settings ===
            row2 = ttk.Frame(slot_container)
            row2.pack(fill=tk.X, pady=(2, 0))

            # Spacer to align with row 1
            ttk.Label(row2, text="", width=8).pack(side=tk.LEFT)

            # Type dropdown (Vertical/Horizontal/Roll/Gripper)
            ttk.Label(row2, text="Type:").pack(side=tk.LEFT, padx=(5, 2))
            type_var = tk.StringVar(value=self.manager.get_type(arm_key, slot))
            self.type_vars[(arm_key, slot)] = type_var
            type_combo = ttk.Combobox(row2, textvariable=type_var, values=["vertical", "horizontal", "roll", "gripper"], width=10, state="readonly")
            type_combo.pack(side=tk.LEFT, padx=2)
            type_combo.bind("<<ComboboxSelected>>", lambda e, a=arm_key, s=slot: self._on_type_change(a, s))

            # Min Position dropdown (dynamic based on type)
            ttk.Label(row2, text="Min Pos:").pack(side=tk.LEFT, padx=(10, 2))
            min_pos_var = tk.StringVar(value=self.manager.get_min_pos(arm_key, slot))
            self.min_pos_vars[(arm_key, slot)] = min_pos_var
            
            # Determine initial options based on type
            current_type = self.manager.get_type(arm_key, slot)
            min_pos_options = self._get_min_pos_options(current_type)
            
            min_pos_combo = ttk.Combobox(row2, textvariable=min_pos_var, values=min_pos_options, width=8, state="readonly")
            min_pos_combo.pack(side=tk.LEFT, padx=2)
            min_pos_combo.bind("<<ComboboxSelected>>", lambda e, a=arm_key, s=slot: self._on_min_pos_change(a, s))
            self.min_pos_combos[(arm_key, slot)] = min_pos_combo

            # Length entry (mm)
            ttk.Label(row2, text="Length:").pack(side=tk.LEFT, padx=(10, 2))
            length_var = tk.StringVar(value=str(self.manager.get_length(arm_key, slot)))
            self.length_vars[(arm_key, slot)] = length_var
            length_entry = ttk.Entry(row2, textvariable=length_var, width=8)
            length_entry.pack(side=tk.LEFT, padx=2)
            length_entry.bind("<FocusOut>", lambda e, a=arm_key, s=slot: self._on_length_change(a, s))
            length_entry.bind("<Return>", lambda e, a=arm_key, s=slot: self._on_length_change(a, s))
            ttk.Label(row2, text="mm").pack(side=tk.LEFT)

            # Actuation Range dropdown (180°/270°)
            ttk.Label(row2, text="Range:").pack(side=tk.LEFT, padx=(10, 2))
            range_var = tk.IntVar(value=self.manager.get_actuation_range(arm_key, slot))
            self.actuation_range_vars[(arm_key, slot)] = range_var
            range_combo = ttk.Combobox(row2, textvariable=range_var, values=[180, 270], width=5, state="readonly")
            range_combo.pack(side=tk.LEFT, padx=2)
            range_combo.bind("<<ComboboxSelected>>", lambda e, a=arm_key, s=slot: self._on_range_change(a, s))
            ttk.Label(row2, text="°").pack(side=tk.LEFT)

    def _create_diagnostics_panel(self):
        """Create diagnostics panel."""
        frame = ttk.LabelFrame(self.root, text="Diagnostics", padding=10)
        frame.pack(fill=tk.X, padx=10, pady=5)

        # Sine test controls
        ttk.Label(frame, text="Sine Test Channel:").pack(side=tk.LEFT)
        self.sine_channel_var = tk.IntVar(value=0)
        ttk.Combobox(frame, textvariable=self.sine_channel_var, values=list(range(NUM_CHANNELS)), width=5).pack(side=tk.LEFT, padx=5)

        self.sine_btn = ttk.Button(frame, text="Start Sine Test", command=self._on_sine_test)
        self.sine_btn.pack(side=tk.LEFT, padx=10)

        # I2C scan button
        ttk.Button(frame, text="Scan I2C", command=self._on_i2c_scan).pack(side=tk.LEFT, padx=10)

    def _create_footer(self):
        """Create footer with action buttons."""
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.X)

        # E-STOP button (prominent)
        estop_btn = tk.Button(
            frame, text="E-STOP", bg=THEME["error"], fg="white",
            font=("Arial", 12, "bold"), width=10,
            command=self._on_estop
        )
        estop_btn.pack(side=tk.RIGHT, padx=5)

        # Save/Load config
        ttk.Button(frame, text="Save Config", command=self._on_save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="Load Config", command=self._on_load_config).pack(side=tk.LEFT, padx=5)
        
        # Home position controls
        ttk.Separator(frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        ttk.Button(frame, text="Set Home", command=self._on_set_home).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="Go Home", command=self._on_go_home).pack(side=tk.LEFT, padx=5)
        
        # Zero Point Calibration controls
        ttk.Separator(frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        ttk.Button(frame, text="Set Zero", command=self._on_set_zero).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="Go to Zero", command=self._on_go_to_zero).pack(side=tk.LEFT, padx=5)
        
        # Motion Duration spinbox
        ttk.Separator(frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        ttk.Label(frame, text="Speed:").pack(side=tk.LEFT)
        self.duration_var = tk.DoubleVar(value=1.0)
        duration_spinbox = ttk.Spinbox(frame, from_=0.5, to=3.0, increment=0.1, textvariable=self.duration_var, width=5, format="%.1f")
        duration_spinbox.pack(side=tk.LEFT, padx=2)
        ttk.Label(frame, text="s").pack(side=tk.LEFT)
        
        # Slider constraint toggle
        ttk.Separator(frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        self.constrain_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Limit to Min/Max", variable=self.constrain_var, command=self._on_constrain_toggle).pack(side=tk.LEFT, padx=5)

    def _refresh_ports(self):
        """Refresh available COM ports."""
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def _on_connect(self):
        """Handle connect/disconnect button click."""
        if self.is_connected:
            # Disconnect
            self.driver.disconnect()
            self.is_connected = False
            self.status_var.set("Disconnected")
            self.status_canvas.itemconfig(self.status_indicator, fill=THEME["error"])
            self.connect_btn.config(text="Connect")
        else:
            # Connect
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "Please select a COM port")
                return

            self.status_var.set("Connecting...")
            self.root.update()

            if self.driver.connect(port):
                self.is_connected = True
                self.status_var.set(f"Connected: {port}")
                self.status_canvas.itemconfig(self.status_indicator, fill=THEME["success"])
                self.connect_btn.config(text="Disconnect")
                self.manager.set_saved_port(port)
            else:
                self.status_var.set("Connection Failed")
                messagebox.showerror("Error", f"Failed to connect to {port}")

    def _adjust_angle(self, arm, slot, delta):
        """Increment or decrement angle by delta."""
        var = self.angle_vars[(arm, slot)]
        current = var.get()
        new_val = round(current + delta, 1)
        
        # Clamp to 0-actuation_range (or limits if constrained)
        min_limit = 0
        max_limit = self.manager.get_actuation_range(arm, slot)
        if self.constrain_var.get():
            limits = self.manager.get_limits(arm, slot)
            min_limit = limits["min"]
            max_limit = limits["max"]
            
        new_val = max(min_limit, min(max_limit, new_val))
        
        # Update variable and trigger change handler
        var.set(new_val)
        self._on_slider_change(arm, slot, new_val)

    def _on_channel_change(self, arm, slot):
        """Handle channel dropdown change."""
        new_channel = self.channel_vars[(arm, slot)].get()
        self.manager.set_channel(arm, slot, new_channel)

    def _on_slider_change(self, arm, slot, value):
        """
        Handle slider movement.
        OPTIMIZED: Updates state only. Sender thread handles transmission.
        Now includes PulseMapper for heterogeneous motor support.
        """
        if not self.is_connected:
            return

        physical_angle = float(value)
        channel = self.manager.get_channel(arm, slot)
        
        # Get motor config for this slot
        slot_key = f"slot_{slot}"
        motor_config = self.manager.config.get(arm, {}).get(slot_key, {})
        
        # Convert physical angle to virtual (Arduino) angle
        virtual_angle = self.pulse_mapper.physical_to_virtual(physical_angle, motor_config)
        
        # Update thread-safe state map with virtual angle
        self.servo_state.update_angle(channel, int(virtual_angle))

    def _sender_thread_loop(self):
        """
        Background thread for sending servo commands.
        Runs at ~30Hz. Retries failed commands automatically.
        """
        while self.sender_running:
            if self.is_connected:
                # Get pending updates
                updates = self.servo_state.get_pending_updates()
                
                for channel, angle in updates:
                    # Returns True only if ACK received
                    if self.driver.set_servo_angle(channel, angle):
                         self.servo_state.mark_as_sent(channel, angle)
                    else:
                        # If ACK failed, do NOT mark as sent.
                        # It will be retried in the next loop because angle != last_sent
                        pass
                        
                    time.sleep(SENDER_CMD_DELAY)
            
            # 30Hz Loop
            time.sleep(SENDER_LOOP_INTERVAL)

    def _on_set_min(self, arm, slot):
        """Set current angle as minimum limit."""
        current_angle = self.angle_vars[(arm, slot)].get()
        self.manager.set_limit(arm, slot, "min", current_angle)
        self.min_labels[(arm, slot)].set(str(current_angle))

    def _on_set_max(self, arm, slot):
        """Set current angle as maximum limit."""
        current_angle = self.angle_vars[(arm, slot)].get()
        self.manager.set_limit(arm, slot, "max", current_angle)
        self.max_labels[(arm, slot)].set(str(current_angle))

    def _get_min_pos_options(self, type_value):
        """Get min_pos options based on joint type."""
        if type_value == "vertical":
            return ["top", "bottom"]
        elif type_value == "horizontal":
            return ["left", "right"]
        elif type_value == "roll":
            return ["cw", "ccw"]
        elif type_value == "gripper":
            return ["open", "close"]
        return ["bottom"]  # fallback

    def _get_default_min_pos(self, type_value):
        """Get default min_pos for a joint type."""
        defaults = {
            "vertical": "bottom",
            "horizontal": "left",
            "roll": "cw",
            "gripper": "open"
        }
        return defaults.get(type_value, "bottom")

    def _on_constrain_toggle(self):
        """Toggle slider constraints between full range and Min/Max limits."""
        constrained = self.constrain_var.get()
        
        for arm in ARM_NAMES:
            for slot in range(1, NUM_SLOTS + 1):
                slider = self.sliders[(arm, slot)]
                limits = self.manager.get_limits(arm, slot)
                min_limit = limits["min"]
                max_limit = limits["max"]
                
                if constrained:
                    # Constrain slider to Min/Max
                    slider.configure(from_=min_limit, to=max_limit)
                    
                    # Clamp current value if outside limits
                    current = self.angle_vars[(arm, slot)].get()
                    if current < min_limit:
                        self.angle_vars[(arm, slot)].set(min_limit)
                        channel = self.manager.get_channel(arm, slot)
                        self.servo_state.update_angle(channel, min_limit)
                    elif current > max_limit:
                        self.angle_vars[(arm, slot)].set(max_limit)
                        channel = self.manager.get_channel(arm, slot)
                        self.servo_state.update_angle(channel, max_limit)
                else:
                    # Reset to full range based on actuation_range
                    full_range = self.manager.get_actuation_range(arm, slot)
                    slider.configure(from_=0, to=full_range)

    def _on_type_change(self, arm, slot):
        """Handle type dropdown change. Updates min_pos options dynamically."""
        new_type = self.type_vars[(arm, slot)].get()
        self.manager.set_type(arm, slot, new_type)
        
        # Update min_pos combo options based on new type
        combo = self.min_pos_combos[(arm, slot)]
        new_options = self._get_min_pos_options(new_type)
        default_pos = self._get_default_min_pos(new_type)
        
        combo['values'] = new_options
        # Reset to default if current value is not valid for new type
        current_pos = self.min_pos_vars[(arm, slot)].get()
        if current_pos not in new_options:
            self.min_pos_vars[(arm, slot)].set(default_pos)
            self.manager.set_min_pos(arm, slot, default_pos)

    def _on_min_pos_change(self, arm, slot):
        """Handle min position dropdown change."""
        new_min_pos = self.min_pos_vars[(arm, slot)].get()
        self.manager.set_min_pos(arm, slot, new_min_pos)

    def _on_length_change(self, arm, slot):
        """Handle length entry change."""
        length_str = self.length_vars[(arm, slot)].get()
        try:
            length = float(length_str)
            self.manager.set_length(arm, slot, length)
        except ValueError:
            # Invalid input, reset to saved value
            self.length_vars[(arm, slot)].set(str(self.manager.get_length(arm, slot)))

    def _on_range_change(self, arm, slot):
        """Handle actuation range dropdown change."""
        new_range = self.actuation_range_vars[(arm, slot)].get()
        self.manager.set_actuation_range(arm, slot, new_range)
        
        # Update slider range dynamically
        slider = self.sliders[(arm, slot)]
        slider.configure(to=new_range)
        
        # Clamp current value if exceeds new range
        current = self.angle_vars[(arm, slot)].get()
        if current > new_range:
            self.angle_vars[(arm, slot)].set(new_range)

    def _on_sine_test(self):
        """Start/stop sine wave test."""
        if self.sine_test_running:
            self.sine_test_running = False
            self.sine_btn.config(text="Start Sine Test")
        else:
            if not self.is_connected:
                messagebox.showwarning("Warning", "Not connected to hardware")
                return

            self.sine_test_running = True
            self.sine_btn.config(text="Stop Sine Test")
            self.sine_test_thread = threading.Thread(target=self._sine_test_loop, daemon=True)
            self.sine_test_thread.start()

    def _sine_test_loop(self):
        """Sine wave test loop (runs in separate thread)."""
        channel = self.sine_channel_var.get()
        t = 0

        while self.sine_test_running:
            # Generate sine wave angle (45-135 degrees)
            angle = 90 + 45 * math.sin(t)
            
            # Using servo_state for thread safety and rate limiting
            self.servo_state.update_angle(channel, int(angle))
            
            t += 0.1
            time.sleep(SINE_TEST_INTERVAL)

    def _on_i2c_scan(self):
        """Scan for I2C devices (placeholder)."""
        if not self.is_connected:
            messagebox.showwarning("Warning", "Not connected to hardware")
            return
        messagebox.showinfo("I2C Scan", "PCA9685 expected at address 0x40\n(Full scan not implemented via Serial)")

    def _on_save_config(self):
        """Save current configuration."""
        if self.manager.save_config():
            messagebox.showinfo("Success", "Configuration saved")
        else:
            messagebox.showerror("Error", "Failed to save configuration")

    def _on_load_config(self):
        """Reload configuration from file."""
        self.manager.load_config()

        # Update UI with loaded values
        for arm in ARM_NAMES:
            for slot in range(1, NUM_SLOTS + 1):
                self.channel_vars[(arm, slot)].set(self.manager.get_channel(arm, slot))
                limits = self.manager.get_limits(arm, slot)
                self.min_labels[(arm, slot)].set(str(limits["min"]))
                self.max_labels[(arm, slot)].set(str(limits["max"]))
                
                # Update kinematics fields
                loaded_type = self.manager.get_type(arm, slot)
                self.type_vars[(arm, slot)].set(loaded_type)
                
                # Update min_pos options and value
                combo = self.min_pos_combos[(arm, slot)]
                combo['values'] = self._get_min_pos_options(loaded_type)
                self.min_pos_vars[(arm, slot)].set(self.manager.get_min_pos(arm, slot))
                
                self.length_vars[(arm, slot)].set(str(self.manager.get_length(arm, slot)))

        messagebox.showinfo("Success", "Configuration loaded")

    def _on_set_home(self):
        """Save current slider positions as home (initial) position for all joints."""
        for arm in ARM_NAMES:
            for slot in range(1, NUM_SLOTS + 1):
                current_angle = self.angle_vars[(arm, slot)].get()
                self.manager.set_initial(arm, slot, current_angle)
        
        # Auto-save config
        if self.manager.save_config():
            messagebox.showinfo("Set Home", "Home position saved successfully!")
        else:
            messagebox.showerror("Error", "Failed to save home position")

    def _on_go_home(self):
        """Move all joints to their saved home (initial) positions with smooth motion."""
        if not self.is_connected:
            messagebox.showwarning("Warning", "Not connected to hardware")
            return
        
        # Force updates even if software thinks it's at the same position
        self.servo_state.clear_history()
        
        # Build target list and update UI
        targets = []
        for arm in ARM_NAMES:
            for slot in range(1, NUM_SLOTS + 1):
                initial_angle = self.manager.get_initial(arm, slot)
                channel = self.manager.get_channel(arm, slot)
                targets.append((channel, initial_angle))
                # Update UI slider immediately
                self.angle_vars[(arm, slot)].set(initial_angle)
        
        # Execute smooth motion
        duration = self.duration_var.get()
        self.motion_planner.move_all(targets, duration)

    def _on_set_zero(self):
        """Save current slider positions as zero point (vertical pose) for all joints."""
        if not messagebox.askyesno("Set Zero Point", 
            "This will save the current pose as Logical 0 (Vertical Position).\n"
            "Make sure the robot is Vertical and Facing Forward (Parallel to Top Edge)!\n\n"
            "현재 자세를 논리적 0점(수직 자세)으로 저장합니다.\n"
            "로봇이 수직으로 서 있고, 상단 모서리와 평행한 정면을 보는지 확인하세요!\n\n"
            "Continue?"):
            return
        
        for arm in ARM_NAMES:
            for slot in range(1, NUM_SLOTS + 1):
                current_angle = self.angle_vars[(arm, slot)].get()
                self.manager.set_zero_offset(arm, slot, current_angle)
        
        # Auto-save config
        if self.manager.save_config():
            messagebox.showinfo("Set Zero", "Zero point saved successfully!\n0점이 성공적으로 저장되었습니다!")
        else:
            messagebox.showerror("Error", "Failed to save zero point")

    def _on_go_to_zero(self):
        """Move all joints to their saved zero point (vertical pose) with smooth motion."""
        if not self.is_connected:
            messagebox.showwarning("Warning", "Not connected to hardware")
            return
        
        # Force updates even if software thinks it's at the same position
        self.servo_state.clear_history()
        
        # Build target list and update UI
        targets = []
        for arm in ARM_NAMES:
            for slot in range(1, NUM_SLOTS + 1):
                zero_angle = self.manager.get_zero_offset(arm, slot)
                channel = self.manager.get_channel(arm, slot)
                targets.append((channel, zero_angle))
                # Update UI slider immediately
                self.angle_vars[(arm, slot)].set(zero_angle)
        
        # Execute smooth motion
        duration = self.duration_var.get()
        self.motion_planner.move_all(targets, duration)

    def _on_estop(self):
        """Emergency stop - release all servos."""
        if self.is_connected:
            self.driver.release_all()
        self.sine_test_running = False
        # Clear history so next commands will be sent even if angle unchanged
        self.servo_state.clear_history()
        messagebox.showinfo("E-STOP", "All servos released")

    def _on_close(self):
        """Handle window close event."""
        # Stop threads
        self.sender_running = False
        self.sine_test_running = False

        # Release all servos and disconnect
        if self.is_connected:
            self.driver.release_all()
            self.driver.disconnect()

        self.root.destroy()

    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()


if __name__ == "__main__":
    app = CalibratorGUI()
    app.run()
