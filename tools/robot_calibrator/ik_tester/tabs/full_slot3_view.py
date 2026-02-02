
import tkinter as tk
from tkinter import ttk
import math
from ..core import BaseTabController
from .full_slot3_widgets import TopDownWidget3, SideElevation4LinkWidget3, GripperStateWidget3



class FullSlot3Tab(BaseTabController):
    """
    Tab 6: Full Slot 3 - Independent copy of Tab 5 for customization.
    - Top View: X/Y sliders, θ1 auto-calculated
    - Side View: θ2/θ3 via IK, θ4 approach angle, 4-Link FK rendering
    (Tab 6 Independent Copy)
    """
    
    # Range constants (same as DualViewTab)
    X_MIN = -300
    X_MAX = 300
    Y_MIN = -300
    Y_MAX = 300
    
    def build_ui(self):
        # --- UI Variables ---
        self.x_var = tk.DoubleVar(value=0.0)
        self.y_var = tk.DoubleVar(value=200.0)
        self.z_var = tk.DoubleVar(value=150.0)  # Z Height for IK
        self.roll_var = tk.DoubleVar(value=90.0)   # Slot 5 (Roll) - manual
        self.gripper_var = tk.DoubleVar(value=0.0)  # Slot 6 (Gripper) - manual
        
        self.main_frame = ttk.Frame(self.parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self._create_top_view(self.main_frame)
        self._create_side_view(self.main_frame)
        self._create_info_panel(self.main_frame)
    
    def _create_top_view(self, parent):
        """Create Top-Down view for X/Y input (same as DualViewTab)."""
        frame = ttk.LabelFrame(parent, text="Top-Down (X/Y)", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=2)
        
        grid = ttk.Frame(frame)
        grid.pack(padx=2, pady=2)
        
        # Y Slider (Vertical, left of canvas)
        y_frame = ttk.Frame(grid)
        y_frame.grid(row=0, column=0, sticky="ns")
        ttk.Label(y_frame, text="Y").pack()
        self.y_slider = ttk.Scale(
            y_frame, from_=self.Y_MAX, to=self.Y_MIN,
            variable=self.y_var, orient=tk.VERTICAL, length=240,
            command=lambda v: self.update_visualization()
        )
        self.y_slider.pack()
        
        # Canvas
        self.top_canvas = tk.Canvas(grid, width=240, height=240, bg="#1a1a2e")
        self.top_canvas.grid(row=0, column=1)
        
        # TopDownWidget3 (config will be updated in _refresh_config)
        self.top_widget = TopDownWidget3(self.top_canvas, {
            'canvas_size': 240, 'scale': 0.4,
            'zero_offset': 0, 'actuation_range': 180,
            'math_min': -90, 'math_max': 90
        })
        
        # X Slider (Horizontal, below canvas)
        x_frame = ttk.Frame(grid)
        x_frame.grid(row=1, column=1, sticky="ew")
        self.x_slider = ttk.Scale(
            x_frame, from_=self.X_MIN, to=self.X_MAX,
            variable=self.x_var, orient=tk.HORIZONTAL, length=240,
            command=lambda v: self.update_visualization()
        )
        self.x_slider.pack()
        
        # Real-time State Frame
        dyn_frame_s1 = ttk.Labelframe(grid, text="Slot 1 Real-time State", padding=5)
        dyn_frame_s1.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        self.lbl_angle_s1 = ttk.Label(dyn_frame_s1, text="Angle: --", font=("Consolas", 9))
        self.lbl_angle_s1.pack(anchor="w")
        
        self.lbl_pulse_s1 = ttk.Label(dyn_frame_s1, text="Pulse: --", font=("Consolas", 9))
        self.lbl_pulse_s1.pack(anchor="w")
        
        # Slot 1 Config Label
        s1_frame = ttk.Labelframe(grid, text="Slot 1 Config", padding=5)
        s1_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        self.lbl_config_s1 = ttk.Label(s1_frame, text="--", font=("Consolas", 8), justify=tk.LEFT)
        self.lbl_config_s1.pack(anchor="w", fill=tk.X)
    
    # Z Range constants for IK
    Z_MIN = -148
    Z_MAX = 362
    
    def _create_side_view(self, parent):
        """Create Side Elevation view with IK mode (Z input → θ2, θ3 auto-calculated)."""
        frame = ttk.LabelFrame(parent, text="Side (IK: R,Z → θ2,θ3)", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=2)
        
        grid = ttk.Frame(frame)
        grid.pack(padx=2, pady=2)
        
        # Z Slider (Height input for IK)
        z_frame = ttk.Frame(grid)
        z_frame.grid(row=0, column=0, sticky="ns")
        ttk.Label(z_frame, text="Z").pack()
        self.z_slider = ttk.Scale(
            z_frame, from_=self.Z_MAX, to=self.Z_MIN,
            variable=self.z_var, orient=tk.VERTICAL, length=220,
            command=lambda v: self.update_visualization()
        )
        self.z_slider.pack()
        
        # Canvas
        self.side_canvas = tk.Canvas(grid, width=240, height=240, bg="#1a2e1a")
        self.side_canvas.grid(row=0, column=1)
        
        # 4-Link Widget3 (includes Slot 4 wrist rendering)
        self.side_widget = SideElevation4LinkWidget3(self.side_canvas, {
            'canvas_size': 240
        })
        
        # Real-time State Frame (Target + Warning)
        dyn_frame = ttk.Labelframe(grid, text="Real-time State", padding=5)
        dyn_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        
        self.lbl_target = ttk.Label(dyn_frame, text="Target: R=-- Z=--", font=("Consolas", 9, "bold"))
        self.lbl_target.pack(anchor="w")
        
        self.lbl_warning = ttk.Label(dyn_frame, text="", font=("Consolas", 9, "bold"), foreground="red")
        self.lbl_warning.pack(anchor="w")
        
        # --- Compact Slot Status Row (horizontal grid under canvas) ---
        slots_frame = ttk.Frame(grid)
        slots_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        
        # Configure grid columns to expand evenly (6 columns: S2-S6 + gripper)
        for i in range(6):
            slots_frame.columnconfigure(i, weight=1)
        
        # Slot 2 (Shoulder) - Compact
        s2_frame = ttk.LabelFrame(slots_frame, text="S2", padding=2)
        s2_frame.grid(row=0, column=0, padx=1, pady=1, sticky="nsew")
        self.lbl_theta2 = ttk.Label(s2_frame, text="θ: 0.0°", font=("Consolas", 7))
        self.lbl_theta2.pack(anchor="w")
        self.lbl_pulse2 = ttk.Label(s2_frame, text="P: --", font=("Consolas", 7))
        self.lbl_pulse2.pack(anchor="w")
        
        # Slot 3 (Elbow) - Compact
        s3_frame = ttk.LabelFrame(slots_frame, text="S3", padding=2)
        s3_frame.grid(row=0, column=1, padx=1, pady=1, sticky="nsew")
        self.lbl_theta3 = ttk.Label(s3_frame, text="θ: 0.0°", font=("Consolas", 7))
        self.lbl_theta3.pack(anchor="w")
        self.lbl_pulse3 = ttk.Label(s3_frame, text="P: --", font=("Consolas", 7))
        self.lbl_pulse3.pack(anchor="w")
        
        # Slot 4 (Wrist Pitch) - Compact
        s4_frame = ttk.LabelFrame(slots_frame, text="S4", padding=2)
        s4_frame.grid(row=0, column=2, padx=1, pady=1, sticky="nsew")
        self.lbl_theta4 = ttk.Label(s4_frame, text="θ: 0.0°", font=("Consolas", 7))
        self.lbl_theta4.pack(anchor="w")
        self.lbl_pulse4 = ttk.Label(s4_frame, text="P: --", font=("Consolas", 7))
        self.lbl_pulse4.pack(anchor="w")
        
        # Slot 5 (Roll) - Manual Slider
        s5_frame = ttk.LabelFrame(slots_frame, text="S5 Roll", padding=2)
        s5_frame.grid(row=0, column=3, padx=1, pady=1, sticky="nsew")
        self.roll_slider = ttk.Scale(
            s5_frame, from_=0, to=180,
            variable=self.roll_var, orient=tk.HORIZONTAL, length=60,
            command=lambda v: self.update_visualization()
        )
        self.roll_slider.pack(fill=tk.X)
        self.lbl_theta5 = ttk.Label(s5_frame, text="θ: 90.0°", font=("Consolas", 7))
        self.lbl_theta5.pack(anchor="w")
        self.lbl_pulse5 = ttk.Label(s5_frame, text="P: --", font=("Consolas", 7))
        self.lbl_pulse5.pack(anchor="w")
        
        # Slot 6 (Gripper) - Manual Slider
        s6_frame = ttk.LabelFrame(slots_frame, text="S6 Grip", padding=2)
        s6_frame.grid(row=0, column=4, padx=1, pady=1, sticky="nsew")
        self.gripper_slider = ttk.Scale(
            s6_frame, from_=0, to=180,
            variable=self.gripper_var, orient=tk.HORIZONTAL, length=60,
            command=lambda v: self.update_visualization()
        )
        self.gripper_slider.pack(fill=tk.X)
        self.lbl_theta6 = ttk.Label(s6_frame, text="θ: 0.0°", font=("Consolas", 7))
        self.lbl_theta6.pack(anchor="w")
        self.lbl_pulse6 = ttk.Label(s6_frame, text="P: --", font=("Consolas", 7))
        self.lbl_pulse6.pack(anchor="w")
    
    def _create_info_panel(self, parent):
        """Create info/status panel with Gripper visualization."""
        frame = ttk.LabelFrame(parent, text="Gripper State", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        
        # Gripper Canvas (Top-Down View)
        gripper_size = 120
        self.gripper_canvas = tk.Canvas(frame, width=gripper_size, height=gripper_size,
                                        bg="#1a1a2e", highlightthickness=1, highlightbackground="#444")
        self.gripper_canvas.pack(pady=5)
        
        # Gripper Widget3
        self.gripper_widget = GripperStateWidget3(self.gripper_canvas, {'canvas_size': gripper_size})
        
        # Info text (compact)
        info_text = """[ 5-Link IK ]
• θ1: Base Yaw
• θ2-θ3: Position IK
• θ4: Approach (-90°)
• θ5: Roll (manual)
• θ6: Gripper (manual)"""
        ttk.Label(frame, text=info_text, font=("Consolas", 8), justify=tk.LEFT).pack(anchor="nw", pady=5)
    
    def on_enter(self):
        """Called when tab is selected."""
        self._refresh_config()
        self.top_widget.draw_static()
        self.side_widget.draw_static()
        self.gripper_widget.draw_static()
        self.update_visualization()
    
    def on_config_updated(self):
        """Handle config reload."""
        self.log("[FullSlot3] Config Reloaded")
        self._refresh_config()
        self.top_widget.draw_static()
        self.side_widget.draw_static()
        self.update_visualization()
    
    def _refresh_config(self):
        """Load Slot 1-6 config and update widgets."""
        p1 = self.context.get_slot_params(1)
        p2 = self.context.get_slot_params(2)
        p3 = self.context.get_slot_params(3)
        p4 = self.context.get_slot_params(4)
        p5 = self.context.get_slot_params(5)
        p6 = self.context.get_slot_params(6)
        
        if p1:
            self.top_widget.cfg.update(p1)
            # Config 기반 direction 계산 (arm 이름 의존 제거)
            min_pos = p1.get('min_pos', 'right')
            zero_offset = p1.get('zero_offset', 0)
            act_range = p1.get('actuation_range', 180)
            base_sign = 1 if min_pos == 'right' else -1
            flip = -1 if zero_offset >= 90 else 1
            direction = base_sign * flip
            self.top_widget.cfg['direction'] = direction
            
            # Math 범위 통일 (로컬 좌표계: 0 ~ actuation_range)
            self.top_widget.cfg['math_min'] = 0
            self.top_widget.cfg['math_max'] = act_range
            self.p1 = p1
        
        # Slot 2/3/4 lengths -> Side View Widget
        if p1:
            self.side_widget.cfg['d1'] = p1.get('length', 107.0)
        if p2:
            self.side_widget.cfg['a2'] = p2.get('length', 105.0)
            self.side_widget.cfg['slot2_params'] = p2  # For Arc rendering
            self.p2 = p2
        if p3:
            self.side_widget.cfg['a3'] = p3.get('length', 150.0)
            self.side_widget.cfg['slot3_params'] = p3  # For Arc rendering
            self.p3 = p3
        if p4:
            self.side_widget.cfg['a4'] = p4.get('length', 65.0)
            self.side_widget.cfg['slot4_params'] = p4  # For Arc rendering
            self.p4 = p4
        
        # Slot 5 (Roll) and Slot 6 (Gripper)
        if p5:
            self.p5 = p5
        if p6:
            self.p6 = p6
            self.side_widget.cfg['a6'] = p6.get('length', 70.0)  # For rendering
        
        # Update Slot 1 Config display
        arm = self.context.get_current_arm()
        raw_cfg = self.context.manager.config.get(arm, {})
        s1_data = raw_cfg.get("slot_1", {})
        lines = [f"{k}: {v}" for k, v in s1_data.items()]
        self.lbl_config_s1.config(text="\n".join(lines) if lines else "--")
    
    def update_visualization(self):
        """Update visualizations based on IK calculation."""
        x = self.x_var.get()
        y = self.y_var.get()
        z = self.z_var.get()
        
        # θ1 Calculation (Config 기반: direction으로 자동 계산)
        direction = self.top_widget.cfg.get('direction', 1)
        if direction == 1:
            theta1 = math.degrees(math.atan2(-x, y)) if (x != 0 or y != 0) else 0
        else:
            theta1 = math.degrees(math.atan2(x, -y)) if (x != 0 or y != 0) else 0
        R = math.sqrt(x**2 + y**2)
        
        # --- Load link lengths from config ---
        d1 = getattr(self, 'p1', {}).get('length', 107.0) if hasattr(self, 'p1') else 107.0
        a2 = getattr(self, 'p2', {}).get('length', 105.0) if hasattr(self, 'p2') else 105.0
        a3 = getattr(self, 'p3', {}).get('length', 150.0) if hasattr(self, 'p3') else 150.0
        a4 = getattr(self, 'p4', {}).get('length', 65.0) if hasattr(self, 'p4') else 65.0
        a6 = getattr(self, 'p6', {}).get('length', 70.0) if hasattr(self, 'p6') else 70.0
        
        # --- 5-Link IK: Gripper TIP reaches Target at 90° ---
        # Gripper points down (-90°), so wrist is (a4 + a6) above target
        wrist_z = z + a4 + a6
        
        # 2-Link IK with Wrist position as target
        theta2, theta3, is_reachable, config_name = self._solve_2link_ik(R, wrist_z, d1, a2, a3)
        
        # Invert θ3 for Slot 3 (min_pos: top)
        theta3 = -theta3
        
        # Update Target Label with configuration (show original z, not wrist_z)
        self.lbl_target.config(text=f"Target: R={R:.1f} Z={z:.1f} [{config_name}]")
        
        # --- Slot 1 Real-time State ---
        pulse_calc_s1 = "--"
        phy_angle_s1 = theta1
        
        if hasattr(self, 'p1'):
            mapper = self.context.mapper
            zero_offset = self.p1.get('zero_offset', 0)
            act_range = self.p1.get('actuation_range', 180)
            
            # direction 기반 physical 각도 계산
            if direction == 1:
                phy_angle_s1 = zero_offset + theta1
            else:
                phy_angle_s1 = zero_offset - theta1
            phy_angle_s1 = max(0, min(act_range, phy_angle_s1))
            
            pulse_val_s1 = mapper.physical_to_pulse(phy_angle_s1, self.p1['motor_config'])
            pulse_calc_s1 = f"{pulse_val_s1}"
        
        self.lbl_angle_s1.config(text=f"Angle: {theta1:.1f} (IK) | {phy_angle_s1:.1f} (Phy)")
        self.lbl_pulse_s1.config(text=f"Pulse: {pulse_calc_s1}")
        
        # --- Slot 2 Real-time State ---
        pulse_calc_s2 = "--"
        phy_angle_s2 = theta2
        valid2 = False
        
        if hasattr(self, 'p2'):
            mapper = self.context.mapper
            zero_offset2 = self.p2.get('zero_offset', 0)
            act_range2 = self.p2.get('actuation_range', 180)
            
            phy_angle_s2 = theta2 + zero_offset2
            phy_angle_s2 = max(0, min(act_range2, phy_angle_s2))
            
            pulse_val_s2 = mapper.physical_to_pulse(phy_angle_s2, self.p2['motor_config'])
            pulse_calc_s2 = f"{pulse_val_s2}"
            
            valid2 = self.p2['math_min'] <= theta2 <= self.p2['math_max']
        
        self.lbl_theta2.config(text=f"θ2: {theta2:.1f} (IK) | {phy_angle_s2:.1f} (Phy)")
        self.lbl_pulse2.config(text=f"Pulse: {pulse_calc_s2}")
        
        # --- Slot 3 Real-time State ---
        pulse_calc_s3 = "--"
        phy_angle_s3 = theta3
        valid3 = False
        
        if hasattr(self, 'p3'):
            mapper = self.context.mapper
            zero_offset3 = self.p3.get('zero_offset', 0)
            act_range3 = self.p3.get('actuation_range', 180)
            
            # min_pos: top → phy = zero + theta (after inversion)
            phy_angle_s3 = zero_offset3 + theta3
            phy_angle_s3 = max(0, min(act_range3, phy_angle_s3))
            
            pulse_val_s3 = mapper.physical_to_pulse(phy_angle_s3, self.p3['motor_config'])
            pulse_calc_s3 = f"{pulse_val_s3}"
            
            valid3 = self.p3['math_min'] <= theta3 <= self.p3['math_max']
        
        self.lbl_theta3.config(text=f"θ3: {theta3:.1f} (IK) | {phy_angle_s3:.1f} (Phy)")
        self.lbl_pulse3.config(text=f"Pulse: {pulse_calc_s3}")
        
        # --- Slot 4 Real-time State (Approach Angle Auto-calculated) ---
        # θ4 = -90 - (θ2 - θ3) to keep gripper perpendicular to ground
        # Note: θ3 is relative angle, global_theta3 = θ2 - θ3
        # When global_theta4 = -90° (pointing down): -90 = (θ2 - θ3) + θ4
        theta4 = -90.0 - theta2 + theta3
        pulse_calc_s4 = "--"
        phy_angle_s4 = theta4
        valid4 = False
        
        if hasattr(self, 'p4'):
            mapper = self.context.mapper
            zero_offset4 = self.p4.get('zero_offset', 0)
            act_range4 = self.p4.get('actuation_range', 180)
            
            # min_pos: top → polarity = -1 → phy = zero - theta
            phy_angle_s4 = zero_offset4 - theta4
            phy_angle_s4 = max(0, min(act_range4, phy_angle_s4))
            
            pulse_val_s4 = mapper.physical_to_pulse(phy_angle_s4, self.p4['motor_config'])
            pulse_calc_s4 = f"{pulse_val_s4}"
            
            valid4 = self.p4['math_min'] <= theta4 <= self.p4['math_max']
        
        self.lbl_theta4.config(text=f"θ4: {theta4:.1f}°")
        self.lbl_pulse4.config(text=f"P: {pulse_calc_s4}")
        
        # --- Slot 5 Real-time State (Roll - Manual Input) ---
        theta5 = self.roll_var.get()
        pulse_calc_s5 = "--"
        phy_angle_s5 = theta5
        valid5 = True
        
        if hasattr(self, 'p5'):
            mapper = self.context.mapper
            zero_offset5 = self.p5.get('zero_offset', 0)
            act_range5 = self.p5.get('actuation_range', 180)
            
            # type: roll, min_pos: ccw → polarity based on config
            phy_angle_s5 = theta5 + zero_offset5
            phy_angle_s5 = max(0, min(act_range5, phy_angle_s5))
            
            pulse_val_s5 = mapper.physical_to_pulse(phy_angle_s5, self.p5['motor_config'])
            pulse_calc_s5 = f"{pulse_val_s5}"
            
            valid5 = self.p5['math_min'] <= theta5 <= self.p5['math_max']
        
        self.lbl_theta5.config(text=f"θ: {theta5:.0f}°")
        self.lbl_pulse5.config(text=f"P: {pulse_calc_s5}")
        
        # --- Slot 6 Real-time State (Gripper - Manual Input) ---
        theta6 = self.gripper_var.get()
        pulse_calc_s6 = "--"
        phy_angle_s6 = theta6
        valid6 = True
        
        if hasattr(self, 'p6'):
            mapper = self.context.mapper
            zero_offset6 = self.p6.get('zero_offset', 0)
            act_range6 = self.p6.get('actuation_range', 180)
            
            # type: gripper, min_pos: open
            phy_angle_s6 = theta6 + zero_offset6
            phy_angle_s6 = max(0, min(act_range6, phy_angle_s6))
            
            pulse_val_s6 = mapper.physical_to_pulse(phy_angle_s6, self.p6['motor_config'])
            pulse_calc_s6 = f"{pulse_val_s6}"
            
            valid6 = self.p6['math_min'] <= theta6 <= self.p6['math_max']
        
        self.lbl_theta6.config(text=f"θ: {theta6:.0f}°")
        self.lbl_pulse6.config(text=f"P: {pulse_calc_s6}")
        
        # --- Warning ---
        warnings = []
        if not is_reachable:
            warnings.append(f"{config_name}")
        if not valid2:
            warnings.append("θ2")
        if not valid3:
            warnings.append("θ3")
        if not valid4:
            warnings.append("θ4")
        if not valid5:
            warnings.append("θ5")
        if not valid6:
            warnings.append("θ6")
        self.lbl_warning.config(text="⚠️ Out: " + ", ".join(warnings) if warnings else "")
        
        # --- Update Top View ---
        valid1 = False
        if hasattr(self, 'p1'):
            valid1 = self.top_widget.cfg['math_min'] <= theta1 <= self.top_widget.cfg['math_max']
        self.top_widget.update_target(x, y, valid1)
        
        # --- Update Side View with IK result (5-link with R,Z target) ---
        self.side_widget.update_target(theta2, theta3, theta4, R, z)
        
        # --- Update Gripper State View ---
        self.gripper_widget.update(theta5, theta6)
        
        # Store calculated angles for send_command
        self._ik_theta2 = theta2
        self._ik_theta3 = theta3
        self._ik_theta4 = theta4
        self._theta5 = theta5
        self._theta6 = theta6
    
    def _solve_2link_ik(self, R, z, d1, a2, a3):
        """
        2-Link Planar IK Solver with multiple solutions.
        Returns: (theta2, theta3, is_reachable, config_name)
        """
        s = z - d1  # Vertical offset from shoulder
        dist_sq = R*R + s*s
        dist = math.sqrt(dist_sq)
        
        max_reach = a2 + a3
        min_reach = abs(a2 - a3)
        
        # Reachability check
        if dist > max_reach or dist < min_reach or dist == 0:
            # Pointing fallback: θ2 = atan2(s, R), θ3 = 0
            theta2 = math.degrees(math.atan2(s, R)) if R > 0 else (90.0 if s >= 0 else -90.0)
            theta3 = 0.0
            return theta2, theta3, False, "Pointing"
        
        # Elbow angle (θ3) via Law of Cosines
        cos_theta3 = (dist_sq - a2*a2 - a3*a3) / (2 * a2 * a3)
        cos_theta3 = max(-1.0, min(1.0, cos_theta3))
        theta3_rad = math.acos(cos_theta3)
        
        # Shoulder angle components
        beta = math.atan2(s, R)
        cos_alpha = (a2*a2 + dist_sq - a3*a3) / (2 * a2 * dist)
        cos_alpha = max(-1.0, min(1.0, cos_alpha))
        alpha = math.acos(cos_alpha)
        
        # Calculate both solutions
        solutions = []
        
        # Elbow Up: θ2 = β + α, θ3 = -|θ3|
        theta2_up = math.degrees(beta + alpha)
        theta3_up = math.degrees(-theta3_rad)
        if self._is_valid_solution(theta2_up, theta3_up):
            solutions.append((theta2_up, theta3_up, "Elbow Up"))
        
        # Elbow Down: θ2 = β - α, θ3 = +|θ3|
        theta2_down = math.degrees(beta - alpha)
        theta3_down = math.degrees(theta3_rad)
        if self._is_valid_solution(theta2_down, theta3_down):
            solutions.append((theta2_down, theta3_down, "Elbow Down"))
        
        # Select best solution
        if not solutions:
            # No valid solution - Pointing fallback
            theta2 = math.degrees(math.atan2(s, R)) if R > 0 else (90.0 if s >= 0 else -90.0)
            return theta2, 0.0, False, "No Valid"
        
        # Prefer Elbow Up (first valid)
        best = solutions[0]
        return best[0], best[1], True, best[2]
    
    def _is_valid_solution(self, theta2, theta3):
        """Check if solution is within joint limits."""
        if not hasattr(self, 'p2') or not hasattr(self, 'p3'):
            return True  # No config, assume valid
        
        # θ2 range check
        math_min2 = self.p2.get('math_min', -90)
        math_max2 = self.p2.get('math_max', 90)
        if not (math_min2 <= theta2 <= math_max2):
            return False
        
        # θ3 range check
        math_min3 = self.p3.get('math_min', -90)
        math_max3 = self.p3.get('math_max', 90)
        if not (math_min3 <= theta3 <= math_max3):
            return False
        
        return True
    
    def send_command(self, duration):
        """Send command - All 6 slots using IK-calculated and manual angles."""
        required = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6']
        missing = [k for k in required if not hasattr(self, k)]
        if missing:
            self.log(f"[FullSlot3] Config missing: {missing}, cannot send.")
            return
        
        x = self.x_var.get()
        y = self.y_var.get()
        direction = self.top_widget.cfg.get('direction', 1)
        if direction == 1:
            theta1 = math.degrees(math.atan2(-x, y)) if (x != 0 or y != 0) else 0
        else:
            theta1 = math.degrees(math.atan2(x, -y)) if (x != 0 or y != 0) else 0
        
        # Use IK-calculated angles (Slot 2-4)
        theta2 = getattr(self, '_ik_theta2', 0.0)
        theta3 = getattr(self, '_ik_theta3', 0.0)
        theta4 = getattr(self, '_ik_theta4', 0.0)
        
        # Manual angles (Slot 5-6)
        theta5 = getattr(self, '_theta5', 90.0)
        theta6 = getattr(self, '_theta6', 0.0)
        
        mapper = self.context.mapper
        
        # Slot 1 (direction 기반)
        zero_off1 = self.p1.get('zero_offset', 0)
        if direction == 1:
            phy1 = zero_off1 + theta1
        else:
            phy1 = zero_off1 - theta1
        phy1 = max(0, min(self.p1.get('actuation_range', 180), phy1))
        pls1 = mapper.physical_to_pulse(phy1, self.p1['motor_config'])
        
        # Slot 2
        zero_off2 = self.p2.get('zero_offset', 0)
        phy2 = max(0, min(self.p2.get('actuation_range', 270), theta2 + zero_off2))
        pls2 = mapper.physical_to_pulse(phy2, self.p2['motor_config'])
        
        # Slot 3 (min_pos: top → phy = zero + theta after inversion)
        zero_off3 = self.p3.get('zero_offset', 0)
        phy3 = zero_off3 + theta3
        phy3 = max(0, min(self.p3.get('actuation_range', 270), phy3))
        pls3 = mapper.physical_to_pulse(phy3, self.p3['motor_config'])
        
        # Slot 4 (min_pos: top → polarity = -1 → phy = zero - theta)
        zero_off4 = self.p4.get('zero_offset', 0)
        phy4 = zero_off4 - theta4
        phy4 = max(0, min(self.p4.get('actuation_range', 180), phy4))
        pls4 = mapper.physical_to_pulse(phy4, self.p4['motor_config'])
        
        # Slot 5 (Roll - manual)
        zero_off5 = self.p5.get('zero_offset', 0)
        phy5 = theta5 + zero_off5
        phy5 = max(0, min(self.p5.get('actuation_range', 180), phy5))
        pls5 = mapper.physical_to_pulse(phy5, self.p5['motor_config'])
        
        # Slot 6 (Gripper - manual)
        zero_off6 = self.p6.get('zero_offset', 0)
        phy6 = theta6 + zero_off6
        phy6 = max(0, min(self.p6.get('actuation_range', 180), phy6))
        pls6 = mapper.physical_to_pulse(phy6, self.p6['motor_config'])
        
        targets = [
            (self.p1['channel'], pls1),
            (self.p2['channel'], pls2),
            (self.p3['channel'], pls3),
            (self.p4['channel'], pls4),
            (self.p5['channel'], pls5),
            (self.p6['channel'], pls6),
        ]
        self.context.motion_planner.move_all(targets, duration)
        self.log(f"[FullSlot3] 6ch sent: Ch{self.p1['channel']}~{self.p6['channel']}")
