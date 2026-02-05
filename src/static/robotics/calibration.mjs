// ─────────────────────────────────────────────────────────────────────────────
// Calibration Page Controller
// src/static/robotics/calibration.mjs
// ─────────────────────────────────────────────────────────────────────────────

import InstantReality from '/sdk/instant-reality.mjs'
import { showToast, showSuccess, showError } from './lib/toast.mjs'
import { computeHomography, applyHomography, isValidHomography, computeReprojectionError } from './transform.mjs'

// ─────────────────────────────────────────────────────────────────────────────
// Globals
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE = ''
let ir = null
// ROLES is now dynamically fetched from server (not hardcoded)
let ROLES = []

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

    // 1. Fetch role mapping from server FIRST (dynamic, not hardcoded)
    try {
        const roleMap = await ir.getRoles()
        // Get only connected roles in defined order
        const orderedRoles = ['TopView', 'QuarterView', 'RightRobot', 'LeftRobot']
        ROLES = orderedRoles.filter(r => roleMap[r] && roleMap[r].connected)
        console.log('Dynamic ROLES from server:', ROLES, roleMap)
    } catch (err) {
        console.error('Failed to fetch roles, using fallback:', err)
        ROLES = ['TopView', 'QuarterView', 'RightRobot', 'LeftRobot']
    }

    ir.on('track', (track, index, roleName) => {
        // roleName is now provided by server - trustworthy
        const role = roleName || ROLES[index]
        console.log(`Received track ${index}, mapped to role: ${role}`)

        // Find correct video element by role
        const roleIndex = ROLES.indexOf(role)

        if (roleIndex !== -1) {
            const video = elements.cameras[roleIndex]
            if (video) {
                video.srcObject = new MediaStream([track])
                video.play().catch(e => console.warn('Autoplay prevented:', e))
            }
        } else {
            console.warn(`Unknown role: ${role}`)
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

    // 2. Connect with dynamically fetched roles
    await ir.connect({ roles: ROLES })

    // Initialize pause buttons after connection
    initPauseButtons()
}

// ─────────────────────────────────────────────────────────────────────────────
// Camera Pause (Per-Client) - Role Based
// ─────────────────────────────────────────────────────────────────────────────

const pausedRoles = new Set()

async function toggleCameraPause(role) {
    if (!ir || !ir.clientId) {
        showError('WebRTC 연결 필요')
        return
    }

    const paused = !pausedRoles.has(role)

    try {
        const res = await fetch(`${API_BASE}/pause_camera_client`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                client_id: ir.clientId,
                role: role,
                paused: paused
            })
        })

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`)
        }

        if (paused) {
            pausedRoles.add(role)
            showToast(`${role} 일시정지됨`)
        } else {
            pausedRoles.delete(role)
            showToast(`${role} 재개됨`)
        }

        updatePauseButtonState(role)
    } catch (e) {
        console.error('Failed to toggle pause:', e)
        showError(`일시정지 실패: ${e.message}`)
    }
}

function updatePauseButtonState(role) {
    const btn = document.querySelector(`.pause-btn[data-role="${role}"]`)
    if (!btn) return

    if (pausedRoles.has(role)) {
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
            const role = btn.dataset.role
            if (role) {
                toggleCameraPause(role)
            }
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
// SVG Overlay - State & DOM Manipulation
// ─────────────────────────────────────────────────────────────────────────────

const overlayState = {
    tool: 'vertex',  // 'vertex' only (base markers are auto-calculated)
    vertices: [],    // [{x, y}, ...] - viewBox (original video) coordinates
    leftBase: null,  // {x, y} - auto-calculated from homography
    rightBase: null, // {x, y} - auto-calculated from homography
    sharePoint: null,    // {x, y} - auto-calculated (origin in robot coords)
    selectedVertex: null,  // index of selected vertex
    isDragging: false,
    dragStart: null,  // {x, y} - for click vs drag detection
    // Calibration state
    homographyMatrix: null,  // 3x3 matrix
    isCalibrated: false,
    robotGeometry: null,     // cached geometry from server
}

const SVG_NS = 'http://www.w3.org/2000/svg'
const VERTEX_RADIUS = 8
const VERTEX_SELECTED_RADIUS = 12
const MARKER_RADIUS = 12
const DELETE_BTN_OFFSET = { x: 25, y: -25 }
const DELETE_BTN_RADIUS = 12

// Get SVG coordinates from mouse event (auto-transforms via getScreenCTM)
function getSVGCoordinates(event) {
    const svg = document.getElementById('overlay-svg')
    if (!svg) return null

    const pt = svg.createSVGPoint()
    pt.x = event.clientX
    pt.y = event.clientY

    const ctm = svg.getScreenCTM()
    if (!ctm) return null

    return pt.matrixTransform(ctm.inverse())
}

// Original camera resolution (server capture size)
const ORIGINAL_WIDTH = 1920
const ORIGINAL_HEIGHT = 1080

// Update SVG viewBox to match original camera resolution (not WebRTC stream size)
function updateViewBox() {
    const svg = document.getElementById('overlay-svg')
    if (!svg) return

    // Always use original camera resolution for coordinate consistency
    svg.setAttribute('viewBox', `0 0 ${ORIGINAL_WIDTH} ${ORIGINAL_HEIGHT}`)
}

// Update polygon points attribute
function updatePolygonPoints() {
    const polygon = document.getElementById('workspace-polygon')
    if (!polygon) return

    const points = overlayState.vertices.map(v => `${v.x},${v.y}`).join(' ')
    polygon.setAttribute('points', points)
}

// Create a vertex circle element
function createVertexCircle(x, y, index) {
    const circle = document.createElementNS(SVG_NS, 'circle')
    circle.setAttribute('cx', x)
    circle.setAttribute('cy', y)
    circle.setAttribute('r', VERTEX_RADIUS)
    circle.setAttribute('class', 'vertex')
    circle.setAttribute('data-index', index)

    // Create label
    const label = document.createElementNS(SVG_NS, 'text')
    label.setAttribute('x', x)
    label.setAttribute('y', y)
    label.setAttribute('class', 'vertex-label')
    label.textContent = index + 1

    return { circle, label }
}

// Create a delete button for selected vertex
function createDeleteButton(x, y) {
    const g = document.createElementNS(SVG_NS, 'g')
    g.setAttribute('class', 'delete-group')

    const btnX = x + DELETE_BTN_OFFSET.x
    const btnY = y + DELETE_BTN_OFFSET.y

    const circle = document.createElementNS(SVG_NS, 'circle')
    circle.setAttribute('cx', btnX)
    circle.setAttribute('cy', btnY)
    circle.setAttribute('r', DELETE_BTN_RADIUS)
    circle.setAttribute('class', 'delete-btn')

    const text = document.createElementNS(SVG_NS, 'text')
    text.setAttribute('x', btnX)
    text.setAttribute('y', btnY)
    text.setAttribute('class', 'marker-label')
    text.textContent = '×'

    g.appendChild(circle)
    g.appendChild(text)

    // Delete click handler
    circle.addEventListener('click', (e) => {
        e.stopPropagation()
        if (overlayState.selectedVertex != null) {
            overlayState.vertices.splice(overlayState.selectedVertex, 1)
            overlayState.selectedVertex = null
            renderOverlay()
        }
    })

    return g
}

// Create a marker element (base or gripper)
function createMarkerElement(type, pos, color, labelText) {
    const g = document.createElementNS(SVG_NS, 'g')
    g.setAttribute('class', 'marker')
    g.setAttribute('data-type', type)

    const circle = document.createElementNS(SVG_NS, 'circle')
    circle.setAttribute('cx', pos.x)
    circle.setAttribute('cy', pos.y)
    circle.setAttribute('r', MARKER_RADIUS)
    circle.setAttribute('fill', color)
    circle.setAttribute('stroke', '#fff')
    circle.setAttribute('stroke-width', '2')

    const label = document.createElementNS(SVG_NS, 'text')
    label.setAttribute('x', pos.x)
    label.setAttribute('y', pos.y)
    label.setAttribute('class', 'marker-label')
    label.textContent = labelText

    g.appendChild(circle)
    g.appendChild(label)

    return g
}

// Render entire overlay (vertices, polygon, markers)
function renderOverlay() {
    const vertexGroup = document.getElementById('vertex-group')
    const markerGroup = document.getElementById('marker-group')
    if (!vertexGroup || !markerGroup) return

    // Clear existing elements
    vertexGroup.innerHTML = ''
    markerGroup.innerHTML = ''

    // Update polygon
    updatePolygonPoints()

    // Render vertices
    overlayState.vertices.forEach((v, i) => {
        const { circle, label } = createVertexCircle(v.x, v.y, i)

        if (overlayState.selectedVertex == i) {
            circle.classList.add('selected')
            circle.setAttribute('r', VERTEX_SELECTED_RADIUS)

            // Add dragging effect when currently being dragged
            if (overlayState.isDragging) {
                circle.classList.add('dragging')
            }
        }

        // Vertex click handler
        circle.addEventListener('mousedown', (e) => {
            e.stopPropagation()
            const coords = getSVGCoordinates(e)
            if (!coords) return

            overlayState.dragStart = { x: coords.x, y: coords.y }
            overlayState.selectedVertex = i
            overlayState.isDragging = true
            renderOverlay()
        })

        vertexGroup.appendChild(circle)
        vertexGroup.appendChild(label)
    })

    // Add delete button for selected vertex
    if (overlayState.selectedVertex != null && overlayState.vertices[overlayState.selectedVertex]) {
        const v = overlayState.vertices[overlayState.selectedVertex]
        const deleteBtn = createDeleteButton(v.x, v.y)
        vertexGroup.appendChild(deleteBtn)
    }

    // Render markers
    // Share point (auto-calculated, shown in green)
    if (overlayState.sharePoint && overlayState.isCalibrated) {
        const marker = createMarkerElement('share-point', overlayState.sharePoint, '#22c55e', '●')
        marker.classList.add('calibrated-marker')
        markerGroup.appendChild(marker)
    }
    // Base markers (auto-calculated)
    if (overlayState.leftBase) {
        const marker = createMarkerElement('left-base', overlayState.leftBase, '#ff6b6b', 'L')
        if (overlayState.isCalibrated) marker.classList.add('calibrated-marker')
        markerGroup.appendChild(marker)
    }
    if (overlayState.rightBase) {
        const marker = createMarkerElement('right-base', overlayState.rightBase, '#4dabf7', 'R')
        if (overlayState.isCalibrated) marker.classList.add('calibrated-marker')
        markerGroup.appendChild(marker)
    }
}

// Handle SVG background click (add vertex only - base/share are auto-calculated)
function handleSVGClick(e) {
    // Ignore if clicking on existing element
    if (e.target.closest('.vertex') || e.target.closest('.marker') || e.target.closest('.delete-btn')) {
        return
    }

    const coords = getSVGCoordinates(e)
    if (!coords) return

    // Only vertex tool is interactive
    if (overlayState.tool == 'vertex') {
        overlayState.vertices.push({ x: coords.x, y: coords.y })
        overlayState.selectedVertex = null
        // Clear calibration when vertices change
        overlayState.isCalibrated = false
        overlayState.homographyMatrix = null
    }

    renderOverlay()
}

// Handle mouse move for dragging
function handleSVGMouseMove(e) {
    if (!overlayState.isDragging || overlayState.selectedVertex == null) return

    const coords = getSVGCoordinates(e)
    if (!coords) return

    overlayState.vertices[overlayState.selectedVertex] = { x: coords.x, y: coords.y }
    renderOverlay()
}

// Handle mouse up (end drag or click)
function handleSVGMouseUp(e) {
    const coords = getSVGCoordinates(e)
    const start = overlayState.dragStart
    const wasDragging = overlayState.isDragging

    overlayState.isDragging = false
    overlayState.dragStart = null

    if (!coords || !start) return

    // Calculate drag distance
    const distance = Math.sqrt((coords.x - start.x) ** 2 + (coords.y - start.y) ** 2)

    // If dragged more than 5 units, it was a drag - don't process as click
    if (distance > 5) return

    // If was dragging vertex, don't add new vertex
    if (wasDragging) return

    // Handle click on background (add new element)
    handleSVGClick(e)
}

function initOverlayTools() {
    const toolbar = document.getElementById('overlay-toolbar')
    const svg = document.getElementById('overlay-svg')
    const video = document.getElementById('camera-0')

    if (!toolbar) return

    // Tool selection
    toolbar.querySelectorAll('.tool-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tool = btn.dataset.tool
            if (!tool) return

            toolbar.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'))
            btn.classList.add('active')
            overlayState.tool = tool
            overlayState.selectedVertex = null
            renderOverlay()
        })
    })

    // Clear button
    const clearBtn = document.getElementById('tool-clear')
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            overlayState.vertices = []
            overlayState.leftBase = null
            overlayState.rightBase = null
            overlayState.sharePoint = null
            overlayState.selectedVertex = null
            overlayState.homographyMatrix = null
            overlayState.isCalibrated = false
            renderOverlay()
            showSuccess('오버레이 초기화됨')
        })
    }

    // Calculate button - trigger homography calibration
    const calcBtn = document.getElementById('calc-btn')
    if (calcBtn) {
        calcBtn.addEventListener('click', runCalibration)
    }

    // SVG events
    if (svg) {
        svg.addEventListener('mousedown', (e) => {
            const coords = getSVGCoordinates(e)
            if (coords) {
                overlayState.dragStart = { x: coords.x, y: coords.y }
            }
        })
        svg.addEventListener('mousemove', handleSVGMouseMove)
        svg.addEventListener('mouseup', handleSVGMouseUp)
        svg.addEventListener('mouseleave', () => {
            overlayState.isDragging = false
            overlayState.dragStart = null
        })

        // Click on polygon to deselect
        const polygon = document.getElementById('workspace-polygon')
        if (polygon) {
            polygon.addEventListener('click', (e) => {
                // Only deselect, don't add vertex when clicking polygon
                if (overlayState.selectedVertex != null) {
                    overlayState.selectedVertex = null
                    renderOverlay()
                    e.stopPropagation()
                }
            })
        }
    }

    // Update viewBox when video loads
    if (video) {
        video.addEventListener('loadedmetadata', () => {
            updateViewBox()
            renderOverlay()
        })
        // Try immediately in case already loaded
        if (video.videoWidth && video.videoHeight) {
            updateViewBox()
        }
    }
}

function getOverlayData() {
    return {
        workspace: { vertices: overlayState.vertices },
        robotBases: {
            left: overlayState.leftBase,
            right: overlayState.rightBase
        },
        sharePoint: overlayState.sharePoint,
        calibration: {
            isCalibrated: overlayState.isCalibrated,
            homographyMatrix: overlayState.homographyMatrix
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Calibration - Homography with Coordinate Normalization
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Normalize robot coordinates to match pixel coordinate system orientation.
 * Robot: +X=right, +Y=up  -->  Normalized: +X=right, +Y=down (same as screen)
 * @param {{x: number, y: number}} robotPoint
 * @returns {[number, number]} [normalizedX, normalizedY]
 */
function normalizeRobotCoord(robotPoint) {
    // Robot +X (right) -> Normalized +X (right in screen) - same direction
    // Robot +Y (up) -> Normalized -Y (down in screen) - inverted
    // 
    // After analysis: Robot and Screen share the same X axis direction.
    // Only Y axis needs inversion.
    return [robotPoint.x, -robotPoint.y]
}

/**
 * Fetch geometry data from servo_config.json via server API
 */
async function fetchGeometry() {
    try {
        const res = await fetch(`${API_BASE}/api/calibration/geometry`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        overlayState.robotGeometry = data
        return data
    } catch (e) {
        showError(`Geometry 로드 실패: ${e.message}`)
        return null
    }
}

/**
 * Run calibration: compute homography from 4 vertices and auto-display base/share markers
 */
async function runCalibration() {
    // 1. Validate vertex count
    if (overlayState.vertices.length < 4) {
        showError(`최소 4개의 Vertex가 필요합니다 (현재: ${overlayState.vertices.length}개)`)
        return
    }

    showToast('캘리브레이션 계산 중...')

    // 2. Fetch geometry from server
    const geometry = await fetchGeometry()
    if (!geometry || !geometry.vertices || !geometry.bases) {
        showError('서버에서 geometry 데이터를 가져올 수 없습니다')
        return
    }

    // 3. Prepare pixel points (from UI)
    const pixelPoints = overlayState.vertices.slice(0, 4).map(v => [v.x, v.y])

    // 4. Prepare normalized robot points (transform to match screen orientation)
    // Robot: +X=right, +Y=up  -->  Normalized: +X=right, -Y=up
    const normalizedRobotPoints = []
    for (let i = 1; i <= 4; i++) {
        const vertex = geometry.vertices[String(i)]
        if (!vertex) {
            showError(`Vertex ${i}이(가) servo_config.json에 없습니다`)
            return
        }
        normalizedRobotPoints.push(normalizeRobotCoord({ x: vertex.x, y: vertex.y }))
    }

    console.log('Calibration input:', {
        pixelPoints,
        normalizedRobotPoints
    })

    // 5. Compute Homography (normalized robot -> pixel)
    // NOTE: We compute in this direction so we can apply H directly (no inverse needed)
    let H
    try {
        H = computeHomography(normalizedRobotPoints, pixelPoints)
    } catch (e) {
        showError(`Homography 계산 실패: ${e.message}`)
        return
    }

    // 6. Validate homography
    if (!isValidHomography(H)) {
        showError('유효하지 않은 Homography 행렬입니다. Vertex 위치를 확인하세요.')
        return
    }

    // 7. Compute reprojection error (robot -> pixel direction)
    const error = computeReprojectionError(H, normalizedRobotPoints, pixelPoints)
    console.log(`Calibration reprojection error: ${error.toFixed(4)}`)

    // 8. Store homography
    overlayState.homographyMatrix = H

    // 9. Transform base and share point coords: normalized robot -> pixel
    // Using applyHomography directly (not inverse)
    try {
        const leftBaseNorm = normalizeRobotCoord(geometry.bases.left_arm)
        const rightBaseNorm = normalizeRobotCoord(geometry.bases.right_arm)
        const sharePointNorm = normalizeRobotCoord({ x: 0, y: 0 })

        console.log('Normalized coords:', { leftBaseNorm, rightBaseNorm, sharePointNorm })

        overlayState.leftBase = applyHomography(H, { x: leftBaseNorm[0], y: leftBaseNorm[1] })
        overlayState.rightBase = applyHomography(H, { x: rightBaseNorm[0], y: rightBaseNorm[1] })
        overlayState.sharePoint = applyHomography(H, { x: sharePointNorm[0], y: sharePointNorm[1] })
    } catch (e) {
        showError(`변환 실패: ${e.message}`)
        return
    }

    // 10. Mark as calibrated and render
    overlayState.isCalibrated = true
    overlayState.reprojectionError = error
    renderOverlay()

    // 11. Auto-save calibration data
    await saveCalibration()

    showSuccess('캘리브레이션(Homography) 완료!')
    console.log('Calibration results:', {
        leftBase: overlayState.leftBase,
        rightBase: overlayState.rightBase,
        sharePoint: overlayState.sharePoint,
        reprojectionError: error
    })
}


// ─────────────────────────────────────────────────────────────────────────────
// Calibration Data Persistence
// ─────────────────────────────────────────────────────────────────────────────

async function saveCalibration() {
    const calibration = {
        timestamp: new Date().toISOString(),
        resolution: {
            width: ORIGINAL_WIDTH,
            height: ORIGINAL_HEIGHT
        },
        homography_matrix: overlayState.homographyMatrix,
        pixel_coords: {
            vertices: overlayState.vertices.reduce((acc, v, i) => {
                acc[String(i + 1)] = { x: v.x, y: v.y }
                return acc
            }, {}),
            share_point: overlayState.sharePoint,
            bases: {
                left_arm: overlayState.leftBase,
                right_arm: overlayState.rightBase
            }
        },
        reprojection_error: overlayState.reprojectionError || 0,
        is_valid: overlayState.isCalibrated
    }

    try {
        const res = await fetch(`${API_BASE}/api/calibration`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role: 'TopView', calibration })
        })
        if (!res.ok) throw new Error(`Save failed: ${res.status}`)
        console.log('Calibration data auto-saved')
    } catch (e) {
        console.error('Failed to save calibration:', e)
        showError(`캘리브레이션 저장 실패: ${e.message}`)
    }
}

async function loadCalibration() {
    try {
        const res = await fetch(`${API_BASE}/api/calibration/TopView`)
        if (!res.ok) {
            if (res.status == 404) {
                console.log('No saved calibration data found')
                return false
            }
            throw new Error(`Load failed: ${res.status}`)
        }

        const cal = await res.json()

        // Resolution mismatch warning (check against original camera resolution)
        if (cal.resolution) {
            if (cal.resolution.width != ORIGINAL_WIDTH ||
                cal.resolution.height != ORIGINAL_HEIGHT) {
                showToast(`저장된 해상도(${cal.resolution.width}x${cal.resolution.height})가 현재 카메라 해상도(${ORIGINAL_WIDTH}x${ORIGINAL_HEIGHT})와 다릅니다. 재캘리브레이션 권장`, 'warning')
            }
        }

        // Restore state
        if (cal.pixel_coords) {
            const verts = cal.pixel_coords.vertices
            overlayState.vertices = ['1', '2', '3', '4']
                .filter(k => verts[k])
                .map(k => ({ x: verts[k].x, y: verts[k].y }))

            overlayState.sharePoint = cal.pixel_coords.share_point
            overlayState.leftBase = cal.pixel_coords.bases?.left_arm
            overlayState.rightBase = cal.pixel_coords.bases?.right_arm
        }

        overlayState.homographyMatrix = cal.homography_matrix
        overlayState.reprojectionError = cal.reprojection_error
        overlayState.isCalibrated = cal.is_valid

        renderOverlay()
        console.log('Calibration data restored from server')
        showSuccess('저장된 캘리브레이션 복원 완료')
        return true
    } catch (e) {
        console.error('Failed to load calibration:', e)
        return false
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

// NOTE: Canvas resize logic removed - SVG viewBox handles automatic scaling

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

    // Load servo config for JSON preview
    await loadServoConfig()

    try {
        await initWebRTC()
        console.log('Calibration page ready')

        // Auto-restore calibration data (after video is ready)
        setTimeout(async () => {
            await loadCalibration()
        }, 500)
    } catch (e) {
        console.error('Failed to initialize WebRTC:', e)
        showError(`WebRTC 초기화 실패: ${e.message}`)
    }
}

init()
