
import tkinter as tk
from tkinter import ttk
import math
from ..core import BaseTabController
from ..widgets import TopDownWidget, SideElevation3LinkWidget


class TripleViewTab(BaseTabController):
    """
    Tab 3: Slot 1+2+3 Visual Prototype.
    Phase 2: Manual sliders, hardcoded FK rendering, no config binding.
    """
    
    def build_ui(self):
        # --- UI Variables ---
        self.theta1_var = tk.DoubleVar(value=0.0)  # Base Yaw
        self.theta2_var = tk.DoubleVar(value=0.0)  # Shoulder Pitch
        self.theta3_var = tk.DoubleVar(value=0.0)  # Elbow Pitch
        
        self.main_frame = ttk.Frame(self.parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self._create_top_view(self.main_frame)
        self._create_side_view(self.main_frame)
        self._create_info_panel(self.main_frame)
    
    def _create_top_view(self, parent):
        """Create Top-Down view for θ1 (Base Yaw)."""
        frame = ttk.LabelFrame(parent, text="Top-Down (θ1)", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=2)
        
        grid = ttk.Frame(frame)
        grid.pack(padx=2, pady=2)
        
        # θ1 Slider (Vertical orientation to match Y-axis feel)
        t1_frame = ttk.Frame(grid)
        t1_frame.grid(row=0, column=0, sticky="ns")
        ttk.Label(t1_frame, text="θ1").pack()
        self.theta1_slider = ttk.Scale(
            t1_frame, from_=90, to=-90,
            variable=self.theta1_var, orient=tk.VERTICAL, length=240,
            command=lambda v: self.update_visualization()
        )
        self.theta1_slider.pack()
        
        # Canvas
        self.top_canvas = tk.Canvas(grid, width=240, height=240, bg="#1a1a2e")
        self.top_canvas.grid(row=0, column=1)
        
        # Simple hardcoded TopDownWidget config
        self.top_widget = TopDownWidget(self.top_canvas, {
            'canvas_size': 240, 'scale': 0.4,
            'zero_offset': 0, 'actuation_range': 180, 
            'math_min': -90, 'math_max': 90
        })
        
        # Slot 1 State Label
        state_frame = ttk.Labelframe(grid, text="Slot 1 State", padding=5)
        state_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        self.lbl_theta1 = ttk.Label(state_frame, text="θ1: 0.0°", font=("Consolas", 10))
        self.lbl_theta1.pack(anchor="w")
        
        self.lbl_pulse1 = ttk.Label(state_frame, text="Pulse: -- (no config)", font=("Consolas", 9))
        self.lbl_pulse1.pack(anchor="w")
    
    def _create_side_view(self, parent):
        """Create Side Elevation view for θ2, θ3 (Shoulder + Elbow)."""
        frame = ttk.LabelFrame(parent, text="Side (θ2 + θ3)", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=2)
        
        grid = ttk.Frame(frame)
        grid.pack(padx=2, pady=2)
        
        # θ2 Slider (Shoulder)
        t2_frame = ttk.Frame(grid)
        t2_frame.grid(row=0, column=0, sticky="ns")
        ttk.Label(t2_frame, text="θ2").pack()
        self.theta2_slider = ttk.Scale(
            t2_frame, from_=90, to=-90,
            variable=self.theta2_var, orient=tk.VERTICAL, length=110,
            command=lambda v: self.update_visualization()
        )
        self.theta2_slider.pack()
        
        # θ3 Slider (Elbow)
        t3_frame = ttk.Frame(grid)
        t3_frame.grid(row=0, column=2, sticky="ns")
        ttk.Label(t3_frame, text="θ3").pack()
        self.theta3_slider = ttk.Scale(
            t3_frame, from_=90, to=-90,
            variable=self.theta3_var, orient=tk.VERTICAL, length=110,
            command=lambda v: self.update_visualization()
        )
        self.theta3_slider.pack()
        
        # Canvas
        self.side_canvas = tk.Canvas(grid, width=240, height=240, bg="#1a2e1a")
        self.side_canvas.grid(row=0, column=1)
        
        # 3-Link Widget (hardcoded)
        self.side_widget = SideElevation3LinkWidget(self.side_canvas, {
            'canvas_size': 240
        })
        
        # Slot 2 State Label
        s2_frame = ttk.Labelframe(grid, text="Slot 2 State", padding=5)
        s2_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        
        self.lbl_theta2 = ttk.Label(s2_frame, text="θ2: 0.0°", font=("Consolas", 10))
        self.lbl_theta2.pack(anchor="w")
        
        self.lbl_pulse2 = ttk.Label(s2_frame, text="Pulse: -- (no config)", font=("Consolas", 9))
        self.lbl_pulse2.pack(anchor="w")
        
        # Slot 3 State Label
        s3_frame = ttk.Labelframe(grid, text="Slot 3 State", padding=5)
        s3_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        
        self.lbl_theta3 = ttk.Label(s3_frame, text="θ3: 0.0° (relative)", font=("Consolas", 10))
        self.lbl_theta3.pack(anchor="w")
        
        self.lbl_pulse3 = ttk.Label(s3_frame, text="Pulse: -- (no config)", font=("Consolas", 9))
        self.lbl_pulse3.pack(anchor="w")
    
    def _create_info_panel(self, parent):
        """Create info/status panel."""
        frame = ttk.LabelFrame(parent, text="Phase 2 Prototype", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        
        info_text = """[ Phase 2 Visual Prototype ]

• θ1: Base Yaw (Top View)
• θ2: Shoulder Pitch
• θ3: Elbow Pitch (relative)

[ Status ]
• Config Binding: OFF
• IK Calculation: OFF
• Pulse Transmission: OFF

[ Hardcoded Values ]
• d1 = 40px (base height)
• a2 = 40px (upper arm)
• a3 = 60px (forearm)

[ Next Phase ]
→ Config Binding
→ Zero Offset Alignment
→ Pulse Calculation
"""
        ttk.Label(frame, text=info_text, font=("Consolas", 9), justify=tk.LEFT).pack(anchor="nw")
    
    def on_enter(self):
        """Called when tab is selected."""
        self.top_widget.draw_static()
        self.side_widget.draw_static()
        self.update_visualization()
    
    def on_config_updated(self):
        """Handle config reload - Phase 2: No-op."""
        self.log("[TripleView] Config updated (no binding in Phase 2)")
    
    def update_visualization(self):
        """Update visualizations based on slider values."""
        theta1 = self.theta1_var.get()
        theta2 = self.theta2_var.get()
        theta3 = self.theta3_var.get()
        
        # Update state labels
        self.lbl_theta1.config(text=f"θ1: {theta1:.1f}°")
        self.lbl_theta2.config(text=f"θ2: {theta2:.1f}°")
        self.lbl_theta3.config(text=f"θ3: {theta3:.1f}° (relative)")
        
        # Update Top View - simple vector at θ1
        # Calculate X, Y from angle for TopDownWidget
        R = 150  # Fixed radius for visualization
        x = R * math.cos(math.radians(theta1))
        y = R * math.sin(math.radians(theta1))
        self.top_widget.update_target(x, y, True)
        
        # Update Side View - 3-Link FK
        self.side_widget.update_target(theta2, theta3)
    
    def send_command(self, duration):
        """Send command - Phase 2: Log only, no actual transmission."""
        theta1 = self.theta1_var.get()
        theta2 = self.theta2_var.get()
        theta3 = self.theta3_var.get()
        
        self.log(f"[TripleView] Phase 2 - Would send: θ1={theta1:.1f}°, θ2={theta2:.1f}°, θ3={theta3:.1f}° (no config binding)")
