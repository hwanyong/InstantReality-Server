# src/server_v2.py
# Gemini Robotics Web App Server (v2)
# Main server - port 8080

import os
import sys
import json
import asyncio
import logging
from pathlib import Path

from aiohttp import web
import aiohttp_cors

# Add project root to path for lib imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.robot_controller import RobotController
from lib.coordinate_transform import CoordinateTransformer, WorkspaceConfig
from src.camera_manager import get_camera, get_active_cameras, init_cameras
from src.camera_mapping import get_index_by_role
from src.ai_engine import GeminiBrain

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
robot: RobotController = None
transformer: CoordinateTransformer = None
brain: GeminiBrain = None
SCENE_INVENTORY = []


# =============================================================================
# API Handlers
# =============================================================================

async def handle_config(request):
    """GET /api/config - Return robot configuration"""
    return web.json_response(robot.get_config_summary())


async def handle_capture(request):
    """GET /api/capture - Capture current camera frame"""
    import cv2
    import base64
    
    camera_index = int(request.query.get('camera', 0))
    cameras = get_active_cameras()
    
    if camera_index not in cameras:
        return web.json_response(
            {"error": f"Camera {camera_index} not active. Available: {cameras}"},
            status=400
        )
    
    cam = get_camera(camera_index)
    high_res, _ = cam.get_frames()
    
    if high_res is None:
        return web.json_response({"error": "Failed to capture frame"}, status=500)
    
    # Resize for Gemini (800px width)
    h, w = high_res.shape[:2]
    target_width = 800
    new_h = int(target_width * h / w)
    resized = cv2.resize(high_res, (target_width, new_h))
    
    # Encode to base64
    _, buffer = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64_image = base64.b64encode(buffer).decode('utf-8')
    
    return web.json_response({
        "image": b64_image,
        "width": target_width,
        "height": new_h,
        "original_size": [w, h]
    })


async def handle_prompt(request):
    """POST /api/prompt - Process natural language command with Gemini"""
    import cv2
    
    data = await request.json()
    instruction = data.get('instruction', '')
    camera_index = data.get('camera', 0)
    
    if not instruction:
        return web.json_response({"error": "Missing instruction"}, status=400)
    
    # Capture frame
    cam = get_camera(camera_index)
    if cam is None:
        return web.json_response({"error": "Camera not available"}, status=500)
    
    high_res, _ = cam.get_frames()
    if high_res is None:
        return web.json_response({"error": "Failed to capture frame"}, status=500)
    
    # Resize for Gemini
    h, w = high_res.shape[:2]
    target_width = 800
    new_h = int(target_width * h / w)
    resized = cv2.resize(high_res, (target_width, new_h))
    
    # Call Gemini with robotics prompt
    prompt = f"""You are a dual-arm robot controller.
User instruction: "{instruction}"

Analyze the image and return:
1. target_arm: "right_arm" or "left_arm" (select optimal arm based on object position)
2. coordinates: [y, x] (0-1000 normalized, origin at top-left)
3. approach_strategy: "straight" | "hook_left" | "hook_right"
4. target_z: estimated object height in mm (default 10 for flat objects)
5. description: brief reasoning

Output strictly in JSON format:
{{
    "target_arm": "right_arm",
    "coordinates": [y, x],
    "approach_strategy": "straight",
    "target_z": 10,
    "description": "..."
}}"""
    
    gemini_result = brain.analyze_frame(resized, prompt)
    
    if "error" in gemini_result:
        return web.json_response(gemini_result, status=500)
    
    # Parse Gemini response
    arm_name = gemini_result.get('target_arm', 'right_arm')
    coords = gemini_result.get('coordinates', [500, 500])
    target_z = gemini_result.get('target_z', 10)
    strategy = gemini_result.get('approach_strategy', 'straight')
    
    # Transform coordinates
    gemini_y, gemini_x = coords[0], coords[1]
    local_x, local_y, local_z = transformer.gemini_to_robot(
        gemini_x, gemini_y, target_z, arm_name
    )
    
    # Solve IK
    ik_result = robot.solve_and_validate(arm_name, local_x, local_y, local_z)
    
    return web.json_response({
        "instruction": instruction,
        "gemini_analysis": gemini_result,
        "transformed_coords": {
            "local_x": round(local_x, 2),
            "local_y": round(local_y, 2), 
            "local_z": round(local_z, 2)
        },
        "ik_result": ik_result,
        "approach_strategy": strategy
    })


async def handle_execute(request):
    """POST /api/execute - Send pulse commands to hardware"""
    data = await request.json()
    pulses = data.get('pulses', [])
    duration = data.get('duration', 500)
    
    if not pulses:
        return web.json_response({"error": "No pulse commands provided"}, status=400)
    
    # TODO: Implement actual serial communication
    # For now, just log and return success
    logger.info(f"Execute pulses: {pulses} (duration: {duration}ms)")
    
    return web.json_response({
        "status": "executed",
        "pulses": pulses,
        "duration": duration,
        "note": "Hardware communication not yet implemented"
    })


async def handle_estop(request):
    """POST /api/estop - Emergency stop"""
    logger.warning("E-STOP triggered!")
    
    # TODO: Send emergency stop command to hardware
    # Send 'X' command to release all servos
    
    return web.json_response({
        "status": "stopped",
        "message": "Emergency stop executed"
    })


async def handle_ik_test(request):
    """POST /api/ik/test - Test IK calculation without execution"""
    data = await request.json()
    
    arm_name = data.get('arm', 'right_arm')
    x = data.get('x', 0)
    y = data.get('y', 200)
    z = data.get('z', 50)
    roll = data.get('roll', 90)
    gripper = data.get('gripper', 0)
    
    result = robot.solve_and_validate(arm_name, x, y, z, roll, gripper)
    return web.json_response(result)


async def handle_scene_init(request):
    """POST /api/scene/init - Scan and initialize scene inventory"""
    global SCENE_INVENTORY
    
    # Get TopView camera
    topview_idx = get_index_by_role("TopView")
    quarterview_idx = get_index_by_role("QuarterView")
    
    if topview_idx is None:
        return web.json_response({
            "error": "TopView camera not configured",
            "objects": []
        }, status=400)
    
    # Capture frames
    topview_cam = get_camera(topview_idx)
    topview_frame, _ = topview_cam.get_frames()
    
    if topview_frame is None:
        return web.json_response({
            "error": "Failed to capture TopView frame",
            "objects": []
        }, status=500)
    
    quarterview_frame = None
    if quarterview_idx is not None:
        quarterview_cam = get_camera(quarterview_idx)
        quarterview_frame, _ = quarterview_cam.get_frames()
    
    # Call AI scan
    result = brain.scan_scene(topview_frame, quarterview_frame)
    
    if "error" not in result or result.get("objects"):
        SCENE_INVENTORY = result.get("objects", [])
        logger.info(f"Scene initialized: {len(SCENE_INVENTORY)} objects detected")
    
    return web.json_response(result)


async def handle_scene_get(request):
    """GET /api/scene - Get current scene inventory"""
    return web.json_response({"objects": SCENE_INVENTORY})

# =============================================================================
# Static Files & App Setup
# =============================================================================

async def init_app():
    """Initialize application"""
    global robot, transformer, brain
    
    # Initialize robot controller
    config_path = PROJECT_ROOT / 'servo_config.json'
    robot = RobotController(str(config_path))
    logger.info(f"Robot controller initialized: {robot.get_available_arms()}")
    
    # Initialize coordinate transformer
    transformer = CoordinateTransformer(WorkspaceConfig(
        width_mm=600,
        height_mm=400,
        robot_base_height=107,
        default_target_z=10
    ))
    logger.info("Coordinate transformer initialized")
    
    # Initialize Gemini brain
    brain = GeminiBrain()
    logger.info("Gemini brain initialized")
    
    # Initialize cameras by role
    topview_idx = get_index_by_role("TopView")
    quarterview_idx = get_index_by_role("QuarterView")
    
    camera_indices = [i for i in [topview_idx, quarterview_idx] if i is not None]
    if camera_indices:
        init_cameras(camera_indices, width=1280, height=720)
        logger.info(f"Cameras initialized by role: TopView={topview_idx}, QuarterView={quarterview_idx}")
    else:
        # Fallback to default camera 0
        init_cameras([0], width=1280, height=720)
        logger.warning("No role-mapped cameras found, using default camera 0")


def create_app():
    """Create and configure the aiohttp application"""
    app = web.Application()
    
    # Setup CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    
    # API routes
    api_routes = [
        web.get('/api/config', handle_config),
        web.get('/api/capture', handle_capture),
        web.post('/api/prompt', handle_prompt),
        web.post('/api/execute', handle_execute),
        web.post('/api/estop', handle_estop),
        web.post('/api/ik/test', handle_ik_test),
        web.post('/api/scene/init', handle_scene_init),
        web.get('/api/scene', handle_scene_get),
    ]
    
    for route in api_routes:
        cors.add(app.router.add_route(route.method, route.path, route.handler))
    
    # Static files
    static_path = Path(__file__).parent / 'static' / 'robotics'
    if static_path.exists():
        app.router.add_static('/robotics/', static_path)
        logger.info(f"Serving static files from: {static_path}")
    
    # Index redirect
    async def index_redirect(request):
        raise web.HTTPFound('/robotics/index.html')
    
    app.router.add_get('/', index_redirect)
    
    # Startup/cleanup
    app.on_startup.append(lambda app: init_app())
    
    return app


if __name__ == '__main__':
    PORT = 8080
    app = create_app()
    logger.info(f"Starting Gemini Robotics Server v2 on port {PORT}")
    web.run_app(app, host='0.0.0.0', port=PORT)
