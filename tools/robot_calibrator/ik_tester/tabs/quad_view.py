
import tkinter as tk
from tkinter import ttk
import math
import json
from ..core import BaseTabController
from ..widgets import TopDownWidget, SideElevation4LinkWidget, TopDownWristWidget
from ..ik_solver import IKSolver


# Gemini Workspace Constants
WORKSPACE_WIDTH = 600.0   # mm
WORKSPACE_DEPTH = 500.0   # mm
L_BASE = 107.0            # mm (ground to shoulder)
DEFAULT_OBJECT_HEIGHT = 20.0  # mm


class QuadViewTab(BaseTabController):
    """
    Tab 4: Slot 1+2+3+4 VLA IK with Gemini Vision Input.
    - Supports both Manual mode (X/Y/Z sliders) and Gemini mode (Vision coordinates)
    - 4-DOF IK: Base Yaw + Shoulder Pitch + Elbow Pitch + Wrist Yaw
    - Coordinate transformation from Gemini Vision Space to Robot Frame
    """
    
    # Range constants
    X_MIN = -300
    X_MAX = 300
    Y_MIN = -300
    Y_MAX = 300
    Z_MIN = -148
    Z_MAX = 362
    DIR_MIN = -180
    DIR_MAX = 180
    
    def build_ui(self):
        # --- UI Variables ---
        self.x_var = tk.DoubleVar(value=0.0)
        self.y_var = tk.DoubleVar(value=200.0)
        self.z_var = tk.DoubleVar(value=150.0)
        self.dir_var = tk.DoubleVar(value=0.0)  # Gripper direction
        
        # Gemini Input Variables
        self.gemini_y_var = tk.StringVar(value="500")
        self.gemini_x_var = tk.StringVar(value="500")
        self.object_height_var = tk.StringVar(value="20")
        self.description_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value="manual")  # "manual" or "gemini"
        
        self.main_frame = ttk.Frame(self.parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self._create_gemini_panel(self.main_frame)
        self._create_top_view(self.main_frame)
        self._create_side_view(self.main_frame)
        self._create_info_panel(self.main_frame)
    
    def _create_gemini_panel(self, parent):
        """Create Gemini Vision Input Panel."""
        frame = ttk.LabelFrame(parent, text="VLA Input Mode", padding=5)
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Mode Toggle
        mode_frame = ttk.Frame(frame)
        mode_frame.pack(fill=tk.X)
        ttk.Radiobutton(mode_frame, text="Manual", variable=self.mode_var, 
                        value="manual", command=self._on_mode_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="Gemini Vision", variable=self.mode_var, 
                        value="gemini", command=self._on_mode_change).pack(side=tk.LEFT, padx=5)
        
        # Gemini Inputs Frame
        self.gemini_frame = ttk.Frame(frame)
        self.gemini_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.gemini_frame, text="Y (0-1000):").grid(row=0, column=0, padx=2)
        ttk.Entry(self.gemini_frame, textvariable=self.gemini_y_var, width=8).grid(row=0, column=1, padx=2)
        
        ttk.Label(self.gemini_frame, text="X (0-1000):").grid(row=0, column=2, padx=2)
        ttk.Entry(self.gemini_frame, textvariable=self.gemini_x_var, width=8).grid(row=0, column=3, padx=2)
        
        ttk.Label(self.gemini_frame, text="Height(mm):").grid(row=0, column=4, padx=2)
        ttk.Entry(self.gemini_frame, textvariable=self.object_height_var, width=6).grid(row=0, column=5, padx=2)
        
        ttk.Label(self.gemini_frame, text="Desc:").grid(row=0, column=6, padx=2)
        ttk.Entry(self.gemini_frame, textvariable=self.description_var, width=20).grid(row=0, column=7, padx=2)
        
        ttk.Button(self.gemini_frame, text="Parse & Solve", 
                   command=self._on_gemini_parse).grid(row=0, column=8, padx=5)
        
        # Selected Arm Display
        self.lbl_arm = ttk.Label(frame, text="Arm: --", font=("Consolas", 10, "bold"))
        self.lbl_arm.pack(anchor="w")
    
    def _on_mode_change(self):
        """Handle mode toggle."""
        mode = self.mode_var.get()
        self.log(f"[QuadView] Mode changed to: {mode}")
    
    def _on_gemini_parse(self):
        """Handle Gemini Parse & Solve button click."""
        try:
            gemini_y = float(self.gemini_y_var.get())
            gemini_x = float(self.gemini_x_var.get())
            height_str = self.object_height_var.get()
            height = float(height_str) if height_str else DEFAULT_OBJECT_HEIGHT
            description = self.description_var.get()
            
            # Select arm
            arm = self.select_arm(gemini_x)
            self.log(f"[QuadView] Selected Arm: {arm}")
            self.lbl_arm.config(text=f"Arm: {arm.upper()}")
            
            # Switch arm in app context
            self.context.arm_var.set("left_arm" if arm == "left" else "right_arm")
            self._refresh_config()
            
            # Convert coordinates
            x_mm, y_mm, z_mm = self.gemini_to_robot(gemini_y, gemini_x, arm, height)
            self.log(f"[QuadView] Robot Coords: X={x_mm:.1f}, Y={y_mm:.1f}, Z={z_mm:.1f}")
            
            # Get wrist direction
            wrist_dir = self.get_wrist_direction(description)
            self.log(f"[QuadView] Wrist Direction: {wrist_dir}°")
            
            # Update sliders
            self.x_var.set(x_mm)
            self.y_var.set(y_mm)
            self.z_var.set(z_mm)
            self.dir_var.set(wrist_dir)
            
            # Solve IK
            self.update_visualization()
            
        except Exception as e:
            self.log(f"[QuadView] Parse Error: {e}")
    
    def select_arm(self, gemini_x):
        """
        Select arm based on Gemini X coordinate.
        x > 500 (right side of image) → Right Arm
        x <= 500 (left side of image) → Left Arm
        """
        return "right" if gemini_x > 500 else "left"
    
    def get_wrist_direction(self, description):
        """
        Parse wrist direction from description text.
        Returns gripper_direction in degrees (passed to IKSolver).
        """
        desc_lower = description.lower()
        
        if "right" in desc_lower:
            return 90.0
        elif "left" in desc_lower:
            return -90.0
        
        return 0.0
    
    def gemini_to_robot(self, gemini_y, gemini_x, arm, object_height=DEFAULT_OBJECT_HEIGHT):
        """
        Convert Gemini Vision coordinates to Robot coordinates.
        
        Args:
            gemini_y: 0-1000 (Top=0, Bottom=1000)
            gemini_x: 0-1000 (Left=0, Right=1000)
            arm: "right" or "left"
            object_height: mm (default: 20mm)
        
        Returns:
            (x_mm, y_mm, z_mm) in robot frame
        """
        # Y-axis inversion (Gemini bottom = Robot front)
        y_mm = (1.0 - gemini_y / 1000.0) * WORKSPACE_DEPTH
        
        # X-axis transformation (arm-dependent)
        if arm == "right":
            # Right arm: reaches from Right(0) to Left(-X)
            x_mm = (gemini_x / 1000.0) * WORKSPACE_WIDTH - WORKSPACE_WIDTH
        else:
            # Left arm: reaches from Left(0) to Right(+X)
            x_mm = (gemini_x / 1000.0) * WORKSPACE_WIDTH
        
        # Z-axis: object height relative to base
        z_mm = object_height - L_BASE
        
        return x_mm, y_mm, z_mm
    
    def _create_top_view(self, parent):
        """Create Top-Down view for X/Y input."""
        frame = ttk.LabelFrame(parent, text="Top-Down (X/Y)", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=2)
        
        grid = ttk.Frame(frame)
        grid.pack(padx=2, pady=2)
        
        # Y Slider
        y_frame = ttk.Frame(grid)
        y_frame.grid(row=0, column=0, sticky="ns")
        ttk.Label(y_frame, text="Y").pack()
        self.y_slider = ttk.Scale(
            y_frame, from_=self.Y_MAX, to=self.Y_MIN,
            variable=self.y_var, orient=tk.VERTICAL, length=200,
            command=lambda v: self.update_visualization()
        )
        self.y_slider.pack()
        
        # Canvas
        self.top_canvas = tk.Canvas(grid, width=200, height=200, bg="#1a1a2e")
        self.top_canvas.grid(row=0, column=1)
        
        self.top_widget = TopDownWidget(self.top_canvas, {
            'canvas_size': 200, 'scale': 0.33,
            'zero_offset': 0, 'actuation_range': 180,
            'math_min': -90, 'math_max': 90
        })
        
        # X Slider
        x_frame = ttk.Frame(grid)
        x_frame.grid(row=1, column=1, sticky="ew")
        self.x_slider = ttk.Scale(
            x_frame, from_=self.X_MIN, to=self.X_MAX,
            variable=self.x_var, orient=tk.HORIZONTAL, length=200,
            command=lambda v: self.update_visualization()
        )
        self.x_slider.pack()
        
        # Slot 1 State
        s1_frame = ttk.Labelframe(grid, text="Slot 1 (Base)", padding=3)
        s1_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        self.lbl_theta1 = ttk.Label(s1_frame, text="θ1: 0.0°", font=("Consolas", 9))
        self.lbl_theta1.pack(anchor="w")
        
        self.lbl_pulse1 = ttk.Label(s1_frame, text="Pulse: --", font=("Consolas", 9))
        self.lbl_pulse1.pack(anchor="w")
    
    def _create_side_view(self, parent):
        """Create Side Elevation view with 4-Link IK."""
        frame = ttk.LabelFrame(parent, text="Side (4-DOF IK)", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=2)
        
        grid = ttk.Frame(frame)
        grid.pack(padx=2, pady=2)
        
        # Z Slider
        z_frame = ttk.Frame(grid)
        z_frame.grid(row=0, column=0, sticky="ns")
        ttk.Label(z_frame, text="Z").pack()
        self.z_slider = ttk.Scale(
            z_frame, from_=self.Z_MAX, to=self.Z_MIN,
            variable=self.z_var, orient=tk.VERTICAL, length=180,
            command=lambda v: self.update_visualization()
        )
        self.z_slider.pack()
        
        # Direction Slider
        dir_frame = ttk.Frame(grid)
        dir_frame.grid(row=0, column=2, sticky="ns")
        ttk.Label(dir_frame, text="Dir").pack()
        self.dir_slider = ttk.Scale(
            dir_frame, from_=self.DIR_MAX, to=self.DIR_MIN,
            variable=self.dir_var, orient=tk.VERTICAL, length=180,
            command=lambda v: self.update_visualization()
        )
        self.dir_slider.pack()
        
        # Canvas
        self.side_canvas = tk.Canvas(grid, width=200, height=200, bg="#1a2e1a")
        self.side_canvas.grid(row=0, column=1)
        
        # 4-Link Widget (a4 = 135mm = L4 + L6)
        self.side_widget = SideElevation4LinkWidget(self.side_canvas, {
            'canvas_size': 200,
            'd1': 107.0,
            'a2': 105.0,
            'a3': 150.0,
            'a4': 135.0  # L4 + L6
        })
        
        # Target & Warning
        info_frame = ttk.Frame(grid)
        info_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        
        self.lbl_target = ttk.Label(info_frame, text="Target: R=-- Z=--", font=("Consolas", 9, "bold"))
        self.lbl_target.pack(anchor="w")
        
        self.lbl_warning = ttk.Label(info_frame, text="", font=("Consolas", 9, "bold"), foreground="red")
        self.lbl_warning.pack(anchor="w")
        
        # Slot 2 State
        s2_frame = ttk.Labelframe(grid, text="Slot 2 (Shoulder)", padding=3)
        s2_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(3, 0))
        
        self.lbl_theta2 = ttk.Label(s2_frame, text="θ2: 0.0°", font=("Consolas", 9))
        self.lbl_theta2.pack(anchor="w")
        
        self.lbl_pulse2 = ttk.Label(s2_frame, text="Pulse: --", font=("Consolas", 9))
        self.lbl_pulse2.pack(anchor="w")
        
        # Slot 3 State
        s3_frame = ttk.Labelframe(grid, text="Slot 3 (Elbow)", padding=3)
        s3_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(3, 0))
        
        self.lbl_theta3 = ttk.Label(s3_frame, text="θ3: 0.0°", font=("Consolas", 9))
        self.lbl_theta3.pack(anchor="w")
        
        self.lbl_pulse3 = ttk.Label(s3_frame, text="Pulse: --", font=("Consolas", 9))
        self.lbl_pulse3.pack(anchor="w")
        
        # Slot 4 State
        s4_frame = ttk.Labelframe(grid, text="Slot 4 (Wrist)", padding=3)
        s4_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(3, 0))
        
        self.lbl_theta4 = ttk.Label(s4_frame, text="θ4: 0.0°", font=("Consolas", 9))
        self.lbl_theta4.pack(anchor="w")
        
        self.lbl_pulse4 = ttk.Label(s4_frame, text="Pulse: --", font=("Consolas", 9))
        self.lbl_pulse4.pack(anchor="w")
    
    def _create_info_panel(self, parent):
        """Create info/status panel."""
        frame = ttk.LabelFrame(parent, text="Status", padding=5)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        
        info_text = """[ Slot 1+2+3+4 VLA Tab ]

Manual Mode:
• X/Y/Z/Dir sliders
• IK auto-calculation

Gemini Mode:
• Vision coords → Robot
• Arm auto-selection
• Wrist direction parse

Link Lengths:
• d1 = 107mm (Base)
• a2 = 105mm (Shoulder)
• a3 = 150mm (Elbow)
• a4 = 135mm (Hand)
"""
        ttk.Label(frame, text=info_text, font=("Consolas", 9), justify=tk.LEFT).pack(anchor="nw")
    
    def on_enter(self):
        """Called when tab is selected."""
        self._refresh_config()
        self._init_ik_solver()
        self.top_widget.draw_static()
        self.side_widget.draw_static()
        self.update_visualization()
    
    def on_config_updated(self):
        """Handle config reload."""
        self.log("[QuadView] Config Reloaded")
        self._refresh_config()
        self._init_ik_solver()
        self.top_widget.draw_static()
        self.side_widget.draw_static()
        self.update_visualization()
    
    def _init_ik_solver(self):
        """Initialize IK Solver with correct link lengths."""
        p1 = self.context.get_slot_params(1)
        p2 = self.context.get_slot_params(2)
        p3 = self.context.get_slot_params(3)
        p4 = self.context.get_slot_params(4)
        
        # L_HAND = L4 (65mm) + L6 (70mm) = 135mm
        L4 = p4.get('length', 65.0) if p4 else 65.0
        L6 = 70.0  # Gripper length
        L_HAND = L4 + L6
        
        link_lengths = {
            'd1': p1.get('length', 107.0) if p1 else 107.0,
            'a2': p2.get('length', 105.0) if p2 else 105.0,
            'a3': p3.get('length', 150.0) if p3 else 150.0,
            'a4': L_HAND
        }
        
        # Get joint limits
        joint_limits = {}
        for slot_num in [1, 2, 3, 4]:
            params = self.context.get_slot_params(slot_num)
            if params:
                joint_limits[f'slot_{slot_num}'] = {
                    'math_min': params['math_min'],
                    'math_max': params['math_max']
                }
        
        self.ik_solver = IKSolver(link_lengths, joint_limits)
        self.log(f"[QuadView] IKSolver initialized: a4={L_HAND}mm")
    
    def _refresh_config(self):
        """Load Slot 1/2/3/4 config and update widgets."""
        self.p1 = self.context.get_slot_params(1)
        self.p2 = self.context.get_slot_params(2)
        self.p3 = self.context.get_slot_params(3)
        self.p4 = self.context.get_slot_params(4)
        
        # Update TopDownWidget config
        if self.p1:
            self.top_widget.cfg.update(self.p1)
        
        # Update SideWidget link lengths
        if self.p1:
            self.side_widget.cfg['d1'] = self.p1.get('length', 107.0)
        if self.p2:
            self.side_widget.cfg['a2'] = self.p2.get('length', 105.0)
        if self.p3:
            self.side_widget.cfg['a3'] = self.p3.get('length', 150.0)
        if self.p4:
            L4 = self.p4.get('length', 65.0)
            self.side_widget.cfg['a4'] = L4 + 70.0  # L4 + L6
    
    def update_visualization(self):
        """Update visualizations based on IK calculation."""
        x = self.x_var.get()
        y = self.y_var.get()
        z = self.z_var.get()
        direction = self.dir_var.get()
        
        if not hasattr(self, 'ik_solver'):
            self._init_ik_solver()
        
        # Solve IK (with Dynamic Cylindrical Clamping)
        result = self.ik_solver.solve((x, y, z), gripper_direction=direction)
        
        R = math.sqrt(x**2 + y**2)
        
        # Show clamping status in target label
        if result.was_clamped:
            cx, cy, cz = result.clamped_target
            clamped_R = math.sqrt(cx**2 + cy**2)
            self.lbl_target.config(
                text=f"Target: R={R:.1f} → Clamped R={clamped_R:.1f}",
                foreground="orange"
            )
        else:
            self.lbl_target.config(
                text=f"Target: R={R:.1f} Z={z:.1f} Dir={direction:.0f}°",
                foreground="white"
            )
        
        if result.best_solution:
            sol = result.best_solution
            theta1, theta2, theta3, theta4 = sol.theta1, sol.theta2, sol.theta3, sol.theta4
            config_name = sol.config_name
            
            # Store for send_command
            self._current_solution = sol
            
            # Update Slot 1 display
            self._update_slot_display(1, theta1, self.lbl_theta1, self.lbl_pulse1)
            
            # Update Slot 2 display
            self._update_slot_display(2, theta2, self.lbl_theta2, self.lbl_pulse2)
            
            # Update Slot 3 display (inverted for min_pos: top)
            theta3_display = -theta3
            self._update_slot_display(3, theta3_display, self.lbl_theta3, self.lbl_pulse3)
            
            # Update Slot 4 display
            self._update_slot_display(4, theta4, self.lbl_theta4, self.lbl_pulse4)
            
            # Update Top View (use clamped coordinates if applicable)
            if result.was_clamped:
                cx, cy, _ = result.clamped_target
                self.top_widget.update_target(cx, cy, True)
            else:
                valid1 = self.p1['math_min'] <= theta1 <= self.p1['math_max'] if self.p1 else True
                self.top_widget.update_target(x, y, valid1)
            
            # Update Side View
            self.side_widget.update_target(theta2, theta3_display, theta4)
            
            # Warnings
            warnings = []
            if result.was_clamped:
                warnings.append("CLAMPED")
            if not sol.is_valid:
                warnings.append("Joint limits exceeded")
            if not result.is_reachable:
                warnings.append(result.error_message)
            self.lbl_warning.config(text="⚠️ " + ", ".join(warnings) if warnings else "")
        else:
            self.lbl_warning.config(text="⚠️ " + result.error_message)
            self._current_solution = None
    
    def _update_slot_display(self, slot_num, theta, lbl_theta, lbl_pulse):
        """Update slot angle and pulse display."""
        params = getattr(self, f'p{slot_num}', None)
        if not params:
            lbl_theta.config(text=f"θ{slot_num}: {theta:.1f}° (No Config)")
            lbl_pulse.config(text="Pulse: --")
            return
        
        mapper = self.context.mapper
        zero_offset = params.get('zero_offset', 0)
        act_range = params.get('actuation_range', 180)
        
        phy_angle = theta + zero_offset
        phy_angle = max(0, min(act_range, phy_angle))
        
        pulse = mapper.physical_to_pulse(phy_angle, params['motor_config'])
        
        lbl_theta.config(text=f"θ{slot_num}: {theta:.1f}° | Phy: {phy_angle:.1f}°")
        lbl_pulse.config(text=f"Pulse: {pulse}")
    
    def send_command(self, duration):
        """Send command to all 4 slots."""
        if not all(hasattr(self, f'p{i}') and getattr(self, f'p{i}') for i in [1, 2, 3, 4]):
            self.log("[QuadView] Config not fully loaded")
            return
        
        sol = getattr(self, '_current_solution', None)
        if not sol:
            self.log("[QuadView] No IK solution available")
            return
        
        mapper = self.context.mapper
        targets = []
        
        for slot_num, theta in [(1, sol.theta1), (2, sol.theta2), (3, -sol.theta3), (4, sol.theta4)]:
            params = getattr(self, f'p{slot_num}')
            zero_off = params.get('zero_offset', 0)
            act_range = params.get('actuation_range', 180)
            
            phy_angle = theta + zero_off
            phy_angle = max(0, min(act_range, phy_angle))
            
            pulse = mapper.physical_to_pulse(phy_angle, params['motor_config'])
            targets.append((params['channel'], pulse))
            self.log(f"[QuadView] Slot{slot_num}: θ={theta:.1f}° → Phy={phy_angle:.1f}° → Pulse={pulse}")
        
        self.context.motion_planner.move_all(targets, duration)
        self.log(f"[QuadView] Sent 4 channels with duration={duration}s")
