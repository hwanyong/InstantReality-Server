// ─────────────────────────────────────────────────────────────────────────────
// Homography Transform Module
// src/static/robotics/transform.mjs
// ─────────────────────────────────────────────────────────────────────────────
// Provides 4-point Homography calculation and coordinate transformation utilities
// for mapping between pixel coordinates (camera) and robot coordinates (mm).
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Compute 3x3 Homography matrix from 4 corresponding point pairs.
 * Uses Direct Linear Transform (DLT) algorithm.
 * 
 * @param {Array<[number, number]>} srcPoints - 4 source points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
 * @param {Array<[number, number]>} dstPoints - 4 destination points
 * @returns {Array<Array<number>>} 3x3 Homography matrix H
 */
export function computeHomography(srcPoints, dstPoints) {
    if (srcPoints.length != 4 || dstPoints.length != 4) {
        throw new Error('Homography requires exactly 4 point pairs')
    }

    // Build matrix A for DLT (8x9)
    const A = []
    for (let i = 0; i < 4; i++) {
        const [x, y] = srcPoints[i]
        const [u, v] = dstPoints[i]

        A.push([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        A.push([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    }

    // Solve using SVD approximation (simplified for 8 equations, 9 unknowns)
    // We use the constraint h33 = 1 to reduce to 8 unknowns
    const h = solveDLT(A)

    // Reshape to 3x3 matrix
    return [
        [h[0], h[1], h[2]],
        [h[3], h[4], h[5]],
        [h[6], h[7], h[8]]
    ]
}

/**
 * Solve DLT system Ah = 0 with constraint h[8] = 1
 * @param {Array<Array<number>>} A - 8x9 matrix
 * @returns {Array<number>} 9-element homography vector
 */
function solveDLT(A) {
    // Rearrange: we set h[8] = 1, so we solve for h[0..7]
    // Ah = 0 becomes A'h' = -b where A' is 8x8 and b is last column
    const A8 = []
    const b = []

    for (let i = 0; i < 8; i++) {
        const row = []
        for (let j = 0; j < 8; j++) {
            row.push(A[i][j])
        }
        A8.push(row)
        b.push(-A[i][8])
    }

    // Solve 8x8 linear system using Gaussian elimination
    const h8 = gaussianElimination(A8, b)

    // Append h[8] = 1
    return [...h8, 1]
}

/**
 * Gaussian elimination with partial pivoting to solve Ax = b
 * @param {Array<Array<number>>} A - n x n matrix
 * @param {Array<number>} b - n-element vector
 * @returns {Array<number>} solution vector x
 */
function gaussianElimination(A, b) {
    const n = b.length

    // Augment matrix
    const aug = A.map((row, i) => [...row, b[i]])

    // Forward elimination with partial pivoting
    for (let col = 0; col < n; col++) {
        // Find pivot
        let maxRow = col
        for (let row = col + 1; row < n; row++) {
            if (Math.abs(aug[row][col]) > Math.abs(aug[maxRow][col])) {
                maxRow = row
            }
        }

        // Swap rows
        [aug[col], aug[maxRow]] = [aug[maxRow], aug[col]]

        // Check for singular matrix
        if (Math.abs(aug[col][col]) < 1e-10) {
            throw new Error('Matrix is singular or near-singular')
        }

        // Eliminate below
        for (let row = col + 1; row < n; row++) {
            const factor = aug[row][col] / aug[col][col]
            for (let j = col; j <= n; j++) {
                aug[row][j] -= factor * aug[col][j]
            }
        }
    }

    // Back substitution
    const x = new Array(n).fill(0)
    for (let i = n - 1; i >= 0; i--) {
        x[i] = aug[i][n]
        for (let j = i + 1; j < n; j++) {
            x[i] -= aug[i][j] * x[j]
        }
        x[i] /= aug[i][i]
    }

    return x
}

/**
 * Apply Homography transformation to a point (forward: src -> dst)
 * @param {Array<Array<number>>} H - 3x3 Homography matrix
 * @param {{x: number, y: number}} point - Source point
 * @returns {{x: number, y: number}} Transformed point
 */
export function applyHomography(H, point) {
    const x = point.x
    const y = point.y

    const w = H[2][0] * x + H[2][1] * y + H[2][2]
    const u = (H[0][0] * x + H[0][1] * y + H[0][2]) / w
    const v = (H[1][0] * x + H[1][1] * y + H[1][2]) / w

    return { x: u, y: v }
}

// ─────────────────────────────────────────────────────────────────────────────
// Share Point Centered Proportional Mapping
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Compute mapping parameters using Share Point (0,0) as the center.
 * 
 * Strategy:
 * 1. Share Point in pixel coords = centroid of 4 pixel vertices
 * 2. Scale factor = average (pixel distance / robot distance) for all vertices
 * 3. For any robot point, calculate pixel position as:
 *    pixelPos = sharePointPixel + (robotOffset * scaleFactor)
 * 
 * Note: Robot coord system is +X=right, +Y=up
 *       Pixel coord system is +X=right, +Y=down
 *       So we need axis transformations.
 * 
 * @param {Array<Array<number>>} pixelPoints - [p1, p2, p3, p4] (Screen coordinates)
 * @param {Array<Array<number>>} robotPoints - [r1, r2, r3, r4] (Robot coordinates, origin at share point)
 * @returns {Object} Mapping object containing sharePointPixel and scale factors
 */
export function computeBilinearMap(pixelPoints, robotPoints) {
    // 1. Share Point pixel position = Centroid of 4 vertices
    const sharePointPixel = {
        x: (pixelPoints[0][0] + pixelPoints[1][0] + pixelPoints[2][0] + pixelPoints[3][0]) / 4,
        y: (pixelPoints[0][1] + pixelPoints[1][1] + pixelPoints[2][1] + pixelPoints[3][1]) / 4
    }

    // 2. Calculate scale factors (pixel per mm) for X and Y separately
    // Robot: +X=right (screen +X), +Y=up (screen -Y)
    let sumScaleX = 0
    let sumScaleY = 0
    let countX = 0
    let countY = 0

    for (let i = 0; i < 4; i++) {
        const robotX = robotPoints[i][0]  // Robot X (+up)
        const robotY = robotPoints[i][1]  // Robot Y (+left)

        // Pixel offset from share point (centroid)
        const pixelDx = pixelPoints[i][0] - sharePointPixel.x  // Pixel X (+right)
        const pixelDy = pixelPoints[i][1] - sharePointPixel.y  // Pixel Y (+down)

        // Robot X (+right) corresponds to Pixel X (+right), so robot X -> pixelDx
        // Robot Y (+up) corresponds to Pixel Y (-down), so robot Y -> -pixelDy
        if (Math.abs(robotX) > 10) {  // Avoid division by near-zero
            sumScaleX += pixelDx / robotX
            countX++
        }
        if (Math.abs(robotY) > 10) {
            sumScaleY += (-pixelDy) / robotY
            countY++
        }
    }

    const scaleX = countX > 0 ? sumScaleX / countX : 1  // pixel per mm for robot X
    const scaleY = countY > 0 ? sumScaleY / countY : 1  // pixel per mm for robot Y

    console.log('Calibration map computed:', {
        sharePointPixel,
        scaleX: scaleX.toFixed(4),
        scaleY: scaleY.toFixed(4)
    })

    return {
        sharePointPixel,
        scaleX,  // Robot X (up) to Pixel Y (down) conversion
        scaleY   // Robot Y (left) to Pixel X (right) conversion
    }
}

/**
 * Apply mapping to convert Robot coords -> Pixel coords
 * 
 * Coordinate transformation:
 * - Robot +X (right) -> Pixel +X (right in screen)
 * - Robot +Y (up) -> Pixel -Y (up in screen)
 * 
 * @param {Object} map - Result from computeBilinearMap
 * @param {Object} point - Robot point {x, y} relative to Share Point (0,0)
 * @returns {Object} Pixel point {x, y}
 */
export function applyBilinearTransform(map, point) {
    const { sharePointPixel, scaleX, scaleY } = map

    // Robot X (+right) -> Pixel X offset (same direction)
    // Robot Y (+up) -> Pixel Y offset (negative because +up = -Y in screen)
    const pixelX = sharePointPixel.x + (point.x * scaleX)
    const pixelY = sharePointPixel.y + (-point.y * scaleY)

    return { x: pixelX, y: pixelY }
}



/**
 * Apply inverse Homography transformation (dst -> src)
 * @param {Array<Array<number>>} H - 3x3 Homography matrix
 * @param {{x: number, y: number}} point - Destination point (robot coords)
 * @returns {{x: number, y: number}} Inverse transformed point (pixel coords)
 */
export function applyInverseHomography(H, point) {
    const Hinv = invertMatrix3x3(H)
    return applyHomography(Hinv, point)
}

/**
 * Compute inverse of 3x3 matrix
 * @param {Array<Array<number>>} M - 3x3 matrix
 * @returns {Array<Array<number>>} Inverse matrix
 */
export function invertMatrix3x3(M) {
    const [[a, b, c], [d, e, f], [g, h, i]] = M

    const det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)

    if (Math.abs(det) < 1e-10) {
        throw new Error('Matrix is singular, cannot invert')
    }

    const invDet = 1 / det

    return [
        [(e * i - f * h) * invDet, (c * h - b * i) * invDet, (b * f - c * e) * invDet],
        [(f * g - d * i) * invDet, (a * i - c * g) * invDet, (c * d - a * f) * invDet],
        [(d * h - e * g) * invDet, (b * g - a * h) * invDet, (a * e - b * d) * invDet]
    ]
}

/**
 * Validate that homography is reasonable (not degenerate)
 * @param {Array<Array<number>>} H - 3x3 Homography matrix
 * @returns {boolean} True if valid
 */
export function isValidHomography(H) {
    // Check determinant is not too small
    const det = H[0][0] * (H[1][1] * H[2][2] - H[1][2] * H[2][1])
        - H[0][1] * (H[1][0] * H[2][2] - H[1][2] * H[2][0])
        + H[0][2] * (H[1][0] * H[2][1] - H[1][1] * H[2][0])

    if (Math.abs(det) < 1e-6) {
        return false
    }

    // Check for NaN or Infinity
    for (let i = 0; i < 3; i++) {
        for (let j = 0; j < 3; j++) {
            if (!isFinite(H[i][j])) {
                return false
            }
        }
    }

    return true
}

/**
 * Compute reprojection error for validation
 * @param {Array<Array<number>>} H - Homography matrix
 * @param {Array<[number, number]>} srcPoints - Source points
 * @param {Array<[number, number]>} dstPoints - Destination points
 * @returns {number} Mean squared reprojection error
 */
export function computeReprojectionError(H, srcPoints, dstPoints) {
    let totalError = 0

    for (let i = 0; i < srcPoints.length; i++) {
        const [x, y] = srcPoints[i]
        const [u, v] = dstPoints[i]

        const projected = applyHomography(H, { x, y })
        const dx = projected.x - u
        const dy = projected.y - v

        totalError += dx * dx + dy * dy
    }

    return totalError / srcPoints.length
}
