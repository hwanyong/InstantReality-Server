"""
Servo State
Thread-safe shared state for servo pulse management.
Copied from tools/robot_calibrator/servo_state.py for server-side use.
"""

import threading


class ServoState:
    """
    Manages the state of servo pulses for threaded communication.
    """
    def __init__(self):
        self._lock = threading.Lock()
        # Key: channel (0-15), Value: target pulse (us)
        self.target_pulses = {}
        # Key: channel (0-15), Value: last sent pulse
        self.last_sent_pulses = {}

    def update_pulse(self, channel, pulse):
        """Update the target pulse for a channel."""
        with self._lock:
            self.target_pulses[channel] = int(pulse)

    def get_pending_updates(self):
        """
        Get list of (channel, pulse) for channels that need updating.
        Returns: list of tuples (channel, pulse)
        """
        updates = []
        with self._lock:
            for channel, pulse in self.target_pulses.items():
                last = self.last_sent_pulses.get(channel, -1)
                if pulse != last:
                    updates.append((channel, pulse))
        return updates

    def mark_as_sent(self, channel, pulse):
        """Mark a channel's pulse as successfully sent."""
        with self._lock:
            self.last_sent_pulses[channel] = pulse

    def clear_history(self):
        """Clear sent history to force updates on next command."""
        with self._lock:
            self.last_sent_pulses.clear()

    def get_pulse(self, channel):
        """Get current target pulse for a channel."""
        with self._lock:
            return self.target_pulses.get(channel, None)
