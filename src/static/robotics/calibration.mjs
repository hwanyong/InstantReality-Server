// ─────────────────────────────────────────────────────────────────────────────
// Calibration Page Controller
// src/static/robotics/calibration.mjs
// ─────────────────────────────────────────────────────────────────────────────

import InstantReality from '/sdk/instant-reality.mjs'
import { showToast, showSuccess, showError } from './lib/toast.mjs'

// ─────────────────────────────────────────────────────────────────────────────
// Globals
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE = ''
let ir = null
const ROLES = ['TopView', 'QuarterView', 'RightRobot', 'LeftRobot']

// UI Elements
const elements = {
    // Video
    cameras: [
        document.getElementById('camera-0'),
        document.getElementById('camera-1'),
        document.getElementById('camera-2'),
        document.getElementById('camera-3')
    ],
    // Robot Control
    robotStatus: document.getElementById('robot-status'),
    robotConnectBtn: document.getElementById('robot-connect-btn'),
    robotDisconnectBtn: document.getElementById('robot-disconnect-btn'),
    goHomeBtn: document.getElementById('go-home-btn'),
    goZeroBtn: document.getElementById('go-zero-btn'),
    motionSpeed: document.getElementById('motion-speed'),
    speedValue: document.getElementById('speed-value'),
    // Calibration
    calStatus: document.getElementById('cal-status'),
    calProgress: document.getElementById('cal-progress'),
    startCalBtn: document.getElementById('start-cal-btn'),
    resetCalBtn: document.getElementById('reset-cal-btn'),
    // Detection
    captureBtn: document.getElementById('capture-btn'),
    detectBaseBtn: document.getElementById('detect-base-btn'),
    detectGripperBtn: document.getElementById('detect-gripper-btn'),
    // Calibration Quality
    qualityAccuracy: document.getElementById('quality-accuracy'),
    qualityReproj: document.getElementById('quality-reproj'),
    qualityPoints: document.getElementById('quality-points'),
    // JSON preview
    jsonPreview: document.getElementById('json-preview')
}

// ─────────────────────────────────────────────────────────────────────────────
// WebRTC Connection
// ─────────────────────────────────────────────────────────────────────────────

async function initWebRTC() {
    ir = new InstantReality({ serverUrl: API_BASE })

    ir.on('track', (track, index) => {
        console.log(`Received track ${index} for role ${ROLES[index]}`)
        const video = elements.cameras[index]
        if (video) {
            video.srcObject = new MediaStream([track])
            video.play().catch(e => console.warn('Autoplay prevented:', e))
        }
    })

    ir.on('connected', () => {
        console.log('WebRTC connected')
        showSuccess('카메라 연결됨')
    })

    ir.on('disconnected', () => {
        console.log('WebRTC disconnected')
        showError('카메라 연결 끊김')
    })

    // Connect with specific roles
    await ir.connect({ roles: ROLES })

    // Setup WebSocket for calibration events
    await ir._connectWebSocket()

    ir.on('calibrationProgress', (data) => {
        updateCalibrationProgress(data)
    })

    ir.on('calibrationComplete', (data) => {
        handleCalibrationComplete(data)
    })

    ir.on('calibrationError', (data) => {
        handleCalibrationError(data)
    })
}

// ─────────────────────────────────────────────────────────────────────────────
// Robot Control
// ─────────────────────────────────────────────────────────────────────────────

async function connectRobot() {
    elements.robotStatus.textContent = 'Connecting...'
    try {
        const res = await fetch(`${API_BASE}/api/robot/connect`, { method: 'POST' })
        const data = await res.json()
        if (data.success) {
            elements.robotStatus.textContent = 'Connected'
            elements.robotStatus.style.color = 'var(--success)'
            elements.robotConnectBtn.disabled = true
            elements.robotDisconnectBtn.disabled = false
            elements.goHomeBtn.disabled = false
            elements.goZeroBtn.disabled = false
            showSuccess('로봇 연결됨')
        } else {
            throw new Error(data.error || 'Connection failed')
        }
    } catch (e) {
        elements.robotStatus.textContent = 'Disconnected'
        elements.robotStatus.style.color = 'var(--danger)'
        showError(`로봇 연결 실패: ${e.message}`)
    }
}

async function disconnectRobot() {
    try {
        await fetch(`${API_BASE}/api/robot/disconnect`, { method: 'POST' })
        elements.robotStatus.textContent = 'Disconnected'
        elements.robotStatus.style.color = 'var(--text-secondary)'
        elements.robotConnectBtn.disabled = false
        elements.robotDisconnectBtn.disabled = true
        elements.goHomeBtn.disabled = true
        elements.goZeroBtn.disabled = true
        showToast('로봇 연결 해제됨')
    } catch (e) {
        showError(`연결 해제 실패: ${e.message}`)
    }
}

async function goHome() {
    const speed = parseFloat(elements.motionSpeed.value)
    showToast(`홈 포지션으로 이동... (${speed}초)`)
    try {
        const res = await fetch(`${API_BASE}/api/robot/home`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ motion_time: speed })
        })
        const data = await res.json()
        if (data.success) {
            showSuccess('홈 포지션 이동 완료')
        }
    } catch (e) {
        showError(`이동 실패: ${e.message}`)
    }
}

async function goZero() {
    const speed = parseFloat(elements.motionSpeed.value)
    showToast(`제로 포지션으로 이동... (${speed}초)`)
    try {
        const res = await fetch(`${API_BASE}/api/robot/zero`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ motion_time: speed })
        })
        const data = await res.json()
        if (data.success) {
            showSuccess('제로 포지션 이동 완료')
        }
    } catch (e) {
        showError(`이동 실패: ${e.message}`)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Calibration
// ─────────────────────────────────────────────────────────────────────────────

async function startCalibration() {
    elements.calStatus.textContent = 'Starting calibration...'
    elements.calProgress.style.width = '0%'
    elements.startCalBtn.disabled = true
    elements.resetCalBtn.disabled = true

    // Reset step indicators
    for (let i = 1; i <= 4; i++) {
        const step = document.getElementById(`step-${i}`)
        if (step) {
            step.classList.remove('active', 'complete')
        }
    }

    try {
        const res = await fetch(`${API_BASE}/api/calibration/start`, { method: 'POST' })
        const data = await res.json()
        if (!data.success) {
            throw new Error(data.error || 'Failed to start calibration')
        }
        showToast('캘리브레이션 시작됨')
    } catch (e) {
        elements.calStatus.textContent = 'Error'
        elements.startCalBtn.disabled = false
        elements.resetCalBtn.disabled = false
        showError(`캘리브레이션 시작 실패: ${e.message}`)
    }
}

function updateCalibrationProgress(data) {
    // Update status text
    if (data.status) {
        elements.calStatus.textContent = data.status
    }

    // Update progress bar
    if (data.progress != null) {
        elements.calProgress.style.width = `${data.progress}%`
    }

    // Update step indicators
    if (data.current_step != null) {
        for (let i = 1; i <= 4; i++) {
            const step = document.getElementById(`step-${i}`)
            if (step) {
                step.classList.remove('active', 'complete')
                if (i < data.current_step) {
                    step.classList.add('complete')
                } else if (i == data.current_step) {
                    step.classList.add('active')
                }
            }
        }
    }
}

function handleCalibrationComplete(data) {
    elements.calStatus.textContent = 'Calibration Complete!'
    elements.calProgress.style.width = '100%'
    elements.startCalBtn.disabled = false
    elements.resetCalBtn.disabled = false

    // Mark all steps complete
    for (let i = 1; i <= 4; i++) {
        const step = document.getElementById(`step-${i}`)
        if (step) {
            step.classList.remove('active')
            step.classList.add('complete')
        }
    }

    // Update quality metrics
    if (data.quality) {
        if (elements.qualityAccuracy) elements.qualityAccuracy.textContent = `${data.quality.accuracy || '--'}mm`
        if (elements.qualityReproj) elements.qualityReproj.textContent = `${data.quality.reproj_error || '--'}px`
        if (elements.qualityPoints) elements.qualityPoints.textContent = data.quality.valid_points || '--'
    }

    // Update JSON preview
    if (elements.jsonPreview) {
        elements.jsonPreview.textContent = JSON.stringify(data, null, 2)
    }

    showSuccess('캘리브레이션 완료!')
    drawWorkspaceMap(data)
}

function handleCalibrationError(data) {
    elements.calStatus.textContent = `Error: ${data.error || 'Unknown error'}`
    elements.calProgress.style.width = '0%'
    elements.startCalBtn.disabled = false
    elements.resetCalBtn.disabled = false
    showError(`캘리브레이션 실패: ${data.error}`)
}

async function resetCalibration() {
    try {
        await fetch(`${API_BASE}/api/calibration/reset`, { method: 'POST' })
        elements.calStatus.textContent = 'Ready to calibrate'
        elements.calProgress.style.width = '0%'

        // Reset step indicators
        for (let i = 1; i <= 4; i++) {
            const step = document.getElementById(`step-${i}`)
            if (step) step.classList.remove('active', 'complete')
        }

        showToast('캘리브레이션 리셋됨')
    } catch (e) {
        showError(`리셋 실패: ${e.message}`)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Detection
// ─────────────────────────────────────────────────────────────────────────────

async function captureAllCameras() {
    showToast('4대 카메라 캡처 중...')
    try {
        const res = await fetch(`${API_BASE}/api/capture_all`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)

        const blob = await res.blob()
        const filename = res.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || 'capture.zip'

        // Trigger download
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)

        showSuccess('캡처 완료! ZIP 파일 다운로드됨')
    } catch (e) {
        showError(`캡처 실패: ${e.message}`)
    }
}

async function detectRobotBase() {
    showToast('로봇 베이스 감지 중...')
    try {
        const res = await fetch(`${API_BASE}/api/calibration/detect_base`, { method: 'POST' })
        const data = await res.json()
        if (data.success) {
            showSuccess('베이스 감지됨')
            if (elements.jsonPreview) {
                elements.jsonPreview.textContent = JSON.stringify(data, null, 2)
            }
        } else {
            throw new Error(data.error || 'Detection failed')
        }
    } catch (e) {
        showError(`감지 실패: ${e.message}`)
    }
}

async function detectGripper() {
    showToast('그리퍼 감지 중...')
    try {
        const res = await fetch(`${API_BASE}/api/calibration/detect_gripper`, { method: 'POST' })
        const data = await res.json()
        if (data.success) {
            showSuccess('그리퍼 감지됨')
            if (elements.jsonPreview) {
                elements.jsonPreview.textContent = JSON.stringify(data, null, 2)
            }
        } else {
            throw new Error(data.error || 'Detection failed')
        }
    } catch (e) {
        showError(`감지 실패: ${e.message}`)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Overlay Canvas - State & Rendering
// ─────────────────────────────────────────────────────────────────────────────

const overlayState = {
    tool: 'vertex',  // 'vertex', 'left-base', 'right-base', 'left-gripper', 'right-gripper'
    vertices: [],    // [{x, y}, ...]
    leftBase: null,  // {x, y}
    rightBase: null, // {x, y}
    leftGripper: null,   // {x, y}
    rightGripper: null,  // {x, y}
    dragging: null,      // {type: 'vertex'|'base'|'gripper', index: number, side: 'left'|'right'}
}

const overlayCanvas = document.getElementById('overlay-canvas')
const overlayCtx = overlayCanvas ? overlayCanvas.getContext('2d') : null

function drawOverlay() {
    if (!overlayCtx) return

    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height)

    // Draw polygon
    if (overlayState.vertices.length > 0) {
        overlayCtx.beginPath()
        overlayCtx.moveTo(overlayState.vertices[0].x, overlayState.vertices[0].y)
        for (let i = 1; i < overlayState.vertices.length; i++) {
            overlayCtx.lineTo(overlayState.vertices[i].x, overlayState.vertices[i].y)
        }
        if (overlayState.vertices.length > 2) {
            overlayCtx.closePath()
            overlayCtx.fillStyle = 'rgba(100, 200, 255, 0.15)'
            overlayCtx.fill()
        }
        overlayCtx.strokeStyle = '#64c8ff'
        overlayCtx.lineWidth = 2
        overlayCtx.stroke()

        // Draw vertices
        overlayState.vertices.forEach((v, i) => {
            overlayCtx.beginPath()
            overlayCtx.arc(v.x, v.y, 8, 0, Math.PI * 2)
            overlayCtx.fillStyle = '#64c8ff'
            overlayCtx.fill()
            overlayCtx.fillStyle = '#000'
            overlayCtx.font = '10px Inter, sans-serif'
            overlayCtx.textAlign = 'center'
            overlayCtx.textBaseline = 'middle'
            overlayCtx.fillText(i + 1, v.x, v.y)
        })
    }

    // Draw bases
    if (overlayState.leftBase) {
        drawMarker(overlayState.leftBase, '#ff6b6b', '◆', 'L')
    }
    if (overlayState.rightBase) {
        drawMarker(overlayState.rightBase, '#4dabf7', '◆', 'R')
    }

    // Draw grippers
    if (overlayState.leftGripper) {
        drawMarker(overlayState.leftGripper, '#ff6b6b', '★', 'L')
    }
    if (overlayState.rightGripper) {
        drawMarker(overlayState.rightGripper, '#4dabf7', '★', 'R')
    }
}

function drawMarker(pos, color, symbol, label) {
    overlayCtx.beginPath()
    overlayCtx.arc(pos.x, pos.y, 12, 0, Math.PI * 2)
    overlayCtx.fillStyle = color
    overlayCtx.fill()
    overlayCtx.strokeStyle = '#fff'
    overlayCtx.lineWidth = 2
    overlayCtx.stroke()

    overlayCtx.fillStyle = '#fff'
    overlayCtx.font = 'bold 12px Inter, sans-serif'
    overlayCtx.textAlign = 'center'
    overlayCtx.textBaseline = 'middle'
    overlayCtx.fillText(label, pos.x, pos.y)
}

function handleOverlayClick(e) {
    const rect = overlayCanvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    switch (overlayState.tool) {
        case 'vertex':
            overlayState.vertices.push({ x, y })
            break
        case 'left-base':
            overlayState.leftBase = { x, y }
            break
        case 'right-base':
            overlayState.rightBase = { x, y }
            break
        case 'left-gripper':
            overlayState.leftGripper = { x, y }
            break
        case 'right-gripper':
            overlayState.rightGripper = { x, y }
            break
    }

    drawOverlay()
}

function initOverlayTools() {
    const toolbar = document.getElementById('overlay-toolbar')
    if (!toolbar) return

    toolbar.querySelectorAll('.tool-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tool = btn.dataset.tool
            if (!tool) return

            // Clear all active
            toolbar.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'))
            btn.classList.add('active')
            overlayState.tool = tool
        })
    })

    // Clear button
    const clearBtn = document.getElementById('tool-clear')
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            overlayState.vertices = []
            overlayState.leftBase = null
            overlayState.rightBase = null
            overlayState.leftGripper = null
            overlayState.rightGripper = null
            drawOverlay()
            showSuccess('오버레이 초기화됨')
        })
    }

    // Canvas click
    if (overlayCanvas) {
        overlayCanvas.addEventListener('click', handleOverlayClick)
    }
}

function getOverlayData() {
    return {
        workspace: { vertices: overlayState.vertices },
        robotBases: {
            left: overlayState.leftBase,
            right: overlayState.rightBase
        },
        grippers: {
            left: overlayState.leftGripper,
            right: overlayState.rightGripper
        }
    }
}


// ─────────────────────────────────────────────────────────────────────────────
// Event Listeners
// ─────────────────────────────────────────────────────────────────────────────

function initEventListeners() {
    // Robot control
    if (elements.robotConnectBtn) elements.robotConnectBtn.addEventListener('click', connectRobot)
    if (elements.robotDisconnectBtn) elements.robotDisconnectBtn.addEventListener('click', disconnectRobot)
    if (elements.goHomeBtn) elements.goHomeBtn.addEventListener('click', goHome)
    if (elements.goZeroBtn) elements.goZeroBtn.addEventListener('click', goZero)

    // Speed slider
    if (elements.motionSpeed) {
        elements.motionSpeed.addEventListener('input', () => {
            elements.speedValue.textContent = `${elements.motionSpeed.value}초`
        })
    }

    // Calibration
    if (elements.startCalBtn) elements.startCalBtn.addEventListener('click', startCalibration)
    if (elements.resetCalBtn) elements.resetCalBtn.addEventListener('click', resetCalibration)

    // Detection
    if (elements.captureBtn) elements.captureBtn.addEventListener('click', captureAllCameras)
    if (elements.detectBaseBtn) elements.detectBaseBtn.addEventListener('click', detectRobotBase)
    if (elements.detectGripperBtn) elements.detectGripperBtn.addEventListener('click', detectGripper)
}

// ─────────────────────────────────────────────────────────────────────────────
// Initialize
// ─────────────────────────────────────────────────────────────────────────────

async function init() {
    console.log('Calibration page initializing...')
    initEventListeners()
    initOverlayTools()

    try {
        await initWebRTC()
        console.log('Calibration page ready')
    } catch (e) {
        console.error('Failed to initialize WebRTC:', e)
        showError(`WebRTC 초기화 실패: ${e.message}`)
    }
}

init()
