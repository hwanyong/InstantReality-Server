
import tkinter as tk
from tkinter import ttk
import math
from ..core import BaseTabController
from ..widgets import TopDownWidget, SideElevation3LinkWidget


class TripleViewTab(BaseTabController):
    """
    Tab 3: Slot 1+2+3 with Top View matching DualViewTab.
    - Top View: X/Y sliders, θ1 auto-calculated (same as DualViewTab)
    - Side View: θ2/θ3 manual sliders, 3-Link FK rendering (hardcoded)
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
        
        # TopDownWidget (config will be updated in _refresh_config)
        self.top_widget = TopDownWidget(self.top_canvas, {
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
        
        # 3-Link Widget
        self.side_widget = SideElevation3LinkWidget(self.side_canvas, {
            'canvas_size': 240
        })
        
        # Real-time State Frame (Target + Warning)
        dyn_frame = ttk.Labelframe(grid, text="Real-time State", padding=5)
        dyn_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        
        self.lbl_target = ttk.Label(dyn_frame, text="Target: R=-- Z=--", font=("Consolas", 9, "bold"))
        self.lbl_target.pack(anchor="w")
        
        self.lbl_warning = ttk.Label(dyn_frame, text="", font=("Consolas", 9, "bold"), foreground="red")
        self.lbl_warning.pack(anchor="w")
        
        # Slot 2 State + Config
        s2_frame = ttk.Labelframe(grid, text="Slot 2 (Shoulder)", padding=5)
        s2_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        
        self.lbl_theta2 = ttk.Label(s2_frame, text="θ2: 0.0°", font=("Consolas", 10))
        self.lbl_theta2.pack(anchor="w")
        
        self.lbl_pulse2 = ttk.Label(s2_frame, text="Pulse: --", font=("Consolas", 9))
        self.lbl_pulse2.pack(anchor="w")
        
        self.lbl_config_s2 = ttk.Label(s2_frame, text="--", font=("Consolas", 8), justify=tk.LEFT)
        self.lbl_config_s2.pack(anchor="w", fill=tk.X)
        
        # Slot 3 State + Config
        s3_frame = ttk.Labelframe(grid, text="Slot 3 (Elbow)", padding=5)
        s3_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        
        self.lbl_theta3 = ttk.Label(s3_frame, text="θ3: 0.0° (rel)", font=("Consolas", 10))
        self.lbl_theta3.pack(anchor="w")
        
        self.lbl_pulse3 = ttk.Label(s3_frame, text="Pulse: --", font=("Consolas", 9))
        self.lbl_pulse3.pack(anchor="w")
        
        self.lbl_config_s3 = ttk.Label(s3_frame, text="--", font=("Consolas", 8), justify=tk.LEFT)
        self.lbl_config_s3.pack(anchor="w", fill=tk.X)
    
    def _create_info_panel(self, parent):
        """Create info/status panel."""
        frame = ttk.LabelFrame(parent, text="Status", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        
        info_text = """[ Slot 1+2+3 Tab ]

Top View:
• X/Y sliders → θ1 auto
• Config binding: ON

Side View:
• θ2/θ3 manual sliders
• Config binding: OFF
• 3-Link FK (hardcoded)

[ Hardcoded (Phase 2) ]
• d1 = 40px
• a2 = 40px
• a3 = 60px
"""
        ttk.Label(frame, text=info_text, font=("Consolas", 9), justify=tk.LEFT).pack(anchor="nw")
    
    def on_enter(self):
        """Called when tab is selected."""
        self._refresh_config()
        self.top_widget.draw_static()
        self.side_widget.draw_static()
        self.update_visualization()
    
    def on_config_updated(self):
        """Handle config reload."""
        self.log("[TripleView] Config Reloaded")
        self._refresh_config()
        self.top_widget.draw_static()
        self.side_widget.draw_static()
        self.update_visualization()
    
    def _refresh_config(self):
        """Load Slot 1/2/3 config and update widgets."""
        p1 = self.context.get_slot_params(1)
        p2 = self.context.get_slot_params(2)
        p3 = self.context.get_slot_params(3)
        
        # Slot 1 (Top View)
        if p1:
            self.top_widget.cfg.update(p1)
            self.p1 = p1
        
        # Slot 2/3 lengths -> Side View Widget
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
        
        # Update Slot 1 Config display
        arm = self.context.get_current_arm()
        raw_cfg = self.context.manager.config.get(arm, {})
        s1_data = raw_cfg.get("slot_1", {})
        lines = [f"{k}: {v}" for k, v in s1_data.items()]
        self.lbl_config_s1.config(text="\n".join(lines) if lines else "--")
        
        # Update Slot 2 Config display
        s2_data = raw_cfg.get("slot_2", {})
        lines2 = [f"{k}: {v}" for k, v in s2_data.items()]
        self.lbl_config_s2.config(text="\n".join(lines2) if lines2 else "--")
        
        # Update Slot 3 Config display
        s3_data = raw_cfg.get("slot_3", {})
        lines3 = [f"{k}: {v}" for k, v in s3_data.items()]
        self.lbl_config_s3.config(text="\n".join(lines3) if lines3 else "--")
    
    def update_visualization(self):
        """Update visualizations based on IK calculation."""
        x = self.x_var.get()
        y = self.y_var.get()
        z = self.z_var.get()
        
        # θ1 Calculation (same as DualViewTab)
        theta1 = math.degrees(math.atan2(y, x)) if (x != 0 or y != 0) else 0
        R = math.sqrt(x**2 + y**2)
        
        # --- Load link lengths from config ---
        d1 = getattr(self, 'p1', {}).get('length', 107.0) if hasattr(self, 'p1') else 107.0
        a2 = getattr(self, 'p2', {}).get('length', 105.0) if hasattr(self, 'p2') else 105.0
        a3 = getattr(self, 'p3', {}).get('length', 150.0) if hasattr(self, 'p3') else 150.0
        
        # --- 2-Link IK Calculation (Multi-solution) ---
        theta2, theta3, is_reachable, config_name = self._solve_2link_ik(R, z, d1, a2, a3)
        
        # Invert θ3 for Slot 3 (min_pos: top)
        theta3 = -theta3
        
        # Update Target Label with configuration
        self.lbl_target.config(text=f"Target: R={R:.1f} Z={z:.1f} [{config_name}]")
        
        # --- Slot 1 Real-time State ---
        pulse_calc_s1 = "--"
        phy_angle_s1 = theta1
        
        if hasattr(self, 'p1'):
            mapper = self.context.mapper
            zero_offset = self.p1.get('zero_offset', 0)
            act_range = self.p1.get('actuation_range', 180)
            
            phy_angle_s1 = theta1 + zero_offset
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
        
        # --- Warning ---
        warnings = []
        if not is_reachable:
            warnings.append(f"{config_name}")
        if not valid2:
            warnings.append("θ2 out of range")
        if not valid3:
            warnings.append("θ3 out of range")
        self.lbl_warning.config(text="⚠️ " + ", ".join(warnings) if warnings else "")
        
        # --- Update Top View ---
        valid1 = False
        if hasattr(self, 'p1'):
            valid1 = self.p1['math_min'] <= theta1 <= self.p1['math_max']
        self.top_widget.update_target(x, y, valid1)
        
        # --- Update Side View with IK result ---
        self.side_widget.update_target(theta2, theta3, R, z)
        
        # Store calculated angles for send_command
        self._ik_theta2 = theta2
        self._ik_theta3 = theta3
    
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
        """Send command - All 3 slots using IK-calculated angles."""
        if not all(hasattr(self, k) for k in ['p1', 'p2', 'p3']):
            self.log("[TripleView] Config not fully loaded, cannot send.")
            return
        
        x = self.x_var.get()
        y = self.y_var.get()
        theta1 = math.degrees(math.atan2(y, x)) if (x != 0 or y != 0) else 0
        
        # Use IK-calculated angles
        theta2 = getattr(self, '_ik_theta2', 0.0)
        theta3 = getattr(self, '_ik_theta3', 0.0)
        
        mapper = self.context.mapper
        
        # Slot 1
        zero_off1 = self.p1.get('zero_offset', 0)
        phy1 = max(0, min(self.p1.get('actuation_range', 180), theta1 + zero_off1))
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
        
        targets = [
            (self.p1['channel'], pls1),
            (self.p2['channel'], pls2),
            (self.p3['channel'], pls3),
        ]
        self.context.motion_planner.move_all(targets, duration)
        self.log(f"[TripleView] Sent Ch{self.p1['channel']}:{pls1} (θ1={theta1:.1f}°)")
        self.log(f"[TripleView] Sent Ch{self.p2['channel']}:{pls2} (θ2={theta2:.1f}° IK, Phy={phy2:.1f}°)")
        self.log(f"[TripleView] Sent Ch{self.p3['channel']}:{pls3} (θ3={theta3:.1f}° IK, Phy={phy3:.1f}°)")

