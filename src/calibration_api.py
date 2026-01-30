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
    app.router.add_post('/api/calibration/verify-visual', handle_verify_visual)
    app.router.add_post('/api/calibration/grasp', handle_grasp_with_verification)
    app.router.add_get('/api/calibration/phase-status', handle_phase_status)
    
    logger.info("Calibration API routes registered")


async def handle_start(request):
    """Start Zero-Reference auto-calibration routine."""
    global _calibration_task, _calibrator
    
    if _calibration_task and not _calibration_task.done():
        return web.json_response({
            'success': False,
            'error': 'Calibration already in progress'
        }, status=400)
    
    if _calibrator is None:
        # Lazy import to avoid circular dependencies
        try:
            from robotics.auto_calibrator import ZeroReferenceCalibrator
            from robotics.coordinator import RobotCoordinator
            
            # Create coordinator and calibrator
            robot = RobotCoordinator()
            _calibrator = ZeroReferenceCalibrator(robot, _camera)
        except ImportError as e:
            return web.json_response({
                'success': False,
                'error': f'Failed to import calibrator: {e}'
            }, status=500)
    
    async def run_calibration():
        """Background calibration task."""
        try:
            result = await _calibrator.run_full_calibration()
            
            # Save calibration data
            _calibrator.save_calibration(result, str(CALIBRATION_FILE))
            
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


async def handle_verify_visual(request):
    """
    Verify action using Visual Success Detection.
    
    Compare before/after images to verify if expected change occurred.
    POST body: {"expected_change": "object picked up"}
    """
    global _camera
    
    if _camera is None:
        return web.json_response({
            'success': False,
            'error': 'Camera not available'
        }, status=503)
    
    try:
        data = await request.json()
    except Exception:
        data = {}
    
    expected_change = data.get('expected_change', 'robot moved to target')
    
    try:
        from robotics.gemini_robotics import GeminiRoboticsClient
        
        # Capture before image
        before_frame = _camera.capture()
        if before_frame is None:
            return web.json_response({
                'success': False,
                'error': 'Failed to capture before frame'
            }, status=500)
        
        before_image = GeminiRoboticsClient.encode_frame(before_frame)
        
        # Wait for user to perform action (or use provided after image)
        await asyncio.sleep(0.5)
        
        # Capture after image
        after_frame = _camera.capture()
        if after_frame is None:
            return web.json_response({
                'success': False,
                'error': 'Failed to capture after frame'
            }, status=500)
        
        after_image = GeminiRoboticsClient.encode_frame(after_frame)
        
        # Run Visual Verification
        client = GeminiRoboticsClient()
        result = await client.verify_action_success(
            before_image,
            after_image,
            expected_change
        )
        
        logger.info(f"Visual Verification: success={result.get('success')}, confidence={result.get('confidence')}")
        
        return web.json_response({
            'success': True,
            'verified': result.get('success', False),
            'confidence': result.get('confidence', 0.0),
            'reason': result.get('reason', ''),
            'detected_change': result.get('detected_change', '')
        })
        
    except Exception as e:
        logger.error(f"Visual verification error: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)


async def handle_grasp_with_verification(request):
    """
    Grasp object with visual verification and auto-retry.
    
    POST body: {
        "target_object": "red block",
        "z_level": "low",
        "max_attempts": 10
    }
    """
    global _camera, _calibrator
    
    if _camera is None:
        return web.json_response({
            'success': False,
            'error': 'Camera not available'
        }, status=503)
    
    try:
        data = await request.json()
    except Exception:
        data = {}
    
    target_object = data.get('target_object', 'target object')
    z_level = data.get('z_level', 'low')
    max_attempts = data.get('max_attempts', 10)
    
    try:
        from robotics.coordinator import RobotCoordinator
        from robotics.gemini_robotics import GeminiRoboticsClient
        
        # Create or reuse coordinator
        if _calibrator and hasattr(_calibrator, 'robot'):
            coordinator = _calibrator.robot
        else:
            coordinator = RobotCoordinator()
            coordinator.connect()
        
        # Camera capture function
        def capture_fn():
            frame = _camera.capture()
            return GeminiRoboticsClient.encode_frame(frame) if frame is not None else b''
        
        # Run grasp with verification
        result = await coordinator.grasp_with_verification(
            camera_fn=capture_fn,
            target_object=target_object,
            z_level=z_level,
            max_attempts=max_attempts
        )
        
        logger.info(f"Grasp with verification: success={result['success']}, attempts={result['attempts']}")
        
        return web.json_response({
            'success': result['success'],
            'attempts': result['attempts'],
            'verification_log': result['verification_log']
        })
        
    except Exception as e:
        logger.error(f"Grasp verification error: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)

