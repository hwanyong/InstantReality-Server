
import tkinter as tk
from tkinter import ttk, messagebox
import math
from ..core import BaseTabController
from ..widgets import TopDownWidget

class Slot1Tab(BaseTabController):
    """
    Tab 1: Slot 1 (Base Yaw) Verification.
    """
    
    # Workspace Config
    X_MIN = -300
    X_MAX = 300
    Y_MIN = -300
    Y_MAX = 300
    CANVAS_SIZE = 300
    SCALE = 0.5
    
    def build_ui(self):
        # UI State Variables
        self.x_var = tk.DoubleVar(value=100.0)
        self.y_var = tk.DoubleVar(value=0.0)
        
        self.theta_var = tk.StringVar(value="--")
        self.physical_var = tk.StringVar(value="--")
        self.pulse_var = tk.StringVar(value="--")
        self.valid_var = tk.StringVar(value="--")
        
        self._create_canvas_panel()
        self._create_output_panel()
        
    def _create_canvas_panel(self):
        frame = ttk.LabelFrame(self.parent, text="Workspace (Top View)", padding=5)
        frame.pack(fill=tk.BOTH, padx=5, pady=5)
        
        grid = ttk.Frame(frame)
        grid.pack()
        
        # Y Slider (Left)
        y_frame = ttk.Frame(grid)
        y_frame.grid(row=0, column=0, sticky="ns")
        ttk.Label(y_frame, text="Y", font=("Arial", 9)).pack()
        self.y_slider = ttk.Scale(y_frame, from_=self.Y_MAX, to=self.Y_MIN,
                                  variable=self.y_var, orient=tk.VERTICAL,
                                  length=self.CANVAS_SIZE,
                                  command=lambda v: self.update_visualization())
        self.y_slider.pack(pady=5)
        
        # Canvas (Center)
        self.canvas = tk.Canvas(grid, width=self.CANVAS_SIZE, height=self.CANVAS_SIZE,
                                bg="#1a1a2e", highlightthickness=1, highlightbackground="#444")
        self.canvas.grid(row=0, column=1)
        
        # Initialize Widget
        self.widget_config = {
            'canvas_size': self.CANVAS_SIZE,
            'scale': self.SCALE,
            'type': 'horizontal', # Default, will update on enter
            'min_pos': 'left',
            'zero_offset': 0.0,
            'actuation_range': 180,
            'math_min': -90,
            'math_max': 90
        }
        self.widget = TopDownWidget(self.canvas, self.widget_config)
        
        # X Slider (Bottom)
        x_frame = ttk.Frame(grid)
        x_frame.grid(row=1, column=1, sticky="ew")
        self.x_slider = ttk.Scale(x_frame, from_=self.X_MIN, to=self.X_MAX,
                                  variable=self.x_var, orient=tk.HORIZONTAL,
                                  length=self.CANVAS_SIZE,
                                  command=lambda v: self.update_visualization())
        self.x_slider.pack()
        ttk.Label(x_frame, text="X", font=("Arial", 9)).pack()

    def _create_output_panel(self):
        frame = ttk.LabelFrame(self.parent, text="Output", padding=10)
        frame.pack(fill=tk.X, padx=5, pady=5)
        
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

    def on_enter(self):
        """Called when tab is selected. Refresh config."""
        self._refresh_config()
        self.widget.draw_static() # Redraw using new config
        self.update_visualization()

    def _refresh_config(self):
        """Fetch latest slot 1 config from context."""
        arm = self.context.get_current_arm() # Need this method in context or similar
        # Actually context is IKTesterApp, let's assume it has get_slot_config helper
        
        # For now, let's access manager directly if needed, but context helper is better.
        # Let's assume context exposes:
        # channel1, zero_offset1, motor_config1, polarity1, math_min1, math_max1, etc.
        # But this couples Tab to Context implementation details.
        # Better: context.get_slot_params(slot_id) returns dict.
        
        params = self.context.get_slot_params(1)
        if params:
            self.widget.cfg.update(params)
            
            # Update internal references/cache
            self.math_min = params['math_min']
            self.math_max = params['math_max']
            self.polarity = params['polarity']
            self.zero_offset = params['zero_offset']
            self.channel = params['channel']
            self.motor_config = params['motor_config']

    def update_visualization(self):
        x = self.x_var.get()
        y = self.y_var.get()
        
        if x == 0 and y == 0:
            theta1 = 0
        else:
            theta1 = math.degrees(math.atan2(y, x))
            
        # Check validity
        if not hasattr(self, 'math_min'): self._refresh_config()
        is_valid = self.math_min <= theta1 <= self.math_max
        
        self.theta_var.set(f"{theta1:.1f}°")
        
        # Physical
        physical = self.zero_offset + (theta1 * self.polarity)
        self.physical_var.set(f"{physical:.1f}°")
        
        # Pulse
        mapper = self.context.mapper # Access PulseMapper from context
        pulse = mapper.physical_to_pulse(physical, self.motor_config)
        self.pulse_var.set(f"{pulse} μs")
        
        if is_valid:
            self.valid_var.set("✓ Valid")
            if hasattr(self, 'valid_label'): self.valid_label.configure(style="Valid.TLabel")
        else:
            self.valid_var.set("✗ Out of Range")
            if hasattr(self, 'valid_label'): self.valid_label.configure(style="Invalid.TLabel")
            
        self.widget.update_target(x, y, is_valid)

    def send_command(self, duration):
        """Called by main app Send button."""
        x = self.x_var.get()
        y = self.y_var.get()
        theta1 = math.degrees(math.atan2(y, x)) if (x != 0 or y != 0) else 0
        
        if theta1 < self.math_min or theta1 > self.math_max:
             messagebox.showwarning("Warning", f"θ1={theta1:.1f}° out of range")
             return
             
        physical = self.zero_offset + (theta1 * self.polarity)
        mapper = self.context.mapper
        pulse = mapper.physical_to_pulse(physical, self.motor_config)
        
        targets = [(self.channel, pulse)]
        self.context.motion_planner.move_all(targets, duration)
        self.log(f"[Tab1] Ch{self.channel}: {pulse}μs (θ1={theta1:.1f}°)")

