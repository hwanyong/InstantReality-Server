
import tkinter as tk
import math
from .core import VisualWidget

def get_tkinter_offset(joint_type, min_pos):
    """
    Get Tkinter angle offset based on min_pos dynamic alignment.
    Unified offset mapping as per analysis.
    """
    if joint_type == "horizontal":
        return 180 if min_pos == "left" else 0
    elif joint_type == "vertical":
        # top: 0° = 위쪽 → offset 0
        # bottom: 0° = 아래 → offset 180
        return 0 if min_pos == "top" else 180
    return 0

class TopDownWidget(VisualWidget):
    """
    Widget for 2D Top-Down (Planar) visualization.
    Used for Base Yaw (Slot 1) verification.
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
        
        # Arcs
        radius = 140
        offset = get_tkinter_offset(self.cfg.get('type', 'horizontal'), self.cfg.get('min_pos', 'left'))
        
        # Background Arc (Physical Capacity)
        full_min_math = 0 - self.cfg['zero_offset']
        self.canvas.create_arc(self.cx - radius, self.cy - radius, 
                               self.cx + radius, self.cy + radius,
                               start=full_min_math + offset, extent=self.cfg['actuation_range'],
                               fill="#222222", outline="#444444", width=1, style=tk.PIESLICE, tags="static")
                               
        # Foreground Arc (Math Valid Zone)
        start_angle = self.cfg['math_min'] + offset
        extent = self.cfg['math_max'] - self.cfg['math_min']
        
        self.canvas.create_arc(self.cx - radius, self.cy - radius, 
                               self.cx + radius, self.cy + radius,
                               start=start_angle, extent=extent,
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


class SideElevationWidget(VisualWidget):
    """
    Widget for 2D Side Elevation (R/Z) visualization.
    Used for Shoulder/Elbow/Wrist verification.
    """
    
    def __init__(self, canvas, config):
        """
        Args:
            canvas: Tkinter canvas.
            config: Dict containing:
                - canvas_size: int
                - scale: float
                - d1: float (Base Height)
                - a2: float (Upper Arm)
                - z_max: float
                - slot2_params: dict (type, min_pos, zero_offset, polarity, range, min, max)
                # Note: Polarity and Limits handled by caller, we just need visual params
        """
        self.canvas = canvas
        self.cfg = config
        self.cx = 120 # Fixed center for shoulder
        
    def _get_base_cy(self):
        scale = self.cfg['scale']
        z_max = self.cfg.get('z_max', 300)
        return 30 + z_max * scale

    def _get_shoulder_cy(self):
        scale = self.cfg['scale']
        z_max = self.cfg.get('z_max', 300)
        d1 = self.cfg.get('d1', 107)
        return 30 + (z_max - d1) * scale

    def draw_static(self):
        self.canvas.delete("static")
        size = self.cfg['canvas_size']
        scale = self.cfg['scale']
        
        # Grid
        for i in range(0, size + 1, 40):
            self.canvas.create_line(i, 0, i, size, fill="#333", dash=(2, 4), tags="static")
            self.canvas.create_line(0, i, size, i, fill="#333", dash=(2, 4), tags="static")
            
        base_cy = self._get_base_cy()
        shoulder_cy = self._get_shoulder_cy()
        shoulder_cx = self.cx
        
        # Ground
        self.canvas.create_line(0, base_cy, size, base_cy, fill="#665544", width=2, tags="static")
        
        # Base Tower (d1)
        self.canvas.create_line(shoulder_cx, base_cy, shoulder_cx, shoulder_cy,
                                fill="#4488ff", width=4, tags="static")
                                
        # Validity Arcs (Shoulder)
        s2 = self.cfg.get('slot2_params', {})
        if s2:
            radius = self.cfg.get('a2', 105) * scale
            offset = get_tkinter_offset(s2.get('type', 'vertical'), s2.get('min_pos', 'bottom'))
            polarity = s2.get('polarity', 1)
            zero_offset = s2.get('zero_offset', 0)
            
            # Background Arc (Capacity)
            # Physical [0, actuation_range] -> Math
            # Math = (Physical - Zero) / Polarity
            math_start = (0 - zero_offset) * polarity
            math_end = (s2.get('actuation_range', 180) - zero_offset) * polarity
            
            # Sort for drawing
            arc_start = min(math_start, math_end)
            arc_extent = abs(math_end - math_start)
            
            self.canvas.create_arc(shoulder_cx-radius, shoulder_cy-radius,
                                   shoulder_cx+radius, shoulder_cy+radius,
                                   start=arc_start + offset, extent=arc_extent,
                                   fill="#222222", outline="#444444", style=tk.PIESLICE, tags="static")
                                   
            # Foreground Arc (Valid Zone)
            math_min = s2.get('math_min', -90)
            math_max = s2.get('math_max', 90)
            extent = math_max - math_min
            
            self.canvas.create_arc(shoulder_cx-radius, shoulder_cy-radius,
                                   shoulder_cx+radius, shoulder_cy+radius,
                                   start=math_min + offset, extent=extent,
                                   fill="#1a3a1a", outline="#44ff44", style=tk.PIESLICE, tags="static")

        # Joints
        self.canvas.create_oval(shoulder_cx-4, base_cy-4, shoulder_cx+4, base_cy+4, fill="#fff", tags="static")
        self.canvas.create_oval(shoulder_cx-4, shoulder_cy-4, shoulder_cx+4, shoulder_cy+4, fill="#88aaff", tags="static")

    def update_target(self, R, z, theta2, valid2):
        """
        Draw ghost arm and target based on angles.
        Args:
            R: Target radius (horizontal distance from base)
            z: Target height (mm)
            theta2: Shoulder Pitch (deg)
            valid2: Boolean validity of shoulder
        """
        self.canvas.delete("dynamic")
        
        scale = self.cfg['scale']
        size = self.cfg['canvas_size']
        shoulder_cx = self.cx
        shoulder_cy = self._get_shoulder_cy()
        base_cy = self._get_base_cy()
        d1 = self.cfg.get('d1', 107)
        
        # --- 1. Draw Arm (Forward Kinematics) ---
        theta2_rad = math.radians(theta2)
        
        elbow_cx = shoulder_cx + (self.cfg['a2'] * scale) * math.cos(theta2_rad)
        elbow_cy = shoulder_cy - (self.cfg['a2'] * scale) * math.sin(theta2_rad)
        
        self.canvas.create_line(shoulder_cx, shoulder_cy, elbow_cx, elbow_cy,
                                fill="#44ff88", width=3, tags="dynamic")
        self.canvas.create_oval(elbow_cx-3, elbow_cy-3, elbow_cx+3, elbow_cy+3,
                                fill="#ffaa44", outline="#fff", tags="dynamic")
        
        # --- 2. Target Guidelines and Point ---
        target_rx = shoulder_cx + R * scale
        target_z_cy = shoulder_cy - (z - d1) * scale
        
        # R Guideline (Vertical) - Improved visibility
        self.canvas.create_line(target_rx, base_cy, target_rx, target_z_cy,
                                fill="#88ff88", dash=(4, 4), width=1, tags="dynamic")
        
        # Z Guideline (Horizontal) - New
        self.canvas.create_line(shoulder_cx, target_z_cy, target_rx, target_z_cy,
                                fill="#ffaa44", dash=(4, 4), width=1, tags="dynamic")
        
        # Target Point - New
        self.canvas.create_oval(target_rx-5, target_z_cy-5, target_rx+5, target_z_cy+5,
                                fill="#ff6666", outline="#fff", width=2, tags="dynamic")
        
        # Shoulder -> Target Angle Line - New
        self.canvas.create_line(shoulder_cx, shoulder_cy, target_rx, target_z_cy,
                                fill="#ff8888", dash=(2, 4), width=2, tags="dynamic")


class SideElevation3LinkWidget(VisualWidget):
    """
    Widget for 3-Link Side Elevation (R/Z) visualization.
    Used for Slot 1+2+3 (Base/Shoulder/Elbow) verification.
    Now supports config-based link lengths.
    """
    
    # Default values (mm) - used when config not provided
    DEFAULT_D1 = 107.0
    DEFAULT_A2 = 105.0
    DEFAULT_A3 = 150.0
    DEFAULT_SCALE = 0.4  # mm -> px
    
    def __init__(self, canvas, config=None):
        """
        Args:
            canvas: Tkinter canvas.
            config: Config dict with optional keys:
                - d1: Base height (mm)
                - a2: Upper arm length (mm)
                - a3: Forearm length (mm)
                - scale: mm to px scale factor
        """
        self.canvas = canvas
        self.cfg = config or {'canvas_size': 240}
        self.cx = 60  # Fixed center X for base
    
    def _get_scale(self):
        return self.cfg.get('scale', self.DEFAULT_SCALE)
    
    def _get_d1(self):
        """Get d1 (base height) in pixels."""
        return self.cfg.get('d1', self.DEFAULT_D1) * self._get_scale()
    
    def _get_a2(self):
        """Get a2 (upper arm) in pixels."""
        return self.cfg.get('a2', self.DEFAULT_A2) * self._get_scale()
    
    def _get_a3(self):
        """Get a3 (forearm) in pixels."""
        return self.cfg.get('a3', self.DEFAULT_A3) * self._get_scale()
        
    def _get_base_cy(self):
        """Get base Y coordinate (ground level)."""
        return self.cfg.get('canvas_size', 240) - 30
    
    def _get_shoulder_cy(self):
        """Get shoulder Y coordinate (top of base tower)."""
        return self._get_base_cy() - self._get_d1()
    
    def draw_static(self):
        """Draw static elements: grid, ground, base tower, Slot 2 Arc."""
        self.canvas.delete("static")
        size = self.cfg.get('canvas_size', 240)
        scale = self._get_scale()
        
        # Grid
        for i in range(0, size + 1, 40):
            self.canvas.create_line(i, 0, i, size, fill="#333", dash=(2, 4), tags="static")
            self.canvas.create_line(0, i, size, i, fill="#333", dash=(2, 4), tags="static")
        
        base_cy = self._get_base_cy()
        shoulder_cy = self._get_shoulder_cy()
        shoulder_cx = self.cx
        
        # Ground line
        self.canvas.create_line(0, base_cy, size, base_cy, 
                               fill="#665544", width=2, tags="static")
        
        # --- Slot 2 Arc (Shoulder) ---
        s2 = self.cfg.get('slot2_params', {})
        if s2:
            radius = self._get_a2()
            offset = get_tkinter_offset(s2.get('type', 'vertical'), s2.get('min_pos', 'bottom'))
            polarity = s2.get('polarity', 1)
            zero_offset = s2.get('zero_offset', 0)
            
            # Physical [0, actuation_range] -> Math
            math_start = (0 - zero_offset) * polarity
            math_end = (s2.get('actuation_range', 180) - zero_offset) * polarity
            
            arc_start = min(math_start, math_end)
            arc_extent = abs(math_end - math_start)
            
            # Background Arc (全範囲) - Slot 2: Blue
            self.canvas.create_arc(shoulder_cx-radius, shoulder_cy-radius,
                                   shoulder_cx+radius, shoulder_cy+radius,
                                   start=arc_start + offset, extent=arc_extent,
                                   fill="", outline="#2266aa", width=1,
                                   style=tk.ARC, tags="static")
            
            # Foreground Arc (有効範囲) - Slot 2: Blue
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
    
    def update_target(self, theta2, theta3, R=None, Z=None):
        """
        Draw 3-link arm based on angles and optional target point.
        Args:
            theta2: Shoulder angle (deg) - 0 = horizontal right
            theta3: Elbow angle (deg) - relative to shoulder, 0 = straight
            R: Optional target radius (horizontal distance) for IK
            Z: Optional target height (mm) for IK
        """
        self.canvas.delete("dynamic")
        
        shoulder_cx = self.cx
        shoulder_cy = self._get_shoulder_cy()
        base_cy = self._get_base_cy()
        d1 = self.cfg.get('d1', self.DEFAULT_D1)
        scale = self.cfg.get('scale', self.DEFAULT_SCALE)
        
        # --- Target Point and Guidelines (IK mode) ---
        if R is not None and Z is not None:
            target_rx = shoulder_cx + R * scale
            target_z_cy = shoulder_cy - (Z - d1) * scale
            
            # R Guideline (Vertical dashed line)
            self.canvas.create_line(target_rx, base_cy, target_rx, target_z_cy,
                                   fill="#88ff88", dash=(4, 4), width=1, tags="dynamic")
            
            # Z Guideline (Horizontal dashed line)
            self.canvas.create_line(shoulder_cx, target_z_cy, target_rx, target_z_cy,
                                   fill="#ffaa44", dash=(4, 4), width=1, tags="dynamic")
            
            # Target Point (Red dot)
            self.canvas.create_oval(target_rx-5, target_z_cy-5, target_rx+5, target_z_cy+5,
                                   fill="#ff6666", outline="#fff", width=2, tags="dynamic")
        
        # --- Link 1: Shoulder -> Elbow (A2) ---
        a2_px = self._get_a2()
        theta2_rad = math.radians(theta2)
        elbow_cx = shoulder_cx + a2_px * math.cos(theta2_rad)
        elbow_cy = shoulder_cy - a2_px * math.sin(theta2_rad)
        
        # --- Slot 3 Arc (Elbow - Dynamic) ---
        s3 = self.cfg.get('slot3_params', {})
        if s3:
            a3_px = self._get_a3()
            offset = get_tkinter_offset(s3.get('type', 'vertical'), s3.get('min_pos', 'top'))
            polarity = s3.get('polarity', 1)
            zero_offset = s3.get('zero_offset', 0)
            
            # Physical [0, actuation_range] -> Math (relative to shoulder line)
            math_start = (0 - zero_offset) * polarity
            math_end = (s3.get('actuation_range', 180) - zero_offset) * polarity
            
            arc_start = min(math_start, math_end)
            arc_extent = abs(math_end - math_start)
            
            # Apply theta2 rotation (Arc rotates with shoulder)
            arc_rotation = theta2
            
            # Background Arc - Slot 3: Orange
            self.canvas.create_arc(elbow_cx-a3_px, elbow_cy-a3_px,
                                   elbow_cx+a3_px, elbow_cy+a3_px,
                                   start=arc_start + offset + arc_rotation, extent=arc_extent,
                                   fill="", outline="#aa6622", width=1,
                                   style=tk.ARC, tags="dynamic")
            
            # Foreground Arc - Slot 3: Orange
            math_min = s3.get('math_min', -90)
            math_max = s3.get('math_max', 90)
            extent = math_max - math_min
            
            self.canvas.create_arc(elbow_cx-a3_px, elbow_cy-a3_px,
                                   elbow_cx+a3_px, elbow_cy+a3_px,
                                   start=math_min + offset + arc_rotation, extent=extent,
                                   fill="", outline="#ffaa44", width=2,
                                   style=tk.ARC, tags="dynamic")
        
        # Draw upper arm
        self.canvas.create_line(shoulder_cx, shoulder_cy, elbow_cx, elbow_cy,
                               fill="#44ff88", width=4, tags="dynamic")
        
        # Elbow joint
        self.canvas.create_oval(elbow_cx-4, elbow_cy-4, elbow_cx+4, elbow_cy+4,
                               fill="#ffaa44", outline="#fff", width=2, tags="dynamic")
        
        # --- Link 2: Elbow -> Wrist (A3) ---
        a3_px = self._get_a3()
        # Global angle = θ2 - θ3 (render with original IK direction)
        global_theta3 = theta2 - theta3
        theta3_rad = math.radians(global_theta3)
        wrist_cx = elbow_cx + a3_px * math.cos(theta3_rad)
        wrist_cy = elbow_cy - a3_px * math.sin(theta3_rad)
        
        # Draw forearm
        self.canvas.create_line(elbow_cx, elbow_cy, wrist_cx, wrist_cy,
                               fill="#88ff44", width=3, tags="dynamic")
        
        # Wrist joint (end effector)
        self.canvas.create_oval(wrist_cx-4, wrist_cy-4, wrist_cx+4, wrist_cy+4,
                               fill="#ff6666", outline="#fff", width=2, tags="dynamic")
        
        # --- Angle labels (debug) ---
        self.canvas.create_text(10, 15, anchor="nw", fill="#aaffaa",
                               font=("Consolas", 9),
                               text=f"θ2: {theta2:.1f}°", tags="dynamic")
        self.canvas.create_text(10, 30, anchor="nw", fill="#ffffaa",
                               font=("Consolas", 9),
                               text=f"θ3: {theta3:.1f}° (rel)", tags="dynamic")
        self.canvas.create_text(10, 45, anchor="nw", fill="#ffaaaa",
                               font=("Consolas", 9),
                               text=f"Global: {global_theta3:.1f}°", tags="dynamic")


class SideElevation4LinkWidget(VisualWidget):
    """
    Widget for 4-Link Side Elevation (R/Z) visualization.
    Extends 3-Link to include Slot 4 (Wrist Pitch).
    """
    
    DEFAULT_D1 = 107.0
    DEFAULT_A2 = 105.0
    DEFAULT_A3 = 150.0
    DEFAULT_A4 = 65.0
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
            offset = get_tkinter_offset(s2.get('type', 'vertical'), s2.get('min_pos', 'bottom'))
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
            offset = get_tkinter_offset(s3.get('type', 'vertical'), s3.get('min_pos', 'top'))
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
            offset = get_tkinter_offset(s4.get('type', 'vertical'), s4.get('min_pos', 'top'))
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
        
        # Draw gripper link (Wrist -> Gripper)
        self.canvas.create_line(wrist_cx, wrist_cy, gripper_cx, gripper_cy,
                               fill="#ff88ff", width=2, tags="dynamic")
        
        # Gripper end point
        self.canvas.create_oval(gripper_cx-4, gripper_cy-4, gripper_cx+4, gripper_cy+4,
                               fill="#ff44ff", outline="#fff", width=2, tags="dynamic")
        
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


class WristPitchGaugeWidget(VisualWidget):
    """
    Widget for Slot 4 (Wrist Pitch) local angle gauge.
    Displays arc and pointer for θ4 visualization.
    """
    
    def __init__(self, canvas, config=None):
        self.canvas = canvas
        self.cfg = config or {'canvas_size': 120}
        size = self.cfg.get('canvas_size', 120)
        self.cx = size // 2
        self.cy = size // 2 + 10
        self.radius = size // 2 - 15
    
    def draw_static(self):
        """Draw static gauge background."""
        self.canvas.delete("static")
        size = self.cfg.get('canvas_size', 120)
        
        # Background arc (full range -90 to +90)
        self.canvas.create_arc(
            self.cx - self.radius, self.cy - self.radius,
            self.cx + self.radius, self.cy + self.radius,
            start=0, extent=180,
            fill="#222233", outline="#444466", width=2,
            style=tk.PIESLICE, tags="static"
        )
        
        # Valid range arc (math_min to math_max)
        math_min = self.cfg.get('math_min', -90)
        math_max = self.cfg.get('math_max', 90)
        start = 90 - math_max
        extent = math_max - math_min
        
        self.canvas.create_arc(
            self.cx - self.radius + 5, self.cy - self.radius + 5,
            self.cx + self.radius - 5, self.cy + self.radius - 5,
            start=start, extent=extent,
            fill="#1a3a1a", outline="#44ff44", width=2,
            style=tk.PIESLICE, tags="static"
        )
        
        # Center point
        self.canvas.create_oval(
            self.cx - 4, self.cy - 4, self.cx + 4, self.cy + 4,
            fill="#ffffff", outline="#888888", tags="static"
        )
        
        # Tick marks
        for angle in [-90, -45, 0, 45, 90]:
            rad = math.radians(90 - angle)
            inner_r = self.radius - 8
            outer_r = self.radius
            x1 = self.cx + inner_r * math.cos(rad)
            y1 = self.cy - inner_r * math.sin(rad)
            x2 = self.cx + outer_r * math.cos(rad)
            y2 = self.cy - outer_r * math.sin(rad)
            self.canvas.create_line(x1, y1, x2, y2, fill="#888888", width=1, tags="static")
    
    def update_target(self, theta4, is_valid=True):
        """Update pointer position."""
        self.canvas.delete("dynamic")
        
        # Pointer
        rad = math.radians(90 - theta4)
        pointer_len = self.radius - 10
        px = self.cx + pointer_len * math.cos(rad)
        py = self.cy - pointer_len * math.sin(rad)
        
        color = "#44ff44" if is_valid else "#ff4444"
        
        self.canvas.create_line(
            self.cx, self.cy, px, py,
            fill=color, width=3, arrow=tk.LAST, tags="dynamic"
        )
        
        # Angle text
        self.canvas.create_text(
            self.cx, self.cy + self.radius + 10,
            text=f"{theta4:.1f}°", fill=color,
            font=("Consolas", 10, "bold"), tags="dynamic"
        )


class TopDownWristWidget(VisualWidget):
    """
    Widget for Slot 4 Top-Down (X-Y) view.
    Shows wrist position and gripper direction based on θ1 and θ4.
    """
    
    def __init__(self, canvas, config=None):
        self.canvas = canvas
        self.cfg = config or {'canvas_size': 120}
        size = self.cfg.get('canvas_size', 120)
        self.cx = size // 2
        self.cy = size // 2
        self.scale = 0.3  # mm -> px
    
    def draw_static(self):
        """Draw static grid and center."""
        self.canvas.delete("static")
        size = self.cfg.get('canvas_size', 120)
        
        # Grid
        for i in range(0, size + 1, 20):
            self.canvas.create_line(i, 0, i, size, fill="#333", dash=(2, 4), tags="static")
            self.canvas.create_line(0, i, size, i, fill="#333", dash=(2, 4), tags="static")
        
        # Axes
        self.canvas.create_line(self.cx, 0, self.cx, size, fill="#555", width=1, tags="static")
        self.canvas.create_line(0, self.cy, size, self.cy, fill="#555", width=1, tags="static")
        
        # Center (base)
        self.canvas.create_oval(self.cx-3, self.cy-3, self.cx+3, self.cy+3,
                               fill="#4488ff", outline="#fff", tags="static")
    
    def update_target(self, theta1, R, a4, theta4):
        """
        Draw top-down view with wrist position and gripper direction.
        Args:
            theta1: Base yaw angle (deg)
            R: Horizontal radius from base to wrist (mm)
            a4: Gripper link length (mm)
            theta4: Wrist pitch angle (deg) - relative to base direction
        """
        self.canvas.delete("dynamic")
        
        # Wrist position (from base along θ1)
        theta1_rad = math.radians(theta1)
        wrist_x = self.cx + R * self.scale * math.cos(theta1_rad)
        wrist_y = self.cy - R * self.scale * math.sin(theta1_rad)  # Tkinter Y inverted
        
        # Base -> Wrist line (arm projection)
        self.canvas.create_line(self.cx, self.cy, wrist_x, wrist_y,
                               fill="#44ff88", width=2, dash=(4, 2), tags="dynamic")
        
        # Wrist joint
        self.canvas.create_oval(wrist_x-4, wrist_y-4, wrist_x+4, wrist_y+4,
                               fill="#ff6666", outline="#fff", width=2, tags="dynamic")
        
        # Gripper direction (θ1 + θ4)
        gripper_angle = theta1 + theta4
        gripper_rad = math.radians(gripper_angle)
        gripper_x = wrist_x + a4 * self.scale * math.cos(gripper_rad)
        gripper_y = wrist_y - a4 * self.scale * math.sin(gripper_rad)
        
        # Wrist -> Gripper line
        self.canvas.create_line(wrist_x, wrist_y, gripper_x, gripper_y,
                               fill="#ff88ff", width=3, arrow=tk.LAST, tags="dynamic")
        
        # Gripper tip
        self.canvas.create_oval(gripper_x-3, gripper_y-3, gripper_x+3, gripper_y+3,
                               fill="#ff44ff", outline="#fff", width=2, tags="dynamic")
        
        # Labels
        self.canvas.create_text(5, 5, anchor="nw", fill="#aaffaa",
                               font=("Consolas", 8),
                               text=f"θ1: {theta1:.0f}°", tags="dynamic")
        self.canvas.create_text(5, 15, anchor="nw", fill="#ffaaff",
                               font=("Consolas", 8),
                               text=f"θ4: {theta4:.1f}°", tags="dynamic")
