"""
Calibration API Router

REST API endpoints for robot calibration:
- POST /api/calibration/start - Start auto-calibration
- POST /api/calibration/stop - Stop calibration
- GET /api/calibration/data - Get calibration data
- POST /api/calibration/save - Save calibration data
- POST /api/calibration/detect-base - Detect robot base
- POST /api/calibration/detect-gripper - Detect gripper position
- POST /api/calibration/verify - Verify calibration accuracy
"""

import json
import asyncio
import logging
from pathlib import Path
from aiohttp import web

logger = logging.getLogger(__name__)

# Default paths
CALIBRATION_FILE = Path("calibration.json")

# Global calibration state
_calibration_task = None
_calibrator = None
_camera = None


def setup_calibration_routes(app, camera_manager=None, calibrator=None):
    """Add calibration routes to the app."""
    global _camera, _calibrator
    _camera = camera_manager
    _calibrator = calibrator
    
    app.router.add_post('/api/calibration/start', handle_start)
    app.router.add_post('/api/calibration/stop', handle_stop)
    app.router.add_get('/api/calibration/data', handle_get_data)
    app.router.add_post('/api/calibration/save', handle_save)
    app.router.add_post('/api/calibration/detect-base', handle_detect_base)
    app.router.add_post('/api/calibration/detect-gripper', handle_detect_gripper)
    app.router.add_post('/api/calibration/verify', handle_verify)
    
    logger.info("Calibration API routes registered")


async def handle_start(request):
    """Start auto-calibration routine."""
    global _calibration_task, _calibrator
    
    if _calibration_task and not _calibration_task.done():
        return web.json_response({
            'success': False,
            'error': 'Calibration already in progress'
        }, status=400)
    
    try:
        data = await request.json()
    except Exception:
        data = {}
    
    grid_size = data.get('grid_size', 9)
    z_height = data.get('z_height', 120.0)
    
    if _calibrator is None:
        # Lazy import to avoid circular dependencies
        try:
            from robotics.auto_calibrator import AutoCalibrator
            from robotics.coordinator import RobotCoordinator
            
            # Create coordinator and calibrator
            robot = RobotCoordinator()
            _calibrator = AutoCalibrator(robot, _camera)
        except ImportError as e:
            return web.json_response({
                'success': False,
                'error': f'Failed to import calibrator: {e}'
            }, status=500)
    
    async def run_calibration():
        """Background calibration task."""
        try:
            result = await _calibrator.run_full_calibration(
                grid_size=grid_size,
                z_height=z_height,
                save_path=str(CALIBRATION_FILE)
            )
            
            # Broadcast completion via WebSocket
            if hasattr(request.app, 'ws_broadcast'):
                await request.app.ws_broadcast({
                    'type': 'calibration_complete',
                    'data': result.to_dict()
                })
                
        except Exception as e:
            logger.error(f"Calibration error: {e}")
            if hasattr(request.app, 'ws_broadcast'):
                await request.app.ws_broadcast({
                    'type': 'calibration_error',
                    'data': {'message': str(e)}
                })
    
    # Setup progress callback
    def progress_callback(step, total, message):
        asyncio.create_task(
            request.app.ws_broadcast({
                'type': 'calibration_progress',
                'data': {'step': step, 'total': total, 'message': message}
            }) if hasattr(request.app, 'ws_broadcast') else asyncio.sleep(0)
        )
    
    if _calibrator:
        _calibrator.set_progress_callback(progress_callback)
    
    # Start calibration in background
    _calibration_task = asyncio.create_task(run_calibration())
    
    return web.json_response({
        'success': True,
        'message': 'Calibration started',
        'grid_size': grid_size,
        'z_height': z_height
    })


async def handle_stop(request):
    """Stop running calibration."""
    global _calibration_task
    
    if _calibration_task and not _calibration_task.done():
        _calibration_task.cancel()
        try:
            await _calibration_task
        except asyncio.CancelledError:
            pass
        _calibration_task = None
    
    return web.json_response({'success': True, 'message': 'Calibration stopped'})


async def handle_get_data(request):
    """Get current calibration data."""
    if not CALIBRATION_FILE.exists():
        return web.json_response({
            'success': False,
            'error': 'No calibration file found'
        }, status=404)
    
    try:
        with open(CALIBRATION_FILE) as f:
            data = json.load(f)
        return web.json_response(data)
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)


async def handle_save(request):
    """Save calibration data."""
    try:
        data = await request.json()
        
        with open(CALIBRATION_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        return web.json_response({'success': True, 'message': 'Calibration saved'})
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)


async def handle_detect_base(request):
    """Detect robot base position using Gemini vision."""
    global _camera
    
    if _camera is None:
        return web.json_response({
            'success': False,
            'error': 'Camera not available'
        }, status=503)
    
    try:
        from robotics.gemini_robotics import GeminiRoboticsClient
        
        frame = _camera.capture()
        if frame is None:
            return web.json_response({
                'success': False,
                'error': 'Failed to capture frame'
            }, status=500)
        
        image_bytes = GeminiRoboticsClient.encode_frame(frame)
        client = GeminiRoboticsClient()
        
        result = await client.get_robot_base_position(image_bytes)
        
        return web.json_response({
            'success': True,
            'point': result.get('point', [0, 0]),
            'label': result.get('label', 'Robot Base')
        })
        
    except Exception as e:
        logger.error(f"Base detection error: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)


async def handle_detect_gripper(request):
    """Detect gripper position using Gemini vision."""
    global _camera
    
    if _camera is None:
        return web.json_response({
            'success': False,
            'error': 'Camera not available'
        }, status=503)
    
    try:
        from robotics.gemini_robotics import GeminiRoboticsClient
        
        frame = _camera.capture()
        if frame is None:
            return web.json_response({
                'success': False,
                'error': 'Failed to capture frame'
            }, status=500)
        
        image_bytes = GeminiRoboticsClient.encode_frame(frame)
        client = GeminiRoboticsClient()
        
        result = await client.get_gripper_position(image_bytes)
        
        return web.json_response({
            'success': True,
            'point': result.get('point', [0, 0]),
            'label': result.get('label', 'Gripper')
        })
        
    except Exception as e:
        logger.error(f"Gripper detection error: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)


async def handle_verify(request):
    """Verify calibration accuracy."""
    global _calibrator
    
    if _calibrator is None:
        return web.json_response({
            'success': False,
            'error': 'Calibrator not initialized'
        }, status=503)
    
    try:
        result = await _calibrator.verify_calibration(num_points=3)
        
        return web.json_response({
            'success': True,
            'mean_error_mm': result.get('mean_error_mm'),
            'max_error_mm': result.get('max_error_mm'),
            'verified_points': result.get('verified_points')
        })
        
    except Exception as e:
        logger.error(f"Verification error: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)
