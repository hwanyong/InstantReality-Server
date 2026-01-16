"""
Robot Calibration GUI
Tkinter-based GUI for servo calibration and hardware diagnostics.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial.tools.list_ports
import threading
import math
import time

from serial_driver import SerialDriver as PCA9685Driver
from servo_manager import ServoManager


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


class CalibratorGUI:
    """
    Main GUI application for robot calibration.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Robot Calibration Tool")
        self.root.geometry("800x700")
        self.root.configure(bg="#2b2b2b")

        # Initialize components
        self.driver = PCA9685Driver()
        self.manager = ServoManager()
        self.servo_state = ServoState()

        # State variables
        self.is_connected = False
        self.sine_test_running = False
        self.sine_test_thread = None
        
        # Sender thread variables
        self.sender_running = True
        self.sender_thread = threading.Thread(target=self._sender_thread_loop, daemon=True)
        self.sender_thread.start()

        # UI variables
        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Disconnected")
        self.sliders = {}
        self.channel_vars = {}
        self.angle_vars = {}
        self.min_labels = {}
        self.max_labels = {}

        # Build UI
        self._create_styles()
        self._create_connection_panel()
        self._create_servo_panels()
        self._create_diagnostics_panel()
        self._create_footer()

        # Load saved port
        saved_port = self.manager.get_saved_port()
        if saved_port:
            self.port_var.set(saved_port)

        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_styles(self):
        """Create custom styles for widgets."""
        style = ttk.Style()
        style.theme_use('clam')

        # Configure colors
        style.configure("TFrame", background="#2b2b2b")
        style.configure("TLabel", background="#2b2b2b", foreground="#ffffff")
        style.configure("TButton", padding=5)
        style.configure("Header.TLabel", font=("Arial", 12, "bold"))
        style.configure("Status.TLabel", font=("Arial", 10))

    def _create_connection_panel(self):
        """Create the connection status panel."""
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.X)

        # Status indicator
        self.status_canvas = tk.Canvas(frame, width=20, height=20, bg="#2b2b2b", highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.status_indicator = self.status_canvas.create_oval(2, 2, 18, 18, fill="#ff4444")

        # Status label
        ttk.Label(frame, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.LEFT)

        # Connect button
        self.connect_btn = ttk.Button(frame, text="Connect", command=self._on_connect)
        self.connect_btn.pack(side=tk.RIGHT, padx=5)

        # Port dropdown
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, width=15)
        self.port_combo.pack(side=tk.RIGHT, padx=5)
        self._refresh_ports()

        # Refresh ports button
        ttk.Button(frame, text="⟳", width=3, command=self._refresh_ports).pack(side=tk.RIGHT)

    def _create_servo_panels(self):
        """Create Left/Right arm servo control panels."""
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left Arm Tab
        left_frame = ttk.Frame(notebook, padding=10)
        notebook.add(left_frame, text="Left Arm")
        self._create_arm_controls(left_frame, "left_arm", range(1, 7))

        # Right Arm Tab
        right_frame = ttk.Frame(notebook, padding=10)
        notebook.add(right_frame, text="Right Arm")
        self._create_arm_controls(right_frame, "right_arm", range(1, 7))

    def _create_arm_controls(self, parent, arm_key, slots):
        """Create control widgets for one arm."""
        for i, slot in enumerate(slots):
            frame = ttk.Frame(parent)
            frame.pack(fill=tk.X, pady=5)

            # Slot label
            ttk.Label(frame, text=f"Slot {slot}:", width=8).pack(side=tk.LEFT)

            # Channel dropdown
            ch_var = tk.IntVar(value=self.manager.get_channel(arm_key, slot))
            self.channel_vars[(arm_key, slot)] = ch_var

            ch_combo = ttk.Combobox(frame, textvariable=ch_var, values=list(range(16)), width=5)
            ch_combo.pack(side=tk.LEFT, padx=5)
            ch_combo.bind("<<ComboboxSelected>>", lambda e, a=arm_key, s=slot: self._on_channel_change(a, s))

            # Angle slider
            angle_var = tk.IntVar(value=90)
            self.angle_vars[(arm_key, slot)] = angle_var

            slider = ttk.Scale(
                frame, from_=0, to=180, variable=angle_var, orient=tk.HORIZONTAL, length=200,
                command=lambda v, a=arm_key, s=slot: self._on_slider_change(a, s, v)
            )
            slider.pack(side=tk.LEFT, padx=10)
            self.sliders[(arm_key, slot)] = slider

            # Angle display
            ttk.Label(frame, textvariable=angle_var, width=4).pack(side=tk.LEFT)
            ttk.Label(frame, text="°").pack(side=tk.LEFT)

            # Min/Max buttons and labels
            limits = self.manager.get_limits(arm_key, slot)

            min_label = tk.StringVar(value=str(limits["min"]))
            max_label = tk.StringVar(value=str(limits["max"]))
            self.min_labels[(arm_key, slot)] = min_label
            self.max_labels[(arm_key, slot)] = max_label

            ttk.Button(frame, text="Set Min", width=8,
                       command=lambda a=arm_key, s=slot: self._on_set_min(a, s)).pack(side=tk.LEFT, padx=2)
            ttk.Label(frame, textvariable=min_label, width=4).pack(side=tk.LEFT)

            ttk.Button(frame, text="Set Max", width=8,
                       command=lambda a=arm_key, s=slot: self._on_set_max(a, s)).pack(side=tk.LEFT, padx=2)
            ttk.Label(frame, textvariable=max_label, width=4).pack(side=tk.LEFT)

    def _create_diagnostics_panel(self):
        """Create diagnostics panel."""
        frame = ttk.LabelFrame(self.root, text="Diagnostics", padding=10)
        frame.pack(fill=tk.X, padx=10, pady=5)

        # Sine test controls
        ttk.Label(frame, text="Sine Test Channel:").pack(side=tk.LEFT)
        self.sine_channel_var = tk.IntVar(value=0)
        ttk.Combobox(frame, textvariable=self.sine_channel_var, values=list(range(16)), width=5).pack(side=tk.LEFT, padx=5)

        self.sine_btn = ttk.Button(frame, text="Start Sine Test", command=self._on_sine_test)
        self.sine_btn.pack(side=tk.LEFT, padx=10)

        # I2C scan button
        ttk.Button(frame, text="Scan I2C", command=self._on_i2c_scan).pack(side=tk.LEFT, padx=10)

    def _create_footer(self):
        """Create footer with action buttons."""
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.X)

        # E-STOP button (prominent)
        estop_btn = tk.Button(
            frame, text="E-STOP", bg="#ff4444", fg="white",
            font=("Arial", 12, "bold"), width=10,
            command=self._on_estop
        )
        estop_btn.pack(side=tk.RIGHT, padx=5)

        # Save/Load config
        ttk.Button(frame, text="Save Config", command=self._on_save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="Load Config", command=self._on_load_config).pack(side=tk.LEFT, padx=5)

    def _refresh_ports(self):
        """Refresh available COM ports."""
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def _on_connect(self):
        """Handle connect/disconnect button click."""
        if self.is_connected:
            # Disconnect
            self.driver.disconnect()
            self.is_connected = False
            self.status_var.set("Disconnected")
            self.status_canvas.itemconfig(self.status_indicator, fill="#ff4444")
            self.connect_btn.config(text="Connect")
        else:
            # Connect
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "Please select a COM port")
                return

            self.status_var.set("Connecting...")
            self.root.update()

            if self.driver.connect(port):
                self.is_connected = True
                self.status_var.set(f"Connected: {port}")
                self.status_canvas.itemconfig(self.status_indicator, fill="#44ff44")
                self.connect_btn.config(text="Disconnect")
                self.manager.set_saved_port(port)
            else:
                self.status_var.set("Connection Failed")
                messagebox.showerror("Error", f"Failed to connect to {port}")

    def _on_channel_change(self, arm, slot):
        """Handle channel dropdown change."""
        new_channel = self.channel_vars[(arm, slot)].get()
        self.manager.set_channel(arm, slot, new_channel)

    def _on_slider_change(self, arm, slot, value):
        """
        Handle slider movement.
        OPTIMIZED: Updates state only. Sender thread handles transmission.
        """
        if not self.is_connected:
            return

        angle = int(float(value))
        channel = self.manager.get_channel(arm, slot)
        
        # Update thread-safe state map instead of sending directly
        self.servo_state.update_angle(channel, angle)

    def _sender_thread_loop(self):
        """
        Background thread for sending servo commands.
        Runs at ~30Hz. Retries failed commands automatically.
        """
        while self.sender_running:
            if self.is_connected:
                # Get pending updates
                updates = self.servo_state.get_pending_updates()
                
                for channel, angle in updates:
                    # Returns True only if ACK received
                    if self.driver.set_servo_angle(channel, angle):
                         self.servo_state.mark_as_sent(channel, angle)
                    else:
                        # If ACK failed, do NOT mark as sent.
                        # It will be retried in the next loop because angle != last_sent
                        pass
                        
                    # Short sleep is still good to avoid saturating input
                    time.sleep(0.002)
            
            # 30Hz Loop
            time.sleep(0.033)

    def _on_set_min(self, arm, slot):
        """Set current angle as minimum limit."""
        current_angle = self.angle_vars[(arm, slot)].get()
        self.manager.set_limit(arm, slot, "min", current_angle)
        self.min_labels[(arm, slot)].set(str(current_angle))

    def _on_set_max(self, arm, slot):
        """Set current angle as maximum limit."""
        current_angle = self.angle_vars[(arm, slot)].get()
        self.manager.set_limit(arm, slot, "max", current_angle)
        self.max_labels[(arm, slot)].set(str(current_angle))

    def _on_sine_test(self):
        """Start/stop sine wave test."""
        if self.sine_test_running:
            self.sine_test_running = False
            self.sine_btn.config(text="Start Sine Test")
        else:
            if not self.is_connected:
                messagebox.showwarning("Warning", "Not connected to hardware")
                return

            self.sine_test_running = True
            self.sine_btn.config(text="Stop Sine Test")
            self.sine_test_thread = threading.Thread(target=self._sine_test_loop, daemon=True)
            self.sine_test_thread.start()

    def _sine_test_loop(self):
        """Sine wave test loop (runs in separate thread)."""
        channel = self.sine_channel_var.get()
        t = 0

        while self.sine_test_running:
            # Generate sine wave angle (45-135 degrees)
            angle = 90 + 45 * math.sin(t)
            
            # Using servo_state for thread safety and rate limiting
            self.servo_state.update_angle(channel, int(angle))
            
            t += 0.1
            time.sleep(0.05)

    def _on_i2c_scan(self):
        """Scan for I2C devices (placeholder)."""
        if not self.is_connected:
            messagebox.showwarning("Warning", "Not connected to hardware")
            return
        messagebox.showinfo("I2C Scan", "PCA9685 expected at address 0x40\n(Full scan not implemented via Serial)")

    def _on_save_config(self):
        """Save current configuration."""
        if self.manager.save_config():
            messagebox.showinfo("Success", "Configuration saved")
        else:
            messagebox.showerror("Error", "Failed to save configuration")

    def _on_load_config(self):
        """Reload configuration from file."""
        self.manager.load_config()

        # Update UI with loaded values
        for arm in ["left_arm", "right_arm"]:
            for slot in range(1, 7):
                self.channel_vars[(arm, slot)].set(self.manager.get_channel(arm, slot))
                limits = self.manager.get_limits(arm, slot)
                self.min_labels[(arm, slot)].set(str(limits["min"]))
                self.max_labels[(arm, slot)].set(str(limits["max"]))

        messagebox.showinfo("Success", "Configuration loaded")

    def _on_estop(self):
        """Emergency stop - release all servos."""
        if self.is_connected:
            self.driver.release_all()
        self.sine_test_running = False
        messagebox.showinfo("E-STOP", "All servos released")

    def _on_close(self):
        """Handle window close event."""
        # Stop threads
        self.sender_running = False
        self.sine_test_running = False

        # Release all servos and disconnect
        if self.is_connected:
            self.driver.release_all()
            self.driver.disconnect()

        self.root.destroy()

    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()


if __name__ == "__main__":
    app = CalibratorGUI()
    app.run()
