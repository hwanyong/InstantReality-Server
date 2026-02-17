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
import cv2
import base64

# WebRTC imports
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, RTCRtpSender
    from aiortc.contrib.media import MediaRelay
    WEBRTC_AVAILABLE = True

    # Monkey-patch: disable aioice mDNS to prevent WinError 10065
    # on Windows hosts where multicast sockets fail.
    # Returns a stub protocol whose resolve() passes hostnames through.
    try:
        import aioice.mdns as _mdns_mod

        class _MdnsStub:
            async def resolve(self, host):
                return host  # pass .local hostnames through as-is
            def close(self):
                pass

        async def _noop_mdns():
            return _MdnsStub()
        _mdns_mod.create_mdns_protocol = _noop_mdns
    except Exception:
        pass  # aioice internals changed — skip silently

except ImportError:
    WEBRTC_AVAILABLE = False
    logging.warning("aiortc not installed - WebRTC disabled")

# Add project root to path for lib imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.camera_manager import get_camera, get_active_cameras, init_cameras, set_camera_focus, set_camera_exposure, set_camera_auto_exposure, on_camera_refresh
from src.camera_mapping import get_index_by_role, get_available_devices, match_roles, assign_role, VALID_ROLES, save_camera_settings, get_all_settings, get_roi_config, save_roi_config, invalidate_role_cache
from src.calibration_manager import get_calibration_for_role, save_calibration_for_role, build_camera_metadata
from src.ai_engine import GeminiBrain
import robot_api
from plan_executor import PlanExecutor
from lib.connection_logger import log_webrtc_connect, log_webrtc_disconnect, log_ws_connect, log_ws_disconnect, log_stream_start, log_stream_end
from lib.connection_logger import create_file_logger

if WEBRTC_AVAILABLE:
    from src.webrtc.video_track import OpenCVVideoCapture, BlackVideoTrack

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# File logging — server events + HTTP access log
_server_file_logger = create_file_logger("server_file", "server.log")
_access_file_logger = create_file_logger("aiohttp.access", "access.log")

# Global instances
brain: GeminiBrain = None
plan_executor: PlanExecutor = None
SCENE_INVENTORY = []
TWIN_CACHE = {'json': None, 'glb': None}  # Cached twin data

# WebRTC state
pcs = set()  # Active PeerConnections
active_tracks = {}  # {pc_id: {camera_index: {"track": proxy_track, "sender": sender, "paused": False}}}
ws_clients = set()  # WebSocket clients

# MediaRelay for efficient multi-client streaming
relay = MediaRelay() if WEBRTC_AVAILABLE else None
source_tracks = {}  # {camera_index: OpenCVVideoCapture} - singleton per camera

def invalidate_source_tracks():
    """Clear stale source tracks after camera refresh.
    Called by camera_manager.refresh_cameras() via callback."""
    for track in source_tracks.values():
        try:
            track.stop()
        except Exception as e:
            logger.debug(f"Error stopping source track: {e}")
    source_tracks.clear()
    logger.info(f"Source tracks invalidated (camera refresh)")


# =============================================================================
# Helper Functions
# =============================================================================

def get_camera_by_role(role):
    """
    Get camera index by role name.
    Returns (index, None) on success, (None, error_response) on failure.
    """
    idx = get_index_by_role(role)
    if idx is None:
        return None, web.json_response({"error": f"Role {role} not connected"}, status=404)
    return idx, None


def apply_exposure_settings(idx, exposure):
    """Apply exposure settings to a camera."""
    auto = exposure.get("auto", False)
    value = exposure.get("value", -5)
    target_brightness = exposure.get("target_brightness", 128)
    
    if auto:
        set_camera_auto_exposure(idx, True, target_brightness)
    else:
        set_camera_auto_exposure(idx, False, target_brightness)
        set_camera_exposure(idx, value)


# =============================================================================
# API Handlers
# =============================================================================

async def handle_capture(request):
    """GET /api/capture - Capture current camera frame"""
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


async def handle_capture_all(request):
    """GET /api/capture_all - Capture FHD frames from all 4 cameras as ZIP"""
    import io
    import zipfile
    from datetime import datetime
    
    # Role names for file naming
    role_mapping = {
        get_index_by_role('TopView'): 'TopView',
        get_index_by_role('QuarterView'): 'QuarterView',
        get_index_by_role('LeftRobot'): 'LeftRobot',
        get_index_by_role('RightRobot'): 'RightRobot'
    }
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for camera_index, role_name in role_mapping.items():
            if camera_index is None:
                continue
                
            cam = get_camera(camera_index)
            if cam is None:
                continue
                
            high_res, _ = cam.get_frames()
            if high_res is None:
                continue
            
            # Encode to JPEG (high quality)
            _, jpeg_bytes = cv2.imencode('.jpg', high_res, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            # Add to ZIP
            zf.writestr(f'{role_name}.jpg', jpeg_bytes.tobytes())
    
    zip_buffer.seek(0)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'capture_{timestamp}.zip'
    
    return web.Response(
        body=zip_buffer.getvalue(),
        content_type='application/zip',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )

async def handle_scene_init(request):
    """POST /api/scene/init - Scan and initialize scene inventory
    
    Query params:
        precision: If 'true', perform 2-Pass analysis
    """
    global SCENE_INVENTORY
    
    # Check for precision mode
    precision = request.query.get('precision', 'false').lower() == 'true'
    
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
    
    # Get ROI config
    roi_config = get_roi_config()
    
    # Call AI scan with ROI support
    result = brain.scan_scene_with_roi(
        topview_frame, 
        quarterview_frame,
        roi_config=roi_config,
        precision=precision
    )
    
    if "error" not in result or result.get("objects"):
        SCENE_INVENTORY = result.get("objects", [])
        logger.info(f"Scene initialized ({result.get('analysis_mode', 'quick')}): {len(SCENE_INVENTORY)} objects detected")
    
    return web.json_response(result)


async def handle_scene_get(request):
    """GET /api/scene - Get current scene inventory"""
    return web.json_response({"objects": SCENE_INVENTORY})


# =============================================================================
# Digital Twin API
# =============================================================================

async def handle_twin_generate(request):
    """POST /api/twin/generate - Full pipeline: capture → scan → GLB generation.

    Captures TopView camera, runs Gemini scene analysis,
    converts to VR coordinates via Homography, generates GLB.
    """
    global TWIN_CACHE

    if not brain:
        return web.json_response({"error": "AI not initialized"}, status=503)

    # 1. Capture TopView frame
    topview_idx = get_index_by_role("TopView")
    if topview_idx is None:
        return web.json_response({"error": "TopView camera not configured"}, status=400)

    topview_cam = get_camera(topview_idx)
    topview_frame, _ = topview_cam.get_frames()
    if topview_frame is None:
        return web.json_response({"error": "Failed to capture TopView frame"}, status=500)

    # Optional QuarterView
    quarterview_frame = None
    quarterview_idx = get_index_by_role("QuarterView")
    if quarterview_idx is not None:
        quarterview_cam = get_camera(quarterview_idx)
        quarterview_frame, _ = quarterview_cam.get_frames()

    # 2. Run Gemini scene scan
    roi_config = get_roi_config()
    scan_result = brain.scan_scene_with_roi(
        topview_frame, quarterview_frame,
        roi_config=roi_config, precision=False
    )

    if "error" in scan_result and not scan_result.get("objects"):
        return web.json_response({"error": scan_result["error"]}, status=500)

    # 3. Get calibration for Homography transform
    from calibration_manager import get_calibration_for_role
    cal = get_calibration_for_role("TopView")
    if not cal:
        cal = {}  # Will use fallback coordinates
        logger.warning("No TopView calibration — using fallback coordinate mapping")

    # 4. Build VR JSON + GLB
    from twin_generator import build_twin_json, build_twin_glb

    twin_json = build_twin_json(scan_result, cal)
    glb_bytes = build_twin_glb(twin_json)

    # 5. Cache results
    TWIN_CACHE['json'] = twin_json
    TWIN_CACHE['glb'] = glb_bytes

    # Also save to disk for static serving fallback
    cache_dir = Path(__file__).parent / 'static' / 'twin'
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / 'scene.json').write_text(json.dumps(twin_json, indent=2))
    (cache_dir / 'scene.glb').write_bytes(glb_bytes)

    logger.info(f"Twin generated: {len(twin_json.get('objects', []))} objects, GLB {len(glb_bytes)} bytes")

    return web.json_response({
        "status": "ok",
        "objects_count": len(twin_json.get('objects', [])),
        "glb_size_bytes": len(glb_bytes),
        "glb_url": "/api/twin/scene.glb",
    })


async def handle_twin_json(request):
    """GET /api/twin/scene.json - Return cached VR JSON."""
    if TWIN_CACHE['json']:
        return web.json_response(TWIN_CACHE['json'])

    # Try disk fallback
    cache_file = Path(__file__).parent / 'static' / 'twin' / 'scene.json'
    if cache_file.exists():
        data = json.loads(cache_file.read_text())
        TWIN_CACHE['json'] = data
        return web.json_response(data)

    return web.json_response({"error": "No twin data. Call POST /api/twin/generate first."}, status=404)


async def handle_twin_glb(request):
    """GET /api/twin/scene.glb - Return cached GLB binary."""
    if TWIN_CACHE['glb']:
        return web.Response(
            body=TWIN_CACHE['glb'],
            content_type='model/gltf-binary',
            headers={'Content-Disposition': 'inline; filename="scene.glb"'}
        )

    # Try disk fallback
    cache_file = Path(__file__).parent / 'static' / 'twin' / 'scene.glb'
    if cache_file.exists():
        glb_bytes = cache_file.read_bytes()
        TWIN_CACHE['glb'] = glb_bytes
        return web.Response(
            body=glb_bytes,
            content_type='model/gltf-binary',
            headers={'Content-Disposition': 'inline; filename="scene.glb"'}
        )

    return web.json_response({"error": "No twin data. Call POST /api/twin/generate first."}, status=404)


async def handle_gemini_analyze(request):
    """POST /api/gemini/analyze - Analyze frame with natural language instruction.
    
    Body: { "instruction": "Pick up the red pen" }
    Response: { "target_detected": true, "coordinates": [y, x], "description": "..." }
    """
    if not request.body_exists:
        return web.json_response({"error": "Missing request body"}, status=400)
    
    data = await request.json()
    instruction = data.get("instruction", "").strip()
    
    if not instruction:
        return web.json_response({"error": "instruction is required"}, status=400)
    
    # Capture frame from TopView camera (server-side)
    topview_idx = get_index_by_role("TopView")
    if topview_idx is None:
        return web.json_response({"error": "TopView camera not configured"}, status=400)
    
    topview_cam = get_camera(topview_idx)
    frame_bgr, _ = topview_cam.get_frames()
    
    if frame_bgr is None:
        return web.json_response({"error": "Failed to capture frame"}, status=500)
    
    # Call Gemini Brain
    result = await asyncio.to_thread(brain.analyze_frame, frame_bgr, instruction)
    
    return web.json_response(result)


async def handle_plan_start(request):
    """POST /api/plan/start - Start server-driven plan execution.

    Body: { "instruction": "Pick up the red pen" }
    Returns plan_id immediately. Execution runs as background task,
    streaming progress via WebSocket events.
    """
    if not request.body_exists:
        return web.json_response({"error": "Missing request body"}, status=400)

    data = await request.json()
    instruction = data.get("instruction", "").strip()

    if not instruction:
        return web.json_response({"error": "instruction is required"}, status=400)

    result = await plan_executor.start(instruction)
    return web.json_response(result)


# =============================================================================
# Camera Management API
# =============================================================================

async def handle_cameras_scan(request):
    """POST /api/cameras/scan - Scan for connected cameras"""
    invalidate_role_cache()
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
        invalidate_role_cache()
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


async def handle_cameras_roles(request):
    """GET /api/cameras/roles - Get current role→camera mapping for client initialization.
    
    This endpoint allows clients to fetch the latest role assignments
    before establishing WebRTC connections, enabling proper role-based abstraction.
    
    Returns:
        {
            "TopView": {"index": 2, "connected": true, "name": "Web Camera", "path": "..."},
            "QuarterView": {"index": 3, "connected": true, "name": "Web Camera", "path": "..."},
            ...
        }
    """
    roles = match_roles()
    return web.json_response(roles)


async def handle_cameras_focus(request):
    """POST /api/cameras/focus - Set focus for a camera"""
    data = await request.json()
    role = data.get("role")
    auto = data.get("auto", True)
    value = data.get("value", 0)
    
    if not role:
        return web.json_response({"error": "role required"}, status=400)
    
    idx = get_index_by_role(role)
    if idx is None:
        return web.json_response({"error": f"Role {role} not connected"}, status=404)
    
    set_camera_focus(idx, auto, value)
    
    # Save settings
    save_camera_settings(role, {"focus": {"auto": auto, "value": value}})
    
    return web.json_response({"success": True, "role": role, "focus": {"auto": auto, "value": value}})


async def handle_cameras_exposure(request):
    """POST /api/cameras/exposure - Set exposure for a camera"""
    data = await request.json()
    role = data.get("role")
    auto = data.get("auto", False)
    value = data.get("value", -5)
    target_brightness = data.get("target_brightness", 128)
    
    if not role:
        return web.json_response({"error": "role required"}, status=400)
    
    idx, err = get_camera_by_role(role)
    if err:
        return err
    
    exposure_config = {"auto": auto, "value": value, "target_brightness": target_brightness}
    apply_exposure_settings(idx, exposure_config)
    
    # Save settings
    save_camera_settings(role, {"exposure": exposure_config})
    
    return web.json_response({
        "success": True, 
        "role": role, 
        "exposure": {"auto": auto, "value": value, "target_brightness": target_brightness}
    })


async def handle_cameras_settings_get(request):
    """GET /api/cameras/settings - Get all camera settings"""
    settings = get_all_settings()
    return web.json_response(settings)


async def handle_cameras_settings_save(request):
    """POST /api/cameras/settings - Save camera settings for a role"""
    data = await request.json()
    role = data.get("role")
    settings = data.get("settings", {})
    
    if not role:
        return web.json_response({"error": "role required"}, status=400)
    
    result = save_camera_settings(role, settings)
    return web.json_response({"success": True, "role": role, "settings": result})


async def handle_stream(request):
    """GET /api/stream/{camera} - MJPEG stream for live preview"""
    camera_index = int(request.match_info.get('camera', 0))
    log_stream_start(request, camera_index)
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
        log_stream_end(request, camera_index)
        if not isinstance(e, (asyncio.CancelledError, ConnectionResetError)):
            logger.debug(f"Stream ended: {type(e).__name__}")
    
    return response


# =============================================================================
# ROI (Region of Interest) API
# =============================================================================

async def handle_roi_get(request):
    """GET /api/roi - Get workspace ROI configuration"""
    roi = get_roi_config()
    return web.json_response(roi)


async def handle_roi_save(request):
    """POST /api/roi - Save workspace ROI configuration"""
    data = await request.json()
    
    result = save_roi_config(data)
    return web.json_response({"success": True, "roi": result})


# =============================================================================
# Servo Config API
# =============================================================================

async def handle_servo_config_get(request):
    """GET /api/servo_config - Get servo configuration"""
    config_path = PROJECT_ROOT / "servo_config.json"
    
    if not config_path.exists():
        return web.json_response({"error": "servo_config.json not found"}, status=404)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return web.json_response(config)


async def handle_servo_config_save(request):
    """POST /api/servo_config - Save servo configuration"""
    data = await request.json()
    config_path = PROJECT_ROOT / "servo_config.json"

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    # Invalidate cached config so IK uses latest values
    from robotics.config_cache import get_config
    get_config().invalidate()

    logger.info("servo_config.json saved")
    return web.json_response({"success": True})


# =============================================================================
# Calibration API
# =============================================================================

async def handle_calibration_geometry(request):
    """GET /api/calibration/geometry - Get geometry section from servo_config.json
    
    Returns:
        {
            "coordinate_system": "+X=right, +Y=up",
            "bases": {"left_arm": {...}, "right_arm": {...}},
            "vertices": {"1": {...}, "2": {...}, ...},
            "distances": {...}
        }
    """
    config_path = PROJECT_ROOT / "servo_config.json"
    
    if not config_path.exists():
        return web.json_response({"error": "servo_config.json not found"}, status=404)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        geometry = config.get("geometry", {})
        if not geometry:
            return web.json_response({"error": "geometry section not found in config"}, status=404)
        
        return web.json_response(geometry)
    except json.JSONDecodeError as e:
        return web.json_response({"error": f"Invalid JSON: {e}"}, status=500)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_calibration_data_get(request):
    """GET /api/calibration/{role} - Get calibration data for a specific role
    
    Returns pixel coordinates, homography matrix, and metadata.
    """
    role = request.match_info.get('role', 'TopView')
    
    calibration = get_calibration_for_role(role)
    if calibration is None:
        return web.json_response({"error": f"No calibration data for {role}"}, status=404)
    
    return web.json_response(calibration)


async def handle_calibration_data_save(request):
    """POST /api/calibration - Save calibration data for a role
    
    Request body:
    {
        "role": "TopView",
        "calibration": {
            "timestamp": "2026-02-05T00:00:00Z",
            "resolution": {"width": 1920, "height": 1080},
            "homography_matrix": [[...], [...], [...]],
            "pixel_coords": {...},
            "reprojection_error": 0.0023,
            "is_valid": true
        }
    }
    """
    data = await request.json()
    role = data.get("role", "TopView")
    calibration = data.get("calibration")
    
    if not calibration:
        return web.json_response({"error": "calibration data required"}, status=400)
    
    result = save_calibration_for_role(role, calibration)
    logger.info(f"Calibration data saved for {role}")
    
    return web.json_response({"success": True, "role": role, "calibration": result})


# =============================================================================
# IK (Inverse Kinematics) API
# =============================================================================

async def handle_ik_calculate(request):
    """POST /api/ik/calculate - Calculate IK angles for given World coordinates

    Request body:
    {
        "world_x": float,  # World X coordinate (mm, Share Point origin)
        "world_y": float,  # World Y coordinate (mm, Share Point origin)
        "z": float,        # Z height (mm, default: 3)
        "arm": str         # "left_arm" or "right_arm"
    }

    Returns:
    {
        "success": true,
        "local": {"x": float, "y": float},
        "reach": float,
        "ik": {"theta1": ..., "theta2": ..., "theta3": ..., "theta4": ...},
        "physical": {"slot1": ..., ..., "slot6": ...},
        "pulse": {"slot1": ..., ..., "slot6": ...},
        "config_name": str,
        "valid": bool
    }
    """
    from robotics.ik_service import compute_ik_detail

    data = await request.json()
    result = compute_ik_detail(
        float(data.get("world_x", 0)),
        float(data.get("world_y", 0)),
        float(data.get("z", 3)),
        data.get("arm", "right_arm")
    )
    return web.json_response(result)


# =============================================================================
# WebRTC Handlers
# =============================================================================

async def handle_offer(request):
    """POST /offer - WebRTC SDP negotiation"""
    if not WEBRTC_AVAILABLE:
        return web.json_response({"error": "WebRTC not available"}, status=503)
    
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    
    # Support role-based camera selection (e.g., ["topview", "quarterview"])
    requested_roles = params.get("roles", [])
    
    pc = RTCPeerConnection()
    pcs.add(pc)
    pc_id = str(id(pc))
    active_tracks[pc_id] = {}
    
    logger.info(f"New WebRTC connection: {pc_id}, roles: {requested_roles}")
    _server_file_logger.info(f"WEBRTC_NEW pc_id={pc_id} roles={requested_roles}")
    log_webrtc_connect(request, pc_id, requested_roles)
    
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Connection state: {pc.connectionState}")
        _server_file_logger.info(f"WEBRTC_STATE pc_id={pc_id} state={pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            log_webrtc_disconnect(pc_id)
            await pc.close()
            pcs.discard(pc)
            active_tracks.pop(pc_id, None)
    
    # Determine which cameras to stream
    mapped_roles = []
    if requested_roles:
        # Role-based selection for calibration
        camera_indices = []
        for role in requested_roles:
            idx = get_index_by_role(role)
            if idx is not None:
                camera_indices.append(idx)
                mapped_roles.append(role)  # Track actually mapped roles
                logger.info(f"Role '{role}' -> camera {idx}")
            else:
                logger.warning(f"Role '{role}' not found")
    else:
        # Broadcast mode: all active cameras
        camera_indices = get_active_cameras()
    
    if not camera_indices:
        logger.warning("No cameras running for WebRTC")
    
    # Force H.264 codec for Safari support
    h264_codecs = []
    try:
        capabilities = RTCRtpSender.getCapabilities("video")
        h264_codecs = [c for c in capabilities.codecs if "H264" in c.mimeType]
        if h264_codecs:
            logger.info(f"Enforcing H.264 codec")
    except Exception as e:
        logger.debug(f"H.264 not available: {e}")
    
    # Add tracks using MediaRelay for efficient multi-client streaming
    for idx in camera_indices:
        try:
            # Get or create singleton source track
            if idx not in source_tracks:
                source_tracks[idx] = OpenCVVideoCapture(camera_index=idx, options={"width": 1920, "height": 1080})
                logger.info(f"Created source track for camera {idx}")
            
            # Create proxy track for this client via MediaRelay
            proxy_track = relay.subscribe(source_tracks[idx], buffered=False)  # Low latency mode
            sender = pc.addTrack(proxy_track)
            active_tracks[pc_id][idx] = {
                "track": proxy_track,
                "sender": sender,
                "paused": False
            }
            
            if h264_codecs:
                transceiver = next((t for t in pc.getTransceivers() if t.sender == sender), None)
                if transceiver:
                    transceiver.setCodecPreferences(h264_codecs)
            
            logger.info(f"Added proxy track for camera {idx}")
        except Exception as e:
            logger.error(f"Failed to add track for camera {idx}: {e}")
    
    # THEN setRemoteDescription (original server.py pattern)
    try:
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
    except OSError as e:
        logger.error(f"ICE/mDNS socket error during offer negotiation: {e}")
        await pc.close()
        pcs.discard(pc)
        active_tracks.pop(pc_id, None)
        return web.json_response({"error": f"WebRTC negotiation failed: {e}"}, status=500)
    
    # Build camera metadata for mapped roles
    camera_metadata = {}
    for role in mapped_roles:
        meta = build_camera_metadata(role)
        if meta:
            camera_metadata[role] = meta

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
        "client_id": pc_id,
        "mapped_roles": mapped_roles,
        "camera_metadata": camera_metadata if camera_metadata else None
    })


async def handle_websocket(request):
    """GET /ws - WebSocket for real-time updates"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws_clients.add(ws)
    logger.info(f"WebSocket client connected. Total: {len(ws_clients)}")
    log_ws_connect(request)
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get("type", "")
                    if msg_type == "plan:abort" and plan_executor:
                        await plan_executor.abort()
                        logger.info("[WS] plan:abort received")
                except json.JSONDecodeError:
                    pass
    finally:
        ws_clients.discard(ws)
        logger.info(f"WebSocket client disconnected. Total: {len(ws_clients)}")
        log_ws_disconnect(request)
    
    return ws


async def ws_broadcast(message):
    """Broadcast message to all WebSocket clients."""
    for ws in list(ws_clients):
        if not ws.closed:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.debug(f"Failed to send to WebSocket: {e}")
                ws_clients.discard(ws)


async def handle_pause_camera(request):
    """POST /pause_camera - Pause/resume camera track (affects all clients)"""
    data = await request.json()
    camera_index = int(data.get("camera_index", 0))
    paused = data.get("paused", True)
    
    # Pause is applied to source track (affects all clients)
    if camera_index in source_tracks:
        source_tracks[camera_index].set_paused(paused)
        logger.info(f"Camera {camera_index}: paused={paused} (all clients)")
    
    return web.json_response({"success": True, "camera_index": camera_index, "paused": paused})


async def handle_pause_camera_client(request):
    """POST /pause_camera_client - Per-client pause (bandwidth saving)
    
    Supports both legacy camera_index and role-based addressing.
    Role-based addressing is preferred for stable camera identification.
    """
    data = await request.json()
    client_id = data.get("client_id")
    paused = data.get("paused", True)
    
    if not client_id:
        return web.json_response({"error": "client_id required"}, status=400)
    
    if client_id not in active_tracks:
        return web.json_response({"error": "Client not found"}, status=404)
    
    # Role-based addressing (preferred)
    role = data.get("role")
    if role:
        camera_index = get_index_by_role(role)
        if camera_index is None:
            return web.json_response({"error": f"Role {role} not connected"}, status=404)
    else:
        # Legacy: direct camera_index
        camera_index = int(data.get("camera_index", 0))
    
    if camera_index not in active_tracks[client_id]:
        return web.json_response({"error": f"Camera {camera_index} not found for client"}, status=404)
    
    track_info = active_tracks[client_id][camera_index]
    sender = track_info["sender"]
    
    if paused:
        # Replace with minimal black track to save bandwidth
        black_track = BlackVideoTrack()
        sender.replaceTrack(black_track)
        track_info["paused"] = True
        logger.info(f"Client {client_id}: camera {camera_index} ({role or 'direct'}) paused (per-client)")
    else:
        # Restore original proxy track
        new_proxy = relay.subscribe(source_tracks[camera_index], buffered=False)
        sender.replaceTrack(new_proxy)
        track_info["track"] = new_proxy
        track_info["paused"] = False
        logger.info(f"Client {client_id}: camera {camera_index} ({role or 'direct'}) resumed (per-client)")
    
    return web.json_response({
        "success": True,
        "client_id": client_id,
        "camera_index": camera_index,
        "role": role,
        "paused": paused
    })


async def broadcast_camera_change(cameras):
    """Broadcast camera change to all WebSocket clients"""
    await ws_broadcast({"type": "camera_change", "cameras": cameras})


# =============================================================================
# Static Files & App Setup
# =============================================================================

async def start_camera_polling():
    """Background task for camera hot-plug detection.
    
    Polls for camera changes every 3 seconds and broadcasts updates via WebSocket.
    This allows settings.html to auto-refresh when cameras are added/removed.
    """
    from src.camera_manager import start_polling
    
    async def on_camera_change(added, removed, cameras):
        logger.info(f"Camera change detected: +{len(added)} added, -{len(removed)} removed")
        await broadcast_camera_change(cameras)
    
    try:
        await start_polling(on_camera_change, interval=3)
    except Exception as e:
        logger.error(f"Camera polling error: {e}")


async def init_app():
    """Initialize application"""
    global brain, plan_executor
    
    # Initialize Gemini brain
    brain = GeminiBrain()
    logger.info("Gemini brain initialized")
    
    # Initialize Plan Executor (server-driven orchestration)
    controller = robot_api.get_controller()
    plan_executor = PlanExecutor(
        brain=brain,
        controller=controller,
        ws_broadcast=ws_broadcast
    )
    logger.info("PlanExecutor initialized")
    
    # Register WebRTC cleanup on camera refresh
    on_camera_refresh(invalidate_source_tracks)
    
    # =========================================================================
    # Phase 1: Initialize ALL physical cameras (not just role-mapped)
    # =========================================================================
    from src.camera_mapping import get_available_devices
    
    # Discover all connected USB video devices
    devices = get_available_devices()
    logger.info(f"Found {len(devices)} USB video devices")
    
    # Filter out virtual devices (Logi Capture, OBS Virtual Camera, etc.)
    VIRTUAL_KEYWORDS = ["capture", "virtual", "obs"]
    physical_devices = [
        d for d in devices
        if not any(kw in d["name"].lower() for kw in VIRTUAL_KEYWORDS)
    ]
    logger.info(f"Physical cameras: {len(physical_devices)}")
    
    # Initialize ALL physical cameras
    camera_indices = [d["index"] for d in physical_devices]
    
    if camera_indices:
        init_cameras(camera_indices, width=1920, height=1080)
        logger.info(f"Cameras initialized: {camera_indices}")
        
        # Build role status for logging
        role_status = {}
        for role in VALID_ROLES:
            idx = get_index_by_role(role)
            role_status[role] = idx
        logger.info(f"Role mapping: {role_status}")
        
        # Apply saved settings only to role-assigned cameras
        all_settings = get_all_settings()
        for role, info in all_settings.items():
            if info["connected"] and info["index"] is not None:
                idx = info["index"]
                settings = info["settings"]
                
                # Apply focus settings
                focus = settings.get("focus", {})
                set_camera_focus(idx, focus.get("auto", True), focus.get("value", 0))
                
                # Apply exposure settings
                exposure = settings.get("exposure", {})
                apply_exposure_settings(idx, exposure)
                
                logger.info(f"Applied settings for {role} (camera {idx})")
    else:
        # Fallback to default camera 0
        init_cameras([0], width=1920, height=1080)
        logger.warning("No physical cameras found, using default camera 0")
    
    # =========================================================================
    # Phase 2: Start background polling for camera hot-plug detection
    # =========================================================================
    asyncio.create_task(start_camera_polling())


@web.middleware
async def sdk_cors_middleware(request, handler):
    if request.path.startswith('/sdk/'):
        if request.method == 'OPTIONS':
            return web.Response(headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': '*',
            })
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    return await handler(request)


def create_app():
    """Create and configure the aiohttp application"""
    app = web.Application(middlewares=[sdk_cors_middleware])
    
    # Setup CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    
    # Register WebSocket broadcast helper on app
    app.ws_broadcast = ws_broadcast
    
    # API routes
    api_routes = [
        # Scene API
        web.get('/api/capture', handle_capture),
        web.get('/api/capture_all', handle_capture_all),
        web.post('/api/scene/init', handle_scene_init),
        web.get('/api/scene', handle_scene_get),
        # Gemini API
        web.post('/api/gemini/analyze', handle_gemini_analyze),
        web.post('/api/plan/start', handle_plan_start),
        # Twin API
        web.post('/api/twin/generate', handle_twin_generate),
        web.get('/api/twin/scene.json', handle_twin_json),
        web.get('/api/twin/scene.glb', handle_twin_glb),
        # Camera Management API
        web.post('/api/cameras/scan', handle_cameras_scan),
        web.post('/api/cameras/assign', handle_cameras_assign),
        web.get('/api/cameras/status', handle_cameras_status),
        web.get('/api/cameras/roles', handle_cameras_roles),
        web.get('/api/stream/{camera}', handle_stream),
        # Camera Control API
        web.post('/api/cameras/focus', handle_cameras_focus),
        web.post('/api/cameras/exposure', handle_cameras_exposure),
        web.get('/api/cameras/settings', handle_cameras_settings_get),
        web.post('/api/cameras/settings', handle_cameras_settings_save),
        # ROI API
        web.get('/api/roi', handle_roi_get),
        web.post('/api/roi', handle_roi_save),
        # Servo Config API
        web.get('/api/servo_config', handle_servo_config_get),
        web.post('/api/servo_config', handle_servo_config_save),
        # Calibration API
        web.get('/api/calibration/geometry', handle_calibration_geometry),
        web.get('/api/calibration/{role}', handle_calibration_data_get),
        web.post('/api/calibration', handle_calibration_data_save),
        # IK API
        web.post('/api/ik/calculate', handle_ik_calculate),
    ]
    
    for route in api_routes:
        cors.add(app.router.add_route(route.method, route.path, route.handler))
    
    # WebRTC routes (no CORS needed for these)
    if WEBRTC_AVAILABLE:
        cors.add(app.router.add_route('POST', '/offer', handle_offer))
        cors.add(app.router.add_route('POST', '/pause_camera', handle_pause_camera))
        cors.add(app.router.add_route('POST', '/pause_camera_client', handle_pause_camera_client))
        logger.info("WebRTC routes registered: /offer, /pause_camera, /pause_camera_client")

    # WebSocket route (independent of WebRTC — used for plan progress)
    app.router.add_get('/ws', handle_websocket)
    logger.info("WebSocket route registered: /ws")
    
    # Robot API routes
    robot_api.setup_routes(app)
    logger.info("Robot API routes registered: /api/robot/*")
    
    # Static files - robotics UI
    static_path = Path(__file__).parent / 'static' / 'robotics'
    if static_path.exists():
        app.router.add_static('/robotics/', static_path)
        logger.info(f"Serving static files from: {static_path}")
    
    # Static files - SDK
    sdk_path = Path(__file__).parent / 'sdk'
    if sdk_path.exists():
        app.router.add_static('/sdk/', sdk_path)
        logger.info(f"Serving SDK from: {sdk_path}")
    
    
    # Index redirect
    async def index_redirect(request):
        raise web.HTTPFound('/robotics/index.html')
    
    app.router.add_get('/', index_redirect)
    
    # Startup/cleanup
    app.on_startup.append(lambda app: init_app())
    
    return app


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='InstantReality Scene Init Server')
    parser.add_argument('--port', '-p', type=int, default=8080, help='Port number (default: 8080)')
    args = parser.parse_args()
    
    app = create_app()
    logger.info(f"Starting Scene Init Server on port {args.port}")
    access_logger = logging.getLogger("aiohttp.access")
    web.run_app(app, host='0.0.0.0', port=args.port, access_log=access_logger)
