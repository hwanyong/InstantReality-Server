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
except ImportError:
    WEBRTC_AVAILABLE = False
    logging.warning("aiortc not installed - WebRTC disabled")

# Add project root to path for lib imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.camera_manager import get_camera, get_active_cameras, init_cameras, set_camera_focus, set_camera_exposure, set_camera_auto_exposure, on_camera_refresh
from src.camera_mapping import get_index_by_role, get_available_devices, match_roles, assign_role, VALID_ROLES, save_camera_settings, get_all_settings, get_roi_config, save_roi_config, invalidate_role_cache
from src.calibration_manager import get_calibration_for_role, save_calibration_for_role
from src.ai_engine import GeminiBrain
import robot_api

if WEBRTC_AVAILABLE:
    from src.webrtc.video_track import OpenCVVideoCapture, BlackVideoTrack

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
brain: GeminiBrain = None
SCENE_INVENTORY = []

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


async def handle_gemini_execute(request):
    """POST /api/gemini/execute - Generate robot execution plan via Function Calling.
    
    Body: { "instruction": "Pick up the red pen" }
    Returns the plan. Execution is handled client-side step by step.
    """
    if not request.body_exists:
        return web.json_response({"error": "Missing request body"}, status=400)
    
    data = await request.json()
    instruction = data.get("instruction", "").strip()
    
    if not instruction:
        return web.json_response({"error": "instruction is required"}, status=400)
    
    # Capture frame from TopView camera
    topview_idx = get_index_by_role("TopView")
    if topview_idx is None:
        return web.json_response({"error": "TopView camera not configured"}, status=400)
    
    topview_cam = get_camera(topview_idx)
    frame_bgr, _ = topview_cam.get_frames()
    
    if frame_bgr is None:
        return web.json_response({"error": "Failed to capture frame"}, status=500)
    
    # Generate execution plan via Function Calling
    plan = await asyncio.to_thread(brain.execute_with_tools, frame_bgr, instruction)
    
    return web.json_response(plan)


async def handle_verify(request):
    """POST /api/robot/verify
    Verify robot action using arm-mounted camera.
    Uses cached role→index mapping + get_camera() to avoid USB re-scan.

    Body: { arm: "right"|"left", step_type: "move_arm"|"gripper", context: "..." }
    """
    if not request.body_exists:
        return web.json_response({"verified": False, "description": "Missing body"}, status=400)

    data = await request.json()
    arm = data.get("arm", "right")
    step_type = data.get("step_type", "move_arm")
    context = data.get("context", "")

    role_map = {"right": "RightRobot", "left": "LeftRobot"}
    role = role_map.get(arm)
    if not role:
        return web.json_response({"verified": False, "description": f"Unknown arm: {arm}"}, status=400)

    # Get camera index (cached — no USB scan)
    idx = get_index_by_role(role)
    if idx is None:
        return web.json_response({
            "verified": True,
            "description": f"Camera {role} not available, skipping verification"
        })

    # Get frame from cached camera (no USB scan)
    try:
        cam = get_camera(idx)
        frame_bgr, _ = cam.get_frames()
        if frame_bgr is None:
            return web.json_response({
                "verified": True,
                "description": "No frame captured, skipping verification"
            })
    except Exception as e:
        return web.json_response({
            "verified": True,
            "description": f"Camera error: {e}, skipping verification"
        })

    # Call AI verification using existing brain singleton
    try:
        result = await asyncio.to_thread(brain.verify_action, frame_bgr, step_type, context)

        # Apply gripper-camera offset compensation
        if step_type == "move_arm" and result.get("offset"):
            from calibration_manager import get_gripper_offsets
            offsets = get_gripper_offsets()
            arm_offset = offsets.get(arm, {"dx": 0, "dy": 0})
            raw_dx = result["offset"].get("dx", 0)
            raw_dy = result["offset"].get("dy", 0)
            result["offset"]["dx"] = raw_dx + arm_offset.get("dx", 0)
            result["offset"]["dy"] = raw_dy + arm_offset.get("dy", 0)
            logger.info(f"[VERIFY] Gripper offset applied: raw({raw_dx},{raw_dy}) + cam({arm_offset}) = ({result['offset']['dx']},{result['offset']['dy']})")

        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "verified": True,
            "description": f"AI error: {e}, skipping verification"
        })

async def handle_coord_convert(request):
    """POST /api/coord/convert - Convert Gemini 0-1000 coords to robot mm.

    Body: { "gx": 600, "gy": 550 }
    Response: { "x": 65.1, "y": -9.5, "arm": "right" }
    """
    data = await request.json()
    gx = float(data.get("gx", 500))
    gy = float(data.get("gy", 500))

    from calibration_manager import get_calibration_for_role
    from lib.coordinate_transform import gemini_to_robot

    cal = get_calibration_for_role("TopView")
    if not cal or not cal.get("homography_matrix"):
        return web.json_response({"error": "No TopView calibration"}, status=400)

    H = cal["homography_matrix"]
    res = cal.get("resolution", {})
    robot = gemini_to_robot(gx, gy, H, res.get("width", 1920), res.get("height", 1080))
    rx = round(robot["x"], 1)
    ry = round(robot["y"], 1)
    arm = "left" if rx < 0 else "right"

    return web.json_response({"x": rx, "y": ry, "arm": arm})


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
    import math
    from lib.robot.pulse_mapper import PulseMapper
    
    pulse_mapper = PulseMapper()
    
    def calc_physical_pulse(ik_angle, slot_config, polarity=1):
        """Calculate physical angle and pulse for a slot.
        Args:
            ik_angle: IK angle (degrees)
            slot_config: Slot config from servo_config.json
            polarity: +1 for normal, -1 for inverted (slot 4)
        """
        zero_offset = slot_config.get("zero_offset", 90)
        act_range = slot_config.get("actuation_range", 180)
        
        phy = zero_offset + (polarity * ik_angle)
        phy = max(0, min(act_range, phy))
        
        # Construct motor_config from slot config (like get_slot_params)
        motor_config = {
            "actuation_range": slot_config.get("actuation_range", 180),
            "pulse_min": slot_config.get("pulse_min", 500),
            "pulse_max": slot_config.get("pulse_max", 2500)
        }
        pulse = pulse_mapper.physical_to_pulse(phy, motor_config)
        
        return round(phy, 2), pulse
    
    try:
        data = await request.json()
        world_x = float(data.get("world_x", 0))
        world_y = float(data.get("world_y", 0))
        z = float(data.get("z", 3))  # Default Z = 3mm (ground level)
        arm = data.get("arm", "right_arm")
        
        # Load servo config
        config_path = PROJECT_ROOT / "servo_config.json"
        if not config_path.exists():
            return web.json_response({"error": "servo_config.json not found"}, status=500)
        
        with open(config_path, 'r') as f:
            servo_config = json.load(f)
        
        arm_config = servo_config.get(arm, {})
        if not arm_config:
            return web.json_response({"error": f"Invalid arm: {arm}"}, status=400)
        
        # Get slot configs
        slot1 = arm_config.get("slot_1", {})
        slot2 = arm_config.get("slot_2", {})
        slot3 = arm_config.get("slot_3", {})
        slot4 = arm_config.get("slot_4", {})
        slot5 = arm_config.get("slot_5", {})
        slot6 = arm_config.get("slot_6", {})
        
        # Get Base coordinates from geometry section
        geometry = servo_config.get("geometry", {})
        bases = geometry.get("bases", {})
        base = bases.get(arm, {"x": 0, "y": 0})
        base_x = float(base.get("x", 0))
        base_y = float(base.get("y", 0))
        
        # Calculate Local coordinates (World → Local)
        local_x = world_x - base_x
        local_y = world_y - base_y
        
        # Get link lengths from config
        d1 = slot1.get("length", 107.0)  # Base height
        a2 = slot2.get("length", 105.0)  # Upper arm
        a3 = slot3.get("length", 150.0)  # Forearm
        a4 = slot4.get("length", 65.0)   # Wrist
        a6 = slot6.get("length", 70.0)   # Gripper
        
        # θ1 calculation (Base Yaw) - Y=forward, CCW positive
        if local_x == 0 and local_y == 0:
            theta1 = 0.0
        else:
            theta1 = math.degrees(math.atan2(-local_x, local_y))
        
        # Reach (horizontal distance from Base)
        reach = math.sqrt(local_x**2 + local_y**2)
        
        # 5-Link IK: Gripper tip reaches target at -90° (pointing down)
        wrist_z = z + a4 + a6
        
        # 2-Link Planar IK in R-Z plane
        s = wrist_z - d1
        dist_sq = reach**2 + s**2
        dist = math.sqrt(dist_sq)
        
        max_reach = a2 + a3
        min_reach = abs(a2 - a3)
        
        # Fixed angles for Slot 5, 6
        theta5 = 0.0   # Wrist Roll: neutral
        theta6 = 0.0   # Gripper: open (will use default from config)
        
        # Reachability check
        is_valid = True
        config_name = "Elbow Up"
        
        if dist > max_reach or dist < min_reach or dist < 0.001:
            # Pointing fallback
            theta2 = math.degrees(math.atan2(s, reach)) if reach > 0 else (90.0 if s >= 0 else -90.0)
            theta3 = 0.0
            theta4 = -90.0 - theta2
            is_valid = False
            config_name = "Pointing"
        else:
            # Law of Cosines for elbow angle (θ3)
            cos_theta3 = (dist_sq - a2**2 - a3**2) / (2 * a2 * a3)
            cos_theta3 = max(-1.0, min(1.0, cos_theta3))
            theta3_rad = math.acos(cos_theta3)
            
            # Shoulder angle components
            beta = math.atan2(s, reach)
            cos_alpha = (a2**2 + dist_sq - a3**2) / (2 * a2 * dist)
            cos_alpha = max(-1.0, min(1.0, cos_alpha))
            alpha = math.acos(cos_alpha)
            
            # Elbow Up solution
            theta2 = math.degrees(beta + alpha)
            theta3 = -math.degrees(theta3_rad)
            theta3 = -theta3  # inversion for min_pos: top
            
            # θ4: keep gripper pointing down
            theta4 = -90.0 - theta2 + theta3
        
        # Calculate Physical angles and Pulses for all slots
        phy1, pls1 = calc_physical_pulse(theta1, slot1, polarity=1)
        phy2, pls2 = calc_physical_pulse(theta2, slot2, polarity=1)
        phy3, pls3 = calc_physical_pulse(theta3, slot3, polarity=1)
        phy4, pls4 = calc_physical_pulse(theta4, slot4, polarity=-1)  # Inverted!
        phy5, pls5 = calc_physical_pulse(theta5, slot5, polarity=1)
        phy6, pls6 = calc_physical_pulse(theta6, slot6, polarity=1)
        
        return web.json_response({
            "success": True,
            "local": {"x": round(local_x, 2), "y": round(local_y, 2)},
            "reach": round(reach, 2),
            "ik": {
                "theta1": round(theta1, 2),
                "theta2": round(theta2, 2),
                "theta3": round(theta3, 2),
                "theta4": round(theta4, 2),
                "theta5": round(theta5, 2),
                "theta6": round(theta6, 2)
            },
            "physical": {
                "slot1": phy1, "slot2": phy2, "slot3": phy3,
                "slot4": phy4, "slot5": phy5, "slot6": phy6
            },
            "pulse": {
                "slot1": pls1, "slot2": pls2, "slot3": pls3,
                "slot4": pls4, "slot5": pls5, "slot6": pls6
            },
            "config_name": config_name,
            "valid": is_valid
        })
        
    except Exception as e:
        logger.error(f"IK calculation error: {e}")
        return web.json_response({"error": str(e)}, status=500)


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
    
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Connection state: {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
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
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    
    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
        "client_id": pc_id,
        "mapped_roles": mapped_roles  # Return actual role mapping
    })


async def handle_websocket(request):
    """GET /ws - WebSocket for real-time updates"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws_clients.add(ws)
    logger.info(f"WebSocket client connected. Total: {len(ws_clients)}")
    
    try:
        async for msg in ws:
            pass  # Keep-alive
    finally:
        ws_clients.discard(ws)
        logger.info(f"WebSocket client disconnected. Total: {len(ws_clients)}")
    
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
    global brain
    
    # Initialize Gemini brain
    brain = GeminiBrain()
    logger.info("Gemini brain initialized")
    
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
        web.post('/api/gemini/execute', handle_gemini_execute),
        web.post('/api/robot/verify', handle_verify),
        web.post('/api/coord/convert', handle_coord_convert),
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
        app.router.add_get('/ws', handle_websocket)
        logger.info("WebRTC routes registered: /offer, /ws, /pause_camera, /pause_camera_client")
    
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
    web.run_app(app, host='0.0.0.0', port=args.port)
