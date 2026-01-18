"""
Coordinate Mapper
Converts Gemini visual coordinates (0-1000) to robot local coordinates (mm).
Handles Bottom-Mount configuration with Y-axis inversion.
"""

import math


class CoordinateMapper:
    """
    Maps Gemini visual coordinates to physical robot workspace coordinates.
    
    Gemini Coordinate System:
        - Origin: Top-Left of screen
        - Range: 0~1000 for both X and Y
        - Y increases downward
    
    Robot Local Coordinate System:
        - Origin: Robot base
        - Y increases away from robot (into workspace)
        - X: Left arm uses positive, Right arm uses offset
    """
    
    def __init__(self, workspace_width_mm, workspace_height_mm):
        """
        Initialize the mapper with workspace dimensions.
        
        Args:
            workspace_width_mm: Physical width of workspace in mm
            workspace_height_mm: Physical height (depth) of workspace in mm
        """
        self.width = workspace_width_mm
        self.height = workspace_height_mm
    
    def map_to_global(self, gemini_x, gemini_y):
        """
        Convert Gemini coordinates to global workspace coordinates.
        
        Args:
            gemini_x: X coordinate (0-1000)
            gemini_y: Y coordinate (0-1000)
        
        Returns:
            tuple: (global_x_mm, global_y_mm)
        """
        global_x = (gemini_x / 1000.0) * self.width
        global_y = (gemini_y / 1000.0) * self.height
        return (global_x, global_y)
    
    def map_to_local(self, gemini_x, gemini_y, arm):
        """
        Convert Gemini coordinates to robot-local coordinates.
        
        Bottom-Mount Configuration:
            - Robots are at the bottom of the screen
            - Y is inverted: screen top (Y=0) is far from robot
            - X offset: Right arm origin is at workspace right edge
        
        Args:
            gemini_x: X coordinate (0-1000)
            gemini_y: Y coordinate (0-1000)
            arm: "left" or "right"
        
        Returns:
            tuple: (local_x_mm, local_y_mm)
        """
        global_x, global_y = self.map_to_global(gemini_x, gemini_y)
        
        # Y-Invert: Robot reaches from bottom (H) to top (0)
        local_y = self.height - global_y
        
        # X-Offset based on arm
        if arm == "left":
            local_x = global_x
        elif arm == "right":
            local_x = global_x - self.width  # Negative for right arm
        else:
            raise ValueError(f"Invalid arm: {arm}. Must be 'left' or 'right'.")
        
        return (local_x, local_y)
    
    def dispatch(self, gemini_x):
        """
        Determine which arm should handle the target based on X position.
        
        Args:
            gemini_x: X coordinate (0-1000)
        
        Returns:
            str: "left" or "right"
        """
        # Simple midpoint dispatch
        if gemini_x < 500:
            return "left"
        else:
            return "right"
    
    def is_reachable(self, local_x, local_y, max_reach):
        """
        Check if a local coordinate is within robot's reach.
        
        Args:
            local_x: Local X coordinate (mm)
            local_y: Local Y coordinate (mm)
            max_reach: Maximum arm reach (mm)
        
        Returns:
            bool: True if reachable
        """
        distance = math.sqrt(local_x**2 + local_y**2)
        return distance <= max_reach


# Test code
if __name__ == "__main__":
    # Example: 400mm x 300mm workspace
    mapper = CoordinateMapper(400, 300)
    
    # Test mapping
    print("=== Coordinate Mapper Test ===")
    
    # Top-left corner (Gemini 0,0) should map to far-left for left arm
    lx, ly = mapper.map_to_local(0, 0, "left")
    print(f"Gemini (0, 0) -> Left Arm Local: ({lx:.1f}, {ly:.1f})")
    
    # Center (Gemini 500, 500)
    lx, ly = mapper.map_to_local(500, 500, "left")
    print(f"Gemini (500, 500) -> Left Arm Local: ({lx:.1f}, {ly:.1f})")
    
    # Right side (Gemini 800, 500) for right arm
    rx, ry = mapper.map_to_local(800, 500, "right")
    print(f"Gemini (800, 500) -> Right Arm Local: ({rx:.1f}, {ry:.1f})")
    
    # Dispatch test
    print(f"\nDispatch(200): {mapper.dispatch(200)}")
    print(f"Dispatch(800): {mapper.dispatch(800)}")
