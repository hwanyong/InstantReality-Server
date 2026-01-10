import asyncio
import json
import os
import time

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from webrtc.video_track import OpenCVVideoCapture
from multi_cam_capture import discover_cameras
from camera_manager import stop_all, init_cameras, get_active_cameras, get_camera
from ai_engine import GeminiBrain

# Global list of active PeerConnections
pcs = set()
brain = GeminiBrain()

async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    print(f"New connection: {pc}")

    # Prepare logic to run when connection closes
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)

    # Broadcast Mode: Use already-running cameras from startup
    # No re-discovery needed, cameras are initialized at server start
    camera_indices = get_active_cameras()
    if not camera_indices:
        print("Warning: No cameras running!")
    
    for idx in camera_indices:
        try:
            # We assume these cameras exist for the test
            track = OpenCVVideoCapture(camera_index=idx, options={"width": 1280, "height": 720})
            pc.addTrack(track)
            print(f"Added track for Camera {idx}")
        except Exception as e:
            print(f"Failed to add track for Camera {idx}: {e}")

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )

async def index(request):
    content = open(os.path.join("src/static", "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)

async def javascript(request):
    content = open(os.path.join("src/static", "client.mjs"), "r").read()
    return web.Response(content_type="application/javascript", text=content)

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
    stop_all()

if __name__ == "__main__":
    # 1. Discover and start cameras at server boot (Broadcast Mode)
    print("Discovering and initializing cameras...")
    discovered_indices = discover_cameras(max_indices=4)
    if discovered_indices:
        init_cameras(discovered_indices, width=1280, height=720)
    else:
        print("Warning: No cameras found at startup!")
    
    # 2. Setup Web Application
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/client.mjs", javascript)
    app.router.add_post("/offer", offer)
    app.router.add_post("/set_focus", set_focus_handler)
    app.router.add_post("/analyze", analyze_handler)
    app.on_shutdown.append(on_shutdown)
    
    print("Server started at http://localhost:8080")
    web.run_app(app, port=8080)
