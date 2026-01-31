# Robot API Router
# HTTP endpoints for robot control

from aiohttp import web
from lib.robot import DualArmController

# Singleton controller instance
robot_controller = None


def get_controller():
    """Get or create the robot controller instance."""
    global robot_controller
    if robot_controller is None:
        robot_controller = DualArmController()
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


def setup_routes(app):
    """Register robot API routes with the app."""
    app.router.add_post('/api/robot/connect', handle_connect)
    app.router.add_post('/api/robot/disconnect', handle_disconnect)
    app.router.add_post('/api/robot/home', handle_home)
    app.router.add_post('/api/robot/zero', handle_zero)
    app.router.add_get('/api/robot/status', handle_status)
    app.router.add_post('/api/robot/release', handle_release)
