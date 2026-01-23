"""
Slot 0 (Base Yaw) Visual Verifier
Minimal IK verification GUI with visual canvas and axis-aligned sliders.
Supports Left and Right arm selection.

Refactored to integrate with ServoManager, MotionPlanner, and async communication.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial.tools.list_ports
import math
import threading
import time

from serial_driver import SerialDriver
from pulse_mapper import PulseMapper
from servo_manager import ServoManager
from servo_state import ServoState
from motion_planner import MotionPlanner


# Thread Timing (seconds)
SENDER_LOOP_INTERVAL = 0.033     # ~30Hz
SENDER_CMD_DELAY = 0.002         # Delay between commands


class Slot0Verifier:
    """
    Visual GUI for verifying Slot 0 (Base Yaw) IK calculations.
    Features:
    - Top-down canvas visualization
    - Axis-aligned X/Y sliders
    - Valid angle zone display
    - Left/Right arm selection
    - Smooth motion via MotionPlanner
    - Async communication via sender thread
    """
    
    # Workspace limits (mm) - symmetric for center-base layout
    X_MIN = -300
    X_MAX = 300
    Y_MIN = -300
    Y_MAX = 300
    Z_MIN = 0
    Z_MAX = 300
    
    # Canvas settings
    CANVAS_SIZE = 300
    SCALE = 0.5  # pixels per mm (300px / 600mm range)
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("IK Tester (Slot 1 + Slot 1+2)")
        self.root.geometry("750x850")
        self.root.configure(bg="#2b2b2b")
        
        # Core Components
        self.driver = SerialDriver()
        self.mapper = PulseMapper()
        self.manager = ServoManager()
        self.servo_state = ServoState()
        self.motion_planner = MotionPlanner(self.servo_state)
        self.is_connected = False
        
        # Sender thread
        self.sender_running = True
        self.sender_thread = threading.Thread(
            target=self._sender_thread_loop, daemon=True
        )
        self.sender_thread.start()
        
        # Dynamic config - Slot 1 (loaded per arm)
        self.channel = None
        self.zero_offset = None
        self.motor_config = None
        self.math_min = None
        self.math_max = None
        
        # Dynamic config - Slot 2
        self.slot2_channel = None
        self.slot2_zero_offset = None
        self.slot2_config = None
        self.theta2_min = None
        self.theta2_max = None
        
        # Dynamic config - Slot 3 (Elbow)
        self.slot3_channel = None
        self.slot3_zero_offset = None
        self.slot3_config = None
        self.theta3_min = None
        self.theta3_max = None
        
        # Link lengths
        self.d1 = 107  # Base height
        self.a2 = 105  # Upper arm
        self.a3 = 100  # Forearm (Default, will be loaded)
        
        # Active arm (default: left)
        self.arm_var = tk.StringVar(value="left")
        self._apply_arm_config()
        
        # UI Variables
        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Disconnected")
        
        # Coordinate sliders (Tab 1)
        self.x_var = tk.DoubleVar(value=100.0)
        self.y_var = tk.DoubleVar(value=0.0)
        
        # Tab 2 sliders
        self.x2_var = tk.DoubleVar(value=100.0)
        self.y2_var = tk.DoubleVar(value=100.0)
        self.z_var = tk.DoubleVar(value=107.0)
        self.theta3_var = tk.DoubleVar(value=0.0)  # Elbow Control switchable
        self.use_theta3_slider = tk.BooleanVar(value=True)  # Manual vs IK mode (Start Manual)
        
        # Motion duration
        self.duration_var = tk.DoubleVar(value=0.5)
        
        # Output (Tab 1)
        self.theta_var = tk.StringVar(value="--")
        self.physical_var = tk.StringVar(value="--")
        self.pulse_var = tk.StringVar(value="--")
        self.valid_var = tk.StringVar(value="--")
        
        # Output (Tab 2)
        # Output (Tab 2)
        self.theta1_tab2_var = tk.StringVar(value="--")
        self.pulse1_tab2_var = tk.StringVar(value="--")
        self.valid1_tab2_var = tk.StringVar(value="--")
        self.theta2_var = tk.StringVar(value="--")
        self.pulse2_var = tk.StringVar(value="--")
        self.valid2_var = tk.StringVar(value="--")
        self.theta3_out_var = tk.StringVar(value="--")
        self.pulse3_var = tk.StringVar(value="--")
        self.valid3_var = tk.StringVar(value="--")
        self.reach_var = tk.StringVar(value="--")
        self.height_var = tk.StringVar(value="--")
        
        # Build UI
        self._create_styles()
        self._create_connection_panel()
        self._create_arm_panel()
        self._create_notebook()    # Tab-based UI
        self._create_control_panel()
        self._create_log_panel()
        
        # Load saved port
        self._load_saved_port()
        
        # Initial update
        self._update_visualization()
        
        # Bind close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _apply_arm_config(self):
        """Apply the selected arm's configuration from ServoManager."""
        arm = "left_arm" if self.arm_var.get() == "left" else "right_arm"
        arm_config = self.manager.config.get(arm, {})
        
        # Slot 1 config
        self.channel = self.manager.get_channel(arm, 1)
        self.zero_offset = self.manager.get_zero_offset(arm, 1)
        self.motor_config = self._get_slot_config(arm, 1)
        limits1 = self.manager.get_limits(arm, 1)
        
        self.slot1_type = arm_config.get("slot_1", {}).get("type", "horizontal")
        self.slot1_min_pos = self.manager.get_min_pos(arm, 1)
        self.slot1_polarity = self._get_physical_polarity(self.slot1_type, self.slot1_min_pos)

        # Range Logic: Apply polarity and ensure math_min < math_max
        bound1_a = (limits1["min"] - self.zero_offset) * self.slot1_polarity
        bound1_b = (limits1["max"] - self.zero_offset) * self.slot1_polarity
        self.math_min = min(bound1_a, bound1_b)
        self.math_max = max(bound1_a, bound1_b)
        
        self.slot1_actuation_range = self.manager.get_actuation_range(arm, 1)
        
        # Slot 2 config
        self.slot2_channel = self.manager.get_channel(arm, 2)
        self.slot2_zero_offset = self.manager.get_zero_offset(arm, 2)
        self.slot2_config = self._get_slot_config(arm, 2)
        limits2 = self.manager.get_limits(arm, 2)
        
        self.slot2_type = arm_config.get("slot_2", {}).get("type", "vertical")
        self.slot2_min_pos = self.manager.get_min_pos(arm, 2)
        self.slot2_polarity = self._get_physical_polarity(self.slot2_type, self.slot2_min_pos)

        # Range Logic: Apply polarity
        bound2_a = (limits2["min"] - self.slot2_zero_offset) * self.slot2_polarity
        bound2_b = (limits2["max"] - self.slot2_zero_offset) * self.slot2_polarity
        self.theta2_min = min(bound2_a, bound2_b)
        self.theta2_max = max(bound2_a, bound2_b)
        
        self.slot2_actuation_range = self.manager.get_actuation_range(arm, 2)
        
        # Slot 3 config (Elbow)
        self.slot3_channel = self.manager.get_channel(arm, 3)
        self.slot3_zero_offset = self.manager.get_zero_offset(arm, 3)
        self.slot3_config = self._get_slot_config(arm, 3)
        limits3 = self.manager.get_limits(arm, 3)
        
        self.slot3_type = arm_config.get("slot_3", {}).get("type", "vertical")
        self.slot3_min_pos = self.manager.get_min_pos(arm, 3)
        self.slot3_polarity = self._get_physical_polarity(self.slot3_type, self.slot3_min_pos)

        # Range Logic: Apply polarity
        bound3_a = (limits3["min"] - self.slot3_zero_offset) * self.slot3_polarity
        bound3_b = (limits3["max"] - self.slot3_zero_offset) * self.slot3_polarity
        self.theta3_min = min(bound3_a, bound3_b)
        self.theta3_max = max(bound3_a, bound3_b)
        
        self.slot3_actuation_range = self.manager.get_actuation_range(arm, 3)
        
        # Link lengths
        self.d1 = arm_config.get("slot_1", {}).get("length", 107)
        self.a2 = arm_config.get("slot_2", {}).get("length", 105)
        self.a3 = arm_config.get("slot_3", {}).get("length", 100)
    
    def _get_slot_config(self, arm, slot):
        """Get motor config dict for PulseMapper."""
        slot_key = f"slot_{slot}"
        config = self.manager.config.get(arm, {}).get(slot_key, {})
        return {
            "actuation_range": config.get("actuation_range", 180),
            "pulse_min": config.get("pulse_min", 500),
            "pulse_max": config.get("pulse_max", 2500)
        }
    
    def _get_tkinter_offset(self, joint_type, min_pos):
        """
        Get Tkinter angle offset based on min_pos dynamic alignment.
        Ensures 'min_pos' aligns with expected visual angle.
        """
        if joint_type == "horizontal":
            return 180 if min_pos == "left" else 0
            
        elif joint_type == "vertical":
            # Reverting to 0 based on user confirmation that 'tk' output (Start=-39.3) is correct.
            # My previous attempt to semantic align 'bottom' to -90 deg caused the 'Reverse' issue.
            # 0 offset implies 0 deg is Right (Forward).
            return 0

        return 0

        return 0
    
    def _get_physical_polarity(self, joint_type, min_pos):
        """
        Get direction multiplier (+1 or -1) for physical mapping.
        """
        if joint_type == "horizontal":
            return -1 if min_pos == "left" else 1

        elif joint_type == "vertical":
            # 'bottom' (e.g. 86.7 deg) is physical min.
            # 'top' (e.g. 270 deg) is physical max.
            # Increasing Angle moves Bottom -> Top (Up).
            # Math Angle Increase (Z-up) also moves Up.
            # So Polarity is STANDARD (1).
            return 1  
        return 1

    def _get_tkinter_offset(self, joint_type, min_pos):
        """Get Tkinter angle offset based on min_pos."""
        if joint_type == "horizontal":
            return 180 if min_pos == "left" else 0
        elif joint_type == "vertical":
            return 180 if min_pos == "bottom" else 90
        return 0

    def _get_direction(self, joint_type, min_pos):
        """Get direction multiplier for drawing (unused for physics now)."""
        if joint_type == "horizontal":
            return 1 if min_pos == "left" else -1
        elif joint_type == "vertical":
            return 1 if min_pos == "bottom" else -1
        return 1
    
    def _sender_thread_loop(self):
        """
        Background thread for sending servo commands.
        Runs at ~30Hz. Retries failed commands automatically.
        """
        while self.sender_running:
            if self.is_connected:
                updates = self.servo_state.get_pending_updates()
                for channel, pulse_us in updates:
                    if self.driver.write_pulse(channel, pulse_us):
                        self.servo_state.mark_as_sent(channel, pulse_us)
                    time.sleep(SENDER_CMD_DELAY)
            time.sleep(SENDER_LOOP_INTERVAL)
    
    def _create_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#2b2b2b")
        style.configure("TLabel", background="#2b2b2b", foreground="#ffffff")
        style.configure("TButton", padding=5)
        style.configure("TRadiobutton", background="#2b2b2b", foreground="#ffffff")
        style.configure("Result.TLabel", font=("Consolas", 11), foreground="#00ff00")
        style.configure("Valid.TLabel", font=("Consolas", 11, "bold"), foreground="#44ff44")
        style.configure("Invalid.TLabel", font=("Consolas", 11, "bold"), foreground="#ff4444")
    
    def _create_connection_panel(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.X)
        
        # Status
        self.status_canvas = tk.Canvas(frame, width=16, height=16, 
                                        bg="#2b2b2b", highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 5))
        self.status_indicator = self.status_canvas.create_oval(2, 2, 14, 14, fill="#ff4444")
        
        ttk.Label(frame, textvariable=self.status_var).pack(side=tk.LEFT)
        
        # Connect
        self.connect_btn = ttk.Button(frame, text="Connect", command=self._on_connect)
        self.connect_btn.pack(side=tk.RIGHT, padx=5)
        
        # Port
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, width=12)
        self.port_combo.pack(side=tk.RIGHT, padx=5)
        self._refresh_ports()
        
        ttk.Button(frame, text="Γƒ│", width=3, command=self._refresh_ports).pack(side=tk.RIGHT)
    
    def _create_arm_panel(self):
        """Create arm selection panel."""
        frame = ttk.Frame(self.root, padding=(10, 5))
        frame.pack(fill=tk.X)
        
        ttk.Label(frame, text="Arm:").pack(side=tk.LEFT)
        
        ttk.Radiobutton(frame, text="Left", variable=self.arm_var, 
                        value="left", command=self._on_arm_change).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(frame, text="Right", variable=self.arm_var, 
                        value="right", command=self._on_arm_change).pack(side=tk.LEFT)
        
        # Channel indicator
        self.channel_label = ttk.Label(frame, text=f"(Ch1: {self.channel}, Ch2: {self.slot2_channel})", foreground="#888888")
        self.channel_label.pack(side=tk.LEFT, padx=20)
    
    def _on_arm_change(self):
        """Handle arm selection change."""
        self._apply_arm_config()
        self.channel_label.config(text=f"(Ch1: {self.channel}, Ch2: {self.slot2_channel})")
        self._redraw_canvas()
        if hasattr(self, 'side_canvas'):
            self._redraw_tab2()
        self._update_visualization()
        self._log(f"Switched to {self.arm_var.get().upper()} arm (Ch1: {self.channel}, Ch2: {self.slot2_channel})")
    
    def _create_notebook(self):
        """Create tab-based UI with Slot 1 and Dual View tabs."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Tab 1: Slot 1 Only
        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text="Slot 1 Only")
        self._create_slot1_tab()
        
        # Tab 2: Slot 1+2 Dual View
        self.tab2 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2, text="Slot 1+2 Dual")
        self._create_dual_tab()
    
    def _create_slot1_tab(self):
        """Create Tab 1 content: existing Slot 1 canvas and output."""
        self._create_canvas_panel(self.tab1)
        self._create_output_panel(self.tab1)
    
    def _create_dual_tab(self):
        """Create Tab 2 content: dual canvas (Top-Down + Side) view."""
        # Main container
        main_frame = ttk.Frame(self.tab2)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # === Left: Top-Down View ===
        left_frame = ttk.LabelFrame(main_frame, text="Top-Down (X/Y)", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=2)
        
        grid1 = ttk.Frame(left_frame)
        grid1.pack(padx=2, pady=2)
        
        # Y2 Slider (Vertical)
        y2_frame = ttk.Frame(grid1)
        y2_frame.grid(row=0, column=0, sticky="ns")
        ttk.Label(y2_frame, text="Y", font=("Arial", 9)).pack()
        self.y2_slider = ttk.Scale(y2_frame, from_=self.Y_MAX, to=self.Y_MIN,
            variable=self.y2_var, orient=tk.VERTICAL, length=240,
            command=lambda v: self._update_tab2())
        self.y2_slider.pack(pady=2)
        
        # Top-Down Canvas
        self.top_canvas = tk.Canvas(grid1, width=240, height=240,
            bg="#1a1a2e", highlightthickness=1, highlightbackground="#444")
        self.top_canvas.grid(row=0, column=1)
        
        # X2 Slider (Horizontal)
        x2_frame = ttk.Frame(grid1)
        x2_frame.grid(row=1, column=1, sticky="ew")
        self.x2_slider = ttk.Scale(x2_frame, from_=self.X_MIN, to=self.X_MAX,
            variable=self.x2_var, orient=tk.HORIZONTAL, length=240,
            command=lambda v: self._update_tab2())
        self.x2_slider.pack()
        ttk.Label(x2_frame, text="X", font=("Arial", 9)).pack()
        
        # === Right: Side View ===
        right_frame = ttk.LabelFrame(main_frame, text="Side (R/Z)", padding=5)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=2)
        
        grid2 = ttk.Frame(right_frame)
        grid2.pack(padx=2, pady=2)
        
        # Z Slider (Vertical)
        z_frame = ttk.Frame(grid2)
        z_frame.grid(row=0, column=0, sticky="ns")
        ttk.Label(z_frame, text="Z", font=("Arial", 9)).pack()
        self.z_slider = ttk.Scale(z_frame, from_=self.Z_MAX, to=self.Z_MIN,
            variable=self.z_var, orient=tk.VERTICAL, length=240,
            command=lambda v: self._update_tab2())
        self.z_slider.pack(pady=2)

        # Theta3 Slider (Vertical)
        t3_frame = ttk.Frame(grid2)
        t3_frame.grid(row=0, column=2, sticky="ns", padx=5)
        ttk.Label(t3_frame, text="╬╕3", font=("Arial", 9)).pack()
        self.t3_slider = ttk.Scale(t3_frame, from_=-150, to=150, # Arbitrary range, will act as override
            variable=self.theta3_var, orient=tk.VERTICAL, length=240,
            command=lambda v: self._update_tab2())
        self.t3_slider.pack(pady=2)
        
        # Side Canvas
        self.side_canvas = tk.Canvas(grid2, width=240, height=240,
            bg="#1a2e1a", highlightthickness=1, highlightbackground="#444")
        self.side_canvas.grid(row=0, column=1)
        
        # Draw static elements
        self._draw_top_static()
        self._draw_side_static()
        
        # === Output Panel ===
        self._create_dual_output(main_frame)
    
    def _create_canvas_panel(self, parent):
        """Create the visual canvas with axis-aligned sliders."""
        frame = ttk.LabelFrame(parent, text="Workspace (Top View)", padding=5)
        frame.pack(fill=tk.BOTH, padx=5, pady=5)
        
        # Grid layout: Y slider (left), Canvas (center), X slider (bottom)
        grid = ttk.Frame(frame)
        grid.pack()
        
        # Y Slider (Vertical, Left)
        y_frame = ttk.Frame(grid)
        y_frame.grid(row=0, column=0, sticky="ns")
        
        ttk.Label(y_frame, text="Y", font=("Arial", 9)).pack()
        self.y_slider = ttk.Scale(y_frame, from_=self.Y_MAX, to=self.Y_MIN,
                                   variable=self.y_var, orient=tk.VERTICAL,
                                   length=self.CANVAS_SIZE,
                                   command=lambda v: self._update_visualization())
        self.y_slider.pack(pady=5)
        
        # Canvas (Center)
        self.canvas = tk.Canvas(grid, width=self.CANVAS_SIZE, height=self.CANVAS_SIZE,
                                 bg="#1a1a2e", highlightthickness=1, highlightbackground="#444")
        self.canvas.grid(row=0, column=1)
        
        # X Slider (Horizontal, Bottom)
        x_frame = ttk.Frame(grid)
        x_frame.grid(row=1, column=1, sticky="ew")
        
        self.x_slider = ttk.Scale(x_frame, from_=self.X_MIN, to=self.X_MAX,
                                   variable=self.x_var, orient=tk.HORIZONTAL,
                                   length=self.CANVAS_SIZE,
                                   command=lambda v: self._update_visualization())
        self.x_slider.pack()
        ttk.Label(x_frame, text="X", font=("Arial", 9)).pack()
        
        # Draw static elements
        self._draw_static_elements()
    
    def _redraw_canvas(self):
        """Redraw all canvas elements (called on arm change)."""
        self.canvas.delete("all")
        self._draw_static_elements()
    
    def _draw_static_elements(self):
        """Draw grid, axes, and valid zone arc."""
        # Base at canvas center for full 360┬░ view
        cx = self.CANVAS_SIZE // 2
        cy = self.CANVAS_SIZE // 2
        
        # Grid lines
        for i in range(0, self.CANVAS_SIZE + 1, 50):
            self.canvas.create_line(i, 0, i, self.CANVAS_SIZE, fill="#333333", dash=(2, 4))
            self.canvas.create_line(0, i, self.CANVAS_SIZE, i, fill="#333333", dash=(2, 4))
        
        # Axes through center
        self.canvas.create_line(cx, 0, cx, self.CANVAS_SIZE, fill="#555555", width=1)
        self.canvas.create_line(0, cy, self.CANVAS_SIZE, cy, fill="#555555", width=1)
        
        # Valid zone arc (fan shape from math_min to math_max)
        radius = 140  # Fit within canvas (150 - margin)
        offset = self._get_tkinter_offset(self.slot1_type, self.slot1_min_pos)

        # Background Arc (Full Range)
        full_min = 0 - self.zero_offset
        self.canvas.create_arc(cx - radius, cy - radius, cx + radius, cy + radius,
                                start=full_min + offset, extent=self.slot1_actuation_range,
                                fill="#222222", outline="#444444", width=1, style=tk.PIESLICE)

        # Foreground Arc (Valid Range)
        start_angle = self.math_min + offset
        extent = self.math_max - self.math_min
        
        self.canvas.create_arc(cx - radius, cy - radius, cx + radius, cy + radius,
                                start=start_angle, extent=extent,
                                fill="#1a3a1a", outline="#44ff44", width=1, style=tk.PIESLICE)
        
        # Base marker
        self.canvas.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill="#ffffff", outline="#888888")
        self.canvas.create_text(cx, cy + 18, text="Base", fill="#888888", font=("Arial", 8))
        
        # Store base coords
        self.base_cx = cx
        self.base_cy = cy
    
    def _update_visualization(self):
        """Update target dot and vector based on slider values."""
        x = self.x_var.get()
        y = self.y_var.get()
        
        # Calculate theta1
        if x == 0 and y == 0:
            theta1 = 0
        else:
            theta1 = math.degrees(math.atan2(y, x))
        
        # Check validity
        is_valid = self.math_min <= theta1 <= self.math_max
        
        # Update output labels
        self.theta_var.set(f"{theta1:.1f}┬░")
        
        # Apply Polarity
        # physical = zero_offset + (theta * polarity)
        physical = self.zero_offset + (theta1 * self.slot1_polarity)
        self.physical_var.set(f"{physical:.1f}┬░")
        
        pulse = self.mapper.physical_to_pulse(physical, self.motor_config)
        self.pulse_var.set(f"{pulse} ╬╝s")
        
        if is_valid:
            self.valid_var.set("Γ£ô Valid")
            self.valid_label.configure(style="Valid.TLabel")
        else:
            self.valid_var.set("Γ£ù Out of Range")
            self.valid_label.configure(style="Invalid.TLabel")
        
        # Update canvas
        self._draw_target(x, y, is_valid)
    
    def _draw_target(self, x, y, is_valid):
        """Draw target dot and vector on canvas."""
        # Clear previous dynamic elements
        self.canvas.delete("dynamic")
        
        # Convert robot coords to canvas coords
        target_cx = self.base_cx + x * self.SCALE
        target_cy = self.base_cy - y * self.SCALE
        
        # Clamp to canvas
        target_cx = max(10, min(self.CANVAS_SIZE - 10, target_cx))
        target_cy = max(10, min(self.CANVAS_SIZE - 10, target_cy))
        
        # Color based on validity
        color = "#44ff44" if is_valid else "#ff4444"
        
        # Vector line
        self.canvas.create_line(self.base_cx, self.base_cy, target_cx, target_cy,
                                 fill=color, width=2, arrow=tk.LAST, tags="dynamic")
        
        # Target dot
        self.canvas.create_oval(target_cx - 8, target_cy - 8, target_cx + 8, target_cy + 8,
                                 fill=color, outline="#ffffff", width=2, tags="dynamic")
        
        self.canvas.create_text(target_cx, target_cy - 15, 
                                 text=f"({x:.0f}, {y:.0f})", fill=color, 
                                 font=("Consolas", 9), tags="dynamic")
    
    def _create_output_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Output", padding=10)
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        grid = ttk.Frame(frame)
        grid.pack(fill=tk.X)
        
        ttk.Label(grid, text="Math ╬╕1:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(grid, textvariable=self.theta_var, style="Result.TLabel").grid(row=0, column=1, sticky="w")
        
        ttk.Label(grid, text="Physical:").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Label(grid, textvariable=self.physical_var, style="Result.TLabel").grid(row=1, column=1, sticky="w")
        
        ttk.Label(grid, text="Pulse:").grid(row=2, column=0, sticky="w", padx=5)
        ttk.Label(grid, textvariable=self.pulse_var, style="Result.TLabel").grid(row=2, column=1, sticky="w")
        
        ttk.Label(grid, text="Status:").grid(row=3, column=0, sticky="w", padx=5)
        self.valid_label = ttk.Label(grid, textvariable=self.valid_var, style="Valid.TLabel")
        self.valid_label.grid(row=3, column=1, sticky="w")
    
    # === Tab 2: Dual View Methods ===
    
    def _draw_top_static(self):
        """Draw static elements on Tab 2 Top-Down canvas."""
        self.top_canvas.delete("static")
        cx, cy = 120, 120  # Center of 240x240 canvas
        
        # Grid
        for i in range(0, 241, 40):
            self.top_canvas.create_line(i, 0, i, 240, fill="#333", dash=(2, 4), tags="static")
            self.top_canvas.create_line(0, i, 240, i, fill="#333", dash=(2, 4), tags="static")
        
        # Axes
        self.top_canvas.create_line(cx, 0, cx, 240, fill="#555", tags="static")
        self.top_canvas.create_line(0, cy, 240, cy, fill="#555", tags="static")
        
        # Valid arc (╬╕1)
        radius = 100
        offset1 = self._get_tkinter_offset(self.slot1_type, self.slot1_min_pos)

        # Background Arc
        full_min = 0 - self.zero_offset
        self.top_canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius,
            start=full_min + offset1, extent=self.slot1_actuation_range,
            fill="#222222", outline="#444444", style=tk.PIESLICE, tags="static")

        # Foreground Arc
        self.top_canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius,
            start=self.math_min + offset1, extent=self.math_max - self.math_min,
            fill="#1a3a1a", outline="#44ff44", style=tk.PIESLICE, tags="static")
        
        # Base marker
        self.top_canvas.create_oval(cx-5, cy-5, cx+5, cy+5, fill="#fff", outline="#888", tags="static")
    
    def _draw_side_static(self):
        """Draw static elements on Tab 2 Side canvas."""
        self.side_canvas.delete("static")
        scale = 0.4  # px/mm
        shoulder_cx = 120
        shoulder_cy = 30 + (self.Z_MAX - self.d1) * scale
        base_cy = 30 + self.Z_MAX * scale
        
        # Grid
        for i in range(0, 241, 40):
            self.side_canvas.create_line(i, 0, i, 240, fill="#333", dash=(2, 4), tags="static")
            self.side_canvas.create_line(0, i, 240, i, fill="#333", dash=(2, 4), tags="static")
        
        # Ground
        self.side_canvas.create_line(0, base_cy, 240, base_cy, fill="#665544", width=2, tags="static")
        
        # Base to Shoulder (d1)
        self.side_canvas.create_line(shoulder_cx, base_cy, shoulder_cx, shoulder_cy,
            fill="#4488ff", width=4, tags="static")
        
        # Valid arc (╬╕2) from shoulder
        radius = self.a2 * scale
        offset2 = self._get_tkinter_offset(self.slot2_type, self.slot2_min_pos)

        # Background Arc (Full Actuation Range)
        # Transform physical range [0, actuation_range] to mathematical space
        # Math = (Physical - Zero) / Polarity
        # We need to find the "Math Angle" corresponding to Physical 0 and Physical Max
        
        phy_min = 0
        phy_max = self.slot2_actuation_range
        
        # Calculate math angles for physical limits
        math_angle_a = (phy_min - self.slot2_zero_offset) * self.slot2_polarity # Since math * pol = phy - zero -> math = (phy-zero)/pol? No. 
        # Formula: Physical = Zero + (Math * Polarity)
        # So: Math = (Physical - Zero) / Polarity
        # Or simply multiply by Polarity if Polarity is +/- 1
        
        math_angle_a = (phy_min - self.slot2_zero_offset) * self.slot2_polarity
        math_angle_b = (phy_max - self.slot2_zero_offset) * self.slot2_polarity
        
        # Determine start and extent
        # Tkinter arc: start is angle 1, extent is angle 2 - angle 1
        # We need the most Counter-Clockwise angle as Start (if extent is positive)
        # OR just use min/max of math angles
        
        arc_start = min(math_angle_a, math_angle_b)
        arc_extent = abs(math_angle_b - math_angle_a)
        
        # Add offset
        self.side_canvas.create_arc(shoulder_cx-radius, shoulder_cy-radius,
            shoulder_cx+radius, shoulder_cy+radius,
            start=arc_start + offset2, extent=arc_extent,
            fill="#222222", outline="#444444", style=tk.PIESLICE, tags="static")

        # Foreground Arc (Valid Software Range)
        # math_min and math_max are already sorted
        self.side_canvas.create_arc(shoulder_cx-radius, shoulder_cy-radius,
            shoulder_cx+radius, shoulder_cy+radius,
            start=self.theta2_min + offset2, extent=self.theta2_max - self.theta2_min,
            fill="#1a3a1a", outline="#44ff44", style=tk.PIESLICE, tags="static")
        
        # Base/Shoulder markers
        self.side_canvas.create_oval(shoulder_cx-4, base_cy-4, shoulder_cx+4, base_cy+4, fill="#fff", tags="static")
        self.side_canvas.create_oval(shoulder_cx-4, shoulder_cy-4, shoulder_cx+4, shoulder_cy+4, fill="#88aaff", tags="static")
    
    def _redraw_tab2(self):
        """Redraw Tab 2 static elements."""
        if hasattr(self, 'top_canvas'):
            self._draw_top_static()
            self._draw_side_static()
    
    def _update_tab2(self):
        """Update Tab 2 visualization."""
        x = self.x2_var.get()
        y = self.y2_var.get()
        z = self.z_var.get()
        
        # Calculate ╬╕1 (same formula as Tab 1)
        theta1 = math.degrees(math.atan2(y, x)) if (x != 0 or y != 0) else 0
        R = math.sqrt(x**2 + y**2)
        
        # Calculate ╬╕2
        s = z - self.d1
        theta2 = math.degrees(math.atan2(s, R)) if (R != 0 or s != 0) else 0
        
        # Validity
        valid1 = self.math_min <= theta1 <= self.math_max
        valid2 = self.theta2_min <= theta2 <= self.theta2_max
        
        # Update outputs
        self.theta1_tab2_var.set(f"{theta1:.1f}┬░")
        
        # Slot 1 Physical with Polarity
        phy1 = self.zero_offset + (theta1 * self.slot1_polarity)
        
        pulse1 = self.mapper.physical_to_pulse(phy1, self.motor_config)
        self.pulse1_tab2_var.set(f"{pulse1} ╬╝s")
        self.valid1_tab2_var.set("Γ£ô" if valid1 else "Γ£ù")
        
        self.theta2_var.set(f"{theta2:.1f}┬░")
        
        # Slot 2 Physical with Polarity
        phy2 = self.slot2_zero_offset + (theta2 * self.slot2_polarity)
        
        pulse2 = self.mapper.physical_to_pulse(phy2, self.slot2_config)
        self.pulse2_var.set(f"{pulse2} ╬╝s")
        self.valid2_var.set("Γ£ô" if valid2 else "Γ£ù")
        
        # Slot 3 (Elbow)
        theta3 = self.theta3_var.get()
        self.theta3_out_var.set(f"{theta3:.1f}┬░")
        
        # Slot 3 Physical with Polarity
        phy3 = self.slot3_zero_offset + (theta3 * self.slot3_polarity)
        
        pulse3 = self.mapper.physical_to_pulse(phy3, self.slot3_config)
        self.pulse3_var.set(f"{pulse3} ╬╝s")
        
        # Slot 3 Validity
        valid3 = self.theta3_min <= theta3 <= self.theta3_max
        self.valid3_var.set("Γ£ô" if valid3 else "Γ£ù")
        
        self.reach_var.set(f"{R:.0f} mm")
        self.height_var.set(f"{z:.0f} mm")
        
        # Draw targets (Pass theta3 and valid3)
        self._draw_tab2_targets(x, y, z, R, theta2, theta3, valid1, valid2, valid3)
    
    def _draw_tab2_targets(self, x, y, z, R, theta2, theta3, valid1, valid2, valid3):
        """Draw targets on Tab 2 canvases."""
        scale_top = 0.4
        scale_side = 0.4
        cx, cy = 120, 120
        
        # Top-Down target
        self.top_canvas.delete("dynamic")
        tx = cx + x * scale_top
        ty = cy - y * scale_top
        color1 = "#44ff44" if valid1 else "#ff4444"
        self.top_canvas.create_line(cx, cy, tx, ty, fill=color1, width=2, arrow=tk.LAST, tags="dynamic")
        self.top_canvas.create_oval(tx-5, ty-5, tx+5, ty+5, fill=color1, outline="#fff", tags="dynamic")
        
        # Side target
        self.side_canvas.delete("dynamic")
        shoulder_cx = 120
        shoulder_cy = 30 + (self.Z_MAX - self.d1) * scale_side
        base_cy = 30 + self.Z_MAX * scale_side
        
        # 1. Shoulder Joint (Fixed)
        self.side_canvas.create_oval(shoulder_cx-4, shoulder_cy-4, shoulder_cx+4, shoulder_cy+4, fill="#88aaff", tags="dynamic")
        
        # 2. Elbow Joint (FK: Rotation from Shoulder)
        # Global Angle: theta2 (relative to horizontal/ground? No, relative to 'min_pos')
        # We need logic for Frame of Reference.
        # usually theta2 is Shoulder Pitch relative to Horizon or Vertical.
        # Let's assume theta2 is relative to Horizon (0=Right).
        # Tkinter: 0=Right, 90=Down.
        # User defined: 0=Forward(Right), +Theta=Up(CCW).
        # So Canvas Angle = -Theta.
        
        # Shoulder Angle on Canvas
        offset2 = self._get_tkinter_offset(self.slot2_type, self.slot2_min_pos) 
        # offset2 ensures 0 deg aligns with screen Right.
        canvas_theta2 = -theta2 if offset2 == 0 else (theta2 + offset2) # Basic check. 
        # Refined: Visual 0 is Right. Math 0 is Right. Math + is Up (CCW). Tkinter + is Down (CW).
        # So Canvas Angle = -Theta.
        canvas_theta2_rad = math.radians(-theta2)

        elbow_cx = shoulder_cx + (self.a2 * scale_side) * math.cos(canvas_theta2_rad)
        elbow_cy = shoulder_cy + (self.a2 * scale_side) * math.sin(canvas_theta2_rad)
        
        # Link 1: Shoulder -> Elbow
        self.side_canvas.create_line(shoulder_cx, shoulder_cy, elbow_cx, elbow_cy,
            fill="#44ff88", width=3, tags="dynamic")
        self.side_canvas.create_oval(elbow_cx-3, elbow_cy-3, elbow_cx+3, elbow_cy+3,
            fill="#ffaa44", outline="#fff", tags="dynamic") # Elbow Joint Color
            
        # 3. Wrist Joint (FK: Rotation from Elbow)
        # Theta3 is Elbow Pitch. Relative to Upper Arm (Local) or Horizon (Global)?
        # Usually FK accumulates angles. Global = Theta2 + Theta3.
        # Math: +Theta3 is Up (CCW).
        
        global_theta3 = theta2 + theta3
        canvas_theta3_rad = math.radians(-global_theta3)
        
        wrist_cx = elbow_cx + (self.a3 * scale_side) * math.cos(canvas_theta3_rad)
        wrist_cy = elbow_cy + (self.a3 * scale_side) * math.sin(canvas_theta3_rad)
        
        # Link 2: Elbow -> Wrist
        self.side_canvas.create_line(elbow_cx, elbow_cy, wrist_cx, wrist_cy,
            fill="#ffff44", width=3, tags="dynamic")
        self.side_canvas.create_oval(wrist_cx-3, wrist_cy-3, wrist_cx+3, wrist_cy+3,
            fill="#ff4444", outline="#fff", tags="dynamic") # Wrist Joint
        
        # Target (Desired Position from Sliders)
        # Note: In 3-Link manual mode, X/Z sliders might just be 'ghost' targets or unused if we drive by angles.
        # But 'R' and 'z' come from sliders. Let's draw them as "Ghost Target".
        
        target_cx = shoulder_cx + R * scale_side
        target_cy = 30 + (self.Z_MAX - z) * scale_side
        color2 = "#44ff44" if valid2 else "#ff4444" # Using theta2 validity for target color for now
        
        self.side_canvas.create_line(shoulder_cx, shoulder_cy, target_cx, target_cy,
            fill=color2, width=1, dash=(4,4), arrow=tk.LAST, tags="dynamic")
        self.side_canvas.create_oval(target_cx-5, target_cy-5, target_cx+5, target_cy+5,
            fill=color2, outline="#fff", tags="dynamic")
        self.side_canvas.create_text(target_cx, target_cy-15, text="Target", fill=color2, font=("Arial",8), tags="dynamic")
    
    def _create_dual_output(self, parent):
        """Create output panel for Tab 2."""
        frame = ttk.LabelFrame(parent, text="Output", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        grid = ttk.Frame(frame)
        grid.pack(fill=tk.X)
        
        # Slot 1
        ttk.Label(grid, text="╬╕1:").grid(row=0, column=0, sticky="w", padx=2)
        ttk.Label(grid, textvariable=self.theta1_tab2_var, style="Result.TLabel").grid(row=0, column=1)
        ttk.Label(grid, textvariable=self.pulse1_tab2_var, style="Result.TLabel").grid(row=0, column=2, padx=5)
        ttk.Label(grid, textvariable=self.valid1_tab2_var, style="Valid.TLabel").grid(row=0, column=3)
        
        # Slot 2
        ttk.Label(grid, text="╬╕2:").grid(row=1, column=0, sticky="w", padx=2)
        ttk.Label(grid, textvariable=self.theta2_var, style="Result.TLabel").grid(row=1, column=1)
        ttk.Label(grid, textvariable=self.pulse2_var, style="Result.TLabel").grid(row=1, column=2, padx=5)
        ttk.Label(grid, textvariable=self.valid2_var, style="Valid.TLabel").grid(row=1, column=3)
        
        # Slot 3
        ttk.Label(grid, text="╬╕3:").grid(row=2, column=0, sticky="w", padx=2)
        ttk.Label(grid, textvariable=self.theta3_out_var, style="Result.TLabel").grid(row=2, column=1)
        ttk.Label(grid, textvariable=self.pulse3_var, style="Result.TLabel").grid(row=2, column=2, padx=5)
        ttk.Label(grid, textvariable=self.valid3_var, style="Valid.TLabel").grid(row=2, column=3)
        
        # Geometry
        ttk.Separator(grid, orient=tk.HORIZONTAL).grid(row=3, column=0, columnspan=4, sticky="ew", pady=3)
        ttk.Label(grid, text="Reach:").grid(row=4, column=0, sticky="w", padx=2)
        ttk.Label(grid, textvariable=self.reach_var, style="Result.TLabel").grid(row=4, column=1)
        ttk.Label(grid, text="Height:").grid(row=4, column=2, sticky="w", padx=2)
        ttk.Label(grid, textvariable=self.height_var, style="Result.TLabel").grid(row=4, column=3)
    
    def _create_control_panel(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.X, padx=10)
        
        ttk.Button(frame, text="Γû╢ Send", command=self._on_send).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="≡ƒÅá Zero", command=self._on_zero).pack(side=tk.LEFT, padx=5)
        
        # Motion Duration
        ttk.Separator(frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        ttk.Label(frame, text="Duration:").pack(side=tk.LEFT)
        ttk.Spinbox(frame, from_=0.1, to=2.0, increment=0.1,
                    textvariable=self.duration_var, width=4, format="%.1f").pack(side=tk.LEFT, padx=2)
        ttk.Label(frame, text="s").pack(side=tk.LEFT)
        
        # E-STOP
        estop = tk.Button(frame, text="E-STOP", bg="#ff4444", fg="white",
                          font=("Arial", 11, "bold"), width=8, command=self._on_estop)
        estop.pack(side=tk.RIGHT, padx=5)
    
    def _create_log_panel(self):
        frame = ttk.LabelFrame(self.root, text="Log", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = tk.Text(frame, height=5, bg="#1e1e1e", fg="#ffffff",
                                 font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def _log(self, msg):
        self.log_text.insert(tk.END, f"> {msg}\n")
        self.log_text.see(tk.END)
    
    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])
    
    def _load_saved_port(self):
        port = self.manager.get_saved_port()
        if port:
            self.port_var.set(port)
    
    def _on_connect(self):
        if self.is_connected:
            self.driver.disconnect()
            self.is_connected = False
            self.status_var.set("Disconnected")
            self.status_canvas.itemconfig(self.status_indicator, fill="#ff4444")
            self.connect_btn.config(text="Connect")
            self._log("Disconnected")
        else:
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "Select a COM port")
                return
            
            if self.driver.connect(port):
                self.is_connected = True
                self.status_var.set(f"Connected: {port}")
                self.status_canvas.itemconfig(self.status_indicator, fill="#44ff44")
                self.connect_btn.config(text="Disconnect")
                self._log(f"Connected to {port}")
            else:
                messagebox.showerror("Error", f"Failed to connect to {port}")
    
    def _on_send(self):
        if not self.is_connected:
            messagebox.showwarning("Warning", "Not connected")
            return
        
        # Check which tab is active
        current_tab = self.notebook.index(self.notebook.select())
        duration = self.duration_var.get()
        
        if current_tab == 0:
            # Tab 1: Slot 1 Only
            self._send_tab1(duration)
        else:
            # Tab 2: Slot 1 + Slot 2
            self._send_tab2(duration)
    
    def _send_tab1(self, duration):
        """Send Slot 1 command from Tab 1."""
        x = self.x_var.get()
        y = self.y_var.get()
        
        theta1 = math.degrees(math.atan2(y, x)) if (x != 0 or y != 0) else 0
        
        if theta1 < self.math_min or theta1 > self.math_max:
            messagebox.showwarning("Warning", f"╬╕1={theta1:.1f}┬░ out of range")
            return
        
        physical = self.zero_offset + (theta1 * self.slot1_polarity)
        pulse = self.mapper.physical_to_pulse(physical, self.motor_config)
        
        targets = [(self.channel, pulse)]
        self.motion_planner.move_all(targets, duration)
        self._log(f"[Tab1] Ch{self.channel}: {pulse}╬╝s (╬╕1={theta1:.1f}┬░)")
    
    def _send_tab2(self, duration):
        """Send Slot 1 + Slot 2 commands from Tab 2."""
        x = self.x2_var.get()
        y = self.y2_var.get()
        z = self.z_var.get()
        
        theta1 = math.degrees(math.atan2(y, x)) if (x != 0 or y != 0) else 0
        R = math.sqrt(x**2 + y**2)
        s = z - self.d1
        theta2 = math.degrees(math.atan2(s, R)) if (R != 0 or s != 0) else 0
        
        # Validate
        if theta1 < self.math_min or theta1 > self.math_max:
            messagebox.showwarning("Warning", f"╬╕1={theta1:.1f}┬░ out of range")
            return
        if theta2 < self.theta2_min or theta2 > self.theta2_max:
            messagebox.showwarning("Warning", f"╬╕2={theta2:.1f}┬░ out of range")
            return
        
        # Slot 3 (Elbow)
        theta3 = self.theta3_var.get()
        if theta3 < self.theta3_min or theta3 > self.theta3_max:
             messagebox.showwarning("Warning", f"╬╕3={theta3:.1f}┬░ out of range")
             return
        
        # Calculate pulses (Apply Polarity!)
        phy1 = self.zero_offset + (theta1 * self.slot1_polarity)
        pulse1 = self.mapper.physical_to_pulse(phy1, self.motor_config)
        
        phy2 = self.slot2_zero_offset + (theta2 * self.slot2_polarity)
        pulse2 = self.mapper.physical_to_pulse(phy2, self.slot2_config)
        
        phy3 = self.slot3_zero_offset + (theta3 * self.slot3_polarity)
        pulse3 = self.mapper.physical_to_pulse(phy3, self.slot3_config)
        
        targets = [(self.channel, pulse1), (self.slot2_channel, pulse2), (self.slot3_channel, pulse3)]
        self.motion_planner.move_all(targets, duration)
        self._log(f"[Tab2] Ch{self.channel}:{pulse1}, Ch{self.slot2_channel}:{pulse2}, Ch{self.slot3_channel}:{pulse3}")
    
    def _on_zero(self):
        """Set sliders to (100, 0) which gives Math 0."""
        self.x_var.set(100.0)
        self.y_var.set(0.0)
        self._update_visualization()
        self._log("Set to Math 0 (X=100, Y=0)")
    
    def _on_estop(self):
        self.motion_planner.stop()
        if self.is_connected:
            self.driver.release_all()
        self._log("!!! E-STOP !!!")
    
    def _on_close(self):
        self.sender_running = False
        self.motion_planner.stop()
        if self.is_connected:
            self.driver.release_all()
            self.driver.disconnect()
        self.root.destroy()
    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = Slot0Verifier()
    app.run()
