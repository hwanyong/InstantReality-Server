"""
Configuration loader with mtime-based Hot-Reload.
src/lib/config_loader.py

Loads prompts (.md), tools (.yaml), and execution config (.yaml)
from src/config/ directory. Caches by file mtime — automatically
reloads when files are modified, no server restart needed.
"""

import os
import yaml
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Cache storage
# ─────────────────────────────────────────────────────────────────────────────

_cache = {}  # key → { "mtime": float, "data": any }

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")


def _get_path(*parts):
    return os.path.join(_CONFIG_DIR, *parts)


def _load_with_cache(filepath):
    """Read file if mtime changed, return cached content otherwise."""
    if not os.path.exists(filepath):
        logger.error(f"[ConfigLoader] File not found: {filepath}")
        return None

    mtime = os.path.getmtime(filepath)
    cached = _cache.get(filepath)

    if cached and cached["mtime"] == mtime:
        return cached["data"]

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    basename = os.path.basename(filepath)
    if cached:
        logger.info(f"[ConfigLoader] Reloaded: {basename}")
    else:
        logger.info(f"[ConfigLoader] Loaded: {basename}")

    _cache[filepath] = {"mtime": mtime, "data": content}
    return content


def _load_yaml_with_cache(filepath):
    """Read and parse YAML file if mtime changed."""
    if not os.path.exists(filepath):
        logger.error(f"[ConfigLoader] File not found: {filepath}")
        return None

    mtime = os.path.getmtime(filepath)
    cached = _cache.get(filepath)

    if cached and cached["mtime"] == mtime:
        return cached["data"]

    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    basename = os.path.basename(filepath)
    if cached:
        logger.info(f"[ConfigLoader] Reloaded: {basename}")
    else:
        logger.info(f"[ConfigLoader] Loaded: {basename}")

    _cache[filepath] = {"mtime": mtime, "data": data}
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def load_prompt(name):
    """
    Load a prompt template from src/config/prompts/{name}.md

    Returns raw text with {placeholders} for str.format().
    Caller is responsible for calling .format(instruction=...) etc.
    """
    filepath = _get_path("prompts", f"{name}.md")
    return _load_with_cache(filepath)


def load_tools():
    """
    Load robot tool definitions from src/config/tools/robot_tools.yaml

    Returns list of google.genai.types.FunctionDeclaration objects,
    ready to pass to types.Tool(function_declarations=...).
    """
    from google.genai import types

    filepath = _get_path("tools", "robot_tools.yaml")
    data = _load_yaml_with_cache(filepath)
    if not data or "tools" not in data:
        logger.error("[ConfigLoader] No tools defined in robot_tools.yaml")
        return []

    declarations = []
    for tool_def in data["tools"]:
        properties = {}
        required = []

        for param_name, param_info in (tool_def.get("parameters") or {}).items():
            type_str = param_info.get("type", "STRING").upper()
            type_map = {
                "NUMBER": "NUMBER",
                "STRING": "STRING",
                "BOOLEAN": "BOOLEAN",
                "INTEGER": "INTEGER",
            }
            schema_type = type_map.get(type_str, "STRING")
            properties[param_name] = types.Schema(
                type=schema_type,
                description=param_info.get("description", "")
            )
            if param_info.get("required"):
                required.append(param_name)

        declarations.append(
            types.FunctionDeclaration(
                name=tool_def["name"],
                description=tool_def.get("description", ""),
                parameters=types.Schema(
                    type="OBJECT",
                    properties=properties,
                    required=required if required else None
                )
            )
        )

    tool_count = len(declarations)
    logger.info(f"[ConfigLoader] Loaded tools: {tool_count} declarations")
    return declarations


def load_execution_config():
    """
    Load execution configuration from src/config/execution_config.yaml

    Returns dict with keys: safety, motion, verification, execution.
    """
    filepath = _get_path("execution_config.yaml")
    data = _load_yaml_with_cache(filepath)
    if not data:
        logger.error("[ConfigLoader] Failed to load execution_config.yaml, using defaults")
        return _default_execution_config()
    return data


def _default_execution_config():
    """Fallback defaults if config file is missing."""
    return {
        "safety": {
            "safe_height_mm": 100,
            "min_z_mm": 5,
            "max_motion_time_sec": 10,
        },
        "motion": {
            "default_motion_time_sec": 2.0,
            "approach_motion_time_sec": 1.0,
        },
        "verification": {
            "position": {
                "tolerance_mm": 3,
                "damping_factor": 0.5,
                "max_retries": 3,
            },
            "gripper": {
                "max_retries": 3,
                "re_analyze_on_fail": True,
            },
        },
        "execution": {
            "step_delay_ms": 500,
            "auto_connect": True,
            "auto_disconnect": True,
            "home_before_plan": True,
        },
    }
