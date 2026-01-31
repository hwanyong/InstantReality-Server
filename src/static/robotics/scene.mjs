// ─────────────────────────────────────────────────────────────────────────────
// Scene Scanner Page Controller
// src/static/robotics/scene.mjs
// ─────────────────────────────────────────────────────────────────────────────

import InstantReality from '/sdk/instant-reality.mjs'
import { showToast, showSuccess, showError } from './lib/toast.mjs'

// ─────────────────────────────────────────────────────────────────────────────
// Globals
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE = ''
let ir = null
const ROLES = ['TopView', 'QuarterView']

// Canvas elements
const topviewCanvas = document.getElementById('topview-canvas')
const topviewOverlay = document.getElementById('topview-overlay')
const quarterviewCanvas = document.getElementById('quarterview-canvas')

// UI elements
const scanBtn = document.getElementById('scan-btn')
const precisionBtn = document.getElementById('precision-btn')
const refreshBtn = document.getElementById('refresh-btn')
const scanStatus = document.getElementById('scan-status')
const objectCount = document.getElementById('object-count')
const objectList = document.getElementById('object-list')
const jsonOutput = document.getElementById('json-output')

let currentObjects = []
let roiConfig = null
let videoElements = new Map() // Store video elements for each track

// ─────────────────────────────────────────────────────────────────────────────
// WebRTC Connection
// ─────────────────────────────────────────────────────────────────────────────

async function initWebRTC() {
    ir = new InstantReality({ serverUrl: API_BASE })

    ir.on('track', (track, index) => {
        console.log(`Received track ${index} for ${ROLES[index]}`)
        setupVideoForCanvas(track, index)
    })

    ir.on('connected', () => {
        console.log('WebRTC connected')
        scanStatus.textContent = '● Connected'
    })

    ir.on('disconnected', () => {
        console.log('WebRTC disconnected')
        scanStatus.textContent = '● Disconnected'
    })

    await ir.connect({ roles: ROLES })
}

function setupVideoForCanvas(track, index) {
    const canvas = index == 0 ? topviewCanvas : quarterviewCanvas
    if (!canvas) return

    // Create hidden video element
    const video = document.createElement('video')
    video.autoplay = true
    video.muted = true
    video.playsInline = true
    video.srcObject = new MediaStream([track])
    video.style.display = 'none'
    document.body.appendChild(video)

    videoElements.set(index, video)

    const ctx = canvas.getContext('2d')

    const render = () => {
        if (video.readyState >= 2) {
            if (canvas.width != video.videoWidth || canvas.height != video.videoHeight) {
                canvas.width = video.videoWidth
                canvas.height = video.videoHeight
            }
            ctx.drawImage(video, 0, 0)

            // Redraw overlays after rendering
            if (index == 0) {
                drawROIOverlay()
                if (currentObjects.length) {
                    drawBoundingBoxes(currentObjects)
                }
            }
        }
        requestAnimationFrame(render)
    }

    video.onloadedmetadata = () => render()
}

// ─────────────────────────────────────────────────────────────────────────────
// ROI Configuration
// ─────────────────────────────────────────────────────────────────────────────

async function loadROIConfig() {
    try {
        const res = await fetch(`${API_BASE}/api/roi`)
        roiConfig = await res.json()
        console.log('ROI config loaded:', roiConfig)
        drawROIOverlay()
    } catch (err) {
        console.error('Failed to load ROI config:', err)
    }
}

function drawROIOverlay() {
    if (!roiConfig || !topviewCanvas.width) return

    const ctx = topviewOverlay.getContext('2d')
    topviewOverlay.width = topviewCanvas.width
    topviewOverlay.height = topviewCanvas.height

    const scaleX = topviewCanvas.width / 1000
    const scaleY = topviewCanvas.height / 1000

    const x = roiConfig.xmin * scaleX
    const y = roiConfig.ymin * scaleY
    const w = (roiConfig.xmax - roiConfig.xmin) * scaleX
    const h = (roiConfig.ymax - roiConfig.ymin) * scaleY

    // Draw ROI border
    ctx.strokeStyle = 'rgba(88, 166, 255, 0.8)'
    ctx.lineWidth = 2
    ctx.setLineDash([8, 4])
    ctx.strokeRect(x, y, w, h)
    ctx.setLineDash([])

    // Fill with semi-transparent
    ctx.fillStyle = 'rgba(88, 166, 255, 0.05)'
    ctx.fillRect(x, y, w, h)
}

// ─────────────────────────────────────────────────────────────────────────────
// Bounding Boxes
// ─────────────────────────────────────────────────────────────────────────────

function drawBoundingBoxes(objects) {
    const ctx = topviewOverlay.getContext('2d')
    topviewOverlay.width = topviewCanvas.width
    topviewOverlay.height = topviewCanvas.height

    // First draw ROI
    drawROIOverlay()

    const scaleX = topviewOverlay.width / 1000
    const scaleY = topviewOverlay.height / 1000

    objects.forEach((obj, i) => {
        if (!obj.box_2d || obj.box_2d.length != 4) return

        const [ymin, xmin, ymax, xmax] = obj.box_2d
        const x = xmin * scaleX
        const y = ymin * scaleY
        const w = (xmax - xmin) * scaleX
        const h = (ymax - ymin) * scaleY

        // Box
        ctx.strokeStyle = obj.point ? '#10b981' : '#58a6ff'
        ctx.lineWidth = 2
        ctx.strokeRect(x, y, w, h)

        // Draw center point if available (precision mode)
        if (obj.point) {
            const [py, px] = obj.point
            const cx = px * scaleX
            const cy = py * scaleY
            ctx.beginPath()
            ctx.arc(cx, cy, 5, 0, Math.PI * 2)
            ctx.fillStyle = '#f5576c'
            ctx.fill()
        }

        // Label background
        ctx.font = '12px Inter, sans-serif'
        const labelWidth = ctx.measureText(obj.label).width + 10
        ctx.fillStyle = obj.point ? 'rgba(16, 185, 129, 0.9)' : 'rgba(88, 166, 255, 0.8)'
        ctx.fillRect(x, y - 20, labelWidth, 20)

        // Label text
        ctx.fillStyle = '#fff'
        ctx.fillText(obj.label, x + 5, y - 6)
    })
}

// ─────────────────────────────────────────────────────────────────────────────
// Object List
// ─────────────────────────────────────────────────────────────────────────────

function renderObjectList(objects) {
    objectList.innerHTML = objects.map((obj, i) => `
        <div class="object-item">
            <span class="label">${i + 1}. ${obj.label}</span>
            <span class="strategy">${obj.point ? '🎯' : ''} ${obj.grasp_strategy || '-'}</span>
        </div>
    `).join('')

    objectCount.textContent = `${objects.length} object(s) detected`
}

// ─────────────────────────────────────────────────────────────────────────────
// Scene Scanning
// ─────────────────────────────────────────────────────────────────────────────

async function scanScene(precision = false) {
    scanBtn.disabled = true
    precisionBtn.disabled = true
    scanStatus.textContent = precision ? '● Precision Scanning...' : '● Quick Scanning...'
    scanStatus.classList.add('loading')

    const url = precision
        ? `${API_BASE}/api/scene/init?precision=true`
        : `${API_BASE}/api/scene/init`

    try {
        const res = await fetch(url, { method: 'POST' })
        const data = await res.json()

        if (data.error) {
            scanStatus.textContent = '● Error'
            jsonOutput.textContent = JSON.stringify(data, null, 2)
            showError(data.error)
            return
        }

        currentObjects = data.objects || []
        const mode = data.analysis_mode == 'precision' ? '🎯 Precision' : '⚡ Quick'
        scanStatus.textContent = `● ${mode} - ${currentObjects.length} objects`

        renderObjectList(currentObjects)
        drawBoundingBoxes(currentObjects)
        jsonOutput.textContent = JSON.stringify(data, null, 2)
        showSuccess(`${currentObjects.length}개 객체 감지됨`)
    } catch (e) {
        scanStatus.textContent = '● Error'
        showError(`스캔 실패: ${e.message}`)
    } finally {
        scanBtn.disabled = false
        precisionBtn.disabled = false
        scanStatus.classList.remove('loading')
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Refresh (capture current frame)
// ─────────────────────────────────────────────────────────────────────────────

async function refreshViews() {
    // With WebRTC, views are already live
    // Just redraw overlays
    drawROIOverlay()
    if (currentObjects.length) {
        drawBoundingBoxes(currentObjects)
    }
    showToast('뷰 새로고침됨')
}

// ─────────────────────────────────────────────────────────────────────────────
// Event Listeners
// ─────────────────────────────────────────────────────────────────────────────

scanBtn.addEventListener('click', () => scanScene(false))
precisionBtn.addEventListener('click', () => scanScene(true))
refreshBtn.addEventListener('click', refreshViews)

// ─────────────────────────────────────────────────────────────────────────────
// Initialize
// ─────────────────────────────────────────────────────────────────────────────

async function init() {
    console.log('Scene scanner initializing...')
    await loadROIConfig()

    try {
        await initWebRTC()
        scanStatus.textContent = '● Ready'
        console.log('Scene scanner ready')
    } catch (e) {
        console.error('Failed to initialize WebRTC:', e)
        scanStatus.textContent = '● WebRTC Error'
        showError(`WebRTC 초기화 실패: ${e.message}`)
    }
}

init()
