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
    
    # Canvas settings
    CANVAS_SIZE = 300
    SCALE = 0.5  # pixels per mm (300px / 600mm range)
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Slot 0 (Base Yaw) Visual Verifier")
        self.root.geometry("500x720")
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
        
        # Dynamic config (loaded per arm)
        self.channel = None
        self.zero_offset = None
        self.motor_config = None
        self.math_min = None
        self.math_max = None
        
        # Active arm (default: left)
        self.arm_var = tk.StringVar(value="left")
        self._apply_arm_config()
        
        # UI Variables
        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Disconnected")
        
        # Coordinate sliders
        self.x_var = tk.DoubleVar(value=100.0)
        self.y_var = tk.DoubleVar(value=0.0)
        
        # Motion duration
        self.duration_var = tk.DoubleVar(value=0.5)
        
        # Output
        self.theta_var = tk.StringVar(value="--")
        self.physical_var = tk.StringVar(value="--")
        self.pulse_var = tk.StringVar(value="--")
        self.valid_var = tk.StringVar(value="--")
        
        # Build UI
        self._create_styles()
        self._create_connection_panel()
        self._create_arm_panel()
        self._create_canvas_panel()
        self._create_output_panel()
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
        
        # Load from ServoManager
        self.channel = self.manager.get_channel(arm, 1)
        self.zero_offset = self.manager.get_zero_offset(arm, 1)
        self.motor_config = self._get_slot_config(arm, 1)
        
        # Calculate math_min/max from physical limits
        limits = self.manager.get_limits(arm, 1)
        self.math_min = limits["min"] - self.zero_offset
        self.math_max = limits["max"] - self.zero_offset
    
    def _get_slot_config(self, arm, slot):
        """Get motor config dict for PulseMapper."""
        slot_key = f"slot_{slot}"
        config = self.manager.config.get(arm, {}).get(slot_key, {})
        return {
            "actuation_range": config.get("actuation_range", 180),
            "pulse_min": config.get("pulse_min", 500),
            "pulse_max": config.get("pulse_max", 2500)
        }
    
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
        
        ttk.Button(frame, text="⟳", width=3, command=self._refresh_ports).pack(side=tk.RIGHT)
    
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
        self.channel_label = ttk.Label(frame, text=f"(Ch: {self.channel})", foreground="#888888")
        self.channel_label.pack(side=tk.LEFT, padx=20)
    
    def _on_arm_change(self):
        """Handle arm selection change."""
        self._apply_arm_config()
        self.channel_label.config(text=f"(Ch: {self.channel})")
        self._redraw_canvas()
        self._update_visualization()
        self._log(f"Switched to {self.arm_var.get().upper()} arm (Ch: {self.channel}, Zero: {self.zero_offset}°)")
    
    def _create_canvas_panel(self):
        """Create the visual canvas with axis-aligned sliders."""
        frame = ttk.LabelFrame(self.root, text="Workspace (Top View)", padding=5)
        frame.pack(fill=tk.BOTH, padx=10, pady=5)
        
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
        # Base at canvas center for full 360° view
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
        start_angle = self.math_min
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
        self.theta_var.set(f"{theta1:.1f}°")
        
        physical = theta1 + self.zero_offset
        self.physical_var.set(f"{physical:.1f}°")
        
        pulse = self.mapper.physical_to_pulse(physical, self.motor_config)
        self.pulse_var.set(f"{pulse} μs")
        
        if is_valid:
            self.valid_var.set("✓ Valid")
            self.valid_label.configure(style="Valid.TLabel")
        else:
            self.valid_var.set("✗ Out of Range")
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
        
        # Coordinate label
        self.canvas.create_text(target_cx, target_cy - 15, 
                                 text=f"({x:.0f}, {y:.0f})", fill=color, 
                                 font=("Consolas", 9), tags="dynamic")
    
    def _create_output_panel(self):
        frame = ttk.LabelFrame(self.root, text="Output", padding=10)
        frame.pack(fill=tk.X, padx=10, pady=5)
        
        grid = ttk.Frame(frame)
        grid.pack(fill=tk.X)
        
        ttk.Label(grid, text="Math θ1:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(grid, textvariable=self.theta_var, style="Result.TLabel").grid(row=0, column=1, sticky="w")
        
        ttk.Label(grid, text="Physical:").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Label(grid, textvariable=self.physical_var, style="Result.TLabel").grid(row=1, column=1, sticky="w")
        
        ttk.Label(grid, text="Pulse:").grid(row=2, column=0, sticky="w", padx=5)
        ttk.Label(grid, textvariable=self.pulse_var, style="Result.TLabel").grid(row=2, column=1, sticky="w")
        
        ttk.Label(grid, text="Status:").grid(row=3, column=0, sticky="w", padx=5)
        self.valid_label = ttk.Label(grid, textvariable=self.valid_var, style="Valid.TLabel")
        self.valid_label.grid(row=3, column=1, sticky="w")
    
    def _create_control_panel(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.X, padx=10)
        
        ttk.Button(frame, text="▶ Send", command=self._on_send).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="🏠 Zero", command=self._on_zero).pack(side=tk.LEFT, padx=5)
        
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
        
        x = self.x_var.get()
        y = self.y_var.get()
        
        if x == 0 and y == 0:
            theta1 = 0
        else:
            theta1 = math.degrees(math.atan2(y, x))
        
        # Check validity
        if theta1 < self.math_min or theta1 > self.math_max:
            messagebox.showwarning("Warning", f"Angle {theta1:.1f}° is out of range [{self.math_min:.1f}, {self.math_max:.1f}]")
            return
        
        physical = theta1 + self.zero_offset
        pulse = self.mapper.physical_to_pulse(physical, self.motor_config)
        
        # Use MotionPlanner for smooth motion
        targets = [(self.channel, pulse)]
        duration = self.duration_var.get()
        self.motion_planner.move_all(targets, duration)
        
        self._log(f"Moving ch{self.channel} to {pulse}μs over {duration:.1f}s (θ1={theta1:.1f}°, Phy={physical:.1f}°)")
    
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
