import asyncio
import json
import os
import time

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCRtpSender

from webrtc.video_track import OpenCVVideoCapture
from multi_cam_capture import discover_cameras
from camera_manager import stop_all, init_cameras, get_active_cameras, get_camera, refresh_cameras, get_camera_by_role, start_polling
from ai_engine import GeminiBrain
from camera_mapping import get_available_devices, assign_role as mapping_assign_role, match_roles, VALID_ROLES

# Global list of active PeerConnections
pcs = set()
brain = GeminiBrain()

# Track registry: {pc_id: {camera_index: track}}
active_tracks = {}

# WebSocket clients for real-time camera updates
ws_clients = set()

# CORS Middleware for cross-origin requests
@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        return web.Response(headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        })
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    
    # Optional: Request specific camera by role
    requested_role = params.get("role")

    pc = RTCPeerConnection()
    pcs.add(pc)
    pc_id = str(id(pc))
    active_tracks[pc_id] = {}

    print(f"New connection: {pc} (client_id: {pc_id}, role: {requested_role})")

    # Prepare logic to run when connection closes
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)
            active_tracks.pop(pc_id, None)

    # Determine which cameras to stream
    if requested_role:
        # Single camera by role
        cam = get_camera_by_role(requested_role)
        if cam:
            camera_indices = [cam.camera_index]
        else:
            print(f"Warning: Role '{requested_role}' not found or not connected!")
            camera_indices = []
    else:
        # Broadcast Mode: Use all running cameras
        camera_indices = get_active_cameras()
        
    if not camera_indices:
        print("Warning: No cameras running!")
    
    # Force H.264 for Safari support
    try:
        capabilities = RTCRtpSender.getCapabilities("video")
        h264_codecs = [c for c in capabilities.codecs if "H264" in c.mimeType]
        if h264_codecs:
            print(f"Enforcing H.264 Codec: {h264_codecs[0]}")
    except Exception as e:
        print(f"Error finding H.264 capability: {e}")
        h264_codecs = []

    for idx in camera_indices:
        try:
            # We assume these cameras exist for the test
            track = OpenCVVideoCapture(camera_index=idx, options={"width": 1920, "height": 1080})
            sender = pc.addTrack(track)
            
            # Register track for pause/resume control (per-client)
            active_tracks[pc_id][idx] = track
            
            # Apply H.264 preference if available
            if h264_codecs:
                transceiver = next((t for t in pc.getTransceivers() if t.sender == sender), None)
                if transceiver:
                    transceiver.setCodecPreferences(h264_codecs)
                    
            print(f"Added track for Camera {idx}")
        except Exception as e:
            print(f"Failed to add track for Camera {idx}: {e}")

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type, "client_id": pc_id}
        ),
    )

async def index(request):
    content = open(os.path.join("src/static", "index.html"), "r", encoding="utf-8").read()
    return web.Response(content_type="text/html", text=content)

async def javascript(request):
    content = open(os.path.join("src/static", "client.mjs"), "r", encoding="utf-8").read()
    return web.Response(content_type="application/javascript", text=content)

async def serve_sdk_library(request):
    content = open(os.path.join("src/sdk", "instant-reality.mjs"), "r", encoding="utf-8").read()
    return web.Response(content_type="application/javascript", text=content)

async def serve_sdk_example(request):
    content = open(os.path.join("src/sdk", "example.html"), "r", encoding="utf-8").read()
    return web.Response(content_type="text/html", text=content)

async def serve_sdk_types(request):
    content = open(os.path.join("src/sdk", "instant-reality.d.ts"), "r", encoding="utf-8").read()
    return web.Response(content_type="application/typescript", text=content)

async def set_focus_handler(request):
    try:
        data = await request.json()
        camera_index = int(data.get("camera_index", 0))
        auto = bool(data.get("auto", True))
        value = int(data.get("value", 0))
        
        from camera_manager import set_camera_focus
        set_camera_focus(camera_index, auto, value)
        
        return web.Response(text=json.dumps({"status": "ok"}), content_type="application/json")
    except Exception as e:
        return web.Response(status=500, text=json.dumps({"error": str(e)}), content_type="application/json")

async def set_exposure_handler(request):
    try:
        data = await request.json()
        camera_index = int(data.get("camera_index", 0))
        value = int(data.get("value", -5))
        
        from camera_manager import set_camera_exposure
        set_camera_exposure(camera_index, value)
        
        return web.Response(text=json.dumps({"status": "ok"}), content_type="application/json")
    except Exception as e:
        return web.Response(status=500, text=json.dumps({"error": str(e)}), content_type="application/json")

async def set_auto_exposure_handler(request):
    try:
        data = await request.json()
        camera_index = int(data.get("camera_index", 0))
        enabled = bool(data.get("enabled", False))
        target_brightness = int(data.get("target_brightness", 128))
        
        from camera_manager import set_camera_auto_exposure
        set_camera_auto_exposure(camera_index, enabled, target_brightness)
        
        return web.Response(text=json.dumps({"status": "ok"}), content_type="application/json")
    except Exception as e:
        return web.Response(status=500, text=json.dumps({"error": str(e)}), content_type="application/json")


async def capture_handler(request):
    """Capture and return 1080p JPEG image from specified camera."""
    import cv2
    
    try:
        camera_index = int(request.query.get("camera_index", 0))
        
        cam_thread = get_camera(camera_index)
        if not cam_thread:
            return web.Response(status=404, text=json.dumps({"error": "Camera not found"}), content_type="application/json")
        
        high_res, _ = cam_thread.get_frames()
        if high_res is None:
            return web.Response(status=503, text=json.dumps({"error": "Camera not ready"}), content_type="application/json")
        
        # Encode to JPEG (high quality)
        _, jpeg_bytes = cv2.imencode('.jpg', high_res, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        # Generate filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"camera_{camera_index}_{timestamp}.jpg"
        
        return web.Response(
            body=jpeg_bytes.tobytes(),
            content_type="image/jpeg",
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
    except Exception as e:
        print(f"Capture Error: {e}")
        return web.Response(status=500, text=json.dumps({"error": str(e)}), content_type="application/json")

async def analyze_handler(request):
    try:
        data = await request.json()
        instruction = data.get("instruction", "Describe this scene")
        camera_index = int(data.get("camera_index", 0))
        
        # Get frame from camera manager
        cam_thread = get_camera(camera_index)
        if not cam_thread:
            return web.Response(status=404, text=json.dumps({"error": "Camera not found"}), content_type="application/json")
            
        high_res, _ = cam_thread.get_frames()
        if high_res is None:
            return web.Response(status=503, text=json.dumps({"error": "Camera not ready"}), content_type="application/json")

        # Perform analysis
        print(f"Analyzing frame from Camera {camera_index} with instruction: {instruction}")
        result = brain.analyze_frame(high_res, instruction)
        
        return web.Response(text=json.dumps(result), content_type="application/json")
    except Exception as e:
        print(f"Analysis Error: {e}")
        return web.Response(status=500, text=json.dumps({"error": str(e)}), content_type="application/json")

async def on_shutdown(app):
    # Close all PCs
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
    active_tracks.clear()
    stop_all()

async def pause_camera_handler(request):
    try:
        data = await request.json()
        camera_index = int(data.get("camera_index", 0))
        paused = data.get("paused", True)
        client_id = data.get("client_id")
        
        if client_id and client_id in active_tracks:
            if camera_index in active_tracks[client_id]:
                active_tracks[client_id][camera_index].set_paused(paused)
                print(f"Client {client_id[:8]}... Camera {camera_index}: paused={paused}")
        
        return web.json_response({"success": True, "camera_index": camera_index, "paused": paused})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def scan_cameras_handler(request):
    """Scan for connected cameras and return their status with roles."""
    try:
        # Get all devices first (for unassigned ones)
        all_devices = get_available_devices()
        
        # Refresh camera connections
        camera_status = refresh_cameras()
        
        # Build response with both mapped and unmapped devices
        mapped_paths = {d["path"] for d in match_roles().values() if d["path"]}
        
        result = {
            "cameras": camera_status,
            "available_devices": [
                {"index": d["index"], "name": d["name"], "path": d["path"], "vid": d["vid"], "pid": d["pid"]}
                for d in all_devices
            ],
            "valid_roles": VALID_ROLES
        }
        return web.json_response(result)
    except Exception as e:
        print(f"Scan error: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def assign_role_handler(request):
    """Assign a role to a device path."""
    try:
        data = await request.json()
        device_path = data.get("device_path")
        role_name = data.get("role_name")
        
        if not device_path or not role_name:
            return web.json_response({"error": "device_path and role_name required"}, status=400)
        
        mapping_assign_role(device_path, role_name)
        
        return web.json_response({"success": True, "device_path": device_path, "role_name": role_name})
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def cameras_handler(request):
    """List all active cameras with their roles."""
    try:
        camera_status = refresh_cameras()
        return web.json_response({"cameras": camera_status})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def websocket_handler(request):
    """WebSocket endpoint for real-time camera change notifications."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws_clients.add(ws)
    print(f"WebSocket client connected. Total: {len(ws_clients)}")
    try:
        async for msg in ws:
            pass  # Keep-alive, no client-to-server messages needed
    finally:
        ws_clients.discard(ws)
        print(f"WebSocket client disconnected. Total: {len(ws_clients)}")
    return ws

async def broadcast_camera_change(event_type, cameras):
    """Broadcast camera change event to all connected WebSocket clients."""
    if not ws_clients:
        return
    msg = json.dumps({"type": event_type, "cameras": cameras})
    dead_clients = set()
    for ws in ws_clients:
        try:
            await ws.send_str(msg)
        except Exception:
            dead_clients.add(ws)
    ws_clients.difference_update(dead_clients)
    print(f"Broadcasted {event_type} to {len(ws_clients)} clients")

async def on_camera_change(added, removed, cameras):
    """Callback for polling - broadcasts camera changes to WebSocket clients."""
    await broadcast_camera_change("camera_change", cameras)

async def on_startup(app):
    """Start background polling when server starts."""
    asyncio.create_task(start_polling(on_camera_change, interval=3))
    print("Background camera polling started (3s interval)")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='InstantReality Server')
    parser.add_argument('--port', '-p', type=int, default=8080, help='Port number (default: 8080)')
    args = parser.parse_args()
    
    # 1. Discover and start cameras at server boot (Broadcast Mode)
    print("Discovering and initializing cameras...")
    discovered_indices = discover_cameras(max_indices=8)
    if discovered_indices:
        init_cameras(discovered_indices, width=1920, height=1080)
    else:
        print("Warning: No cameras found at startup!")
    
    # 2. Setup Web Application with CORS middleware
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", index)
    app.router.add_get("/client.mjs", javascript)
    app.router.add_post("/offer", offer)
    app.router.add_post("/set_focus", set_focus_handler)
    app.router.add_post("/set_exposure", set_exposure_handler)
    app.router.add_post("/set_auto_exposure", set_auto_exposure_handler)
    app.router.add_get("/capture", capture_handler)
    app.router.add_post("/analyze", analyze_handler)
    app.router.add_post("/pause_camera", pause_camera_handler)
    # Camera management routes
    app.router.add_post("/scan_cameras", scan_cameras_handler)
    app.router.add_post("/assign_role", assign_role_handler)
    app.router.add_get("/cameras", cameras_handler)
    app.router.add_get("/ws", websocket_handler)
    # SDK routes
    app.router.add_get("/sdk/instant-reality.mjs", serve_sdk_library)
    app.router.add_get("/sdk/instant-reality.d.ts", serve_sdk_types)
    app.router.add_get("/sdk/example.html", serve_sdk_example)
    app.on_shutdown.append(on_shutdown)
    app.on_startup.append(on_startup)
    
    print(f"Server started at http://localhost:{args.port}")
    web.run_app(app, port=args.port)
