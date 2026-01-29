# src/server_v2.py
# Scene Initialization Server
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

from src.camera_manager import get_camera, get_active_cameras, init_cameras
from src.camera_mapping import get_index_by_role, get_available_devices, match_roles, assign_role, VALID_ROLES
from src.ai_engine import GeminiBrain

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
brain: GeminiBrain = None
SCENE_INVENTORY = []


# =============================================================================
# API Handlers
# =============================================================================

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
# Camera Management API
# =============================================================================

async def handle_cameras_scan(request):
    """POST /api/cameras/scan - Scan for connected cameras"""
    devices = get_available_devices()
    roles = match_roles(devices)
    
    return web.json_response({
        "devices": devices,
        "roles": roles,
        "valid_roles": VALID_ROLES
    })


async def handle_cameras_assign(request):
    """POST /api/cameras/assign - Assign role to a camera"""
    data = await request.json()
    device_path = data.get("device_path")
    role_name = data.get("role")
    
    if not device_path or not role_name:
        return web.json_response(
            {"error": "device_path and role required"},
            status=400
        )
    
    try:
        assign_role(device_path, role_name)
        return web.json_response({
            "success": True,
            "device_path": device_path,
            "role": role_name
        })
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)


async def handle_cameras_status(request):
    """GET /api/cameras/status - Get current camera status"""
    active = get_active_cameras()
    roles = match_roles()
    
    return web.json_response({
        "active_cameras": active,
        "role_mapping": roles
    })


async def handle_stream(request):
    """GET /api/stream/{camera} - MJPEG stream for live preview"""
    import cv2
    
    camera_index = int(request.match_info.get('camera', 0))
    cam = get_camera(camera_index)
    
    if cam is None:
        return web.Response(text="Camera not found", status=404)
    
    response = web.StreamResponse(
        status=200,
        headers={
            'Content-Type': 'multipart/x-mixed-replace; boundary=frame',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    )
    await response.prepare(request)
    
    try:
        while True:
            _, low_res = cam.get_frames()
            if low_res is not None:
                # Encode to JPEG
                _, jpeg = cv2.imencode('.jpg', low_res, [cv2.IMWRITE_JPEG_QUALITY, 70])
                
                # Send MJPEG frame
                await response.write(
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' +
                    jpeg.tobytes() +
                    b'\r\n'
                )
            
            await asyncio.sleep(0.033)  # ~30fps
    except (asyncio.CancelledError, ConnectionResetError, Exception) as e:
        # Client disconnected - this is normal behavior
        if not isinstance(e, (asyncio.CancelledError, ConnectionResetError)):
            logger.debug(f"Stream ended: {type(e).__name__}")
    
    return response


# =============================================================================
# Static Files & App Setup
# =============================================================================

async def init_app():
    """Initialize application"""
    global brain
    
    # Initialize Gemini brain
    brain = GeminiBrain()
    logger.info("Gemini brain initialized")
    
    # Initialize all role-mapped cameras
    camera_indices = []
    role_status = {}
    
    for role in VALID_ROLES:
        idx = get_index_by_role(role)
        if idx is not None:
            camera_indices.append(idx)
            role_status[role] = idx
        else:
            role_status[role] = None
    
    if camera_indices:
        init_cameras(camera_indices, width=1280, height=720)
        logger.info(f"Cameras initialized: {role_status}")
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
        # Scene API
        web.get('/api/capture', handle_capture),
        web.post('/api/scene/init', handle_scene_init),
        web.get('/api/scene', handle_scene_get),
        # Camera Management API
        web.post('/api/cameras/scan', handle_cameras_scan),
        web.post('/api/cameras/assign', handle_cameras_assign),
        web.get('/api/cameras/status', handle_cameras_status),
        web.get('/api/stream/{camera}', handle_stream),
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
        raise web.HTTPFound('/robotics/scene.html')
    
    app.router.add_get('/', index_redirect)
    
    # Startup/cleanup
    app.on_startup.append(lambda app: init_app())
    
    return app


if __name__ == '__main__':
    PORT = 8080
    app = create_app()
    logger.info(f"Starting Scene Init Server on port {PORT}")
    web.run_app(app, host='0.0.0.0', port=PORT)
