# Connection & File Logger
# Logs client connection events to logs/connection.log
# Also exports create_file_logger() for other log files (access.log, server.log)
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


def _make_timestamped_namer(base_name):
    """Create a namer function for rotated logs: base.log.1 → base-20260201210352.log"""
    stem = base_name.rsplit(".", 1)[0] if "." in base_name else base_name
    def namer(default_name):
        base_dir = os.path.dirname(default_name)
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return os.path.join(base_dir, f"{stem}-{stamp}.log")
    return namer


def _noop_rotator(source, dest):
    """Simple rename rotator for custom namer."""
    if os.path.exists(source):
        os.rename(source, dest)


def create_file_logger(name, filename, max_bytes=MAX_BYTES, backup_count=BACKUP_COUNT):
    """Create a named logger that writes to logs/{filename} with rotation.

    Reusable factory for any log file with the same rotation pattern.
    Returns the configured logger. Idempotent — safe to call multiple times.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    file_logger = logging.getLogger(name)
    if file_logger.handlers:
        return file_logger

    file_logger.setLevel(logging.INFO)
    file_logger.propagate = False

    handler = RotatingFileHandler(
        str(LOG_DIR / filename),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.namer = _make_timestamped_namer(filename)
    handler.rotator = _noop_rotator

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    file_logger.addHandler(handler)

    return file_logger


_logger = create_file_logger("connection", "connection.log")


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
