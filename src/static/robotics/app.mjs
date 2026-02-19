// ─────────────────────────────────────────────────────────────────────────────
// Gemini Robotics Control - Main Controller
// src/static/robotics/app.mjs
//
// Architecture: <video> + SVG overlay (from verified calibration.mjs pattern)
// ─────────────────────────────────────────────────────────────────────────────

import { showToast, showSuccess, showError } from './lib/toast.mjs'
import { WebRTCHelper } from './lib/webrtc-helper.mjs'

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE = ''
const SVG_NS = 'http://www.w3.org/2000/svg'

// Original camera resolution (server capture size) — Master Scale Alignment
const ORIGINAL_WIDTH = 1920
const ORIGINAL_HEIGHT = 1080

// ─────────────────────────────────────────────────────────────────────────────
// Globals
// ─────────────────────────────────────────────────────────────────────────────

let webrtc = null
let ROLES = []

// UI Elements
const elements = {
    video: document.getElementById('camera-0'),
    overlaySvg: document.getElementById('overlay-svg'),
    resultGroup: document.getElementById('result-group'),
    connectionStatus: document.getElementById('connection-status'),
    estopBtn: document.getElementById('estop-btn'),
    promptInput: document.getElementById('prompt-input'),
    sendBtn: document.getElementById('send-prompt-btn'),
    scanBtn: document.getElementById('scan-btn'),
    executeBtn: document.getElementById('execute-btn'),
    geminiResult: document.getElementById('gemini-result'),
    taskSteps: document.getElementById('task-steps'),
    abortPlanBtn: document.getElementById('abort-plan-btn'),
}

// Current execution plan
let currentPlan = null

// Step icons for rendering
const STEP_ICONS = {
    move_arm: '🦾', open_gripper: '✋', close_gripper: '✊', go_home: '🏠'
}

// ─────────────────────────────────────────────────────────────────────────────
// Task Step Rendering
// ─────────────────────────────────────────────────────────────────────────────

function renderTaskSteps(steps) {
    if (!elements.taskSteps) return
    if (!steps || steps.length == 0) {
        elements.taskSteps.innerHTML = '<li class="step-empty">대기 중…</li>'
        return
    }
    elements.taskSteps.innerHTML = steps.map((s, i) => {
        const icon = STEP_ICONS[s.tool] || '⚙️'
        const desc = s.description || s.tool
        return `<li class="step-item" data-index="${i}" data-status="pending">${icon} ${desc}</li>`
    }).join('')
}

function updateStepStatus(index, status) {
    if (!elements.taskSteps) return
    const item = elements.taskSteps.querySelector(`[data-index="${index}"]`)
    if (!item) return
    item.dataset.status = status
    const prefix = status == 'running' ? '🔄' : status == 'done' ? '✅' : status == 'error' ? '❌' : '⏳'
    item.textContent = `${prefix} ${item.textContent.substring(2)}`
}

// ─────────────────────────────────────────────────────────────────────────────
// WebRTC Connection (from calibration.mjs:45-70)
// ─────────────────────────────────────────────────────────────────────────────

async function initWebRTC() {
    webrtc = new WebRTCHelper()

    // Bind video tracks to camera elements by role
    webrtc.on('track', (track, index, role) => {
        const roleIndex = webrtc.roles.indexOf(role)
        if (roleIndex == 0) {
            // Only bind the first role (TopView) to the main video
            if (elements.video) {
                elements.video.srcObject = new MediaStream([track])
                elements.video.play().catch(e => console.warn('Autoplay prevented:', e))
            }
        }
    })

    webrtc.on('connected', () => {
        updateConnectionStatus('connected')
        showSuccess('카메라 연결됨')
    })

    webrtc.on('disconnected', () => {
        updateConnectionStatus('disconnected')
        showError('카메라 연결 끊김')
    })

    await webrtc.connect()
    ROLES = webrtc.roles
}

// ─────────────────────────────────────────────────────────────────────────────
// Connection Status
// ─────────────────────────────────────────────────────────────────────────────

function updateConnectionStatus(state) {
    if (!elements.connectionStatus) return

    if (state == 'connected') {
        elements.connectionStatus.textContent = '● Connected'
        elements.connectionStatus.className = 'status connected'
    } else {
        elements.connectionStatus.textContent = '● Disconnected'
        elements.connectionStatus.className = 'status disconnected'
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// SVG Overlay (from calibration.mjs:241-248)
// ─────────────────────────────────────────────────────────────────────────────

function updateViewBox() {
    if (!elements.overlaySvg) return
    // Always use original camera resolution for coordinate consistency
    elements.overlaySvg.setAttribute('viewBox', `0 0 ${ORIGINAL_WIDTH} ${ORIGINAL_HEIGHT}`)
}

function clearOverlay() {
    if (!elements.resultGroup) return
    elements.resultGroup.innerHTML = ''
}

// Draw Gemini analysis result on SVG overlay
// Expects result with: coordinates [y, x] (0-1000), box_2d [ymin, xmin, ymax, xmax] (0-1000)
function drawGeminiResult(result) {
    clearOverlay()
    if (!result || !elements.resultGroup) return

    const scaleX = ORIGINAL_WIDTH / 1000
    const scaleY = ORIGINAL_HEIGHT / 1000

    // Draw bounding box if available
    if (result.box_2d && result.box_2d.length == 4) {
        const [ymin, xmin, ymax, xmax] = result.box_2d
        const x = xmin * scaleX
        const y = ymin * scaleY
        const w = (xmax - xmin) * scaleX
        const h = (ymax - ymin) * scaleY

        const rect = document.createElementNS(SVG_NS, 'rect')
        rect.setAttribute('class', 'bbox')
        rect.setAttribute('x', x)
        rect.setAttribute('y', y)
        rect.setAttribute('width', w)
        rect.setAttribute('height', h)
        elements.resultGroup.appendChild(rect)

        // Label
        const label = document.createElementNS(SVG_NS, 'text')
        label.setAttribute('class', 'bbox-label')
        label.setAttribute('x', x + 6)
        label.setAttribute('y', y - 8)
        label.textContent = result.description || 'Target'
        elements.resultGroup.appendChild(label)
    }

    // Draw center point if available
    if (result.coordinates && result.coordinates.length == 2) {
        const [py, px] = result.coordinates
        const cx = px * scaleX
        const cy = py * scaleY

        const circle = document.createElementNS(SVG_NS, 'circle')
        circle.setAttribute('class', 'center-point')
        circle.setAttribute('cx', cx)
        circle.setAttribute('cy', cy)
        circle.setAttribute('r', 10)
        elements.resultGroup.appendChild(circle)
    }

    // Draw multiple objects if available (scan result)
    if (result.objects && Array.isArray(result.objects)) {
        result.objects.forEach((obj, i) => {
            if (!obj.box_2d || obj.box_2d.length != 4) return

            const [ymin, xmin, ymax, xmax] = obj.box_2d
            const x = xmin * scaleX
            const y = ymin * scaleY
            const w = (xmax - xmin) * scaleX
            const h = (ymax - ymin) * scaleY

            const rect = document.createElementNS(SVG_NS, 'rect')
            rect.setAttribute('class', 'bbox')
            rect.setAttribute('x', x)
            rect.setAttribute('y', y)
            rect.setAttribute('width', w)
            rect.setAttribute('height', h)
            if (obj.point) {
                rect.setAttribute('stroke', '#10b981')
            }
            elements.resultGroup.appendChild(rect)

            // Label
            const label = document.createElementNS(SVG_NS, 'text')
            label.setAttribute('class', 'bbox-label')
            label.setAttribute('x', x + 6)
            label.setAttribute('y', y - 8)
            label.textContent = obj.label || `Object ${i + 1}`
            elements.resultGroup.appendChild(label)

            // Center point
            if (obj.point && obj.point.length == 2) {
                const [py, px] = obj.point
                const cx = px * scaleX
                const cy = py * scaleY

                const circle = document.createElementNS(SVG_NS, 'circle')
                circle.setAttribute('class', 'center-point')
                circle.setAttribute('cx', cx)
                circle.setAttribute('cy', cy)
                circle.setAttribute('r', 8)
                elements.resultGroup.appendChild(circle)
            }
        })
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Gemini API
// ─────────────────────────────────────────────────────────────────────────────

async function sendPrompt() {
    const instruction = elements.promptInput?.value?.trim()
    if (!instruction) {
        showError('명령을 입력해주세요')
        return
    }

    elements.sendBtn.disabled = true
    elements.sendBtn.textContent = '⏳ Analyzing...'
    elements.geminiResult.textContent = 'Analyzing...'
    clearOverlay()

    try {
        const res = await fetch(`${API_BASE}/api/gemini/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instruction })
        })
        const data = await res.json()

        if (data.error) {
            elements.geminiResult.textContent = `Error: ${data.error}`
            showError(data.error)
            return
        }

        elements.geminiResult.textContent = JSON.stringify(data, null, 2)
        drawGeminiResult(data)

        if (data.target_detected) {
            showSuccess('타겟 감지됨')
        } else {
            showToast('타겟을 찾지 못했습니다')
        }
    } catch (e) {
        elements.geminiResult.textContent = `Error: ${e.message}`
        showError(`분석 실패: ${e.message}`)
    } finally {
        elements.sendBtn.disabled = false
        elements.sendBtn.textContent = '🚀 Analyze'
    }
}

async function scanScene() {
    elements.scanBtn.disabled = true
    elements.scanBtn.textContent = '⏳ Scanning...'
    elements.geminiResult.textContent = 'Scanning scene...'
    clearOverlay()

    try {
        const res = await fetch(`${API_BASE}/api/scene/init`, {
            method: 'POST'
        })
        const data = await res.json()

        if (data.error) {
            elements.geminiResult.textContent = `Error: ${data.error}`
            showError(data.error)
            return
        }

        elements.geminiResult.textContent = JSON.stringify(data, null, 2)
        drawGeminiResult(data)
        const count = data.objects?.length || 0
        showSuccess(`${count}개 객체 감지됨`)
    } catch (e) {
        elements.geminiResult.textContent = `Error: ${e.message}`
        showError(`스캔 실패: ${e.message}`)
    } finally {
        elements.scanBtn.disabled = false
        elements.scanBtn.textContent = '🔍 Scan'
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// E-STOP
// ─────────────────────────────────────────────────────────────────────────────

async function emergencyStop() {
    try {
        const res = await fetch(`${API_BASE}/api/robot/release`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        })
        const data = await res.json()
        if (data.success) {
            showToast('🛑 E-STOP: 모든 서보 해제')
        } else {
            showError(`E-STOP 실패: ${data.error || 'Unknown error'}`)
        }
    } catch (e) {
        showError(`E-STOP 실패: ${e.message}`)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Event Listeners
// ─────────────────────────────────────────────────────────────────────────────

function initEventListeners() {
    // E-STOP
    if (elements.estopBtn) {
        elements.estopBtn.addEventListener('click', emergencyStop)
    }

    // Send prompt (analyze)
    if (elements.sendBtn) {
        elements.sendBtn.addEventListener('click', sendPrompt)
    }

    // Scan scene
    if (elements.scanBtn) {
        elements.scanBtn.addEventListener('click', scanScene)
    }

    // Execute (generate plan + start execution on server)
    if (elements.executeBtn) {
        elements.executeBtn.addEventListener('click', executeCommand)
    }

    // Abort plan (via WebSocket)
    if (elements.abortPlanBtn) {
        elements.abortPlanBtn.addEventListener('click', abortPlan)
    }

    // Enter key in prompt
    if (elements.promptInput) {
        elements.promptInput.addEventListener('keydown', (e) => {
            if (e.key == 'Enter' && !e.shiftKey) {
                e.preventDefault()
                sendPrompt()
            }
        })
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Execute Command — Server-Driven Orchestration
// ─────────────────────────────────────────────────────────────────────────────

async function executeCommand() {
    const instruction = elements.promptInput?.value?.trim()
    if (!instruction) {
        showError('명령을 입력해주세요')
        return
    }

    elements.executeBtn.disabled = true
    elements.executeBtn.textContent = '⏳ Planning...'
    elements.geminiResult.textContent = 'Generating and executing plan...'
    renderTaskSteps([])

    try {
        const res = await fetch(`${API_BASE}/api/plan/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instruction })
        })
        const data = await res.json()

        if (data.error) {
            elements.geminiResult.textContent = `Error: ${data.error}`
            showError(data.error)
            elements.executeBtn.disabled = false
            elements.executeBtn.textContent = '⚡ Execute'
            return
        }

        // Plan is now executing on server. UI updates come via WebSocket.
        if (elements.abortPlanBtn) elements.abortPlanBtn.disabled = false
        showSuccess(`Plan ${data.plan_id} 시작됨 (${data.step_count || 0}단계)`)
    } catch (e) {
        elements.geminiResult.textContent = `Error: ${e.message}`
        showError(`실행 계획 생성 실패: ${e.message}`)
        elements.executeBtn.disabled = false
        elements.executeBtn.textContent = '⚡ Execute'
    }
}

async function abortPlan() {
    showToast('⏹ 중단 요청...')
    // Send abort via WebSocket
    if (window._planWs && window._planWs.readyState == WebSocket.OPEN) {
        window._planWs.send(JSON.stringify({ type: 'plan:abort' }))
    }
    // Also E-STOP as fallback
    try {
        await fetch(`${API_BASE}/api/robot/release`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        })
    } catch (_) { }
}

// ─────────────────────────────────────────────────────────────────────────────
// WebSocket: Server-Driven Plan Progress
// ─────────────────────────────────────────────────────────────────────────────

function initPlanWebSocket() {
    const protocol = location.protocol == 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${location.host}/ws`)
    window._planWs = ws

    ws.onmessage = (event) => {
        let data
        try { data = JSON.parse(event.data) } catch { return }

        const type = data.type

        if (type == 'plan:ready') {
            currentPlan = data
            renderTaskSteps(data.steps || [])
            elements.geminiResult.textContent = JSON.stringify(data, null, 2)
            showSuccess(`${data.step_count || 0}단계 실행 계획 생성됨`)
        }

        if (type == 'step:start') {
            updateStepStatus(data.index, 'running')
            showToast(`🔄 Step ${data.index + 1}: ${data.description || data.tool}`)
        }

        if (type == 'step:done') {
            updateStepStatus(data.index, 'done')
        }

        if (type == 'step:failed') {
            updateStepStatus(data.index, 'error')
            showError(`Step ${data.index + 1} 실패: ${data.error || 'Unknown'}`)
        }

        if (type == 'step:corrected') {
            showToast(`🔧 Step ${data.index + 1} 보정 (${data.attempt}차)`)
        }

        if (type == 'plan:complete') {
            showSuccess(`실행 완료 (${data.total_time_sec}s)`)
            _resetExecuteUI()
        }

        if (type == 'plan:failed' || type == 'plan:error') {
            showError(`실행 실패: ${data.error || 'Unknown'}`)
            _resetExecuteUI()
        }

        if (type == 'plan:aborted') {
            showToast('⏹ Plan 중단됨')
            _resetExecuteUI()
        }
    }

    ws.onclose = () => {
        // Auto-reconnect after 3 seconds
        setTimeout(initPlanWebSocket, 3000)
    }
}

function _resetExecuteUI() {
    if (elements.executeBtn) {
        elements.executeBtn.disabled = false
        elements.executeBtn.textContent = '⚡ Execute'
    }
    if (elements.abortPlanBtn) elements.abortPlanBtn.disabled = true
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms))
}

// ─────────────────────────────────────────────────────────────────────────────
// Initialize (from calibration.mjs:1364-1389)
// ─────────────────────────────────────────────────────────────────────────────

async function init() {
    console.log('[app.mjs] Gemini Robotics Control initializing...')
    initEventListeners()
    updateViewBox()
    initPlanWebSocket()

    try {
        await initWebRTC()
        console.log('[app.mjs] WebRTC connected, roles:', ROLES)
    } catch (e) {
        console.error('[app.mjs] Failed to initialize WebRTC:', e)
        showError(`WebRTC 초기화 실패: ${e.message}`)
    }
}

init()
