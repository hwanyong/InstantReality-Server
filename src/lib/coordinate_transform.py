# Coordinate Transform Module
# Converts between Gemini normalized (0-1000), pixel, and robot mm coordinates
# using Homography transformation. Python port of transform.mjs math.
#
# All functions are pure — no I/O, no side effects.

def apply_homography(H, point):
    """Apply 3x3 Homography to a 2D point (forward: src -> dst).
    
    Args:
        H: 3x3 matrix (list of 3 lists of 3 floats)
        point: dict with 'x', 'y' keys
    Returns:
        dict with 'x', 'y' keys
    """
    x, y = point["x"], point["y"]

    w = H[2][0] * x + H[2][1] * y + H[2][2]
    u = (H[0][0] * x + H[0][1] * y + H[0][2]) / w
    v = (H[1][0] * x + H[1][1] * y + H[1][2]) / w

    return {"x": u, "y": v}


def invert_matrix_3x3(H):
    """Invert a 3x3 matrix using Cramer's rule.
    
    Args:
        H: 3x3 matrix
    Returns:
        Inverted 3x3 matrix
    Raises:
        ValueError: if matrix is singular
    """
    a, b, c = H[0][0], H[0][1], H[0][2]
    d, e, f = H[1][0], H[1][1], H[1][2]
    g, h, i = H[2][0], H[2][1], H[2][2]

    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)

    if abs(det) < 1e-10:
        raise ValueError("Matrix is singular and cannot be inverted")

    inv_det = 1.0 / det

    return [
        [(e * i - f * h) * inv_det, (c * h - b * i) * inv_det, (b * f - c * e) * inv_det],
        [(f * g - d * i) * inv_det, (a * i - c * g) * inv_det, (c * d - a * f) * inv_det],
        [(d * h - e * g) * inv_det, (b * g - a * h) * inv_det, (a * e - b * d) * inv_det],
    ]


def pixel_to_robot(H, pixel_point):
    """Convert pixel coordinates to robot mm via inverse Homography.
    
    Applies Y-axis inversion (screen Y-down -> robot Y-up).
    Matches calibration.mjs addTestPointAtPixel behavior.
    
    Args:
        H: 3x3 Homography matrix (Robot -> Pixel direction)
        pixel_point: dict with 'x', 'y' (pixel coordinates)
    Returns:
        dict with 'x', 'y' (robot mm, Y already inverted)
    """
    H_inv = invert_matrix_3x3(H)
    raw = apply_homography(H_inv, pixel_point)

    # Y inversion: screen Y-down -> robot Y-up (same as calibration.mjs L722-723)
    return {"x": raw["x"], "y": -raw["y"]}


def gemini_to_pixel(gx, gy, width, height):
    """Convert Gemini normalized coords (0-1000) to pixel coords.
    
    Gemini uses a 1000x1000 grid regardless of image dimensions.
    Format: top-left = (0, 0), bottom-right = (1000, 1000).
    
    Args:
        gx: Gemini X (0-1000)
        gy: Gemini Y (0-1000)
        width: image width in pixels (e.g. 1920)
        height: image height in pixels (e.g. 1080)
    Returns:
        dict with 'x', 'y' (pixel coordinates)
    """
    return {
        "x": (gx / 1000.0) * width,
        "y": (gy / 1000.0) * height,
    }


def gemini_to_robot(gx, gy, H, width, height):
    """Full pipeline: Gemini coords -> pixel -> robot mm.
    
    Args:
        gx: Gemini X (0-1000)
        gy: Gemini Y (0-1000)
        H: 3x3 Homography matrix from calibration_data.json
        width: image width in pixels
        height: image height in pixels
    Returns:
        dict with 'x', 'y' (robot mm)
    """
    pixel = gemini_to_pixel(gx, gy, width, height)
    return pixel_to_robot(H, pixel)
