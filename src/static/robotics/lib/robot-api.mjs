// ─────────────────────────────────────────────────────────────────────────────
// Robot API Client Module
// src/static/robotics/lib/robot-api.mjs
//
// Shared REST API client for robot control, IK calculation,
// servo config, and calibration geometry.
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE = ''

// ─────────────────────────────────────────────────────────────────────────────
// Internal Helpers
// ─────────────────────────────────────────────────────────────────────────────

async function postJSON(url, body = {}) {
    const res = await fetch(`${API_BASE}${url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
    return await res.json()
}

async function getJSON(url) {
    const res = await fetch(`${API_BASE}${url}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
}

// ─────────────────────────────────────────────────────────────────────────────
// Robot Connection
// ─────────────────────────────────────────────────────────────────────────────

export async function robotConnect() {
    return await postJSON('/api/robot/connect')
}

export async function robotDisconnect() {
    return await postJSON('/api/robot/disconnect')
}

// ─────────────────────────────────────────────────────────────────────────────
// Robot Movement
// ─────────────────────────────────────────────────────────────────────────────

export async function robotHome(motionTime = 3) {
    return await postJSON('/api/robot/home', { motion_time: motionTime })
}

export async function robotZero(motionTime = 3) {
    return await postJSON('/api/robot/zero', { motion_time: motionTime })
}

export async function robotMoveTo(x, y, z, arm, motionTime = 3) {
    return await postJSON('/api/robot/move_to', { x, y, z, arm, motion_time: motionTime })
}

// ─────────────────────────────────────────────────────────────────────────────
// Robot Status
// ─────────────────────────────────────────────────────────────────────────────

export async function robotStatus() {
    return await getJSON('/api/robot/status')
}

// ─────────────────────────────────────────────────────────────────────────────
// IK Calculation
// ─────────────────────────────────────────────────────────────────────────────

export async function calculateIK(worldX, worldY, arm, z = 3) {
    const res = await fetch(`${API_BASE}/api/ik/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ world_x: worldX, world_y: worldY, z, arm })
    })

    if (!res.ok) {
        console.error('IK API error:', res.status)
        return null
    }

    return await res.json()
}

// ─────────────────────────────────────────────────────────────────────────────
// Config & Geometry
// ─────────────────────────────────────────────────────────────────────────────

export async function getServoConfig() {
    return await getJSON('/api/servo_config')
}

export async function getCalibrationGeometry() {
    return await getJSON('/api/calibration/geometry')
}

// ─────────────────────────────────────────────────────────────────────────────
// Gripper Control
// ─────────────────────────────────────────────────────────────────────────────

export async function robotGripperOpen(arm = 'right') {
    return await postJSON('/api/robot/gripper/open', { arm })
}

export async function robotGripperClose(arm = 'right') {
    return await postJSON('/api/robot/gripper/close', { arm })
}
