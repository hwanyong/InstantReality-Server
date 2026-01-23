
import tkinter as tk
from tkinter import ttk, messagebox
import math
from ..core import BaseTabController
from ..widgets import TopDownWidget, SideElevationWidget

class DualViewTab(BaseTabController):
    """
    Tab 2: Slot 1+2 Dual View with 3rd axis manual control.
    """
    
    # Config
    X_MIN = -300
    X_MAX = 300
    Y_MIN = -300
    Y_MAX = 300
    Z_MIN = -150
    Z_MAX = 360
    
    def build_ui(self):
        self.x_var = tk.DoubleVar(value=0.0)
        self.y_var = tk.DoubleVar(value=200.0)
        self.z_var = tk.DoubleVar(value=150.0) # Height Control (Z)
        
        self.main_frame = ttk.Frame(self.parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self._create_top_view(self.main_frame)
        self._create_side_view(self.main_frame)
        self._create_output_panel(self.main_frame)
        
    def _create_top_view(self, parent):
        frame = ttk.LabelFrame(parent, text="Top-Down (X/Y)", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=2)
        
        grid = ttk.Frame(frame)
        grid.pack(padx=2, pady=2)
        
        # Y2 Slider
        y_frame = ttk.Frame(grid)
        y_frame.grid(row=0, column=0, sticky="ns")
        ttk.Label(y_frame, text="Y").pack()
        self.y_slider = ttk.Scale(y_frame, from_=self.Y_MAX, to=self.Y_MIN,
            variable=self.y_var, orient=tk.VERTICAL, length=240,
            command=lambda v: self.update_visualization())
        self.y_slider.pack()
        
        # Canvas
        self.top_canvas = tk.Canvas(grid, width=240, height=240, bg="#1a1a2e")
        self.top_canvas.grid(row=0, column=1)
        
        self.top_widget = TopDownWidget(self.top_canvas, {
            'canvas_size': 240, 'scale': 0.4,
            'zero_offset': 0, 'actuation_range': 180, 'math_min': -90, 'math_max': 90
        })
        
        # X2 Slider
        x_frame = ttk.Frame(grid)
        x_frame.grid(row=1, column=1, sticky="ew")
        self.x_slider = ttk.Scale(x_frame, from_=self.X_MIN, to=self.X_MAX,
            variable=self.x_var, orient=tk.HORIZONTAL, length=240,
            command=lambda v: self.update_visualization())
        self.x_slider.pack()

        # Real-time State Frame (New)
        dyn_frame_s1 = ttk.Labelframe(grid, text="Real-time State", padding=5)
        dyn_frame_s1.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        self.lbl_angle_s1 = ttk.Label(dyn_frame_s1, text="Angle: --", font=("Consolas", 9))
        self.lbl_angle_s1.pack(anchor="w")
        
        self.lbl_pulse_s1 = ttk.Label(dyn_frame_s1, text="Pulse: --", font=("Consolas", 9))
        self.lbl_pulse_s1.pack(anchor="w")

        # Slot 1 Config Label (Expanded) - Moved to Row 3
        s1_frame = ttk.Labelframe(grid, text="Slot 1 Config", padding=5)
        s1_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        self.lbl_config_s1 = ttk.Label(s1_frame, text="--", font=("Consolas", 8), justify=tk.LEFT)
        self.lbl_config_s1.pack(anchor="w", fill=tk.X)

    def _create_side_view(self, parent):
        frame = ttk.LabelFrame(parent, text="Side (R/Z) + Elbow", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=2)
        
        grid = ttk.Frame(frame)
        grid.pack(padx=2, pady=2)
        
        # Slider (Z Height)
        t2_frame = ttk.Frame(grid)
        t2_frame.grid(row=0, column=0, sticky="ns")
        ttk.Label(t2_frame, text="Height").pack()
        self.z_slider = ttk.Scale(t2_frame, from_=360, to=-150,
            variable=self.z_var, orient=tk.VERTICAL, length=240,
            command=lambda v: self.update_visualization())
        self.z_slider.pack()
        
        # Canvas
        self.side_canvas = tk.Canvas(grid, width=240, height=240, bg="#1a2e1a")
        self.side_canvas.grid(row=0, column=1)
        
        self.side_widget = SideElevationWidget(self.side_canvas, {
            'canvas_size': 240, 'scale': 0.4, 'z_max': 300,
            'd1': 107, 'a2': 105
        })
        
        # Info Panel (Grey Area)
        # Split into Dynamic (Top) and Static (Bottom)
        
        # 1. Dynamic Info Frame
        dyn_frame = ttk.Labelframe(grid, text="Real-time State", padding=5)
        dyn_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        self.lbl_target = ttk.Label(dyn_frame, text="Target: X=-- Y=-- Z=--", font=("Consolas", 9, "bold"))
        self.lbl_target.pack(anchor="w", pady=(0, 2))
        

        
        self.lbl_angle = ttk.Label(dyn_frame, text="Angle: --", font=("Consolas", 9))
        self.lbl_angle.pack(anchor="w")
        
        self.lbl_pulse = ttk.Label(dyn_frame, text="Pulse: --", font=("Consolas", 9))
        self.lbl_pulse.pack(anchor="w")
        
        self.lbl_warning = ttk.Label(dyn_frame, text="", font=("Consolas", 9, "bold"), foreground="red")
        self.lbl_warning.pack(anchor="w")
        
        # 2. Static Config Frame (Slot 2 Only)
        static_frame = ttk.Labelframe(grid, text="Slot 2 Config", padding=5)
        static_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        
        # Auto-expanding Label instead of Scrollbar/Text
        self.lbl_config_s2 = ttk.Label(static_frame, text="--", font=("Consolas", 8), justify=tk.LEFT)
        self.lbl_config_s2.pack(anchor="w", fill=tk.X)

    def _create_output_panel(self, parent):
        # Placeholder for output vars
        self.theta1_var = tk.StringVar(value="--")
        self.theta2_var_disp = tk.StringVar(value="--")
        # self.theta3_out_var = tk.StringVar(value="--") # Removed
        # In real impl, add labels...
        # For brevity, skipping full label creation in this snippet 
        # but logic vars are needed.

    def on_enter(self):
        self._refresh_config()
        self.top_widget.draw_static()
        self.side_widget.draw_static()
        self.update_visualization()

    def on_config_updated(self):
        """Handle config reload."""
        self.context.log("[Dual] Config Reloaded")
        self._refresh_config()
        self.top_widget.draw_static()
        self.side_widget.draw_static()
        self.update_visualization()

    def _refresh_config(self):
        p1 = self.context.get_slot_params(1)
        p2 = self.context.get_slot_params(2)
        p3 = self.context.get_slot_params(3) # Load P3 for IK (a3)
        
        if p1:
            self.top_widget.cfg.update(p1)
            self.p1 = p1
            # Update Height (d1)
            d1 = p1.get('length', 107)
            self.side_widget.cfg['d1'] = d1
            self.d1_val = d1
            
        if p2:
            self.side_widget.cfg['slot2_params'] = p2
            self.p2 = p2
            # Update Length (a2)
            a2 = p2.get('length', 105)
            self.side_widget.cfg['a2'] = a2
            self.a2_val = a2 

        if p3:
            self.p3 = p3 

        # Update Static Config Dump (Split)
        arm = self.context.get_current_arm()
        raw_cfg = self.context.manager.config.get(arm, {})
        
        def format_slot(slot_num):
            s_key = f"slot_{slot_num}"
            data = raw_cfg.get(s_key, {})
            lines = []
            for k, v in data.items():
                lines.append(f"{k}: {v}")
            return "\n".join(lines)
            
        # Slot 1 -> Top View
        self.lbl_config_s1.config(text=format_slot(1))
        
        # Slot 2 -> Side View
        self.lbl_config_s2.config(text=format_slot(2)) 

    def update_visualization(self):
        x = self.x_var.get()
        y = self.y_var.get()
        z = self.z_var.get()
        
        # Update Target Label
        self.lbl_target.config(text=f"Target: X={x:.0f} Y={y:.0f} Z={z:.0f}")
        
        # θ1 Calculation
        theta1 = math.degrees(math.atan2(y, x)) if (x != 0 or y != 0) else 0
        R = math.sqrt(x**2 + y**2)
        
        # Update Slot 1 Real-time Labels
        pulse_calc_s1 = "--"
        pulse_sent_s1 = "--"
        phy_angle_s1 = theta1 # Default
        
        if hasattr(self, 'p1'):
             mapper = self.context.mapper
             zero_offset = self.p1.get('zero_offset', 0)
             act_range = self.p1.get('actuation_range', 180)
             
             phy_angle_s1 = theta1 + zero_offset
             phy_angle_s1 = max(0, min(act_range, phy_angle_s1)) # Clamp
             
             pulse_val_s1 = mapper.physical_to_pulse(phy_angle_s1, self.p1['motor_config'])
             pulse_calc_s1 = f"{pulse_val_s1}"
             pulse_sent_s1 = f"{pulse_val_s1}"
             
        self.lbl_angle_s1.config(text=f"Angle: [sync] {theta1:.1f} (Vis) | {theta1:.1f} (In) | {phy_angle_s1:.1f} (Phy)")
        self.lbl_pulse_s1.config(text=f"Pulse: [sync] -- (R) | {pulse_calc_s1} (C) | {pulse_sent_s1} (S)")
        
        # --- IK Calculation for Slot 2 (Shoulder) ---
        # Constants
        d1 = 107.0
        a2 = 105.0
        a3 = 150.0 
        # Attempt to load exacts
        if hasattr(self, 'p1'): d1 = self.p1.get('length', 107.0)
        if hasattr(self, 'p2'): a2 = self.p2.get('length', 105.0)
        if hasattr(self, 'p3'): a3 = self.p3.get('length', 150.0)
        
        # S: Vertical distance from shoulder pivot
        s = z - d1
        
        # D: Direct distance
        D_sq = R**2 + s**2
        D = math.sqrt(D_sq)
        
        theta2 = 0.0
        
        # Reachability Check
        max_reach = a2 + a3
        min_reach = abs(a3 - a2)
        
        # IK Math
        if min_reach <= D <= max_reach:
            # Law of Cosines for Theta3
            cos_t3 = (D_sq - a2**2 - a3**2) / (2 * a2 * a3)
            cos_t3 = max(-1.0, min(1.0, cos_t3))
            t3_math = math.degrees(math.acos(cos_t3))
            
            # Left Arm uses Elbow Up (-t3)
            ar = "left_arm"
            if self.context and self.context.get_current_arm:
                ar = self.context.get_current_arm()
            
            if ar == "left_arm":
                t3_math = -t3_math 
            
            # Theta 2
            alpha = math.atan2(s, R)
            beta = math.atan2(a3 * math.sin(math.radians(t3_math)),
                             a2 + a3 * math.cos(math.radians(t3_math)))
            theta2 = math.degrees(alpha - beta)
        
        # Update Grey Area Labels
        # 2. Pulse: {Calc} | {Sent}
        pulse_calc = "--"
        pulse_sent = "--"
        phy_angle = theta2 # Default
        
        if hasattr(self, 'p2'):
            mapper = self.context.mapper
            
            # Physical angle calculation
            zero_offset = self.p2.get('zero_offset', 0)
            act_range = self.p2.get('actuation_range', 180)
            
            phy_angle = theta2 + zero_offset
            phy_angle = max(0, min(act_range, phy_angle)) # Clamp
            
            pulse_val = mapper.physical_to_pulse(phy_angle, self.p2['motor_config'])
            
            pulse_calc = f"{pulse_val}"
            pulse_sent = f"{pulse_val}" 
            
        # 1. Angle: {Visual} | {Input} | {Physical}
        # {Visual}(Shoulder) | {IK}(Shoulder) | {Physical}(Shoulder)
        self.lbl_angle.config(text=f"Angle: [sync] {theta2:.1f} (Vis) | {theta2:.1f} (IK) | {phy_angle:.1f} (Phy)")
        self.lbl_pulse.config(text=f"Pulse: [sync] -- (R) | {pulse_calc} (C) | {pulse_sent} (S)")
        
        # Validity
        valid1 = False
        valid2 = False
        if hasattr(self, 'p1'):
            valid1 = self.p1['math_min'] <= theta1 <= self.p1['math_max']
            self.top_widget.update_target(x, y, valid1)
        if hasattr(self, 'p2'):
            valid2 = self.p2['math_min'] <= theta2 <= self.p2['math_max']
            
        # Update Side Widget
        self.side_widget.update_target(R, theta2, valid2)
        
        # Config-based Validation
        self.is_valid_target = True  # Default
        if hasattr(self, 'p2'):
            phy_min = self.p2.get('min', 0)
            phy_max = self.p2.get('max', 270)
            
            if phy_min <= phy_angle <= phy_max:
                self.lbl_warning.config(text="")
            else:
                self.is_valid_target = False
                self.lbl_warning.config(text=f"⚠️ Out of Range [{phy_min:.0f}~{phy_max:.0f}]")
        
        # Store calculated values
        self.calculated_theta1 = theta1
        self.calculated_theta2 = theta2
        
    def send_command(self, duration):
        # Validate
        if not all(hasattr(self, k) for k in ['p1', 'p2']): return
        
        # Safety Gate: Block if target is out of range
        if not getattr(self, 'is_valid_target', False):
            self.logger.log("[Dual] BLOCKED: Target out of valid range.")
            return
        
        t1 = self.calculated_theta1
        t2 = self.calculated_theta2
        
        # Check limits (optional here if checked in math)
        
        mapper = self.context.mapper
        
        # Slot 1
        # phy1 = t1 + zero_offset
        zero_off1 = self.p1.get('zero_offset', 0)
        phy1 = max(0, min(self.p1.get('actuation_range', 180), t1 + zero_off1))
        pls1 = mapper.physical_to_pulse(phy1, self.p1['motor_config'])
        
        # Slot 2 (Shoulder)
        # phy2 = t2 + zero_offset
        zero_off2 = self.p2.get('zero_offset', 0)
        phy2 = max(0, min(self.p2.get('actuation_range', 180), t2 + zero_off2))
        pls2 = mapper.physical_to_pulse(phy2, self.p2['motor_config'])
        
        targets = [
            (self.p1['channel'], pls1),
            (self.p2['channel'], pls2)
        ]
        self.context.motion_planner.move_all(targets, duration)
        self.logger.log(f"[Dual] Sent Ch{self.p1['channel']}:{pls1} (Phy1={phy1:.1f}), Ch{self.p2['channel']}:{pls2} (Phy2={phy2:.1f})")

