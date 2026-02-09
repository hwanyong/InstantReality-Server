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
const SAFE_HEIGHT = 50  // mm above table for safe approach/ascend
const MAX_VERIFY_RETRIES = 3  // max correction attempts per step
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
    runPlanBtn: document.getElementById('run-plan-btn'),
    abortPlanBtn: document.getElementById('abort-plan-btn'),
}

// Current execution plan
let currentPlan = null
let planAborted = false

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

    // Execute (generate plan)
    if (elements.executeBtn) {
        elements.executeBtn.addEventListener('click', executeCommand)
    }

    // Run plan
    if (elements.runPlanBtn) {
        elements.runPlanBtn.addEventListener('click', runPlan)
    }

    // Abort plan
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
// Execute Command (Function Calling)
// ─────────────────────────────────────────────────────────────────────────────

async function executeCommand() {
    const instruction = elements.promptInput?.value?.trim()
    if (!instruction) {
        showError('명령을 입력해주세요')
        return
    }

    elements.executeBtn.disabled = true
    elements.executeBtn.textContent = '⏳ Planning...'
    elements.geminiResult.textContent = 'Generating execution plan...'
    renderTaskSteps([])

    try {
        const res = await fetch(`${API_BASE}/api/gemini/execute`, {
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

        currentPlan = data
        elements.geminiResult.textContent = JSON.stringify(data, null, 2)
        renderTaskSteps(data.steps || [])

        if (elements.runPlanBtn && data.steps?.length > 0) {
            elements.runPlanBtn.disabled = false
        }

        showSuccess(`${data.step_count || 0}단계 실행 계획 생성됨`)
    } catch (e) {
        elements.geminiResult.textContent = `Error: ${e.message}`
        showError(`실행 계획 생성 실패: ${e.message}`)
    } finally {
        elements.executeBtn.disabled = false
        elements.executeBtn.textContent = '⚡ Execute'
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Task Plan Rendering & Execution
// ─────────────────────────────────────────────────────────────────────────────

const STEP_ICONS = {
    pending: '⏳',
    running: '🔄',
    done: '✅',
    error: '❌',
}

function renderTaskSteps(steps) {
    if (!elements.taskSteps) return

    if (!steps || steps.length == 0) {
        elements.taskSteps.innerHTML = '<div class="task-step pending"><span class="step-icon">⏳</span><span class="step-text">No plan yet</span></div>'
        if (elements.runPlanBtn) elements.runPlanBtn.disabled = true
        return
    }

    elements.taskSteps.innerHTML = steps.map((step, i) => {
        const status = step.status || 'pending'
        const icon = STEP_ICONS[status] || '⏳'
        const desc = step.description || `${step.tool}()`
        return `<div class="task-step ${status}" id="step-${i}"><span class="step-icon">${icon}</span><span class="step-text">${i + 1}. ${desc}</span></div>`
    }).join('')
}

function updateStepStatus(index, status) {
    const el = document.getElementById(`step-${index}`)
    if (!el) return
    el.className = `task-step ${status}`
    const iconEl = el.querySelector('.step-icon')
    if (iconEl) iconEl.textContent = STEP_ICONS[status] || '⏳'
}

async function runPlan() {
    if (!currentPlan || !currentPlan.steps?.length) {
        showError('실행할 계획이 없습니다')
        return
    }

    planAborted = false
    if (elements.runPlanBtn) elements.runPlanBtn.disabled = true
    if (elements.executeBtn) elements.executeBtn.disabled = true
    if (elements.abortPlanBtn) elements.abortPlanBtn.disabled = false

    // Auto-connect robot
    try {
        showToast('🔌 로봇 연결 중...')
        const connectRes = await fetch(`${API_BASE}/api/robot/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        })
        const connectData = await connectRes.json()
        if (connectData.success === false) {
            showError(`로봇 연결 실패: ${connectData.error || 'Unknown'}`)
            if (elements.runPlanBtn) elements.runPlanBtn.disabled = false
            if (elements.executeBtn) elements.executeBtn.disabled = false
            if (elements.abortPlanBtn) elements.abortPlanBtn.disabled = true
            return
        }
        showToast('🤖 로봇 연결됨, Home 이동 중...')

        // Go home first to prevent collisions from unknown position
        const homeRes = await fetch(`${API_BASE}/api/robot/home`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        })
        const homeData = await homeRes.json()
        if (homeData.success === false) {
            showError(`Home 이동 실패: ${homeData.error || 'Unknown'}`)
            if (elements.runPlanBtn) elements.runPlanBtn.disabled = false
            if (elements.executeBtn) elements.executeBtn.disabled = false
            if (elements.abortPlanBtn) elements.abortPlanBtn.disabled = true
            return
        }
        showToast('🏠 Home 완료, 실행 시작...')
    } catch (e) {
        showError(`로봇 연결 실패: ${e.message}`)
        if (elements.runPlanBtn) elements.runPlanBtn.disabled = false
        if (elements.executeBtn) elements.executeBtn.disabled = false
        if (elements.abortPlanBtn) elements.abortPlanBtn.disabled = true
        return
    }

    const steps = currentPlan.steps
    lastMoveArgs = null  // Reset safe approach state

    try {
        for (let i = 0; i < steps.length; i++) {
            if (planAborted) {
                showToast('⏹ Plan 중단됨')
                for (let j = i; j < steps.length; j++) updateStepStatus(j, 'error')
                break
            }

            const step = steps[i]
            updateStepStatus(i, 'running')

            const result = await executeStep(step)

            if (result.success !== false) {
                // Verify step via arm camera
                const verifyResult = await _verifyStep(step, result)
                if (verifyResult.aborted) {
                    showToast(`⚠️ Step ${i + 1} 검증 실패, 다음 스텝 진행`)
                }
                updateStepStatus(i, 'done')
            } else {
                updateStepStatus(i, 'error')
                showError(`Step ${i + 1} 실패: ${result.error || 'Unknown'}`)
                break
            }

            await sleep(500)
        }

        if (!planAborted) showSuccess('실행 완료')
    } catch (e) {
        showError(`실행 중 오류: ${e.message}`)
    } finally {
        // Auto-disconnect robot
        try {
            await fetch(`${API_BASE}/api/robot/disconnect`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            })
            showToast('🔌 로봇 연결 해제')
        } catch (_) { }

        if (elements.runPlanBtn) elements.runPlanBtn.disabled = false
        if (elements.executeBtn) elements.executeBtn.disabled = false
        if (elements.abortPlanBtn) elements.abortPlanBtn.disabled = true
    }
}

async function abortPlan() {
    planAborted = true
    showToast('⏹ 중단 요청...')

    // Immediate servo release
    try {
        await fetch(`${API_BASE}/api/robot/release`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        })
    } catch (_) { }
}

// Safe approach motion state
let lastMoveArgs = null

async function _moveTo(x, y, z, arm, motionTime, orientation = null) {
    const body = { x, y, z, arm, motion_time: motionTime }
    if (orientation != null) body.orientation = orientation
    const res = await fetch(`${API_BASE}/api/robot/move_to`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
    return await res.json()
}

async function _verifyStep(step, result) {
    const tool = step.tool
    const args = step.args || {}

    // Only verify move_arm and close_gripper (open_gripper needs no verification)
    if (tool != 'move_arm' && tool != 'close_gripper') {
        return { aborted: false }
    }

    const arm = args.arm || lastMoveArgs?.arm || 'right'
    const stepType = tool == 'move_arm' ? 'move_arm' : 'gripper'
    const context = step.description || tool

    for (let retry = 0; retry < MAX_VERIFY_RETRIES; retry++) {
        showToast(`🔍 검증 중... (${retry + 1}/${MAX_VERIFY_RETRIES})`)

        try {
            const res = await fetch(`${API_BASE}/api/robot/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ arm, step_type: stepType, context })
            })
            const vResult = await res.json()

            if (vResult.verified) {
                showToast(`✅ 검증 통과: ${vResult.description || 'OK'}`)
                return { aborted: false }
            }

            showToast(`⚠️ 검증 실패: ${vResult.description || 'Unknown'}`)

            // Position correction — rotate camera offset to robot coordinates
            if (stepType == 'move_arm' && vResult.offset) {
                const dx = vResult.offset.dx || 0
                const dy = vResult.offset.dy || 0
                // Tolerance: ignore offsets < 3mm
                const offsetMag = Math.sqrt(dx * dx + dy * dy)
                if (offsetMag < 3.0) {
                    showToast(`✅ 허용 범위 내 (${offsetMag.toFixed(1)}mm)`)
                    return { aborted: false }
                }
                // Camera-to-robot 2D rotation by -yaw + damping
                const DAMPING = 0.5
                const yawRad = -(lastMoveArgs?.yaw || 0) * Math.PI / 180
                const robotDx = (dx * Math.cos(yawRad) - dy * Math.sin(yawRad)) * DAMPING
                const robotDy = (dx * Math.sin(yawRad) + dy * Math.cos(yawRad)) * DAMPING
                const newX = (lastMoveArgs?.x || 0) + robotDx
                const newY = (lastMoveArgs?.y || 0) + robotDy
                showToast(`🔧 위치 보정: cam(${dx},${dy}) → robot(${robotDx.toFixed(1)},${robotDy.toFixed(1)})`)
                const corrRes = await _moveTo(newX, newY, args.z ?? 1, arm, 1.0)
                lastMoveArgs = { x: newX, y: newY, arm, yaw: corrRes.yaw_deg || lastMoveArgs?.yaw || 0 }
                continue  // re-verify
            }

            // Gripper grasp retry: open → ascend → re-analyze → re-position → close
            if (stepType == 'gripper' && !vResult.verified) {
                const arm = args.arm || lastMoveArgs?.arm || 'right'
                showToast(`🔄 그립 실패 — 재시도 (${retry + 1}/${MAX_VERIFY_RETRIES})`)

                // 1. Re-open gripper
                await executeStep({ tool: 'open_gripper', args: { arm } })

                // 2. Ascend to safe height
                if (lastMoveArgs) {
                    await _moveTo(lastMoveArgs.x, lastMoveArgs.y, SAFE_HEIGHT, arm, 1.0)
                }

                // 3. Re-analyze object via TopView
                const aRes = await fetch(`${API_BASE}/api/gemini/analyze`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ instruction: context })
                })
                const analysis = await aRes.json()

                if (!analysis.coordinates || !analysis.target_detected) {
                    showToast('❌ 물체 재탐지 실패')
                    continue
                }

                // 4. Convert Gemini 0-1000 coords to robot mm
                const [gy, gx] = analysis.coordinates
                const cRes = await fetch(`${API_BASE}/api/coord/convert`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ gx, gy })
                })
                const coord = await cRes.json()

                if (coord.error) {
                    showToast(`❌ 좌표 변환 실패: ${coord.error}`)
                    continue
                }

                showToast(`🎯 재위치: (${coord.x}, ${coord.y}) arm=${coord.arm}`)

                // 5. Re-position (approach + descend)
                await _moveTo(coord.x, coord.y, SAFE_HEIGHT, coord.arm, 1.0)
                const descRes = await _moveTo(coord.x, coord.y, args.z ?? 1, coord.arm, 1.5)
                lastMoveArgs = { x: coord.x, y: coord.y, arm: coord.arm, yaw: descRes.yaw_deg || 0 }

                // 6. Close gripper again
                await executeStep({ tool: 'close_gripper', args: { arm: coord.arm } })
                continue  // re-verify
            }

            // No correction available
            return { aborted: false }
        } catch (e) {
            console.error('Verify error:', e)
            return { aborted: false }  // Network error, skip verification
        }
    }

    return { aborted: true }  // Exceeded retries
}

async function executeStep(step) {
    const tool = step.tool
    const args = step.args || {}

    if (tool == 'move_arm') {
        const targetX = args.x || 0
        const targetY = args.y || 0
        const targetZ = args.z ?? 1
        const arm = args.arm || 'auto'
        const motionTime = args.motion_time || 2.0
        const orientation = args.orientation ?? null

        // Phase 0: Ascend from previous position (if any)
        if (lastMoveArgs) {
            const ascendRes = await _moveTo(lastMoveArgs.x, lastMoveArgs.y, SAFE_HEIGHT, lastMoveArgs.arm, 1.0)
            if (ascendRes.success === false) return ascendRes
        }

        // Phase 1: Approach — move to target XY at safe height
        const approachRes = await _moveTo(targetX, targetY, SAFE_HEIGHT, arm, 1.0)
        if (approachRes.success === false) return approachRes

        // Phase 2: Descend — lower to target Z (with orientation for gripper alignment)
        const descendRes = await _moveTo(targetX, targetY, targetZ, arm, motionTime, orientation)

        // Track position + yaw for next ascend and verification
        lastMoveArgs = { x: targetX, y: targetY, arm, yaw: descendRes.yaw_deg || 0 }

        return descendRes
    }

    if (tool == 'open_gripper') {
        const res = await fetch(`${API_BASE}/api/robot/gripper/open`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ arm: args.arm || 'right' })
        })
        return await res.json()
    }

    if (tool == 'close_gripper') {
        const res = await fetch(`${API_BASE}/api/robot/gripper/close`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ arm: args.arm || 'right' })
        })
        return await res.json()
    }

    if (tool == 'go_home') {
        // Safety: ascend before homing to avoid dragging across table
        if (lastMoveArgs) {
            await _moveTo(lastMoveArgs.x, lastMoveArgs.y, SAFE_HEIGHT, lastMoveArgs.arm, 1.0)
            lastMoveArgs = null
        }

        const res = await fetch(`${API_BASE}/api/robot/home`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ motion_time: args.motion_time || 3.0 })
        })
        return await res.json()
    }

    return { success: false, error: `Unknown tool: ${tool}` }
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

    try {
        await initWebRTC()
        console.log('[app.mjs] WebRTC connected, roles:', ROLES)
    } catch (e) {
        console.error('[app.mjs] Failed to initialize WebRTC:', e)
        showError(`WebRTC 초기화 실패: ${e.message}`)
    }
}

init()
