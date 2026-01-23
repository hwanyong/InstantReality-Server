
import tkinter as tk
from tkinter import ttk
import abc

class VisualWidget(abc.ABC):
    """Abstract base class for reusable visualization widgets."""
    
    @abc.abstractmethod
    def draw_static(self):
        """Draw static elements like grid and axes."""
        pass

    @abc.abstractmethod
    def update_target(self, *args, **kwargs):
        """Update dynamic target elements."""
        pass


class BaseTabController(abc.ABC):
    """Abstract base class for Tab Controllers."""
    
    def __init__(self, parent, context):
        """
        Args:
            parent: The Tkinter parent widget (frame).
            context: Global application context (manager, driver, etc.).
        """
        self.parent = parent
        self.context = context
        self.root = parent.winfo_toplevel()
        
        # Build UI immediately
        self.build_ui()
        
        # Subscribe to Config Updates
        if hasattr(self.context, 'manager'):
            self.context.manager.add_observer(self.on_config_updated)
    
    @abc.abstractmethod
    def build_ui(self):
        """Create tab-specific UI elements."""
        pass
        
    def on_config_updated(self):
        """
        Called when ServoManager reloads configuration.
        Override this to refresh UI with new values.
        """
        pass
    
    def on_enter(self):
        """Called when this tab is selected."""
        pass
        
    def on_leave(self):
        """Called when this tab is deselected."""
        pass
        
    def log(self, msg):
        """Delegate logging to the main app context if available."""
        if hasattr(self.context, 'log'):
            self.context.log(msg)
        else:
            print(f"[TabLog] {msg}")

    # --- Helper Methods for Dynamic Angle Calculation ---

    def calculate_physical_angle(self, target_math_deg, config):
        """
        Calculate physical angle based on 'Zero Offset' with Phase Correction.
        
        Formula: Physical = ZeroOffset + ((IK_Angle + PhaseShift) * Polarity)
        
        Args:
            target_math_deg (float): Desired angle in Cartesian frame (0=Reference/Horizontal).
            config (dict): Slot configuration dictionary.
            
        Returns:
            float: Physical angle to send to servo.
        """
        zero_offset = config.get('zero_offset', 0.0)
        
        typ = config.get('type', 'vertical')
        min_pos = config.get('min_pos', 'bottom')
        polarity = 1
        
        if typ == 'horizontal' and min_pos == 'left':
            polarity = -1
            
        # Cartesian Phase Correction
        # If 'min_pos' is 'bottom', it implies the physical frame is shifted -90 degrees
        # relative to the horizontal zero.
        # Observation: ZeroOffset(139.1) -> Vertical Up (90 deg).
        # We want ZeroOffset to represent Horizontal (0 deg).
        # Correction: Apply -90 shift to target.
        phase_shift = 0.0
        if min_pos == 'bottom':
            phase_shift = -90.0
            
        physical = zero_offset + ((target_math_deg + phase_shift) * polarity)
        return physical
