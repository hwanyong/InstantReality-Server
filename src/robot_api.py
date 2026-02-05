# Robot API Router
# HTTP endpoints for robot control

from aiohttp import web
from lib.robot import RobotController

# Singleton controller instance
robot_controller = None


def get_controller():
    """Get or create the robot controller instance."""
    global robot_controller
    if robot_controller is None:
        robot_controller = RobotController()
    return robot_controller


async def handle_connect(request):
    """
    POST /api/robot/connect
    Connect to robot via serial port.
    """
    controller = get_controller()
    
    if controller.is_connected():
        return web.json_response({
            "success": True,
            "message": "Already connected"
        })
    
    success = controller.connect()
    
    if success:
        return web.json_response({
            "success": True,
            "message": "Connected to robot",
            "status": controller.get_status()
        })
    else:
        return web.json_response({
            "success": False,
            "error": "Failed to connect to robot"
        }, status=500)


async def handle_disconnect(request):
    """
    POST /api/robot/disconnect
    Disconnect from robot.
    """
    controller = get_controller()
    controller.disconnect()
    
    return web.json_response({
        "success": True,
        "message": "Disconnected"
    })


async def handle_home(request):
    """
    POST /api/robot/home
    Move robot to home position.
    Body: { "motion_time": 3.0 } (optional)
    """
    controller = get_controller()
    
    if not controller.is_connected():
        return web.json_response({
            "success": False,
            "error": "Robot not connected"
        }, status=400)
    
    data = {}
    if request.body_exists:
        data = await request.json()
    
    motion_time = data.get("motion_time", 3.0)
    
    success = controller.go_home(motion_time)
    
    return web.json_response({
        "success": success,
        "message": "Moved to home position" if success else "Motion failed"
    })


async def handle_zero(request):
    """
    POST /api/robot/zero
    Move robot to zero position.
    Body: { "motion_time": 3.0 } (optional)
    """
    controller = get_controller()
    
    if not controller.is_connected():
        return web.json_response({
            "success": False,
            "error": "Robot not connected"
        }, status=400)
    
    data = {}
    if request.body_exists:
        data = await request.json()
    
    motion_time = data.get("motion_time", 3.0)
    
    success = controller.go_zero(motion_time)
    
    return web.json_response({
        "success": success,
        "message": "Moved to zero position" if success else "Motion failed"
    })


async def handle_status(request):
    """
    GET /api/robot/status
    Get robot connection status.
    """
    controller = get_controller()
    
    return web.json_response({
        "success": True,
        "status": controller.get_status()
    })


async def handle_release(request):
    """
    POST /api/robot/release
    Release all servos (E-STOP).
    """
    controller = get_controller()
    controller.release_all()
    
    return web.json_response({
        "success": True,
        "message": "All servos released"
    })


async def handle_move_to(request):
    """
    POST /api/robot/move_to
    Move robot arm to specified coordinates using IK.
    
    Body: {
        "x": 200.0,        # Robot mm (relative to share point)
        "y": 100.0,        # Robot mm
        "z": 5.0,          # Robot mm (default 5)
        "arm": "auto",     # "left" | "right" | "auto"
        "motion_time": 2.0 # Seconds (default 2)
    }
    """
    import math
    import json
    from pathlib import Path
    from lib.robot.pulse_mapper import PulseMapper
    
    controller = get_controller()
    
    if not controller.is_connected():
        return web.json_response({
            "success": False,
            "error": "Robot not connected"
        }, status=400)
    
    data = await request.json()
    x = data.get("x", 0.0)
    y = data.get("y", 0.0)
    z = data.get("z", 5.0)
    arm = data.get("arm", "auto")
    motion_time = data.get("motion_time", 2.0)
    
    # Auto arm selection: x < 0 -> left, x >= 0 -> right
    if arm == "auto":
        arm = "left_arm" if x < 0 else "right_arm"
    elif arm == "left":
        arm = "left_arm"
    elif arm == "right":
        arm = "right_arm"
    
    # Load servo config
    config_path = Path(__file__).parent.parent / "servo_config.json"
    if not config_path.exists():
        return web.json_response({"success": False, "error": "servo_config.json not found"}, status=500)
    
    with open(config_path, 'r') as f:
        servo_config = json.load(f)
    
    arm_config = servo_config.get(arm, {})
    if not arm_config:
        return web.json_response({"success": False, "error": f"Invalid arm: {arm}"}, status=400)
    
    # Get slot configs and channels
    slots = {}
    for i in range(1, 7):
        slots[i] = arm_config.get(f"slot_{i}", {})
    
    # Get Base coordinates from geometry
    geometry = servo_config.get("geometry", {})
    bases = geometry.get("bases", {})
    base = bases.get(arm, {"x": 0, "y": 0})
    base_x = float(base.get("x", 0))
    base_y = float(base.get("y", 0))
    
    # Calculate Local coordinates
    local_x = x - base_x
    local_y = y - base_y
    
    # Get link lengths
    d1 = slots[1].get("length", 107.0)
    a2 = slots[2].get("length", 105.0)
    a3 = slots[3].get("length", 150.0)
    a4 = slots[4].get("length", 65.0)
    a6 = slots[6].get("length", 70.0)
    
    # θ1 calculation (Base Yaw)
    if local_x == 0 and local_y == 0:
        theta1 = 0.0
    else:
        theta1 = math.degrees(math.atan2(-local_x, local_y))
    
    # Reach calculation
    reach = math.sqrt(local_x**2 + local_y**2)
    
    # 5-Link IK
    wrist_z = z + a4 + a6
    s = wrist_z - d1
    dist_sq = reach**2 + s**2
    dist = math.sqrt(dist_sq)
    
    max_reach = a2 + a3
    min_reach = abs(a2 - a3)
    
    # Fixed angles for Slot 5, 6
    theta5 = 0.0
    theta6 = 0.0
    
    is_valid = True
    
    if dist > max_reach or dist < min_reach or dist < 0.001:
        # Pointing fallback
        theta2 = math.degrees(math.atan2(s, reach)) if reach > 0 else (90.0 if s >= 0 else -90.0)
        theta3 = 0.0
        theta4 = -90.0 - theta2
        is_valid = False
    else:
        # Law of Cosines
        cos_theta3 = (dist_sq - a2**2 - a3**2) / (2 * a2 * a3)
        cos_theta3 = max(-1.0, min(1.0, cos_theta3))
        theta3_rad = math.acos(cos_theta3)
        
        beta = math.atan2(s, reach)
        cos_alpha = (a2**2 + dist_sq - a3**2) / (2 * a2 * dist)
        cos_alpha = max(-1.0, min(1.0, cos_alpha))
        alpha = math.acos(cos_alpha)
        
        theta2 = math.degrees(beta + alpha)
        theta3 = math.degrees(theta3_rad)
        theta4 = -90.0 - theta2 + theta3
    
    # Calculate pulses
    pulse_mapper = PulseMapper()
    
    def calc_pulse(ik_angle, slot_config, polarity=1):
        zero_offset = slot_config.get("zero_offset", 90)
        act_range = slot_config.get("actuation_range", 180)
        phy = zero_offset + (polarity * ik_angle)
        phy = max(0, min(act_range, phy))
        motor_config = {
            "actuation_range": slot_config.get("actuation_range", 180),
            "pulse_min": slot_config.get("pulse_min", 500),
            "pulse_max": slot_config.get("pulse_max", 2500)
        }
        return pulse_mapper.physical_to_pulse(phy, motor_config)
    
    pls1 = calc_pulse(theta1, slots[1], polarity=1)
    pls2 = calc_pulse(theta2, slots[2], polarity=1)
    pls3 = calc_pulse(theta3, slots[3], polarity=1)
    pls4 = calc_pulse(theta4, slots[4], polarity=-1)
    pls5 = calc_pulse(theta5, slots[5], polarity=1)
    pls6 = calc_pulse(theta6, slots[6], polarity=1)
    
    # Build targets with channels
    targets = []
    for i in range(1, 7):
        channel = slots[i].get("channel", i - 1)
        pulse = [pls1, pls2, pls3, pls4, pls5, pls6][i - 1]
        targets.append((channel, pulse))
    
    # Execute movement
    success = controller.move_to_pulses(targets, motion_time)
    
    return web.json_response({
        "success": success,
        "arm": arm,
        "target": {"x": x, "y": y, "z": z},
        "motion_time": motion_time,
        "valid": is_valid,
        "message": "Moving to target" if success else "Motion failed"
    })


def setup_routes(app):
    """Register robot API routes with the app."""
    app.router.add_post('/api/robot/connect', handle_connect)
    app.router.add_post('/api/robot/disconnect', handle_disconnect)
    app.router.add_post('/api/robot/home', handle_home)
    app.router.add_post('/api/robot/zero', handle_zero)
    app.router.add_get('/api/robot/status', handle_status)
    app.router.add_post('/api/robot/release', handle_release)
    app.router.add_post('/api/robot/move_to', handle_move_to)

