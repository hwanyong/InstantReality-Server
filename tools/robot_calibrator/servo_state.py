"""
Servo State
Thread-safe shared state for servo angle management.
Extracted from calibrator_gui.py for reuse across tools.
"""

import threading


class ServoState:
    """
    Manages the state of servo angles for threaded communication.
    """
    def __init__(self):
        self._lock = threading.Lock()
        # Key: channel (0-15), Value: target angle (0-180)
        self.target_angles = {}
        # Key: channel (0-15), Value: last sent angle
        self.last_sent_angles = {}

    def update_angle(self, channel, angle):
        """Update the target angle for a channel."""
        with self._lock:
            self.target_angles[channel] = angle

    def get_pending_updates(self):
        """
        Get list of (channel, angle) for channels that need updating.
        Returns: list of tuples (channel, angle)
        """
        updates = []
        with self._lock:
            for channel, angle in self.target_angles.items():
                last = self.last_sent_angles.get(channel, -1)
                if angle != last:
                    updates.append((channel, angle))
        return updates

    def mark_as_sent(self, channel, angle):
        """Mark a channel's angle as successfully sent."""
        with self._lock:
            self.last_sent_angles[channel] = angle

    def clear_history(self):
        """Clear sent history to force updates on next command."""
        with self._lock:
            self.last_sent_angles.clear()

    def get_angle(self, channel):
        """Get current target angle for a channel."""
        with self._lock:
            return self.target_angles.get(channel, None)
