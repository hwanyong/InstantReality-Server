
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import sys
import os

# Ensure parent directory is in path to import sibling modules (serial_driver etc)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    
try:
    from serial_driver import SerialDriver
    from pulse_mapper import PulseMapper
    from servo_manager import ServoManager
    from servo_state import ServoState
    from motion_planner import MotionPlanner
    import serial.tools.list_ports
except ImportError as e:
    print(f"Error importing core modules: {e}")
    # Fallback for compilation check
    SerialDriver = object
    PulseMapper = object
    ServoManager = object
    ServoState = object
    MotionPlanner = object

from .tabs.base import Slot1Tab
from .tabs.dual_view import DualViewTab
from .tabs.triple_view import TripleViewTab
from .tabs.quad_view import QuadViewTab
from .tabs.full_slot_view import FullSlotTab

# Thread Timing
SENDER_LOOP_INTERVAL = 0.033
SENDER_CMD_DELAY = 0.002

class IKTesterApp:
    """
    Main Application Shell for IK Tester.
    Manages global state (Hardware, Config) and Tabs.
    """
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("IK Tester Modular (Packet)")
        self.root.geometry("750x850")
        self.root.configure(bg="#2b2b2b")
        
        # Core Components
        self.driver = SerialDriver()
        self.mapper = PulseMapper()
        self.manager = ServoManager()
        self.servo_state = ServoState()
        self.motion_planner = MotionPlanner(self.servo_state)
        
        self.is_connected = False
        
        # Sender Thread
        self.sender_running = True
        self.sender_thread = threading.Thread(target=self._sender_thread_loop, daemon=True)
        self.sender_thread.start()
        
        # Global UI Vars
        self.arm_var = tk.StringVar(value="left")
        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Disconnected")
        self.duration_var = tk.DoubleVar(value=0.5)
        
        # Styles
        self._create_styles()
        
        # Build Global Layout
        self._create_connection_panel()
        self._create_arm_panel()
        
        # Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        self.tabs = []
        self._register_tabs()
        
        # Global Controls
        self._create_control_panel()
        self._create_log_panel()
        
        # Init
        self._load_saved_port()
        self.current_tab = None

    def _register_tabs(self):
        """Register available tabs."""
        # Tab 1: Slot 1
        t1_frame = ttk.Frame(self.notebook)
        self.notebook.add(t1_frame, text="Slot 1 Only")
        self.tabs.append(Slot1Tab(t1_frame, self))
        
        # Tab 2: Dual View
        t2_frame = ttk.Frame(self.notebook)
        self.notebook.add(t2_frame, text="Slot 1+2 Dual")
        self.tabs.append(DualViewTab(t2_frame, self))
        
        # Tab 3: Triple View (Phase 2 Prototype)
        t3_frame = ttk.Frame(self.notebook)
        self.notebook.add(t3_frame, text="Slot 1+2+3 IK")
        self.tabs.append(TripleViewTab(t3_frame, self))
        
        # Tab 4: Quad View (VLA Robot Controller)
        t4_frame = ttk.Frame(self.notebook)
        self.notebook.add(t4_frame, text="Slot 1+2+3+4 VLA")
        self.tabs.append(QuadViewTab(t4_frame, self))
        
        # Tab 5: Full Slot (Gripper X)
        t5_frame = ttk.Frame(self.notebook)
        self.notebook.add(t5_frame, text="Full Slot (Gripper X)")
        self.tabs.append(FullSlotTab(t5_frame, self))

    def _create_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#2b2b2b")
        style.configure("TLabel", background="#2b2b2b", foreground="#ffffff")
        style.configure("TButton", padding=5)
        style.configure("TRadiobutton", background="#2b2b2b", foreground="#ffffff")
        style.configure("Result.TLabel", font=("Consolas", 11), foreground="#00ff00")
        style.configure("Valid.TLabel", font=("Consolas", 11, "bold"), foreground="#44ff44")
        style.configure("Invalid.TLabel", font=("Consolas", 11, "bold"), foreground="#ff4444")

    def _create_connection_panel(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.X)
        
        self.status_canvas = tk.Canvas(frame, width=16, height=16, bg="#2b2b2b", highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 5))
        self.status_indicator = self.status_canvas.create_oval(2, 2, 14, 14, fill="#ff4444")
        
        ttk.Label(frame, textvariable=self.status_var).pack(side=tk.LEFT)
        
        self.connect_btn = ttk.Button(frame, text="Connect", command=self._on_connect)
        self.connect_btn.pack(side=tk.RIGHT, padx=5)
        
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, width=12)
        self.port_combo.pack(side=tk.RIGHT, padx=5)
        self._refresh_ports()
        ttk.Button(frame, text="⟳", width=3, command=self._refresh_ports).pack(side=tk.RIGHT)

    def _create_arm_panel(self):
        frame = ttk.Frame(self.root, padding=(10, 5))
        frame.pack(fill=tk.X)
        ttk.Label(frame, text="Arm:").pack(side=tk.LEFT)
        ttk.Radiobutton(frame, text="Left", variable=self.arm_var, value="left", command=self._on_arm_change).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(frame, text="Right", variable=self.arm_var, value="right", command=self._on_arm_change).pack(side=tk.LEFT)

    def _create_control_panel(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.X, padx=10)
        
        ttk.Button(frame, text="▶ Send", command=self._on_send).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="⟳ Reload Config", command=self._on_reload_config).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        ttk.Label(frame, text="Duration:").pack(side=tk.LEFT)
        ttk.Spinbox(frame, from_=0.1, to=2.0, increment=0.1, textvariable=self.duration_var, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(frame, text="s").pack(side=tk.LEFT)
        
        estop = tk.Button(frame, text="E-STOP", bg="#ff4444", fg="white", font=("Arial", 11, "bold"), width=8, command=self._on_estop)
        estop.pack(side=tk.RIGHT, padx=5)

    def _create_log_panel(self):
        frame = ttk.LabelFrame(self.root, text="Log", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text = tk.Text(frame, height=5, bg="#1e1e1e", fg="#ffffff", font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, msg):
        self.log_text.insert(tk.END, f"> {msg}\n")
        self.log_text.see(tk.END)

    def _sender_thread_loop(self):
        while self.sender_running:
            if self.is_connected:
                updates = self.servo_state.get_pending_updates()
                for channel, pulse_us in updates:
                    if self.driver.write_pulse(channel, pulse_us):
                        self.servo_state.mark_as_sent(channel, pulse_us)
                    time.sleep(SENDER_CMD_DELAY)
            time.sleep(SENDER_LOOP_INTERVAL)

    # --- Connection Logic ---
    def _refresh_ports(self):
        try:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            self.port_combo['values'] = ports
            if ports and not self.port_var.get():
                self.port_var.set(ports[0])
        except: pass

    def _load_saved_port(self):
        try:
            port = self.manager.get_saved_port()
            if port: self.port_var.set(port)
        except: pass

    def _on_connect(self):
        if self.is_connected:
            self.driver.disconnect()
            self.is_connected = False
            self.status_var.set("Disconnected")
            self.status_canvas.itemconfig(self.status_indicator, fill="#ff4444")
            self.connect_btn.config(text="Connect")
            self.log("Disconnected")
        else:
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "Select a COM port")
                return
            if self.driver.connect(port):
                self.is_connected = True
                self.status_var.set(f"Connected: {port}")
                self.status_canvas.itemconfig(self.status_indicator, fill="#44ff44")
                self.connect_btn.config(text="Disconnect")
                self.log(f"Connected to {port}")
            else:
                messagebox.showerror("Error", f"Failed to connect to {port}")

    def _on_estop(self):
        self.motion_planner.stop()
        if self.is_connected: self.driver.release_all()
        self.log("!!! E-STOP !!!")

    def _on_arm_change(self):
        self.log(f"Switched to {self.arm_var.get().upper()} arm")
        if self.current_tab:
            self.current_tab.on_enter()

    def _on_tab_changed(self, event):
        idx = self.notebook.index("current")
        if 0 <= idx < len(self.tabs):
            if self.current_tab:
                self.current_tab.on_leave()
            self.current_tab = self.tabs[idx]
            self.current_tab.on_enter()

    def _on_send(self):
        if not self.is_connected:
            messagebox.showwarning("Warning", "Not connected")
            return
        if self.current_tab:
            self.current_tab.send_command(self.duration_var.get())

    def _on_reload_config(self):
        if self.manager:
            self.manager.load_config()
            self.log("Configuration Reloaded from Disk")

    # --- Context Methods (Dependency Injection) ---
    def get_current_arm(self):
        return "left_arm" if self.arm_var.get() == "left" else "right_arm"

    def get_slot_params(self, slot_num):
        """
        Helper to fetch comprehensive slot parameters from Manager.
        Returns dict with keys needed for widgets.
        """
        arm = self.get_current_arm()
        
        # We need to manually construct this as Manager APIs are granular
        try:
            channel = self.manager.get_channel(arm, slot_num)
            zero = self.manager.get_zero_offset(arm, slot_num)
            limits = self.manager.get_limits(arm, slot_num)
            act_range = self.manager.get_actuation_range(arm, slot_num)
            
            # Need type/min_pos from raw config text config usually
            # manager.config is the dict loaded from json
            # arm_config = manager.config.get(arm, {})
            # slot_key = f"slot_{slot_num}"
            # slot_conf = arm_config.get(slot_key, {})
            # type = slot_conf.get("type", "horizontal") ...
            
            arm_conf = self.manager.config.get(arm, {}).get(f"slot_{slot_num}", {})
            typ = arm_conf.get("type", "horizontal")
            min_pos = self.manager.get_min_pos(arm, slot_num)
            
            # Polarity Logic (Copied/Adapted from Legacy)
            polarity = 1
            if typ == "horizontal" and min_pos == "left": polarity = -1
            # Vertical: bottom->1, top->-1
            if typ == "vertical":
                polarity = -1 if min_pos == "top" else 1
            
            # Math Min/Max
            # Range Logic: Apply polarity
            bound_a = (limits["min"] - zero) * polarity
            bound_b = (limits["max"] - zero) * polarity
            math_min = min(bound_a, bound_b)
            math_max = max(bound_a, bound_b)
            
            motor_conf = {
                "actuation_range": arm_conf.get("actuation_range", 180),
                "pulse_min": arm_conf.get("pulse_min", 500),
                "pulse_max": arm_conf.get("pulse_max", 2500)
            }
            # Or use helper _get_slot_config from legacy
            
            return {
                'channel': channel,
                'zero_offset': zero,
                'min': limits['min'],
                'max': limits['max'],
                'actuation_range': act_range,
                'type': typ,
                'min_pos': min_pos,
                'polarity': polarity,
                'math_min': math_min,
                'math_max': math_max,
                'motor_config': motor_conf,
                # For side view link lengths (only relevant for slot 2/3 but included)
                'length': arm_conf.get("length", 100)
            }
        except Exception as e:
            print(f"Error getting slot {slot_num} params: {e}")
            return None

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.sender_running = False
        self.motion_planner.stop()
        if self.is_connected:
            self.driver.release_all()
            self.driver.disconnect()
        self.root.destroy()
