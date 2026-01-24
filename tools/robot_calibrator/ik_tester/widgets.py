
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
        # 'bottom' (6 o'clock) needs 0 offset to map +Angle to CCW (Up) correctly
        # relative to the 3 o'clock (0 deg) anchor.
        return 180 
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
    Phase 2: Hardcoded link lengths, no config binding.
    """
    
    # Hardcoded constants (Phase 2 - no config binding)
    D1 = 40   # Base height (pixels, scaled)
    A2 = 40   # Upper arm length (pixels, scaled)
    A3 = 60   # Forearm length (pixels, scaled)
    
    def __init__(self, canvas, config=None):
        """
        Args:
            canvas: Tkinter canvas.
            config: Optional config dict (not used in Phase 2).
        """
        self.canvas = canvas
        self.cfg = config or {'canvas_size': 240}
        self.cx = 60  # Fixed center X for base
        
    def _get_base_cy(self):
        """Get base Y coordinate (ground level)."""
        return self.cfg.get('canvas_size', 240) - 30
    
    def _get_shoulder_cy(self):
        """Get shoulder Y coordinate (top of base tower)."""
        return self._get_base_cy() - self.D1
    
    def draw_static(self):
        """Draw static elements: grid, ground, base tower."""
        self.canvas.delete("static")
        size = self.cfg.get('canvas_size', 240)
        
        # Grid
        for i in range(0, size + 1, 40):
            self.canvas.create_line(i, 0, i, size, fill="#333", dash=(2, 4), tags="static")
            self.canvas.create_line(0, i, size, i, fill="#333", dash=(2, 4), tags="static")
        
        base_cy = self._get_base_cy()
        shoulder_cy = self._get_shoulder_cy()
        
        # Ground line
        self.canvas.create_line(0, base_cy, size, base_cy, 
                               fill="#665544", width=2, tags="static")
        
        # Base tower (d1)
        self.canvas.create_line(self.cx, base_cy, self.cx, shoulder_cy,
                               fill="#4488ff", width=4, tags="static")
        
        # Base joint
        self.canvas.create_oval(self.cx-4, base_cy-4, self.cx+4, base_cy+4, 
                               fill="#fff", outline="#888", tags="static")
        
        # Shoulder joint
        self.canvas.create_oval(self.cx-5, shoulder_cy-5, self.cx+5, shoulder_cy+5, 
                               fill="#88aaff", outline="#fff", width=2, tags="static")
    
    def update_target(self, theta2, theta3):
        """
        Draw 3-link arm based on angles.
        Args:
            theta2: Shoulder angle (deg) - 0 = horizontal right
            theta3: Elbow angle (deg) - relative to shoulder, 0 = straight
        """
        self.canvas.delete("dynamic")
        
        shoulder_cx = self.cx
        shoulder_cy = self._get_shoulder_cy()
        
        # --- Link 1: Shoulder -> Elbow (A2) ---
        theta2_rad = math.radians(theta2)
        elbow_cx = shoulder_cx + self.A2 * math.cos(theta2_rad)
        elbow_cy = shoulder_cy - self.A2 * math.sin(theta2_rad)
        
        # Draw upper arm
        self.canvas.create_line(shoulder_cx, shoulder_cy, elbow_cx, elbow_cy,
                               fill="#44ff88", width=4, tags="dynamic")
        
        # Elbow joint
        self.canvas.create_oval(elbow_cx-4, elbow_cy-4, elbow_cx+4, elbow_cy+4,
                               fill="#ffaa44", outline="#fff", width=2, tags="dynamic")
        
        # --- Link 2: Elbow -> Wrist (A3) ---
        # Global angle = θ2 + θ3 (cumulative)
        global_theta3 = theta2 + theta3
        theta3_rad = math.radians(global_theta3)
        wrist_cx = elbow_cx + self.A3 * math.cos(theta3_rad)
        wrist_cy = elbow_cy - self.A3 * math.sin(theta3_rad)
        
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

