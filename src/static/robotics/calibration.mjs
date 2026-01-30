/**
 * Calibration Page JavaScript Module
 * 
 * Handles:
 * - Auto-calibration workflow control
 * - Workspace visualization
 * - Calibration data management
 * - Real-time progress updates
 */

// Configuration
const API_BASE = '/api'
const WS_URL = `ws://${location.host}/ws`

// State
let ws = null
let isCalibrating = false
let calibrationData = null
let videoCanvas = null
let arCanvas = null
let workspaceCanvas = null

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

    // Setup canvases
    setupCanvases()

    // Connect WebSocket
    connectWebSocket()

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

function setupCanvases() {
    videoCanvas = document.getElementById('video-canvas')
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

function connectWebSocket() {
    try {
        ws = new WebSocket(WS_URL)

        ws.onopen = () => {
            updateConnectionStatus(true)
            console.log('WebSocket connected')
        }

        ws.onclose = () => {
            updateConnectionStatus(false)
            console.log('WebSocket disconnected')
            // Reconnect after delay
            setTimeout(connectWebSocket, 3000)
        }

        ws.onmessage = handleMessage

        ws.onerror = (err) => {
            console.error('WebSocket error:', err)
        }
    } catch (e) {
        console.error('WebSocket connection failed:', e)
        updateConnectionStatus(false)
    }
}

function updateConnectionStatus(connected) {
    if (elements.connectionStatus) {
        elements.connectionStatus.textContent = connected ? '● Connected' : '● Disconnected'
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

    const gridSize = parseInt(elements.gridSize?.value) || 9
    const zHeight = parseFloat(elements.calZ?.value) || 120

    isCalibrating = true
    elements.startBtn.disabled = true
    elements.stopBtn.disabled = false

    updateCalStatus('Starting calibration...')
    updateProgress({ step: 0, total: 4 + gridSize, message: 'Initializing...' })

    try {
        const response = await fetch(`${API_BASE}/calibration/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ grid_size: gridSize, z_height: zHeight })
        })

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`)
        }

        const result = await response.json()
        console.log('Calibration started:', result)

    } catch (e) {
        console.error('Failed to start calibration:', e)
        onCalibrationError({ message: e.message })
    }
}

function stopCalibration() {
    if (!isCalibrating) return

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

async function captureFrame() {
    try {
        const response = await fetch(`${API_BASE}/camera/capture`)
        const blob = await response.blob()
        const img = await createImageBitmap(blob)

        const ctx = videoCanvas.getContext('2d')
        ctx.drawImage(img, 0, 0, videoCanvas.width, videoCanvas.height)
    } catch (e) {
        console.error('Capture failed:', e)
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
