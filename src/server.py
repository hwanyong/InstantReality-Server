import asyncio
import json
import os
import time

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from webrtc.video_track import OpenCVVideoCapture
from multi_cam_capture import discover_cameras
from camera_manager import stop_all

# Global list of active PeerConnections
pcs = set()

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

    # Note: We need to discover cameras. 
    # For a real system, we might want a global CameraManager so we don't open/close cams per user
    # But for this prototype, checking availability per connection or sharing a global track is key.
    # Opening the SAME camera multiple times on Windows often fails.
    # We should probably use a Shared Track approach or just support 1 client for now.
    # Let's try to just open them. If it fails, we know we need a Manager.
    # Actually, let's stick to the plan: multiple tracks.
    
    # Simple discovery for this connection
    # WARNING: Opening a camera that is already open (by another process or previous connection) might fail.
    # We will grab index 0 and 1 if available.
    
    # Ideally we should have a global set of tracks that are added to the PC.
    # For now, let's instantiate tracks here.
    camera_indices = [0, 1] # Hardcoded for test or use discover_cameras()
    
    for idx in camera_indices:
        try:
            # We assume these cameras exist for the test
            track = OpenCVVideoCapture(camera_index=idx, options={"width": 1920, "height": 1080})
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
    content = open(os.path.join("src/static", "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)

async def on_shutdown(app):
    # Close all PCs
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
    stop_all()

if __name__ == "__main__":
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/offer", offer)
    app.on_shutdown.append(on_shutdown)
    
    print("Server started at http://localhost:8080")
    web.run_app(app, port=8080)
