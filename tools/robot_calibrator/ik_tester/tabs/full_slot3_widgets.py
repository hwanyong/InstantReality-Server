
import tkinter as tk
import math
import abc


class VisualWidget3(abc.ABC):
    """Abstract base class for reusable visualization widgets (Tab 6 Independent)."""
    
    @abc.abstractmethod
    def draw_static(self):
        """Draw static elements like grid and axes."""
        pass

    @abc.abstractmethod
    def update_target(self, *args, **kwargs):
        """Update dynamic target elements."""
        pass


def get_tkinter_offset3(joint_type, min_pos):
    """
    Get Tkinter angle offset based on min_pos dynamic alignment.
    Unified offset mapping as per analysis.
    (Tab 6 Independent Copy)
    """
    if joint_type == "horizontal":
        return 180 if min_pos == "left" else 0
    elif joint_type == "vertical":
        # top: 0° = 위쪽 → offset 0
        # bottom: 0° = 아래 → offset 180
        return 0 if min_pos == "top" else 180
    return 0


class TopDownWidget3(VisualWidget3):
    """
    Widget for 2D Top-Down (Planar) visualization.
    Used for Base Yaw (Slot 1) verification.
    (Tab 6 Independent Copy)
    """
    
    def __init__(self, canvas, config):
        """
        Args:
            canvas: The tk.Canvas instance to draw on.
            config: Dict containing:
                - canvas_size: int (e.g. 300)
                - scale: float (pixels per mm)
                - type: str ("horizontal")
                - min_pos: str
                - zero_offset: float
                - actuation_range: float
                - math_min: float
                - math_max: float
        """
        self.canvas = canvas
        self.cfg = config
        self.cx = config['canvas_size'] // 2
        self.cy = config['canvas_size'] // 2
        
    def draw_static(self):
        """Draw grid, axes, and validity arcs."""
        self.canvas.delete("static")
        size = self.cfg['canvas_size']
        
        # Grid lines
        for i in range(0, size + 1, 50):
            self.canvas.create_line(i, 0, i, size, fill="#333333", dash=(2, 4), tags="static")
            self.canvas.create_line(0, i, size, i, fill="#333333", dash=(2, 4), tags="static")
            
        # Axes
        self.canvas.create_line(self.cx, 0, self.cx, size, fill="#555555", width=1, tags="static")
        self.canvas.create_line(0, self.cy, size, self.cy, fill="#555555", width=1, tags="static")
        
        # Arcs (Config 기반: direction으로 자동 계산)
        radius = 140
        direction = self.cfg.get('direction', 1)
        base_offset = get_tkinter_offset3(self.cfg.get('type', 'horizontal'), self.cfg.get('min_pos', 'left'))
        arm_offset = 90 * direction
        offset = base_offset + arm_offset
        
        # Background Arc (Physical Capacity)
        full_min_math = 0 - self.cfg['zero_offset']
        extent_bg = self.cfg['actuation_range']  # direction 제거: 로컬 좌표계 CCW
        self.canvas.create_arc(self.cx - radius, self.cy - radius, 
                               self.cx + radius, self.cy + radius,
                               start=full_min_math + offset, extent=extent_bg,
                               fill="#222222", outline="#444444", width=1, style=tk.PIESLICE, tags="static")
                               
        # Foreground Arc (Math Valid Zone)
        start_angle = self.cfg['math_min'] + offset
        extent_fg = self.cfg['math_max'] - self.cfg['math_min']  # direction 제거
        
        self.canvas.create_arc(self.cx - radius, self.cy - radius, 
                               self.cx + radius, self.cy + radius,
                               start=start_angle, extent=extent_fg,
                               fill="#1a3a1a", outline="#44ff44", width=1, style=tk.PIESLICE, tags="static")
        
        # Base Marker
        self.canvas.create_oval(self.cx - 6, self.cy - 6, self.cx + 6, self.cy + 6, 
                                fill="#ffffff", outline="#888888", tags="static")

    def update_target(self, x, y, is_valid):
        """Draw target vector."""
        self.canvas.delete("dynamic")
        
        scale = self.cfg['scale']
        
        # Robot Frame (X-Right, Y-Forward) to Canvas Frame (X-Right, Y-Up -> Tkinter Y-Down)
        # Canvas X = cx + X
        # Canvas Y = cy - Y  (Inverted Y)
        
        target_cx = self.cx + x * scale
        target_cy = self.cy - y * scale
        
        # Clamp visual
        size = self.cfg['canvas_size']
        target_cx = max(10, min(size - 10, target_cx))
        target_cy = max(10, min(size - 10, target_cy))
        
        color = "#44ff44" if is_valid else "#ff4444"
        
        # Vector
        self.canvas.create_line(self.cx, self.cy, target_cx, target_cy,
                                fill=color, width=2, arrow=tk.LAST, tags="dynamic")
        
        # Dot
        self.canvas.create_oval(target_cx - 8, target_cy - 8, target_cx + 8, target_cy + 8,
                                fill=color, outline="#ffffff", width=2, tags="dynamic")


class SideElevation4LinkWidget3(VisualWidget3):
    """
    Widget for 4-Link Side Elevation (R/Z) visualization.
    Extends 3-Link to include Slot 4 (Wrist Pitch).
    (Tab 6 Independent Copy)
    """
    
    DEFAULT_D1 = 107.0
    DEFAULT_A2 = 105.0
    DEFAULT_A3 = 150.0
    DEFAULT_A4 = 65.0
    DEFAULT_A6 = 70.0  # Gripper length
    DEFAULT_SCALE = 0.35
    
    def __init__(self, canvas, config=None):
        self.canvas = canvas
        self.cfg = config or {'canvas_size': 180}
        self.cx = 40
    
    def _get_scale(self):
        return self.cfg.get('scale', self.DEFAULT_SCALE)
    
    def _get_d1(self):
        return self.cfg.get('d1', self.DEFAULT_D1) * self._get_scale()
    
    def _get_a2(self):
        return self.cfg.get('a2', self.DEFAULT_A2) * self._get_scale()
    
    def _get_a3(self):
        return self.cfg.get('a3', self.DEFAULT_A3) * self._get_scale()
    
    def _get_a4(self):
        return self.cfg.get('a4', self.DEFAULT_A4) * self._get_scale()
    
    def _get_a6(self):
        return self.cfg.get('a6', self.DEFAULT_A6) * self._get_scale()
    
    def _get_base_cy(self):
        return self.cfg.get('canvas_size', 180) - 20
    
    def _get_shoulder_cy(self):
        return self._get_base_cy() - self._get_d1()
    
    def draw_static(self):
        """Draw static elements: grid, ground, base, Slot 2 Arc."""
        self.canvas.delete("static")
        size = self.cfg.get('canvas_size', 240)
        
        # Grid
        for i in range(0, size + 1, 40):
            self.canvas.create_line(i, 0, i, size, fill="#333", dash=(2, 4), tags="static")
            self.canvas.create_line(0, i, size, i, fill="#333", dash=(2, 4), tags="static")
        
        base_cy = self._get_base_cy()
        shoulder_cy = self._get_shoulder_cy()
        shoulder_cx = self.cx
        
        # Ground line
        self.canvas.create_line(0, base_cy, size, base_cy, fill="#665544", width=2, tags="static")
        
        # --- Slot 2 Arc (Shoulder) - Blue ---
        s2 = self.cfg.get('slot2_params', {})
        if s2:
            radius = self._get_a2()
            offset = get_tkinter_offset3(s2.get('type', 'vertical'), s2.get('min_pos', 'bottom'))
            polarity = s2.get('polarity', 1)
            zero_offset = s2.get('zero_offset', 0)
            
            # Background Arc (full range)
            math_start = (0 - zero_offset) * polarity
            math_end = (s2.get('actuation_range', 180) - zero_offset) * polarity
            arc_start = min(math_start, math_end)
            arc_extent = abs(math_end - math_start)
            
            self.canvas.create_arc(shoulder_cx-radius, shoulder_cy-radius,
                                   shoulder_cx+radius, shoulder_cy+radius,
                                   start=arc_start + offset, extent=arc_extent,
                                   fill="", outline="#2266aa", width=1,
                                   style=tk.ARC, tags="static")
            
            # Foreground Arc (valid range)
            math_min = s2.get('math_min', -90)
            math_max = s2.get('math_max', 90)
            extent = math_max - math_min
            
            self.canvas.create_arc(shoulder_cx-radius, shoulder_cy-radius,
                                   shoulder_cx+radius, shoulder_cy+radius,
                                   start=math_min + offset, extent=extent,
                                   fill="", outline="#44aaff", width=2,
                                   style=tk.ARC, tags="static")
        
        # Base tower (d1)
        self.canvas.create_line(self.cx, base_cy, self.cx, shoulder_cy,
                               fill="#4488ff", width=4, tags="static")
        
        # Base joint
        self.canvas.create_oval(self.cx-4, base_cy-4, self.cx+4, base_cy+4,
                               fill="#fff", outline="#888", tags="static")
        
        # Shoulder joint
        self.canvas.create_oval(self.cx-5, shoulder_cy-5, self.cx+5, shoulder_cy+5,
                               fill="#88aaff", outline="#fff", width=2, tags="static")
    
    def update_target(self, theta2, theta3, theta4, R=None, Z=None):
        """
        Draw 4-link arm based on angles with full monitoring features.
        Args:
            theta2: Shoulder angle (deg)
            theta3: Elbow angle (deg, relative)
            theta4: Wrist angle (deg, approach angle)
            R: Optional target radius for IK visualization
            Z: Optional target height for IK visualization
        """
        self.canvas.delete("dynamic")
        
        shoulder_cx = self.cx
        shoulder_cy = self._get_shoulder_cy()
        base_cy = self._get_base_cy()
        d1 = self.cfg.get('d1', self.DEFAULT_D1)
        scale = self._get_scale()
        
        # --- Target Point and Guidelines (IK mode) ---
        if R is not None and Z is not None:
            target_rx = shoulder_cx + R * scale
            target_z_cy = shoulder_cy - (Z - d1) * scale
            
            # R Guideline (Vertical dashed line - green)
            self.canvas.create_line(target_rx, base_cy, target_rx, target_z_cy,
                                   fill="#88ff88", dash=(4, 4), width=1, tags="dynamic")
            
            # Z Guideline (Horizontal dashed line - orange)
            self.canvas.create_line(shoulder_cx, target_z_cy, target_rx, target_z_cy,
                                   fill="#ffaa44", dash=(4, 4), width=1, tags="dynamic")
            
            # Target Point (Red dot)
            self.canvas.create_oval(target_rx-5, target_z_cy-5, target_rx+5, target_z_cy+5,
                                   fill="#ff6666", outline="#fff", width=2, tags="dynamic")
        
        # --- Link 1: Shoulder -> Elbow (a2) ---
        a2_px = self._get_a2()
        theta2_rad = math.radians(theta2)
        elbow_cx = shoulder_cx + a2_px * math.cos(theta2_rad)
        elbow_cy = shoulder_cy - a2_px * math.sin(theta2_rad)
        
        # --- Slot 3 Arc (Elbow - Dynamic, rotates with θ2) ---
        s3 = self.cfg.get('slot3_params', {})
        if s3:
            a3_px = self._get_a3()
            offset = get_tkinter_offset3(s3.get('type', 'vertical'), s3.get('min_pos', 'top'))
            polarity = s3.get('polarity', 1)
            zero_offset = s3.get('zero_offset', 0)
            
            math_start = (0 - zero_offset) * polarity
            math_end = (s3.get('actuation_range', 180) - zero_offset) * polarity
            arc_start = min(math_start, math_end)
            arc_extent = abs(math_end - math_start)
            arc_rotation = theta2  # Arc rotates with shoulder
            
            # Background Arc (Orange - dim)
            self.canvas.create_arc(elbow_cx-a3_px, elbow_cy-a3_px,
                                   elbow_cx+a3_px, elbow_cy+a3_px,
                                   start=arc_start + offset + arc_rotation, extent=arc_extent,
                                   fill="", outline="#aa6622", width=1,
                                   style=tk.ARC, tags="dynamic")
            
            # Foreground Arc (Orange - bright, valid range)
            math_min = s3.get('math_min', -90)
            math_max = s3.get('math_max', 90)
            extent = math_max - math_min
            
            self.canvas.create_arc(elbow_cx-a3_px, elbow_cy-a3_px,
                                   elbow_cx+a3_px, elbow_cy+a3_px,
                                   start=math_min + offset + arc_rotation, extent=extent,
                                   fill="", outline="#ffaa44", width=2,
                                   style=tk.ARC, tags="dynamic")
        
        # Draw upper arm (Shoulder -> Elbow)
        self.canvas.create_line(shoulder_cx, shoulder_cy, elbow_cx, elbow_cy,
                               fill="#44ff88", width=4, tags="dynamic")
        
        # Elbow joint
        self.canvas.create_oval(elbow_cx-4, elbow_cy-4, elbow_cx+4, elbow_cy+4,
                               fill="#ffaa44", outline="#fff", width=2, tags="dynamic")
        
        # --- Link 2: Elbow -> Wrist (a3) ---
        a3_px = self._get_a3()
        global_theta3 = theta2 - theta3
        theta3_rad = math.radians(global_theta3)
        wrist_cx = elbow_cx + a3_px * math.cos(theta3_rad)
        wrist_cy = elbow_cy - a3_px * math.sin(theta3_rad)
        
        # --- Slot 4 Arc (Wrist - Dynamic, rotates with global_theta3) ---
        s4 = self.cfg.get('slot4_params', {})
        if s4:
            a4_px = self._get_a4()
            offset = get_tkinter_offset3(s4.get('type', 'vertical'), s4.get('min_pos', 'top'))
            polarity = s4.get('polarity', 1)
            zero_offset = s4.get('zero_offset', 0)
            
            math_start = (0 - zero_offset) * polarity
            math_end = (s4.get('actuation_range', 180) - zero_offset) * polarity
            arc_start = min(math_start, math_end)
            arc_extent = abs(math_end - math_start)
            arc_rotation = global_theta3  # Arc rotates with forearm
            
            # Background Arc (Pink - dim)
            self.canvas.create_arc(wrist_cx-a4_px, wrist_cy-a4_px,
                                   wrist_cx+a4_px, wrist_cy+a4_px,
                                   start=arc_start + offset + arc_rotation, extent=arc_extent,
                                   fill="", outline="#aa22aa", width=1,
                                   style=tk.ARC, tags="dynamic")
            
            # Foreground Arc (Pink - bright, valid range)
            math_min = s4.get('math_min', -90)
            math_max = s4.get('math_max', 90)
            extent = math_max - math_min
            
            self.canvas.create_arc(wrist_cx-a4_px, wrist_cy-a4_px,
                                   wrist_cx+a4_px, wrist_cy+a4_px,
                                   start=math_min + offset + arc_rotation, extent=extent,
                                   fill="", outline="#ff44ff", width=2,
                                   style=tk.ARC, tags="dynamic")
        
        # Draw forearm (Elbow -> Wrist)
        self.canvas.create_line(elbow_cx, elbow_cy, wrist_cx, wrist_cy,
                               fill="#88ff44", width=3, tags="dynamic")
        
        # Wrist joint
        self.canvas.create_oval(wrist_cx-4, wrist_cy-4, wrist_cx+4, wrist_cy+4,
                               fill="#ff6666", outline="#fff", width=2, tags="dynamic")
        
        # --- Link 3: Wrist -> Gripper (a4) ---
        a4_px = self._get_a4()
        global_theta4 = global_theta3 + theta4  # Absolute angle in R-Z plane
        theta4_rad = math.radians(global_theta4)
        
        gripper_cx = wrist_cx + a4_px * math.cos(theta4_rad)
        gripper_cy = wrist_cy - a4_px * math.sin(theta4_rad)
        
        # Draw wrist link (Wrist -> Wrist End)
        self.canvas.create_line(wrist_cx, wrist_cy, gripper_cx, gripper_cy,
                               fill="#ff88ff", width=2, tags="dynamic")
        
        # Wrist end joint
        self.canvas.create_oval(gripper_cx-3, gripper_cy-3, gripper_cx+3, gripper_cy+3,
                               fill="#ff44ff", outline="#fff", width=1, tags="dynamic")
        
        # --- Link 4: Gripper Extension (a6) ---
        a6_px = self._get_a6()
        # Gripper extends in same direction as wrist (theta4)
        gripper_tip_cx = gripper_cx + a6_px * math.cos(theta4_rad)
        gripper_tip_cy = gripper_cy - a6_px * math.sin(theta4_rad)
        
        # Draw gripper link (Yellow)
        self.canvas.create_line(gripper_cx, gripper_cy, gripper_tip_cx, gripper_tip_cy,
                               fill="#ffff44", width=3, tags="dynamic")
        
        # Gripper Tip (Yellow dot = Target)
        self.canvas.create_oval(gripper_tip_cx-5, gripper_tip_cy-5, 
                               gripper_tip_cx+5, gripper_tip_cy+5,
                               fill="#ffff00", outline="#fff", width=2, tags="dynamic")
        
        # --- Angle labels ---
        self.canvas.create_text(10, 15, anchor="nw", fill="#aaffaa",
                               font=("Consolas", 9),
                               text=f"θ2: {theta2:.1f}°", tags="dynamic")
        self.canvas.create_text(10, 30, anchor="nw", fill="#ffffaa",
                               font=("Consolas", 9),
                               text=f"θ3: {theta3:.1f}° (rel)", tags="dynamic")
        self.canvas.create_text(10, 45, anchor="nw", fill="#ffaaff",
                               font=("Consolas", 9),
                               text=f"θ4: {theta4:.1f}° → G: {global_theta4:.1f}°", tags="dynamic")


class GripperStateWidget3(VisualWidget3):
    """
    Widget for Gripper rotation (Roll θ5) and Open/Close (θ6) visualization.
    Top-down view showing gripper fingers and rotation state.
    (Tab 6 Independent Copy)
    """
    
    def __init__(self, canvas, config=None):
        self.canvas = canvas
        self.cfg = config or {'canvas_size': 120}
        size = self.cfg.get('canvas_size', 120)
        self.cx = size // 2
        self.cy = size // 2
        self.finger_length = 25
        self.finger_width = 6
    
    def draw_static(self):
        """Draw grid and center point."""
        self.canvas.delete("static")
        size = self.cfg.get('canvas_size', 120)
        
        # Background
        self.canvas.create_rectangle(0, 0, size, size, fill="#1a1a2e", outline="", tags="static")
        
        # Grid
        for i in range(0, size + 1, 30):
            self.canvas.create_line(i, 0, i, size, fill="#333", dash=(2, 4), tags="static")
            self.canvas.create_line(0, i, size, i, fill="#333", dash=(2, 4), tags="static")
        
        # Center cross
        self.canvas.create_line(self.cx - 10, self.cy, self.cx + 10, self.cy,
                               fill="#555", width=1, tags="static")
        self.canvas.create_line(self.cx, self.cy - 10, self.cx, self.cy + 10,
                               fill="#555", width=1, tags="static")
    
    def update_target(self, *args, **kwargs):
        """Abstract method implementation - delegates to update()."""
        if len(args) >= 2:
            self.update(args[0], args[1])
    
    def update(self, roll_angle, gripper_angle):
        """
        Update gripper visualization.
        Args:
            roll_angle: Wrist roll angle (θ5) in degrees
            gripper_angle: Gripper angle (θ6) in degrees (0=open, 180=closed)
        """
        self.canvas.delete("dynamic")
        
        # Convert angles to radians
        roll_rad = math.radians(roll_angle)
        
        # Gripper opening: 0° = max open, ~55° = closed
        max_opening = 20  # max finger separation (pixels)
        min_opening = 2   # min finger separation when closed
        # Map gripper angle to opening (0° = open, 55° = closed)
        opening = max(min_opening, max_opening - (gripper_angle / 55.0) * (max_opening - min_opening))
        
        # Calculate finger positions based on roll angle
        # Perpendicular to roll direction
        perp_angle = roll_rad + math.pi / 2
        
        # Finger 1 (left when roll=0)
        f1_start_x = self.cx + opening * math.cos(perp_angle)
        f1_start_y = self.cy - opening * math.sin(perp_angle)
        f1_end_x = f1_start_x + self.finger_length * math.cos(roll_rad)
        f1_end_y = f1_start_y - self.finger_length * math.sin(roll_rad)
        
        # Finger 2 (right when roll=0)
        f2_start_x = self.cx - opening * math.cos(perp_angle)
        f2_start_y = self.cy + opening * math.sin(perp_angle)
        f2_end_x = f2_start_x + self.finger_length * math.cos(roll_rad)
        f2_end_y = f2_start_y - self.finger_length * math.sin(roll_rad)
        
        # Draw wrist mount (circle at center)
        mount_r = 8
        self.canvas.create_oval(self.cx - mount_r, self.cy - mount_r,
                               self.cx + mount_r, self.cy + mount_r,
                               fill="#444", outline="#666", width=2, tags="dynamic")
        
        # Draw fingers (yellow)
        self.canvas.create_line(f1_start_x, f1_start_y, f1_end_x, f1_end_y,
                               fill="#ffff44", width=self.finger_width, 
                               capstyle=tk.ROUND, tags="dynamic")
        self.canvas.create_line(f2_start_x, f2_start_y, f2_end_x, f2_end_y,
                               fill="#ffff44", width=self.finger_width,
                               capstyle=tk.ROUND, tags="dynamic")
        
        # Draw finger tips (slightly darker)
        tip_r = 3
        self.canvas.create_oval(f1_end_x - tip_r, f1_end_y - tip_r,
                               f1_end_x + tip_r, f1_end_y + tip_r,
                               fill="#cccc00", outline="", tags="dynamic")
        self.canvas.create_oval(f2_end_x - tip_r, f2_end_y - tip_r,
                               f2_end_x + tip_r, f2_end_y + tip_r,
                               fill="#cccc00", outline="", tags="dynamic")
        
        # Draw roll direction indicator (arrow from center)
        arrow_len = 35
        arrow_x = self.cx + arrow_len * math.cos(roll_rad)
        arrow_y = self.cy - arrow_len * math.sin(roll_rad)
        self.canvas.create_line(self.cx, self.cy, arrow_x, arrow_y,
                               fill="#88aaff", width=2, arrow=tk.LAST, tags="dynamic")
        
        # State label
        state = "OPEN" if gripper_angle < 30 else "CLOSED" if gripper_angle > 50 else "PARTIAL"
        state_color = "#44ff44" if state == "OPEN" else "#ff4444" if state == "CLOSED" else "#ffaa44"
        
        self.canvas.create_text(self.cx, self.cfg.get('canvas_size', 120) - 8,
                               anchor="s", fill=state_color,
                               font=("Consolas", 9, "bold"),
                               text=state, tags="dynamic")
        
        # Angle labels
        self.canvas.create_text(5, 5, anchor="nw", fill="#88aaff",
                               font=("Consolas", 8),
                               text=f"Roll: {roll_angle:.0f}°", tags="dynamic")
        self.canvas.create_text(5, 15, anchor="nw", fill="#ffff44",
                               font=("Consolas", 8),
                               text=f"Grip: {gripper_angle:.0f}°", tags="dynamic")
