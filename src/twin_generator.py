# Twin Generator Module
# Converts scene scan results into VR-ready JSON and GLB files.
# Uses Homography-based coordinate transform for accurate positioning.
#
# Dependencies: trimesh, numpy (both in requirements.txt)

import json
import time
import io

try:
    import trimesh
    HAS_TRIMESH = True
except ImportError:
    HAS_TRIMESH = False


# =============================================================================
# Color Mapping
# =============================================================================

def get_color_rgba(color_name):
    """Maps string color names to RGBA 0-255 values."""
    cmap = {
        'red':    [255, 0, 0, 255],
        'white':  [240, 240, 240, 255],
        'blue':   [0, 0, 255, 255],
        'green':  [0, 255, 0, 255],
        'yellow': [255, 255, 0, 255],
        'orange': [255, 165, 0, 255],
        'pink':   [255, 192, 203, 255],
        'black':  [20, 20, 20, 255],
        'purple': [128, 0, 128, 255],
        'brown':  [139, 69, 19, 255],
    }
    return cmap.get(color_name.lower().strip(), [128, 128, 128, 255])


# =============================================================================
# VR JSON Builder
# =============================================================================

def _extract_color_from_label(label):
    """Extract color name from a label like 'red cup' or 'Blue_Dice'."""
    label_lower = label.lower().replace('_', ' ')
    known_colors = [
        'red', 'blue', 'green', 'yellow', 'orange',
        'pink', 'white', 'black', 'purple', 'brown'
    ]
    for color in known_colors:
        if color in label_lower:
            return color
    return 'gray'


def _box2d_center(box_2d):
    """Calculate center point from box_2d [ymin, xmin, ymax, xmax] (Gemini 0-1000)."""
    ymin, xmin, ymax, xmax = box_2d
    return {
        'gx': (xmin + xmax) / 2.0,
        'gy': (ymin + ymax) / 2.0,
    }


def build_twin_json(scan_result, calibration_data, dice_size_mm=20.0):
    """Convert scan_scene() result into VR-ready JSON using Homography.

    Args:
        scan_result: dict from brain.scan_scene() or scan_scene_with_roi()
                     Must contain 'objects' list with 'label' and 'box_2d'
        calibration_data: dict with 'homography_matrix' and 'resolution'
                          from calibration_manager.get_calibration_for_role('TopView')
        dice_size_mm: Size of dice cubes in mm (default 20mm)

    Returns:
        dict with 'timestamp', 'objects' list in VR format
    """
    from lib.coordinate_transform import gemini_to_robot

    H = calibration_data.get('homography_matrix')
    res = calibration_data.get('resolution', {})
    img_w = res.get('width', 1920)
    img_h = res.get('height', 1080)

    objects = scan_result.get('objects', [])
    vr_objects = []

    for i, obj in enumerate(objects):
        label = obj.get('label', f'object_{i}')
        box_2d = obj.get('box_2d')

        if not box_2d or len(box_2d) != 4:
            continue

        # Convert Gemini 0-1000 center to robot mm via Homography
        center = _box2d_center(box_2d)

        if H:
            robot = gemini_to_robot(center['gx'], center['gy'], H, img_w, img_h)
            x_mm = round(robot['x'], 1)
            y_mm = round(robot['y'], 1)
        else:
            # Fallback: simple normalization (no Homography)
            x_mm = round((center['gx'] / 1000.0) * 400.0, 1)
            y_mm = round((center['gy'] / 1000.0) * 300.0, 1)

        color = _extract_color_from_label(label)
        obj_id = f"{color.capitalize()}_{label.split()[-1]}_{i}" if ' ' in label else f"{label}_{i}"

        vr_obj = {
            'id': obj_id,
            'type': 'object',
            'properties': {
                'color': color,
                'label': label,
            },
            'transform': {
                'position': {
                    'x': x_mm,
                    'y': dice_size_mm / 2.0,  # Half height above ground
                    'z': y_mm,
                },
                'rotation': {
                    'x': 0,
                    'y': obj.get('rotation', 0),
                    'z': 0,
                },
                'scale': {
                    'x': 1,
                    'y': 1,
                    'z': 1,
                },
            },
        }
        vr_objects.append(vr_obj)

    return {
        'timestamp': time.time(),
        'dice_size_mm': dice_size_mm,
        'objects': vr_objects,
    }


# =============================================================================
# GLB Builder
# =============================================================================

def build_twin_glb(twin_json, default_size_mm=20.0):
    """Convert VR JSON into GLB binary using trimesh.

    GLB is exported in **meter** units (glTF standard).
    - Cube size: default_size_mm * 0.001 (e.g. 20mm → 0.02m)
    - Coordinates: mm values from JSON are converted via * 0.001
    - Floor correction: cubes are shifted up by half-height so bottom sits on Y=0

    Args:
        twin_json: dict from build_twin_json() with 'objects' list
        default_size_mm: Cube size in mm (default 20mm)

    Returns:
        bytes: GLB binary data

    Raises:
        ImportError: if trimesh is not installed
    """
    if not HAS_TRIMESH:
        raise ImportError("trimesh is required for GLB generation. Install with: pip install trimesh")

    import numpy as np

    MM_TO_M = 0.001
    scene = trimesh.Scene()
    box_size = twin_json.get('dice_size_mm', default_size_mm) * MM_TO_M  # e.g. 20mm → 0.02m

    for obj in twin_json.get('objects', []):
        obj_id = obj.get('id', 'unknown')
        props = obj.get('properties', {})
        trans = obj.get('transform', {})

        # Create box mesh (meter units)
        mesh = trimesh.creation.box(extents=[box_size, box_size, box_size])

        # Floor correction: shift cube up so bottom face sits at Y=0
        mesh.apply_translation([0, box_size / 2, 0])

        # Apply color
        color_name = props.get('color', 'gray')
        rgba = get_color_rgba(color_name)
        mesh.visual.face_colors = rgba

        # Build transform matrix
        pos = trans.get('position', {'x': 0, 'y': 0, 'z': 0})
        rot = trans.get('rotation', {'x': 0, 'y': 0, 'z': 0})
        scl = trans.get('scale', {'x': 1, 'y': 1, 'z': 1})

        # Rotation (degrees → radians → matrix)
        euler_rad = np.radians([rot['x'], rot['y'], rot['z']])
        matrix_rot = trimesh.transformations.euler_matrix(
            euler_rad[0], euler_rad[1], euler_rad[2], axes='sxyz'
        )

        # Scale matrix
        matrix_scale = np.eye(4)
        matrix_scale[0, 0] = scl['x']
        matrix_scale[1, 1] = scl['y']
        matrix_scale[2, 2] = scl['z']

        # Translation matrix (mm → m conversion)
        matrix_trans = trimesh.transformations.translation_matrix([
            pos['x'] * MM_TO_M,
            pos['y'] * MM_TO_M,
            pos['z'] * MM_TO_M,
        ])

        # Combine: T @ R @ S
        final_transform = trimesh.transformations.concatenate_matrices(
            matrix_trans, matrix_rot, matrix_scale
        )

        # Add to scene with node-level transform
        scene.add_geometry(mesh, node_name=obj_id, transform=final_transform)

    # Export to GLB bytes in memory
    buffer = io.BytesIO()
    scene.export(buffer, file_type='glb')
    return buffer.getvalue()
