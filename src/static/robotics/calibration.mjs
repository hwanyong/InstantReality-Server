// ─────────────────────────────────────────────────────────────────────────────
// Calibration Page Controller
// src/static/robotics/calibration.mjs
// ─────────────────────────────────────────────────────────────────────────────

import { showToast, showSuccess, showError } from './lib/toast.mjs'
import { computeHomography, applyHomography, isValidHomography, computeReprojectionError, pixelToRobot } from './transform.mjs'
import { robotConnect, robotDisconnect, robotHome, robotZero, robotMoveTo, robotStatus, calculateIK, getServoConfig, getCalibrationGeometry, robotGripperOpen, robotGripperClose } from './lib/robot-api.mjs'
import { WebRTCHelper } from './lib/webrtc-helper.mjs'

// ─────────────────────────────────────────────────────────────────────────────
// Globals
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE = ''
let webrtc = null
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
    webrtc = new WebRTCHelper()

    // Bind video tracks to camera elements by role
    webrtc.on('track', (track, index, role) => {
        const roleIndex = webrtc.roles.indexOf(role)
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

    webrtc.on('connected', () => showSuccess('카메라 연결됨'))
    webrtc.on('disconnected', () => showError('카메라 연결 끊김'))

    await webrtc.connect()
    ROLES = webrtc.roles

    // Initialize pause buttons after connection
    initPauseButtons()
}

// ─────────────────────────────────────────────────────────────────────────────
// Camera Pause (Per-Client) - Role Based
// ─────────────────────────────────────────────────────────────────────────────

async function toggleCameraPause(role) {
    if (!webrtc || !webrtc.clientId) {
        showError('WebRTC 연결 필요')
        return
    }

    try {
        const paused = await webrtc.togglePause(role)
        if (paused) {
            showToast(`${role} 일시정지됨`)
        } else {
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

    if (webrtc.isRolePaused(role)) {
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
    // Test mode state
    testModeActive: false,   // when true, clicks move robot
}

// Test Mode Constants
const DEFAULT_Z = 5       // mm - height above ground
const DEFAULT_SPEED = 2   // seconds

// calculateIK is now imported from lib/robot-api.mjs

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
            if (overlayState.testModeActive) return
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
    // Always ignore clicks on test markers (let their own click handler show detail popup)
    if (e.target.closest('.test-marker')) return

    // In normal mode, ignore clicks on existing elements
    if (!overlayState.testModeActive) {
        if (e.target.closest('.vertex') || e.target.closest('.marker') || e.target.closest('.delete-btn')) {
            return
        }
    }

    const coords = getSVGCoordinates(e)
    if (!coords) return

    // Test mode: click to add point marker
    if (overlayState.testModeActive && overlayState.isCalibrated && overlayState.homographyMatrix) {
        addTestPointAtPixel(coords)
        return
    }

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
    if (overlayState.testModeActive) return
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
        const data = await getCalibrationGeometry()
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

    // 12. Enable test mode button
    enableTestModeButton()

    showSuccess('캘리브레이션(Homography) 완료!')
    console.log('Calibration results:', {
        leftBase: overlayState.leftBase,
        rightBase: overlayState.rightBase,
        sharePoint: overlayState.sharePoint,
        reprojectionError: error
    })
}


// ─────────────────────────────────────────────────────────────────────────────
// Test Mode - Move Robot to Clicked Position
// ─────────────────────────────────────────────────────────────────────────────

// Add test point marker (converts pixel to robot coords via inverse homography)
function addTestPointAtPixel(pixelCoord) {
    if (!overlayState.homographyMatrix) {
        showError('캘리브레이션이 필요합니다')
        return
    }

    try {
        // Convert pixel to robot coordinates
        const robotCoord = pixelToRobot(overlayState.homographyMatrix, pixelCoord)

        // Y-axis inversion: screen Y-down, robot Y-up
        const x = robotCoord.x
        const y = -robotCoord.y

        // Determine which arm would handle this position
        const arm = x < 0 ? 'left_arm' : 'right_arm'

        // Add visual marker with tooltip
        addTestMarker(pixelCoord, { x: x, y: y, arm: arm })

        showToast(`📍 #${testMarkers.length}: (${x.toFixed(0)}, ${y.toFixed(0)}) mm - ${arm == 'left_arm' ? '왼팔' : '오른팔'}`)
    } catch (e) {
        showError(`좌표 변환 실패: ${e.message}`)
    }
}

// Toggle test mode on/off
function toggleTestMode() {
    overlayState.testModeActive = !overlayState.testModeActive

    const btn = document.getElementById('test-mode-btn')
    const vertexBtn = document.getElementById('tool-vertex')
    const clearBtn = document.getElementById('tool-clear')
    const vertexGroup = document.getElementById('vertex-group')
    const polygon = document.getElementById('workspace-polygon')

    if (btn) {
        btn.classList.toggle('active', overlayState.testModeActive)
        btn.style.background = overlayState.testModeActive ? '#f59e0b' : ''
        btn.style.color = overlayState.testModeActive ? '#000' : ''
    }

    // Disable all vertex interactions when test mode is active
    const disabled = overlayState.testModeActive
    if (vertexBtn) {
        vertexBtn.disabled = disabled
        vertexBtn.style.opacity = disabled ? '0.5' : ''
    }
    if (clearBtn) {
        clearBtn.disabled = disabled
        clearBtn.style.opacity = disabled ? '0.5' : ''
    }
    if (vertexGroup) {
        vertexGroup.style.pointerEvents = disabled ? 'none' : ''
        vertexGroup.style.opacity = disabled ? '0.5' : ''
    }
    if (polygon) {
        polygon.style.pointerEvents = disabled ? 'none' : ''
        polygon.style.opacity = disabled ? '0.5' : ''
    }

    // Deselect vertex when entering test mode
    if (disabled) {
        overlayState.selectedVertex = null
        renderOverlay()
    }

    if (overlayState.testModeActive) {
        // Clear previous markers when re-entering test mode
        clearTestMarkers()
        showToast('🎯 테스트 모드 활성화 - 클릭하여 포인트 등록')
    } else {
        showToast('테스트 모드 비활성화')
        // Clear test markers when exiting test mode
        clearTestMarkers()
    }
}

// Setup test mode button
function setupTestModeButton() {
    const btn = document.getElementById('test-mode-btn')
    if (!btn) return

    btn.addEventListener('click', toggleTestMode)
}

// Enable test mode button (called after calibration completes)
function enableTestModeButton() {
    const btn = document.getElementById('test-mode-btn')
    if (btn) {
        btn.disabled = false
        btn.title = '클릭하여 테스트 모드 활성화'
    }
}

// Test markers storage (Single Source of Truth)
const testMarkers = []

// Add test marker data (data only, then render)
// Only keeps ONE marker - new click replaces previous
async function addTestMarker(pixelCoords, robotCoords) {
    // Clear previous markers (keep only 1)
    testMarkers.length = 0
    renderTestMarkers()  // Clear DOM

    const markerIndex = 1  // Always index 1 (single marker)

    // Get ALL data from server (Single Source of Truth)
    const res = await calculateIK(robotCoords.x, robotCoords.y, robotCoords.arm)

    if (!res || !res.success) {
        console.error('IK calculation failed:', res?.error)
        showError('IK 계산 실패')
        return
    }

    const markerData = {
        index: markerIndex,
        pixel: { x: pixelCoords.x, y: pixelCoords.y },
        world: { x: robotCoords.x, y: robotCoords.y },
        local: res.local,
        reach: res.reach,
        ik: res.ik,               // { theta1~6 }
        physical: res.physical,   // { slot1~6 }
        pulse: res.pulse,         // { slot1~6 }
        configName: res.config_name,
        ikValid: res.valid,
        arm: robotCoords.arm,
        timestamp: new Date().toISOString()
    }
    testMarkers.push(markerData)
    renderTestMarkers()

    // Get Speed from slider
    const speedSlider = document.getElementById('motion-speed')
    const motionTime = parseFloat(speedSlider?.value || 3)

    // Call move_to API to actually move the robot
    try {
        const zInput = document.getElementById('test-z-value')
        const z = parseFloat(zInput?.value || 5)
        const moveData = await robotMoveTo(robotCoords.x, robotCoords.y, z, robotCoords.arm, motionTime)

        if (moveData.success) {
            showToast(`🤖 이동 중... (${motionTime}s)`)
        } else {
            showError(`이동 실패: ${moveData.error || moveData.message}`)
        }
    } catch (err) {
        console.error('Move API error:', err)
        showError('로봇 이동 API 호출 실패')
    }
}


// Render all test markers from data (DOM is just a view)
function renderTestMarkers() {
    const svg = document.getElementById('overlay-svg')
    if (!svg) return

    // Get or create marker group with data-type
    let markerGroup = svg.querySelector('[data-marker-type="test"]')
    if (!markerGroup) {
        markerGroup = document.createElementNS(SVG_NS, 'g')
        markerGroup.setAttribute('data-marker-type', 'test')
        svg.appendChild(markerGroup)
    }

    // Clear existing markers in group
    markerGroup.innerHTML = ''

    // Render each marker from data
    testMarkers.forEach((data) => {
        const armLabel = data.arm == 'left_arm' ? '왼팔' : '오른팔'

        // Create marker circle
        const circle = document.createElementNS(SVG_NS, 'circle')
        circle.setAttribute('cx', data.pixel.x)
        circle.setAttribute('cy', data.pixel.y)
        circle.setAttribute('r', 8)
        circle.setAttribute('fill', '#f59e0b')
        circle.setAttribute('stroke', '#ffffff')
        circle.setAttribute('stroke-width', 2)
        circle.setAttribute('class', 'test-marker')
        circle.setAttribute('data-marker-index', data.index)
        circle.style.cursor = 'pointer'
        circle.style.pointerEvents = 'auto'

        // Add tooltip with World + Local + Reach + θ1
        const title = document.createElementNS(SVG_NS, 'title')
        title.textContent = `#${data.index}\nWorld: (${data.world.x.toFixed(1)}, ${data.world.y.toFixed(1)})\nLocal: (${data.local.x.toFixed(1)}, ${data.local.y.toFixed(1)})\nReach: ${data.reach.toFixed(1)} mm\nθ1: ${data.ik?.theta1?.toFixed(1) ?? '--'}°\nArm: ${armLabel}`
        circle.appendChild(title)

        // Add marker index label
        const text = document.createElementNS(SVG_NS, 'text')
        text.setAttribute('x', data.pixel.x)
        text.setAttribute('y', data.pixel.y + 4)
        text.setAttribute('text-anchor', 'middle')
        text.setAttribute('fill', '#000')
        text.setAttribute('font-size', '10')
        text.setAttribute('font-weight', 'bold')
        text.setAttribute('pointer-events', 'none')
        text.setAttribute('data-marker-index', data.index)
        text.textContent = data.index

        markerGroup.appendChild(circle)
        markerGroup.appendChild(text)

        // Add click event for detail popup
        circle.addEventListener('click', (e) => {
            e.stopPropagation()
            showMarkerDetail(data)
        })
    })
}

// Clear all test markers (data + DOM + popups)
function clearTestMarkers() {
    // 1. Clear data
    testMarkers.length = 0

    // 2. Clear DOM (find by data-marker-type)
    const svg = document.getElementById('overlay-svg')
    if (svg) {
        const group = svg.querySelector('[data-marker-type="test"]')
        if (group) group.innerHTML = ''
    }

    // 3. Close all popups
    closeMarkerDetail()
}

// Popup counter for unique IDs and positioning
let popupCounter = 0

// Show marker detail popup (stays open until closed, supports multiple)
function showMarkerDetail(markerData) {
    const armLabel = markerData.arm == 'left_arm' ? '왼팔 (Left)' : '오른팔 (Right)'
    const time = new Date(markerData.timestamp).toLocaleTimeString('ko-KR')

    // Generate unique ID and position offset
    const popupId = `marker-popup-${markerData.index}`
    const offset = (popupCounter % 5) * 30
    popupCounter++

    // Remove existing popup for same marker if any
    const existing = document.getElementById(popupId)
    if (existing) existing.remove()

    // Create popup container
    const popup = document.createElement('div')
    popup.id = popupId
    popup.className = 'marker-detail-popup'
    popup.style.cssText = `
        position: fixed;
        top: calc(30% + ${offset}px);
        left: calc(60% + ${offset}px);
        background: var(--bg-card, #1e1e2e);
        border: 2px solid #f59e0b;
        border-radius: 12px;
        padding: 0;
        min-width: 280px;
        z-index: ${10000 + popupCounter};
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        color: var(--text-primary, #fff);
        font-family: system-ui, sans-serif;
        cursor: default;
    `

    popup.innerHTML = `
        <div class="popup-header" style="
            display: flex; justify-content: space-between; align-items: center;
            padding: 12px 16px;
            background: #f59e0b;
            border-radius: 10px 10px 0 0;
            cursor: move;
        ">
            <h3 style="margin: 0; color: #000; font-size: 1rem; font-weight: 600;">📍 Point #${markerData.index}</h3>
            <button class="popup-close-btn" style="
                background: transparent;
                border: none;
                color: #000;
                font-size: 1.2rem;
                cursor: pointer;
                padding: 0 4px;
                line-height: 1;
                opacity: 0.7;
            ">&times;</button>
        </div>
        <div style="padding: 12px 16px;">
            <table style="width: 100%; font-size: 0.85rem;">
                <tr><td style="color: #888; padding: 3px 0;">Pixel</td><td style="text-align: right;"><code>(${markerData.pixel.x.toFixed(0)}, ${markerData.pixel.y.toFixed(0)})</code></td></tr>
                <tr><td colspan="2" style="border-top: 1px solid #444; padding: 6px 0 3px; color: #666; font-size: 0.75rem;">좌표 (mm)</td></tr>
                <tr><td style="color: #888; padding: 3px 0;">World</td><td style="text-align: right;"><code>(${markerData.world.x.toFixed(1)}, ${markerData.world.y.toFixed(1)})</code></td></tr>
                <tr><td style="color: #888; padding: 3px 0;">Local</td><td style="text-align: right;"><code style="color: #4ade80;">(${markerData.local.x.toFixed(1)}, ${markerData.local.y.toFixed(1)})</code></td></tr>
                <tr><td style="color: #888; padding: 3px 0;">Reach</td><td style="text-align: right;"><code style="color: #4ade80;">${markerData.reach.toFixed(1)}</code></td></tr>
                <tr><td colspan="2" style="border-top: 1px solid #444; padding: 6px 0 3px; color: #666; font-size: 0.75rem;">IK Angles (${markerData.configName || 'Unknown'})</td></tr>
                <tr><td style="color: #888; padding: 3px 0;">θ1</td><td style="text-align: right;"><code style="color: #60a5fa;">${markerData.ik?.theta1?.toFixed(1) ?? '--'}°</code></td></tr>
                <tr><td style="color: #888; padding: 3px 0;">θ2</td><td style="text-align: right;"><code style="color: #60a5fa;">${markerData.ik?.theta2?.toFixed(1) ?? '--'}°</code></td></tr>
                <tr><td style="color: #888; padding: 3px 0;">θ3</td><td style="text-align: right;"><code style="color: #60a5fa;">${markerData.ik?.theta3?.toFixed(1) ?? '--'}°</code></td></tr>
                <tr><td style="color: #888; padding: 3px 0;">θ4</td><td style="text-align: right;"><code style="color: #60a5fa;">${markerData.ik?.theta4?.toFixed(1) ?? '--'}°</code></td></tr>
                <tr><td colspan="2" style="border-top: 1px solid #444; padding: 6px 0 3px; color: #666; font-size: 0.75rem;">Physical / Pulse</td></tr>
                <tr><td style="color: #888; padding: 3px 0;">Slot 1</td><td style="text-align: right;"><code>${markerData.physical?.slot1?.toFixed(1) ?? '--'}°</code> / <code style="color: #c084fc;">${markerData.pulse?.slot1 ?? '--'}</code></td></tr>
                <tr><td style="color: #888; padding: 3px 0;">Slot 2</td><td style="text-align: right;"><code>${markerData.physical?.slot2?.toFixed(1) ?? '--'}°</code> / <code style="color: #c084fc;">${markerData.pulse?.slot2 ?? '--'}</code></td></tr>
                <tr><td style="color: #888; padding: 3px 0;">Slot 3</td><td style="text-align: right;"><code>${markerData.physical?.slot3?.toFixed(1) ?? '--'}°</code> / <code style="color: #c084fc;">${markerData.pulse?.slot3 ?? '--'}</code></td></tr>
                <tr><td style="color: #888; padding: 3px 0;">Slot 4</td><td style="text-align: right;"><code>${markerData.physical?.slot4?.toFixed(1) ?? '--'}°</code> / <code style="color: #c084fc;">${markerData.pulse?.slot4 ?? '--'}</code></td></tr>
                <tr><td style="color: #888; padding: 3px 0;">Slot 5</td><td style="text-align: right;"><code>${markerData.physical?.slot5?.toFixed(1) ?? '--'}°</code> / <code style="color: #c084fc;">${markerData.pulse?.slot5 ?? '--'}</code></td></tr>
                <tr><td style="color: #888; padding: 3px 0;">Slot 6</td><td style="text-align: right;"><code>${markerData.physical?.slot6?.toFixed(1) ?? '--'}°</code> / <code style="color: #c084fc;">${markerData.pulse?.slot6 ?? '--'}</code></td></tr>
                <tr><td colspan="2" style="border-top: 1px solid #444; padding: 6px 0 3px;"></td></tr>
                <tr><td style="color: #888; padding: 3px 0;">Arm</td><td style="text-align: right;">${armLabel}</td></tr>
                <tr><td style="color: #888; padding: 3px 0;">Valid</td><td style="text-align: right;"><span style="color: ${markerData.ikValid ? '#4ade80' : '#f87171'};">${markerData.ikValid ? '✓' : '✗'}</span></td></tr>
                <tr><td style="color: #888; padding: 3px 0;">Time</td><td style="text-align: right;">${time}</td></tr>
            </table>
        </div>
    `


    document.body.appendChild(popup)

    // Close button handler
    popup.querySelector('.popup-close-btn').addEventListener('click', () => popup.remove())

    // Drag functionality
    const header = popup.querySelector('.popup-header')
    let isDragging = false
    let dragStartX, dragStartY, popupStartX, popupStartY

    header.addEventListener('mousedown', (e) => {
        if (e.target.classList.contains('popup-close-btn')) return
        isDragging = true
        dragStartX = e.clientX
        dragStartY = e.clientY
        popupStartX = popup.offsetLeft
        popupStartY = popup.offsetTop
        popup.style.zIndex = 10000 + (++popupCounter)
    })

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return
        popup.style.left = (popupStartX + e.clientX - dragStartX) + 'px'
        popup.style.top = (popupStartY + e.clientY - dragStartY) + 'px'
    })

    document.addEventListener('mouseup', () => {
        isDragging = false
    })
}

// Close all marker detail popups
function closeMarkerDetail() {
    document.querySelectorAll('.marker-detail-popup').forEach(p => p.remove())
    popupCounter = 0
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

        // Enable test mode button if calibration is valid
        if (overlayState.isCalibrated) {
            enableTestModeButton()
        }

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

    // Capture All button - download all camera FHD frames as ZIP
    const captureAllBtn = document.getElementById('capture-all-btn')
    if (captureAllBtn) {
        captureAllBtn.addEventListener('click', async () => {
            captureAllBtn.disabled = true
            captureAllBtn.textContent = '⏳ Capturing...'
            try {
                const res = await fetch('/api/capture_all')
                if (!res.ok) throw new Error(`HTTP ${res.status}`)
                const blob = await res.blob()
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = res.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || 'capture.zip'
                a.click()
                URL.revokeObjectURL(url)
                showSuccess('캡쳐 다운로드 완료')
            } catch (e) {
                showError(`캡쳐 실패: ${e.message}`)
            } finally {
                captureAllBtn.disabled = false
                captureAllBtn.textContent = '📸 Capture'
            }
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
        servoConfig = await getServoConfig()
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
// Robot Control
// ─────────────────────────────────────────────────────────────────────────────

function initRobotControl() {
    const connectBtn = document.getElementById('robot-connect-btn')
    const disconnectBtn = document.getElementById('robot-disconnect-btn')
    const homeBtn = document.getElementById('go-home-btn')
    const zeroBtn = document.getElementById('go-zero-btn')
    const statusSpan = document.getElementById('robot-status')
    const speedSlider = document.getElementById('motion-speed')
    const speedValue = document.getElementById('speed-value')

    if (!connectBtn) return // Robot Control tab not present

    // Speed slider update
    if (speedSlider && speedValue) {
        speedSlider.addEventListener('input', () => {
            speedValue.textContent = `${speedSlider.value}s`
        })
    }

    // Connect button
    connectBtn.addEventListener('click', async () => {
        connectBtn.disabled = true
        statusSpan.textContent = 'Connecting...'

        try {
            const data = await robotConnect()

            if (data.success) {
                statusSpan.textContent = 'Connected'
                statusSpan.className = 'robot-status-inline connected'
                disconnectBtn.disabled = false
                homeBtn.disabled = false
                document.querySelectorAll('#gripper-open-left, #gripper-close-left, #gripper-open-right, #gripper-close-right').forEach(b => b.disabled = false)
                zeroBtn.disabled = false
                connectBtn.disabled = true
            } else {
                statusSpan.textContent = data.error || 'Connection failed'
                connectBtn.disabled = false
            }
        } catch (e) {
            console.error('Robot connect error:', e)
            statusSpan.textContent = 'Error'
            connectBtn.disabled = false
        }
    })

    // Disconnect button
    disconnectBtn.addEventListener('click', async () => {
        try {
            await robotDisconnect()
            statusSpan.textContent = 'Disconnected'
            statusSpan.className = 'robot-status-inline'
            disconnectBtn.disabled = true
            homeBtn.disabled = true
            document.querySelectorAll('#gripper-open-left, #gripper-close-left, #gripper-open-right, #gripper-close-right').forEach(b => b.disabled = true)
            zeroBtn.disabled = true
            connectBtn.disabled = false
        } catch (e) {
            console.error('Robot disconnect error:', e)
        }
    })

    // Home button
    homeBtn.addEventListener('click', async () => {
        const motionTime = parseFloat(speedSlider?.value || 3)
        homeBtn.disabled = true
        homeBtn.textContent = '🏠 Moving...'

        try {
            const data = await robotHome(motionTime)

            if (data.success) {
                console.log('Home position reached')
            } else {
                console.error('Home failed:', data.error)
            }
        } catch (e) {
            console.error('Home error:', e)
        } finally {
            homeBtn.disabled = false
            homeBtn.textContent = '🏠 Home'
        }
    })

    // Zero button
    zeroBtn.addEventListener('click', async () => {
        const motionTime = parseFloat(speedSlider?.value || 3)
        zeroBtn.disabled = true
        zeroBtn.textContent = '📐 Moving...'

        try {
            const data = await robotZero(motionTime)

            if (data.success) {
                console.log('Zero position reached')
            } else {
                console.error('Zero failed:', data.error)
            }
        } catch (e) {
            console.error('Zero error:', e)
        } finally {
            zeroBtn.disabled = false
            zeroBtn.textContent = '📐 Zero'
        }
    })

    // Z height range ↔ number input sync
    const zRange = document.getElementById('test-z-range')
    const zValue = document.getElementById('test-z-value')
    if (zRange && zValue) {
        zRange.addEventListener('input', () => { zValue.value = zRange.value })
        zValue.addEventListener('input', () => {
            const v = Math.max(-10, Math.min(100, parseInt(zValue.value) || 0))
            zRange.value = v
        })
    }

    // Gripper buttons
    const gripperBtns = [
        { id: 'gripper-open-left', fn: () => robotGripperOpen('left'), label: '🤚 L Open' },
        { id: 'gripper-close-left', fn: () => robotGripperClose('left'), label: '✊ L Close' },
        { id: 'gripper-open-right', fn: () => robotGripperOpen('right'), label: '🤚 R Open' },
        { id: 'gripper-close-right', fn: () => robotGripperClose('right'), label: '✊ R Close' },
    ]
    gripperBtns.forEach(({ id, fn, label }) => {
        const btn = document.getElementById(id)
        if (!btn) return
        btn.addEventListener('click', async () => {
            btn.disabled = true
            btn.textContent = '⏳'
            try {
                const res = await fn()
                if (res.success) {
                    showToast(res.message || `${label} 완료`)
                } else {
                    showError(res.error || `${label} 실패`)
                }
            } catch (e) {
                showError(`Gripper 오류: ${e.message}`)
            } finally {
                btn.disabled = false
                btn.textContent = label
            }
        })
    })

    // Check initial status
    fetchRobotStatus()
}

async function fetchRobotStatus() {
    try {
        const data = await robotStatus()

        if (data.success && data.status) {
            const isConnected = data.status.connected
            const statusSpan = document.getElementById('robot-status')
            const connectBtn = document.getElementById('robot-connect-btn')
            const disconnectBtn = document.getElementById('robot-disconnect-btn')
            const homeBtn = document.getElementById('go-home-btn')
            const zeroBtn = document.getElementById('go-zero-btn')

            if (isConnected) {
                statusSpan.textContent = 'Connected'
                statusSpan.className = 'robot-status-inline connected'
                connectBtn.disabled = true
                disconnectBtn.disabled = false
                homeBtn.disabled = false
                zeroBtn.disabled = false
                document.querySelectorAll('#gripper-open-left, #gripper-close-left, #gripper-open-right, #gripper-close-right').forEach(b => b.disabled = false)
            } else {
                statusSpan.textContent = 'Disconnected'
                statusSpan.className = 'robot-status-inline'
            }
        }
    } catch (e) {
        console.error('Status check failed:', e)
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
    setupTestModeButton()
    initRobotControl()

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
