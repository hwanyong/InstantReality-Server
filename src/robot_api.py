"""
Robot Control API Router

REST API endpoints for robot position control:
- POST /api/robot/connect - Connect to robot
- POST /api/robot/disconnect - Disconnect from robot
- GET /api/robot/status - Get connection status
- POST /api/robot/home - Move to home position (initial_pulse)
- POST /api/robot/zero - Move to zero position (zero_pulse)
- POST /api/robot/speed - Set motion speed
"""

import json
import asyncio
import logging
import time
from pathlib import Path
from aiohttp import web

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

logger = logging.getLogger(__name__)

# Default paths
CONFIG_FILE = Path("servo_config.json")

# Global state
_serial_conn = None
_config = None
_motion_duration = 3.0  # Default 3 seconds


def load_config():
    """Load servo configuration from JSON."""
    global _config
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            _config = json.load(f)
        logger.info(f"Loaded servo config from {CONFIG_FILE}")
    else:
        logger.warning(f"Config file not found: {CONFIG_FILE}")
        _config = {}
    return _config


def get_port():
    """Get configured serial port."""
    if _config and "connection" in _config:
        return _config["connection"].get("port", "COM7")
    return "COM7"


def get_all_pulses(pulse_type):
    """
    Get pulse values for all 12 channels.
    
    Args:
        pulse_type: "initial_pulse" for home, "zero_pulse" for zero
        
    Returns:
        List of 12 pulse values [ch0...ch11]
    """
    if not _config:
        load_config()
    
    pulses = [1500] * 12  # Default center position
    
    for arm_key in ["right_arm", "left_arm"]:
        arm_config = _config.get(arm_key, {})
        for slot_key, slot_data in arm_config.items():
            if slot_key.startswith("slot_"):
                channel = slot_data.get("channel", 0)
                pulse = slot_data.get(pulse_type, 1500)
                if 0 <= channel < 12:
                    pulses[channel] = pulse
    
    return pulses


def setup_robot_routes(app):
    """Add robot control routes to the app."""
    load_config()
    
    app.router.add_post('/api/robot/connect', handle_connect)
    app.router.add_post('/api/robot/disconnect', handle_disconnect)
    app.router.add_get('/api/robot/status', handle_status)
    app.router.add_post('/api/robot/home', handle_go_home)
    app.router.add_post('/api/robot/zero', handle_go_zero)
    app.router.add_post('/api/robot/speed', handle_set_speed)
    
    logger.info("Robot API routes registered")


async def handle_connect(request):
    """Connect to robot via serial port."""
    global _serial_conn
    
    if serial is None:
        return web.json_response({
            'success': False,
            'error': 'pyserial not installed'
        }, status=500)
    
    if _serial_conn and _serial_conn.is_open:
        return web.json_response({
            'success': True,
            'message': 'Already connected',
            'port': _serial_conn.port
        })
    
    port = get_port()
    
    try:
        _serial_conn = serial.Serial(port, 115200, timeout=1)
        await asyncio.sleep(2)  # Wait for Arduino reset
        
        logger.info(f"Connected to robot on {port}")
        return web.json_response({
            'success': True,
            'message': f'Connected to {port}',
            'port': port
        })
        
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)


async def handle_disconnect(request):
    """Disconnect from robot."""
    global _serial_conn
    
    if _serial_conn and _serial_conn.is_open:
        _serial_conn.close()
        _serial_conn = None
        logger.info("Disconnected from robot")
    
    return web.json_response({
        'success': True,
        'message': 'Disconnected'
    })


async def handle_status(request):
    """Get current robot connection status."""
    connected = _serial_conn is not None and _serial_conn.is_open
    port = _serial_conn.port if connected else None
    
    # List available ports
    available_ports = []
    if serial:
        available_ports = [p.device for p in serial.tools.list_ports.comports()]
    
    return web.json_response({
        'connected': connected,
        'port': port,
        'available_ports': available_ports,
        'motion_duration': _motion_duration
    })


async def handle_go_home(request):
    """Move all servos to home position (initial_pulse)."""
    global _serial_conn
    
    if not _serial_conn or not _serial_conn.is_open:
        return web.json_response({
            'success': False,
            'error': 'Robot not connected'
        }, status=503)
    
    pulses = get_all_pulses("initial_pulse")
    
    # Send W command for each channel
    # Protocol: W <ch> <us>\n
    try:
        for channel, pulse in enumerate(pulses):
            cmd = f"W {channel} {pulse}\n"
            _serial_conn.write(cmd.encode())
            time.sleep(0.01)  # Wait for ACK
        
        logger.info(f"Go Home: sent {len(pulses)} channels")
        
        # Wait for motion to complete
        await asyncio.sleep(_motion_duration)
        
        return web.json_response({
            'success': True,
            'message': 'Moved to home position',
            'pulses': pulses
        })
        
    except Exception as e:
        logger.error(f"Go Home failed: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)


async def handle_go_zero(request):
    """Move all servos to zero position (zero_pulse)."""
    global _serial_conn
    
    if not _serial_conn or not _serial_conn.is_open:
        return web.json_response({
            'success': False,
            'error': 'Robot not connected'
        }, status=503)
    
    pulses = get_all_pulses("zero_pulse")
    
    # Send W command for each channel
    try:
        for channel, pulse in enumerate(pulses):
            cmd = f"W {channel} {pulse}\n"
            _serial_conn.write(cmd.encode())
            time.sleep(0.01)  # Wait for ACK
        
        logger.info(f"Go Zero: sent {len(pulses)} channels")
        
        # Wait for motion to complete
        await asyncio.sleep(_motion_duration)
        
        return web.json_response({
            'success': True,
            'message': 'Moved to zero position',
            'pulses': pulses
        })
        
    except Exception as e:
        logger.error(f"Go Zero failed: {e}")
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)


async def handle_set_speed(request):
    """Set motion speed (duration in seconds)."""
    global _motion_duration
    
    try:
        data = await request.json()
        duration = float(data.get('duration', 2.0))
        
        # Clamp to reasonable range
        _motion_duration = max(0.5, min(5.0, duration))
        
        return web.json_response({
            'success': True,
            'duration': _motion_duration
        })
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=400)
