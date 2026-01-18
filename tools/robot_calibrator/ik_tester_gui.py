"""
IK Tester GUI
Tkinter-based GUI for testing and verifying IK calculations.
Supports manual XYZ control and automated test sequences.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial.tools.list_ports
import threading
import os
import json

from serial_driver import SerialDriver
from dual_arm_control import DualArmController


class IKTesterGUI:
    """
    GUI application for IK verification and testing.
    """
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("IK Verification Tool")
        self.root.geometry("900x700")
        self.root.configure(bg="#2b2b2b")
        
        # Initialize components
        self.driver = SerialDriver()
        self.controller = None
        
        # State
        self.is_connected = False
        self.sequence_running = False
        
        # UI variables
        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Disconnected")
        self.arm_var = tk.StringVar(value="auto")
        
        # Coordinate variables
        self.gemini_x_var = tk.IntVar(value=500)
        self.gemini_y_var = tk.IntVar(value=500)
        self.z_var = tk.DoubleVar(value=100.0)
        self.duration_var = tk.DoubleVar(value=1.0)  # Motion duration in seconds
        
        # Workspace settings
        self.workspace_w_var = tk.DoubleVar(value=400.0)
        self.workspace_h_var = tk.DoubleVar(value=300.0)
        
        # Calculated values display
        self.local_x_var = tk.StringVar(value="--")
        self.local_y_var = tk.StringVar(value="--")
        self.angles_var = tk.StringVar(value="--")
        self.dispatch_var = tk.StringVar(value="--")
        
        # Build UI
        self._create_styles()
        self._create_connection_panel()
        self._create_control_panel()
        self._create_results_panel()
        self._create_sequence_panel()
        self._create_log_panel()
        
        # Load saved port
        self._load_saved_port()
        
        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_styles(self):
        """Create custom styles."""
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure("TFrame", background="#2b2b2b")
        style.configure("TLabel", background="#2b2b2b", foreground="#ffffff")
        style.configure("TButton", padding=5)
        style.configure("Header.TLabel", font=("Arial", 12, "bold"))
        style.configure("Result.TLabel", font=("Consolas", 11), foreground="#00ff00")
    
    def _create_connection_panel(self):
        """Create connection panel."""
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.X)
        
        # Status indicator
        self.status_canvas = tk.Canvas(frame, width=20, height=20, 
                                       bg="#2b2b2b", highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.status_indicator = self.status_canvas.create_oval(2, 2, 18, 18, fill="#ff4444")
        
        ttk.Label(frame, textvariable=self.status_var).pack(side=tk.LEFT)
        
        # Connect button
        self.connect_btn = ttk.Button(frame, text="Connect", command=self._on_connect)
        self.connect_btn.pack(side=tk.RIGHT, padx=5)
        
        # Port dropdown
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, width=15)
        self.port_combo.pack(side=tk.RIGHT, padx=5)
        self._refresh_ports()
        
        ttk.Button(frame, text="⟳", width=3, command=self._refresh_ports).pack(side=tk.RIGHT)
    
    def _create_control_panel(self):
        """Create coordinate control panel."""
        frame = ttk.LabelFrame(self.root, text="Coordinate Control", padding=10)
        frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Gemini X
        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=5)
        
        ttk.Label(row1, text="Gemini X:", width=12).pack(side=tk.LEFT)
        ttk.Scale(row1, from_=0, to=1000, variable=self.gemini_x_var, 
                  orient=tk.HORIZONTAL, length=300,
                  command=lambda v: self._on_coord_change()).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, textvariable=self.gemini_x_var, width=5).pack(side=tk.LEFT)
        
        # Gemini Y
        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=5)
        
        ttk.Label(row2, text="Gemini Y:", width=12).pack(side=tk.LEFT)
        ttk.Scale(row2, from_=0, to=1000, variable=self.gemini_y_var,
                  orient=tk.HORIZONTAL, length=300,
                  command=lambda v: self._on_coord_change()).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, textvariable=self.gemini_y_var, width=5).pack(side=tk.LEFT)
        
        # Z Height
        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X, pady=5)
        
        ttk.Label(row3, text="Z Height (mm):", width=12).pack(side=tk.LEFT)
        ttk.Scale(row3, from_=0, to=200, variable=self.z_var,
                  orient=tk.HORIZONTAL, length=300,
                  command=lambda v: self._on_coord_change()).pack(side=tk.LEFT, padx=5)
        ttk.Label(row3, textvariable=self.z_var, width=5).pack(side=tk.LEFT)
        
        # Duration (Speed Control)
        row_dur = ttk.Frame(frame)
        row_dur.pack(fill=tk.X, pady=5)
        
        ttk.Label(row_dur, text="Duration (s):", width=12).pack(side=tk.LEFT)
        ttk.Scale(row_dur, from_=0.5, to=5.0, variable=self.duration_var,
                  orient=tk.HORIZONTAL, length=300).pack(side=tk.LEFT, padx=5)
        ttk.Label(row_dur, textvariable=self.duration_var, width=5).pack(side=tk.LEFT)
        
        # Arm selection
        row4 = ttk.Frame(frame)
        row4.pack(fill=tk.X, pady=5)
        
        ttk.Label(row4, text="Arm:", width=12).pack(side=tk.LEFT)
        ttk.Radiobutton(row4, text="Auto", variable=self.arm_var, value="auto").pack(side=tk.LEFT)
        ttk.Radiobutton(row4, text="Left", variable=self.arm_var, value="left").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(row4, text="Right", variable=self.arm_var, value="right").pack(side=tk.LEFT)
        
        # Move button
        ttk.Button(row4, text="▶ Move", command=self._on_move).pack(side=tk.RIGHT, padx=5)
        ttk.Button(row4, text="Calculate", command=self._on_calculate).pack(side=tk.RIGHT, padx=5)
    
    def _create_results_panel(self):
        """Create results display panel."""
        frame = ttk.LabelFrame(self.root, text="Calculation Results", padding=10)
        frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Grid layout for results
        grid = ttk.Frame(frame)
        grid.pack(fill=tk.X)
        
        # Row 0: Dispatch
        ttk.Label(grid, text="Dispatched Arm:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(grid, textvariable=self.dispatch_var, style="Result.TLabel").grid(row=0, column=1, sticky="w")
        
        # Row 1: Local X
        ttk.Label(grid, text="Local X (mm):").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Label(grid, textvariable=self.local_x_var, style="Result.TLabel").grid(row=1, column=1, sticky="w")
        
        # Row 2: Local Y
        ttk.Label(grid, text="Local Y (mm):").grid(row=2, column=0, sticky="w", padx=5)
        ttk.Label(grid, textvariable=self.local_y_var, style="Result.TLabel").grid(row=2, column=1, sticky="w")
        
        # Row 3: Angles
        ttk.Label(grid, text="Servo Angles:").grid(row=3, column=0, sticky="w", padx=5)
        ttk.Label(grid, textvariable=self.angles_var, style="Result.TLabel").grid(row=3, column=1, sticky="w")
    
    def _create_sequence_panel(self):
        """Create test sequence panel."""
        frame = ttk.LabelFrame(self.root, text="Test Sequences", padding=10)
        frame.pack(fill=tk.X, padx=10, pady=5)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="🔄 Workspace Sweep", 
                   command=lambda: self._run_sequence("sweep")).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📏 Linear Accuracy",
                   command=lambda: self._run_sequence("linear")).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📦 Pick & Place",
                   command=lambda: self._run_sequence("pick_place")).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🎲 Random Poke",
                   command=lambda: self._run_sequence("random_poke")).pack(side=tk.LEFT, padx=5)
        
        # Home button
        ttk.Button(btn_frame, text="🏠 Home", command=self._on_home).pack(side=tk.RIGHT, padx=5)
        
        # E-STOP
        estop_btn = tk.Button(btn_frame, text="E-STOP", bg="#ff4444", fg="white",
                              font=("Arial", 12, "bold"), width=10, command=self._on_estop)
        estop_btn.pack(side=tk.RIGHT, padx=10)
    
    def _create_log_panel(self):
        """Create log panel."""
        frame = ttk.LabelFrame(self.root, text="Log", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = tk.Text(frame, height=10, bg="#1e1e1e", fg="#ffffff",
                                font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
    
    def _log(self, message):
        """Add message to log."""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
    
    def _refresh_ports(self):
        """Refresh COM ports list."""
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])
    
    def _load_saved_port(self):
        """Load saved port from config."""
        config_path = os.path.join(os.path.dirname(__file__), "servo_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                port = config.get("connection", {}).get("port", "")
                if port:
                    self.port_var.set(port)
    
    def _on_connect(self):
        """Handle connect/disconnect."""
        if self.is_connected:
            self.driver.disconnect()
            self.is_connected = False
            self.controller = None
            self.status_var.set("Disconnected")
            self.status_canvas.itemconfig(self.status_indicator, fill="#ff4444")
            self.connect_btn.config(text="Connect")
            self._log("Disconnected")
        else:
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
                
                # Initialize controller
                config_path = os.path.join(os.path.dirname(__file__), "servo_config.json")
                self.controller = DualArmController(
                    config_path,
                    workspace_width=self.workspace_w_var.get(),
                    workspace_height=self.workspace_h_var.get(),
                    driver=self.driver
                )
                self._log(f"Connected to {port}")
            else:
                self.status_var.set("Connection Failed")
                messagebox.showerror("Error", f"Failed to connect to {port}")
    
    def _on_coord_change(self):
        """Handle coordinate slider changes (preview only)."""
        if self.controller is None:
            # Simulation mode - create temp controller for calculation
            config_path = os.path.join(os.path.dirname(__file__), "servo_config.json")
            if os.path.exists(config_path):
                temp_controller = DualArmController(
                    config_path,
                    workspace_width=self.workspace_w_var.get(),
                    workspace_height=self.workspace_h_var.get(),
                    driver=None
                )
                self._calculate_with_controller(temp_controller)
        else:
            self._calculate_with_controller(self.controller)
    
    def _calculate_with_controller(self, controller):
        """Calculate and display IK results."""
        gx = self.gemini_x_var.get()
        gy = self.gemini_y_var.get()
        z = self.z_var.get()
        
        arm = self.arm_var.get()
        if arm == "auto":
            arm = controller.dispatch(gx)
        
        self.dispatch_var.set(arm.upper())
        
        # Get local coordinates
        local_x, local_y = controller.mapper.map_to_local(gx, gy, arm)
        self.local_x_var.set(f"{local_x:.1f}")
        self.local_y_var.set(f"{local_y:.1f}")
        
        # Calculate IK
        arm_obj = controller.get_arm(arm)
        try:
            angles = arm_obj.solve_ik(local_x, local_y, z)
            self.angles_var.set(f"[{', '.join(f'{a:.1f}' for a in angles)}]")
        except ValueError as e:
            self.angles_var.set(f"Error: {e}")
    
    def _on_calculate(self):
        """Force calculation and log result."""
        self._on_coord_change()
        self._log(f"Gemini({self.gemini_x_var.get()}, {self.gemini_y_var.get()}) Z={self.z_var.get():.1f} -> "
                  f"Local({self.local_x_var.get()}, {self.local_y_var.get()}) "
                  f"Angles: {self.angles_var.get()}")
    
    def _on_move(self):
        """Execute move to current coordinates."""
        if not self.is_connected:
            messagebox.showwarning("Warning", "Not connected to hardware")
            return
        
        gx = self.gemini_x_var.get()
        gy = self.gemini_y_var.get()
        z = self.z_var.get()
        duration = self.duration_var.get()
        arm = self.arm_var.get() if self.arm_var.get() != "auto" else None
        
        result = self.controller.move_to_gemini_coord(gx, gy, z, arm, duration)
        
        if result["success"]:
            self._log(f"✓ Moved {result['arm'].upper()} to ({gx}, {gy}) Z={z}")
        else:
            self._log(f"✗ Move failed: {result.get('error', 'Unknown error')}")
    
    def _run_sequence(self, name):
        """Run a test sequence in a thread."""
        if not self.is_connected:
            messagebox.showwarning("Warning", "Not connected to hardware")
            return
        
        if self.sequence_running:
            messagebox.showwarning("Warning", "A sequence is already running")
            return
        
        self.sequence_running = True
        
        def run():
            try:
                self.controller.run_sequence(name, delay=1.0, 
                                             callback=lambda msg: self._log(msg))
            except Exception as e:
                self._log(f"Sequence error: {e}")
            finally:
                self.sequence_running = False
        
        threading.Thread(target=run, daemon=True).start()
    
    def _on_home(self):
        """Move both arms to home position."""
        if not self.is_connected:
            messagebox.showwarning("Warning", "Not connected to hardware")
            return
        
        self.controller.home()
        self._log("Moved to home position")
    
    def _on_estop(self):
        """Emergency stop."""
        if self.is_connected:
            self.driver.release_all()
        self.sequence_running = False
        self._log("!!! E-STOP ACTIVATED !!!")
        messagebox.showinfo("E-STOP", "All servos released")
    
    def _on_close(self):
        """Handle window close."""
        self.sequence_running = False
        if self.is_connected:
            self.driver.release_all()
            self.driver.disconnect()
        self.root.destroy()
    
    def run(self):
        """Start the GUI."""
        self.root.mainloop()


if __name__ == "__main__":
    app = IKTesterGUI()
    app.run()
