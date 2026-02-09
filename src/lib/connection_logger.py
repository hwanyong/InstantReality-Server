# Connection Logger
# Logs client connection events to logs/connection.log
# Rotation: 5MB max, backups named {name}-{yyyyMMddHHmmss}.log

import os
import logging
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Project root = 2 levels up from src/lib/
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "connection.log"

MAX_BYTES = 5 * 1024 * 1024  # 5MB
BACKUP_COUNT = 10


def _timestamped_namer(default_name):
    """Rename rotated log: connection.log.1 → connection-20260201210352.log"""
    base_dir = os.path.dirname(default_name)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return os.path.join(base_dir, f"connection-{stamp}.log")


def _noop_rotator(source, dest):
    """Simple rename rotator for custom namer."""
    if os.path.exists(source):
        os.rename(source, dest)


def _create_logger():
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("connection")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = RotatingFileHandler(
        str(LOG_FILE),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.namer = _timestamped_namer
    handler.rotator = _noop_rotator

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


_logger = _create_logger()


def _extract_client_info(request):
    ip = request.headers.get("X-Forwarded-For", request.remote or "unknown")
    ua = request.headers.get("User-Agent", "unknown")
    return ip, ua


def log_webrtc_connect(request, pc_id, roles):
    ip, ua = _extract_client_info(request)
    _logger.info(f"WEBRTC_CONNECT {ip} | {ua} | pc_id={pc_id} roles={roles}")


def log_webrtc_disconnect(pc_id):
    _logger.info(f"WEBRTC_DISCONNECT pc_id={pc_id}")


def log_ws_connect(request):
    ip, ua = _extract_client_info(request)
    _logger.info(f"WS_CONNECT {ip} | {ua}")


def log_ws_disconnect(request):
    ip = request.headers.get("X-Forwarded-For", request.remote or "unknown")
    _logger.info(f"WS_DISCONNECT {ip}")


def log_stream_start(request, camera_index):
    ip, ua = _extract_client_info(request)
    _logger.info(f"STREAM_START {ip} | {ua} | camera={camera_index}")


def log_stream_end(request, camera_index):
    ip = request.headers.get("X-Forwarded-For", request.remote or "unknown")
    _logger.info(f"STREAM_END {ip} | camera={camera_index}")
