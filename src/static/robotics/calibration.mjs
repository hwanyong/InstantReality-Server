/**
 * Calibration Page JavaScript Module
 * 
 * Handles:
 * - Auto-calibration workflow control
 * - Workspace visualization
 * - Calibration data management
 * - Real-time progress updates
 * - Camera streaming via WebRTC (InstantReality SDK)
 */

import InstantReality from '../sdk/instant-reality.mjs'

// Configuration
const API_BASE = '/api'

// Camera role names
const CAMERA_ROLES = ['TopView', 'QuarterView', 'RightRobot', 'LeftRobot']
const CALIBRATION_CAMERAS = ['TopView', 'QuarterView']

// State
let isCalibrating = false
let calibrationData = null
let videoElements = []
let arCanvas = null
let workspaceCanvas = null
let roleMapping = {}
let ir = null  // InstantReality instance
let isRobotConnected = false

// DOM Elements
const elements = {
    connectionStatus: null,
    calStatus: null,
    calProgress: null,
    startBtn: null,
    stopBtn: null,
    gridSize: null,
    calZ: null,
    jsonPreview: null,
    steps: {},
    stats: {}
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', init)

async function init() {
    // Cache DOM elements
    cacheElements()

    // Setup video elements for WebRTC
    setupVideoElements()

    // Initialize WebRTC streaming
    await initWebRTC()

    // Load existing calibration
    await loadCalibration()

    // Event listeners
    setupEventListeners()
}

function cacheElements() {
    elements.connectionStatus = document.getElementById('connection-status')
    elements.calStatus = document.getElementById('cal-status')
    elements.calProgress = document.getElementById('cal-progress')
    elements.startBtn = document.getElementById('start-cal-btn')
    elements.stopBtn = document.getElementById('stop-cal-btn')
    elements.gridSize = document.getElementById('grid-size')
    elements.calZ = document.getElementById('cal-z')
    elements.jsonPreview = document.getElementById('json-preview')

    // Step elements
    for (let i = 1; i <= 4; i++) {
        elements.steps[i] = document.getElementById(`step-${i}`)
    }

    // Stat elements
    elements.stats = {
        width: document.getElementById('stat-width'),
        height: document.getElementById('stat-height'),
        points: document.getElementById('stat-points'),
        meanErr: document.getElementById('stat-mean-err'),
        maxErr: document.getElementById('stat-max-err'),
        status: document.getElementById('stat-status')
    }
}

function setupVideoElements() {
    // Get all 4 video elements for WebRTC streaming
    videoElements = [
        document.getElementById('camera-0'),
        document.getElementById('camera-1'),
        document.getElementById('camera-2'),
        document.getElementById('camera-3')
    ]
    arCanvas = document.getElementById('ar-overlay')
    workspaceCanvas = document.getElementById('workspace-canvas')

    // Initialize workspace canvas
    if (workspaceCanvas) {
        const rect = workspaceCanvas.parentElement.getBoundingClientRect()
        workspaceCanvas.width = rect.width
        workspaceCanvas.height = rect.height
        drawWorkspaceGrid()
    }
}

// Initialize WebRTC streaming using InstantReality SDK
async function initWebRTC() {
    try {
        updateConnectionStatus(false, 'Connecting...')

        ir = new InstantReality()

        // Handle incoming video tracks
        ir.on('track', (track, index) => {
            console.log(`Track ${index} received`)
            if (videoElements[index]) {
                videoElements[index].srcObject = new MediaStream([track])
            }
        })

        ir.on('connected', () => {
            updateConnectionStatus(true, 'WebRTC Connected')
            console.log('WebRTC connected')
        })

        ir.on('disconnected', () => {
            updateConnectionStatus(false, 'Disconnected')
            console.log('WebRTC disconnected')
        })

        ir.on('cameraChange', async (cameras) => {
            console.log('Camera change detected:', cameras)
            await ir.reconnect()
        })

        // Calibration event listeners
        ir.on('calibrationProgress', (data) => {
            console.log('Calibration progress:', data)
            updateProgress(data)
        })

        ir.on('calibrationComplete', (data) => {
            console.log('Calibration complete:', data)
            onCalibrationComplete(data)
        })

        ir.on('calibrationError', (data) => {
            console.log('Calibration error:', data)
            onCalibrationError(data)
        })

        // Connect with role-based camera selection
        await ir.connect({
            roles: CAMERA_ROLES
        })

        // Also load role mapping for calibration API
        await loadRoleMapping()

    } catch (err) {
        console.error('WebRTC init failed:', err)
        updateConnectionStatus(false, 'WebRTC Error')
    }
}

// Load role mapping from server
async function loadRoleMapping() {
    try {
        updateConnectionStatus(false, 'Loading...')
        const res = await fetch(`${API_BASE}/cameras/status`)
        const data = await res.json()
        roleMapping = {}

        for (const [role, info] of Object.entries(data.role_mapping || {})) {
            if (info && info.index !== undefined) {
                roleMapping[role] = info.index
            }
        }
        console.log('Role mapping loaded:', roleMapping)
        updateConnectionStatus(true)
    } catch (err) {
        console.error('Failed to load role mapping:', err)
        updateConnectionStatus(false, 'Error')
    }
}

// Deprecated: captureFrame - now using WebRTC streaming
// Kept for backward compatibility with capture button
async function captureFrame(cameraRole, videoElement) {
    // For capture button, we can grab from video element
    if (!videoElement) return null
    return videoElement  // Return video element for frame capture
}

// Deprecated: refreshAllCameras - WebRTC handles streaming automatically
function refreshAllCameras() {
    // No-op: WebRTC provides real-time streaming
}

// Deprecated: startAutoRefresh - WebRTC handles streaming automatically
function startAutoRefresh() {
    console.log('WebRTC streaming active - no polling needed')
}

function stopAutoRefresh() {
    // No-op: WebRTC cleanup handled by ir.disconnect()
}

function updateConnectionStatus(connected, message = null) {
    if (elements.connectionStatus) {
        const text = message || (connected ? 'Connected' : 'Disconnected')
        elements.connectionStatus.textContent = `● ${text}`
        elements.connectionStatus.className = `status ${connected ? 'connected' : 'disconnected'}`
    }
}

function handleMessage(event) {
    try {
        const msg = JSON.parse(event.data)

        switch (msg.type) {
            case 'calibration_progress':
                updateProgress(msg.data)
                break
            case 'calibration_complete':
                onCalibrationComplete(msg.data)
                break
            case 'calibration_error':
                onCalibrationError(msg.data)
                break
            case 'video_frame':
                drawVideoFrame(msg.data)
                break
            case 'detection_result':
                drawDetection(msg.data)
                break
        }
    } catch (e) {
        console.error('Message parse error:', e)
    }
}

function setupEventListeners() {
    // Start calibration
    elements.startBtn?.addEventListener('click', startCalibration)

    // Stop calibration
    elements.stopBtn?.addEventListener('click', stopCalibration)

    // Detection buttons
    document.getElementById('detect-base-btn')?.addEventListener('click', detectRobotBase)
    document.getElementById('detect-gripper-btn')?.addEventListener('click', detectGripper)

    // Robot control buttons
    document.getElementById('robot-connect-btn')?.addEventListener('click', connectRobot)
    document.getElementById('robot-disconnect-btn')?.addEventListener('click', disconnectRobot)
    document.getElementById('go-home-btn')?.addEventListener('click', goHome)
    document.getElementById('go-zero-btn')?.addEventListener('click', goToZero)

    // Motion speed slider
    const speedSlider = document.getElementById('motion-speed')
    const speedValue = document.getElementById('speed-value')
    speedSlider?.addEventListener('input', (e) => {
        const val = e.target.value
        speedValue.textContent = `${val}초`
    })
    speedSlider?.addEventListener('change', (e) => {
        setMotionSpeed(parseFloat(e.target.value))
    })

    // Grid preview
    document.getElementById('test-grid-btn')?.addEventListener('click', previewGridPoints)

    // Calibration data
    document.getElementById('load-cal-btn')?.addEventListener('click', loadCalibration)
    document.getElementById('save-cal-btn')?.addEventListener('click', saveCalibration)
    document.getElementById('export-cal-btn')?.addEventListener('click', exportCalibration)

    // Verify
    document.getElementById('verify-cal-btn')?.addEventListener('click', verifyCalibration)

    // Capture
    document.getElementById('capture-btn')?.addEventListener('click', captureFrame)
}

// === Calibration Control ===

async function startCalibration() {
    if (isCalibrating) return

    // Zero-Reference calibration - no parameters needed
    isCalibrating = true
    elements.startBtn.disabled = true
    elements.stopBtn.disabled = false

    updateCalStatus('Starting Zero-Reference calibration...')
    updateProgress({ step: 0, total: 4, message: 'Initializing...' })

    try {
        const response = await fetch(`${API_BASE}/calibration/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})  // No parameters for Zero-Reference
        })

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`)
        }

        const result = await response.json()
        console.log('Zero-Reference calibration started:', result)

        // Start polling for phase status
        startPhasePolling()

    } catch (e) {
        console.error('Failed to start calibration:', e)
        onCalibrationError({ message: e.message })
    }
}

// === Phase Status Polling for Zero-Reference Calibration ===
let phasePollingInterval = null

function startPhasePolling() {
    if (phasePollingInterval) return
    phasePollingInterval = setInterval(pollPhaseStatus, 2000)
}

function stopPhasePolling() {
    if (phasePollingInterval) {
        clearInterval(phasePollingInterval)
        phasePollingInterval = null
    }
}

async function pollPhaseStatus() {
    try {
        const resp = await fetch(`${API_BASE}/calibration/phase-status`)
        const data = await resp.json()

        // Update progress based on phase
        updateProgress({
            step: data.current_phase,
            total: 4,
            message: data.phase_name
        })

        // Update step indicators
        updateStepIndicators(data.current_phase + 1, 4)

        // Check if calibration is done
        if (!data.is_running && data.current_phase >= 4) {
            stopPhasePolling()
            isCalibrating = false
            elements.startBtn.disabled = false
            elements.stopBtn.disabled = true

            // Load final calibration data
            await loadCalibration()
        }

    } catch (e) {
        console.error('Phase status poll error:', e)
    }
}

function stopCalibration() {
    if (!isCalibrating) return

    // Stop polling first
    stopPhasePolling()

    fetch(`${API_BASE}/calibration/stop`, { method: 'POST' })
        .then(() => {
            isCalibrating = false
            elements.startBtn.disabled = false
            elements.stopBtn.disabled = true
            updateCalStatus('Calibration stopped')
        })
        .catch(e => console.error('Stop failed:', e))
}

function updateProgress(data) {
    const { step, total, message } = data
    const percent = Math.round((step / total) * 100)

    // Update progress bar
    if (elements.calProgress) {
        elements.calProgress.style.width = `${percent}%`
    }

    // Update status text
    updateCalStatus(message || `Step ${step}/${total}`)

    // Update step indicators
    updateStepIndicators(step, total)
}

function updateStepIndicators(currentStep, total) {
    // Map progress to 4 main steps
    let activeStep = 1
    if (currentStep > 1) activeStep = 2  // Grid calibration
    if (currentStep > total - 2) activeStep = 3  // Transform calculation
    if (currentStep >= total) activeStep = 4  // Mapping complete

    for (let i = 1; i <= 4; i++) {
        const stepEl = elements.steps[i]
        if (!stepEl) continue

        stepEl.classList.remove('active', 'done')
        if (i < activeStep) {
            stepEl.classList.add('done')
        } else if (i == activeStep) {
            stepEl.classList.add('active')
        }
    }
}

function updateCalStatus(message) {
    if (elements.calStatus) {
        elements.calStatus.textContent = message
    }
}

function onCalibrationComplete(data) {
    isCalibrating = false
    elements.startBtn.disabled = false
    elements.stopBtn.disabled = true

    calibrationData = data
    updateCalStatus('✅ Calibration complete!')
    updateProgress({ step: 100, total: 100, message: 'Complete!' })

    // Update stats
    updateCalibrationStats(data)

    // Update JSON preview
    updateJsonPreview(data)

    // Draw workspace
    drawWorkspaceMap(data)
}

function onCalibrationError(data) {
    isCalibrating = false
    elements.startBtn.disabled = false
    elements.stopBtn.disabled = true

    updateCalStatus(`❌ Error: ${data.message}`)
    elements.stats.status.textContent = '❌'
}

function updateCalibrationStats(data) {
    if (data.workspace) {
        elements.stats.width.textContent = data.workspace.width_mm?.toFixed(0) || '--'
        elements.stats.height.textContent = data.workspace.height_mm?.toFixed(0) || '--'
    }

    if (data.quality) {
        elements.stats.points.textContent = data.quality.calibration_points || '--'
        elements.stats.meanErr.textContent = data.quality.mean_error_mm?.toFixed(1) || '--'
        elements.stats.maxErr.textContent = data.quality.max_error_mm?.toFixed(1) || '--'

        // Status based on error
        const meanErr = data.quality.mean_error_mm || 999
        elements.stats.status.textContent = meanErr < 10 ? '✅' : meanErr < 20 ? '⚠️' : '❌'
    }
}

function updateJsonPreview(data) {
    if (elements.jsonPreview) {
        elements.jsonPreview.textContent = JSON.stringify(data, null, 2)
    }
}

// === Detection Functions ===

async function detectRobotBase() {
    updateCalStatus('Detecting robot base...')

    try {
        const response = await fetch(`${API_BASE}/calibration/detect-base`, {
            method: 'POST'
        })
        const result = await response.json()

        if (result.success) {
            updateCalStatus(`✅ Base detected at [${result.point.join(', ')}]`)
            drawDetection({ point: result.point, label: 'Robot Base', color: '#58a6ff' })
        } else {
            updateCalStatus(`❌ ${result.error}`)
        }
    } catch (e) {
        updateCalStatus(`❌ Detection failed: ${e.message}`)
    }
}

async function detectGripper() {
    updateCalStatus('Detecting gripper...')

    try {
        const response = await fetch(`${API_BASE}/calibration/detect-gripper`, {
            method: 'POST'
        })
        const result = await response.json()

        if (result.success) {
            updateCalStatus(`✅ Gripper at [${result.point.join(', ')}]`)
            drawDetection({ point: result.point, label: 'Gripper', color: '#3fb950' })
        } else {
            updateCalStatus(`❌ ${result.error}`)
        }
    } catch (e) {
        updateCalStatus(`❌ Detection failed: ${e.message}`)
    }
}

// === Visualization ===

function drawDetection(data) {
    const ctx = arCanvas.getContext('2d')
    const { point, label, color } = data

    // Scale point from 0-1000 to canvas size
    const x = (point[1] / 1000) * arCanvas.width
    const y = (point[0] / 1000) * arCanvas.height

    // Draw crosshair
    ctx.strokeStyle = color || '#58a6ff'
    ctx.lineWidth = 2

    ctx.beginPath()
    ctx.moveTo(x - 20, y)
    ctx.lineTo(x + 20, y)
    ctx.moveTo(x, y - 20)
    ctx.lineTo(x, y + 20)
    ctx.stroke()

    // Draw circle
    ctx.beginPath()
    ctx.arc(x, y, 10, 0, Math.PI * 2)
    ctx.stroke()

    // Label
    ctx.fillStyle = color || '#58a6ff'
    ctx.font = '12px Inter, sans-serif'
    ctx.fillText(label || 'Detection', x + 15, y - 10)
}

function drawWorkspaceGrid() {
    if (!workspaceCanvas) return

    const ctx = workspaceCanvas.getContext('2d')
    const w = workspaceCanvas.width
    const h = workspaceCanvas.height

    // Clear
    ctx.fillStyle = '#161b22'
    ctx.fillRect(0, 0, w, h)

    // Grid lines
    ctx.strokeStyle = '#30363d'
    ctx.lineWidth = 1

    for (let i = 0; i <= 10; i++) {
        const x = (i / 10) * w
        const y = (i / 10) * h

        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, h)
        ctx.moveTo(0, y)
        ctx.lineTo(w, y)
        ctx.stroke()
    }

    // Origin marker (bottom-right for robot)
    ctx.fillStyle = '#f85149'
    ctx.beginPath()
    ctx.arc(w - 20, h - 20, 8, 0, Math.PI * 2)
    ctx.fill()

    ctx.fillStyle = '#e6edf3'
    ctx.font = '10px Inter'
    ctx.fillText('Robot', w - 45, h - 30)
}

function drawWorkspaceMap(data) {
    if (!workspaceCanvas || !data.robot?.reachable_area) return

    const ctx = workspaceCanvas.getContext('2d')
    const w = workspaceCanvas.width
    const h = workspaceCanvas.height

    // Redraw grid
    drawWorkspaceGrid()

    const area = data.robot.reachable_area
    const xRange = area.x_range
    const yRange = area.y_range

    // Map physical coords to canvas
    const mapX = (x) => ((x - xRange[0]) / (xRange[1] - xRange[0])) * (w - 40) + 20
    const mapY = (y) => h - ((y - yRange[0]) / (yRange[1] - yRange[0])) * (h - 40) - 20

    // Draw reachable area
    ctx.fillStyle = 'rgba(88, 166, 255, 0.2)'
    ctx.strokeStyle = '#58a6ff'
    ctx.lineWidth = 2

    ctx.beginPath()
    ctx.rect(mapX(xRange[0]), mapY(yRange[1]),
        mapX(xRange[1]) - mapX(xRange[0]),
        mapY(yRange[0]) - mapY(yRange[1]))
    ctx.fill()
    ctx.stroke()

    // Draw calibration points if available
    if (data.points) {
        ctx.fillStyle = '#3fb950'
        for (const [physical, pixel] of data.points) {
            const x = mapX(physical[0])
            const y = mapY(physical[1])

            ctx.beginPath()
            ctx.arc(x, y, 4, 0, Math.PI * 2)
            ctx.fill()
        }
    }
}

function previewGridPoints() {
    const gridSize = parseInt(elements.gridSize?.value) || 9
    const n = Math.sqrt(gridSize)

    // Generate preview points
    const xMin = -250, xMax = -50
    const yMin = 100, yMax = 300

    const points = []
    for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
            const x = xMin + (i / (n - 1)) * (xMax - xMin)
            const y = yMin + (j / (n - 1)) * (yMax - yMin)
            points.push([x, y])
        }
    }

    // Draw on workspace canvas
    drawWorkspaceGrid()

    const ctx = workspaceCanvas.getContext('2d')
    const w = workspaceCanvas.width
    const h = workspaceCanvas.height

    ctx.fillStyle = '#d29922'
    ctx.strokeStyle = '#d29922'
    ctx.lineWidth = 1

    // Map coords
    const mapX = (x) => ((x + 300) / 350) * (w - 40) + 20
    const mapY = (y) => h - ((y - 50) / 300) * (h - 40) - 20

    for (let i = 0; i < points.length; i++) {
        const [x, y] = points[i]
        const cx = mapX(x)
        const cy = mapY(y)

        ctx.beginPath()
        ctx.arc(cx, cy, 6, 0, Math.PI * 2)
        ctx.fill()

        // Number label
        ctx.fillStyle = '#0d1117'
        ctx.font = 'bold 10px Inter'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(i + 1, cx, cy)
        ctx.fillStyle = '#d29922'
    }

    updateCalStatus(`Preview: ${gridSize} grid points`)
}

// === Calibration Data Management ===

async function loadCalibration() {
    try {
        const response = await fetch(`${API_BASE}/calibration/data`)
        if (!response.ok) {
            updateJsonPreview('No calibration data found')
            return
        }

        calibrationData = await response.json()
        updateCalibrationStats(calibrationData)
        updateJsonPreview(calibrationData)
        drawWorkspaceMap(calibrationData)

        updateCalStatus('✅ Calibration loaded')
    } catch (e) {
        console.error('Load failed:', e)
        updateJsonPreview('Failed to load calibration')
    }
}

async function saveCalibration() {
    if (!calibrationData) {
        updateCalStatus('❌ No calibration data to save')
        return
    }

    try {
        const response = await fetch(`${API_BASE}/calibration/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(calibrationData)
        })

        if (response.ok) {
            updateCalStatus('✅ Calibration saved')
        } else {
            updateCalStatus('❌ Save failed')
        }
    } catch (e) {
        updateCalStatus(`❌ Save error: ${e.message}`)
    }
}

function exportCalibration() {
    if (!calibrationData) {
        updateCalStatus('❌ No calibration data to export')
        return
    }

    const blob = new Blob([JSON.stringify(calibrationData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)

    const a = document.createElement('a')
    a.href = url
    a.download = 'calibration.json'
    a.click()

    URL.revokeObjectURL(url)
    updateCalStatus('✅ Calibration exported')
}

async function verifyCalibration() {
    updateCalStatus('Verifying calibration...')

    try {
        const response = await fetch(`${API_BASE}/calibration/verify`, {
            method: 'POST'
        })
        const result = await response.json()

        if (result.success) {
            elements.stats.meanErr.textContent = result.mean_error_mm?.toFixed(1) || '--'
            elements.stats.maxErr.textContent = result.max_error_mm?.toFixed(1) || '--'

            const status = result.mean_error_mm < 10 ? '✅' : result.mean_error_mm < 20 ? '⚠️' : '❌'
            elements.stats.status.textContent = status

            updateCalStatus(`✅ Verification: ${result.mean_error_mm?.toFixed(1)}mm mean error`)
        } else {
            updateCalStatus(`❌ ${result.error}`)
        }
    } catch (e) {
        updateCalStatus(`❌ Verification failed: ${e.message}`)
    }
}

// =============================================================================
// Robot Control Functions
// =============================================================================

function updateRobotStatus(connected, message = null) {
    const statusEl = document.getElementById('robot-status')
    if (statusEl) {
        statusEl.textContent = message || (connected ? 'Connected' : 'Disconnected')
        statusEl.className = `calibration-status ${connected ? 'active' : ''}`
    }

    // Update button states
    const connectBtn = document.getElementById('robot-connect-btn')
    const disconnectBtn = document.getElementById('robot-disconnect-btn')
    const homeBtn = document.getElementById('go-home-btn')
    const zeroBtn = document.getElementById('go-zero-btn')

    if (connectBtn) connectBtn.disabled = connected
    if (disconnectBtn) disconnectBtn.disabled = !connected
    if (homeBtn) homeBtn.disabled = !connected
    if (zeroBtn) zeroBtn.disabled = !connected

    isRobotConnected = connected
}

async function connectRobot() {
    updateRobotStatus(false, 'Connecting...')

    try {
        const response = await fetch(`${API_BASE}/robot/connect`, {
            method: 'POST'
        })
        const result = await response.json()

        if (result.success) {
            updateRobotStatus(true, `Connected: ${result.port}`)
            console.log('Robot connected:', result)
        } else {
            updateRobotStatus(false, `❌ ${result.error}`)
        }
    } catch (e) {
        updateRobotStatus(false, `❌ ${e.message}`)
    }
}

async function disconnectRobot() {
    try {
        const response = await fetch(`${API_BASE}/robot/disconnect`, {
            method: 'POST'
        })
        const result = await response.json()

        updateRobotStatus(false, 'Disconnected')
        console.log('Robot disconnected:', result)
    } catch (e) {
        updateRobotStatus(false, `❌ ${e.message}`)
    }
}

async function goHome() {
    if (!isRobotConnected) return

    updateRobotStatus(true, '🏠 Moving to Home...')

    try {
        const response = await fetch(`${API_BASE}/robot/home`, {
            method: 'POST'
        })
        const result = await response.json()

        if (result.success) {
            updateRobotStatus(true, '✅ Home position reached')
            console.log('Go Home result:', result)
        } else {
            updateRobotStatus(true, `❌ ${result.error}`)
        }
    } catch (e) {
        updateRobotStatus(true, `❌ ${e.message}`)
    }
}

async function goToZero() {
    if (!isRobotConnected) return

    updateRobotStatus(true, '📐 Moving to Zero...')

    try {
        const response = await fetch(`${API_BASE}/robot/zero`, {
            method: 'POST'
        })
        const result = await response.json()

        if (result.success) {
            updateRobotStatus(true, '✅ Zero position reached')
            console.log('Go Zero result:', result)
        } else {
            updateRobotStatus(true, `❌ ${result.error}`)
        }
    } catch (e) {
        updateRobotStatus(true, `❌ ${e.message}`)
    }
}

async function setMotionSpeed(duration) {
    try {
        const response = await fetch(`${API_BASE}/robot/speed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ duration: duration })
        })
        const result = await response.json()
        console.log('Motion speed set:', result)
    } catch (e) {
        console.error('Failed to set motion speed:', e)
    }
}
