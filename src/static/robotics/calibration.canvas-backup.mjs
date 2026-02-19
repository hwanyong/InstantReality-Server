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

    // JSON preview
    jsonPreview: document.getElementById('json-preview'),
    // Tab elements
    tabButtons: document.querySelectorAll('.tab-btn'),
    tabPanels: document.querySelectorAll('.tab-panel'),
    // Toolbar buttons
    loadCalBtn: document.getElementById('load-cal-btn'),
    saveCalBtn: document.getElementById('save-cal-btn'),
    exportCalBtn: document.getElementById('export-cal-btn')
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

    // Initialize pause buttons after connection
    initPauseButtons()
}

// ─────────────────────────────────────────────────────────────────────────────
// Camera Pause (Per-Client)
// ─────────────────────────────────────────────────────────────────────────────

const pausedCameras = new Set()

async function toggleCameraPause(cameraIndex) {
    if (!ir || !ir.clientId) {
        showError('WebRTC 연결 필요')
        return
    }

    const paused = !pausedCameras.has(cameraIndex)

    try {
        const res = await fetch(`${API_BASE}/pause_camera_client`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                client_id: ir.clientId,
                camera_index: cameraIndex,
                paused: paused
            })
        })

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`)
        }

        if (paused) {
            pausedCameras.add(cameraIndex)
            showToast(`카메라 ${cameraIndex} 일시정지됨`)
        } else {
            pausedCameras.delete(cameraIndex)
            showToast(`카메라 ${cameraIndex} 재개됨`)
        }

        updatePauseButtonState(cameraIndex)
    } catch (e) {
        console.error('Failed to toggle pause:', e)
        showError(`일시정지 실패: ${e.message}`)
    }
}

function updatePauseButtonState(cameraIndex) {
    const btn = document.querySelector(`.pause-btn[data-camera="${cameraIndex}"]`)
    if (!btn) return

    if (pausedCameras.has(cameraIndex)) {
        btn.classList.add('paused')
        btn.textContent = '▶'
        btn.title = '재생'
    } else {
        btn.classList.remove('paused')
        btn.textContent = '⏸'
        btn.title = '일시정지'
    }
}

function initPauseButtons() {
    document.querySelectorAll('.pause-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation()
            const cameraIndex = parseInt(btn.dataset.camera)
            toggleCameraPause(cameraIndex)
        })
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
    selectedVertex: null,  // index of selected vertex
    isDragging: false,
    dragStart: null,  // {x, y} - for click vs drag detection
}

const overlayCanvas = document.getElementById('overlay-canvas')
const overlayCtx = overlayCanvas ? overlayCanvas.getContext('2d') : null

const HIT_RADIUS = 15
const DELETE_BTN_OFFSET = { x: 20, y: -20 }
const DELETE_BTN_SIZE = 18

function findNearestVertex(x, y) {
    for (let i = 0; i < overlayState.vertices.length; i++) {
        const v = overlayState.vertices[i]
        const dist = Math.sqrt((v.x - x) ** 2 + (v.y - y) ** 2)
        if (dist < HIT_RADIUS) return i
    }
    return null
}

function isClickOnDeleteBtn(x, y) {
    if (overlayState.selectedVertex == null) return false
    const v = overlayState.vertices[overlayState.selectedVertex]
    if (!v) return false
    const btnX = v.x + DELETE_BTN_OFFSET.x
    const btnY = v.y + DELETE_BTN_OFFSET.y
    return Math.abs(x - btnX) < DELETE_BTN_SIZE && Math.abs(y - btnY) < DELETE_BTN_SIZE
}

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
            const isSelected = overlayState.selectedVertex == i
            overlayCtx.beginPath()
            overlayCtx.arc(v.x, v.y, isSelected ? 12 : 8, 0, Math.PI * 2)
            overlayCtx.fillStyle = isSelected ? '#ffd43b' : '#64c8ff'
            overlayCtx.fill()
            if (isSelected) {
                overlayCtx.strokeStyle = '#fff'
                overlayCtx.lineWidth = 2
                overlayCtx.stroke()
            }
            overlayCtx.fillStyle = '#000'
            overlayCtx.font = '10px Inter, sans-serif'
            overlayCtx.textAlign = 'center'
            overlayCtx.textBaseline = 'middle'
            overlayCtx.fillText(i + 1, v.x, v.y)

            // Draw delete button for selected vertex
            if (isSelected) {
                const btnX = v.x + DELETE_BTN_OFFSET.x
                const btnY = v.y + DELETE_BTN_OFFSET.y
                overlayCtx.beginPath()
                overlayCtx.arc(btnX, btnY, DELETE_BTN_SIZE / 2, 0, Math.PI * 2)
                overlayCtx.fillStyle = '#f03e3e'
                overlayCtx.fill()
                overlayCtx.fillStyle = '#fff'
                overlayCtx.font = 'bold 12px Inter, sans-serif'
                overlayCtx.fillText('×', btnX, btnY)
            }
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

    // Check delete button click first
    if (isClickOnDeleteBtn(x, y)) {
        overlayState.vertices.splice(overlayState.selectedVertex, 1)
        overlayState.selectedVertex = null
        drawOverlay()
        return
    }

    // Check hit on existing vertex
    const hitIndex = findNearestVertex(x, y)

    switch (overlayState.tool) {
        case 'vertex':
            if (hitIndex != null) {
                // Select or deselect vertex
                overlayState.selectedVertex = overlayState.selectedVertex == hitIndex ? null : hitIndex
            } else {
                // Add new vertex
                overlayState.vertices.push({ x, y })
                overlayState.selectedVertex = null
            }
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

function handleOverlayMouseDown(e) {
    const rect = overlayCanvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    overlayState.dragStart = { x, y }

    if (overlayState.tool == 'vertex') {
        const hitIndex = findNearestVertex(x, y)
        if (hitIndex != null) {
            overlayState.selectedVertex = hitIndex
            overlayState.isDragging = true
            drawOverlay()
        }
    }
}

function handleOverlayMouseMove(e) {
    if (!overlayState.isDragging || overlayState.selectedVertex == null) return

    const rect = overlayCanvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    overlayState.vertices[overlayState.selectedVertex] = { x, y }
    drawOverlay()
}

function handleOverlayMouseUp(e) {
    const rect = overlayCanvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    const start = overlayState.dragStart
    const wasDragging = overlayState.isDragging
    overlayState.isDragging = false
    overlayState.dragStart = null

    // Calculate distance to determine click vs drag
    const distance = start ? Math.sqrt((x - start.x) ** 2 + (y - start.y) ** 2) : 0

    // If moved more than 5px, it was a drag - don't process as click
    if (distance > 5) return

    // If was dragging a vertex, don't process as click (vertex already moved)
    if (wasDragging && overlayState.selectedVertex != null) return

    // Process as click
    // Check delete button first
    if (isClickOnDeleteBtn(x, y)) {
        overlayState.vertices.splice(overlayState.selectedVertex, 1)
        overlayState.selectedVertex = null
        drawOverlay()
        return
    }

    const hitIndex = findNearestVertex(x, y)

    switch (overlayState.tool) {
        case 'vertex':
            if (hitIndex != null) {
                overlayState.selectedVertex = overlayState.selectedVertex == hitIndex ? null : hitIndex
            } else {
                overlayState.vertices.push({ x, y })
                overlayState.selectedVertex = null
            }
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

function handleOverlayMouseLeave() {
    // Only reset state, don't process as click
    overlayState.isDragging = false
    overlayState.dragStart = null
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
            overlayState.selectedVertex = null
            drawOverlay()
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
            overlayState.selectedVertex = null
            drawOverlay()
            showSuccess('오버레이 초기화됨')
        })
    }

    // Canvas events
    if (overlayCanvas) {
        overlayCanvas.addEventListener('mousedown', handleOverlayMouseDown)
        overlayCanvas.addEventListener('mousemove', handleOverlayMouseMove)
        overlayCanvas.addEventListener('mouseup', handleOverlayMouseUp)
        overlayCanvas.addEventListener('mouseleave', handleOverlayMouseLeave)
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
            elements.speedValue.textContent = `${elements.motionSpeed.value}s`
        })
    }

    // Load button - reload servo config
    if (elements.loadCalBtn) {
        elements.loadCalBtn.addEventListener('click', async () => {
            showToast('설정 불러오는 중...')
            await loadServoConfig()
            showSuccess('설정 로드 완료')
        })
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tab System
// ─────────────────────────────────────────────────────────────────────────────

function initTabs() {
    elements.tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab

            // Update button states
            elements.tabButtons.forEach(b => b.classList.remove('active'))
            btn.classList.add('active')

            // Update panel visibility
            elements.tabPanels.forEach(panel => {
                panel.classList.remove('active')
                if (panel.id == `tab-${tabId}`) {
                    panel.classList.add('active')
                }
            })
        })
    })
}

// ─────────────────────────────────────────────────────────────────────────────
// Canvas Resize
// ─────────────────────────────────────────────────────────────────────────────

function initCanvasResize() {
    const container = document.getElementById('topview-container')
    const video = document.getElementById('camera-0')
    const canvas = document.getElementById('overlay-canvas')

    if (!container || !video || !canvas) return

    function resizeCanvas() {
        // Match canvas size to video display size
        const rect = video.getBoundingClientRect()
        canvas.width = rect.width
        canvas.height = rect.height
        canvas.style.width = rect.width + 'px'
        canvas.style.height = rect.height + 'px'

        // Redraw overlay with new size
        if (typeof drawOverlay == 'function') {
            drawOverlay()
        }
    }

    // Resize on video metadata loaded
    video.addEventListener('loadedmetadata', resizeCanvas)

    // Resize on window resize
    window.addEventListener('resize', resizeCanvas)

    // Initial resize attempt
    setTimeout(resizeCanvas, 500)
}

// ─────────────────────────────────────────────────────────────────────────────
// Servo Config API
// ─────────────────────────────────────────────────────────────────────────────

let servoConfig = null

async function loadServoConfig() {
    try {
        const res = await fetch(`${API_BASE}/api/servo_config`)
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`)
        }
        servoConfig = await res.json()
        updateJsonPreview()
        console.log('Servo config loaded')
        return servoConfig
    } catch (e) {
        console.error('Failed to load servo config:', e)
        if (elements.jsonPreview) {
            elements.jsonPreview.textContent = `Failed to load: ${e.message}`
        }
        return null
    }
}

function updateJsonPreview() {
    if (!elements.jsonPreview) return

    if (servoConfig) {
        elements.jsonPreview.textContent = JSON.stringify(servoConfig, null, 2)
    } else {
        elements.jsonPreview.textContent = 'No calibration data'
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Initialize
// ─────────────────────────────────────────────────────────────────────────────

async function init() {
    console.log('Calibration page initializing...')
    initEventListeners()
    initOverlayTools()
    initTabs()
    initCanvasResize()

    // Load servo config for JSON preview
    await loadServoConfig()

    try {
        await initWebRTC()
        console.log('Calibration page ready')
    } catch (e) {
        console.error('Failed to initialize WebRTC:', e)
        showError(`WebRTC 초기화 실패: ${e.message}`)
    }
}

init()
