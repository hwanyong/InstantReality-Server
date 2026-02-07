"""
Motion Planner
Provides smooth trajectory interpolation for servo movements.
Uses threading to execute motions without blocking.
Copied from tools/robot_calibrator/motion_planner.py for server-side use.
"""

import threading
import time


class MotionPlanner:
    """
    Generates interpolated waypoints to achieve smooth servo motion.
    """

    def __init__(self, servo_state, update_interval_ms=20):
        """
        Args:
            servo_state: ServoState instance for pulse updates.
            update_interval_ms: Time between interpolation steps (default 20ms = 50Hz).
        """
        self.servo_state = servo_state
        self.update_interval = update_interval_ms / 1000.0
        self._motion_thread = None
        self._stop_flag = False

    def move_all(self, targets, duration_sec, callback=None):
        """
        Move multiple servos to target pulses over specified duration.

        Args:
            targets: List of tuples [(channel, target_pulse), ...]
            duration_sec: Time to complete the motion.
            callback: Optional function to call when motion completes.
        """
        if self._motion_thread and self._motion_thread.is_alive():
            self._stop_flag = True
            self._motion_thread.join(timeout=0.5)

        self._stop_flag = False
        self._motion_thread = threading.Thread(
            target=self._execute_motion,
            args=(targets, duration_sec, callback),
            daemon=True
        )
        self._motion_thread.start()

    def _execute_motion(self, targets, duration_sec, callback):
        """
        Internal method: runs in a separate thread.
        Generates and sends interpolated waypoints.
        """
        # Get current pulses
        start_pulses = {}
        for channel, target in targets:
            current = self.servo_state.get_pulse(channel)
            start_pulses[channel] = current if current is not None else target

        # Calculate number of steps
        num_steps = max(1, int(duration_sec / self.update_interval))

        # Execute interpolation
        for step in range(1, num_steps + 1):
            if self._stop_flag:
                break

            t = step / num_steps  # Progress 0.0 to 1.0

            for channel, target_pulse in targets:
                start = start_pulses[channel]
                interpolated = int(self._lerp(start, target_pulse, t))
                self.servo_state.update_pulse(channel, interpolated)

            time.sleep(self.update_interval)

        # Final position (ensure exact target)
        if not self._stop_flag:
            for channel, target_pulse in targets:
                self.servo_state.update_pulse(channel, target_pulse)

        if callback:
            callback()

    def _lerp(self, start, end, t):
        """Linear interpolation."""
        return start + (end - start) * t

    def stop(self):
        """Stop any ongoing motion."""
        self._stop_flag = True
        if self._motion_thread and self._motion_thread.is_alive():
            self._motion_thread.join(timeout=0.5)

    def wait_for_completion(self, timeout=10.0):
        """Block until current motion completes."""
        if self._motion_thread and self._motion_thread.is_alive():
            self._motion_thread.join(timeout=timeout)
        return not (self._motion_thread and self._motion_thread.is_alive())

    def is_moving(self):
        """Check if motion is in progress."""
        return self._motion_thread is not None and self._motion_thread.is_alive()
