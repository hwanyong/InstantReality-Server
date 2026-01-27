// src/static/robotics/app.mjs
// Gemini Robotics Web App - Main Application
// Vanilla JS + Native WebAPIs only

const API_BASE = ''

// =============================================================================
// State
// =============================================================================
let robotConfig = null
let currentArm = null
let lastIKResult = null

// =============================================================================
// DOM Elements
// =============================================================================
const elements = {
    connectionStatus: document.getElementById('connection-status'),
    estopBtn: document.getElementById('estop-btn'),
    videoCanvas: document.getElementById('video-canvas'),
    arOverlay: document.getElementById('ar-overlay'),
    captureBtn: document.getElementById('capture-btn'),
    clearArBtn: document.getElementById('clear-ar-btn'),
    promptInput: document.getElementById('prompt-input'),
    sendPromptBtn: document.getElementById('send-prompt-btn'),
    geminiResult: document.getElementById('gemini-result'),
    armSelection: document.getElementById('arm-selection'),
    jointSliders: document.getElementById('joint-sliders'),
    sendManualBtn: document.getElementById('send-manual-btn'),
    ikX: document.getElementById('ik-x'),
    ikY: document.getElementById('ik-y'),
    ikZ: document.getElementById('ik-z'),
    testIkBtn: document.getElementById('test-ik-btn'),
    ikResult: document.getElementById('ik-result')
}

// =============================================================================
// API Functions
// =============================================================================
async function api(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    }
    if (data) options.body = JSON.stringify(data)

    const response = await fetch(`${API_BASE}${endpoint}`, options)
    return response.json()
}

async function loadConfig() {
    try {
        robotConfig = await api('/api/config')
        console.log('Config loaded:', robotConfig)
        setConnected(true)
        generateJointSliders()
    } catch (err) {
        console.error('Failed to load config:', err)
        setConnected(false)
    }
}

async function captureFrame() {
    elements.captureBtn.classList.add('loading')
    try {
        const result = await api('/api/capture')
        if (result.image) {
            displayImage(result.image)
        }
    } catch (err) {
        console.error('Capture failed:', err)
    }
    elements.captureBtn.classList.remove('loading')
}

async function sendPrompt() {
    const instruction = elements.promptInput.value.trim()
    if (!instruction) return

    elements.sendPromptBtn.classList.add('loading')
    elements.geminiResult.textContent = 'Processing...'

    try {
        const result = await api('/api/prompt', 'POST', { instruction })

        // Display result
        elements.geminiResult.textContent = JSON.stringify(result, null, 2)

        // Update arm selection
        if (result.ik_result?.arm) {
            currentArm = result.ik_result.arm
            elements.armSelection.textContent = currentArm
        }

        // Draw AR overlay
        if (result.gemini_analysis?.coordinates) {
            drawTargetOverlay(result)
        }

        lastIKResult = result.ik_result

    } catch (err) {
        elements.geminiResult.textContent = 'Error: ' + err.message
    }
    elements.sendPromptBtn.classList.remove('loading')
}

async function testIK() {
    const x = parseFloat(elements.ikX.value)
    const y = parseFloat(elements.ikY.value)
    const z = parseFloat(elements.ikZ.value)

    try {
        const result = await api('/api/ik/test', 'POST', { x, y, z, arm: currentArm || 'right_arm' })
        elements.ikResult.textContent = JSON.stringify(result, null, 2)
        lastIKResult = result
    } catch (err) {
        elements.ikResult.textContent = 'Error: ' + err.message
    }
}

async function sendManual() {
    if (!lastIKResult?.pulses) {
        alert('No IK result to execute')
        return
    }

    try {
        const result = await api('/api/execute', 'POST', {
            pulses: lastIKResult.pulses,
            duration: 500
        })
        console.log('Execute result:', result)
    } catch (err) {
        console.error('Execute failed:', err)
    }
}

async function emergencyStop() {
    try {
        await api('/api/estop', 'POST', {})
        elements.connectionStatus.textContent = '● E-STOP'
        elements.connectionStatus.style.color = 'var(--danger)'
    } catch (err) {
        console.error('E-STOP failed:', err)
    }
}

// =============================================================================
// UI Functions
// =============================================================================
function setConnected(connected) {
    if (connected) {
        elements.connectionStatus.textContent = '● Connected'
        elements.connectionStatus.classList.remove('disconnected')
        elements.connectionStatus.classList.add('connected')
    } else {
        elements.connectionStatus.textContent = '● Disconnected'
        elements.connectionStatus.classList.remove('connected')
        elements.connectionStatus.classList.add('disconnected')
    }
}

function generateJointSliders() {
    if (!robotConfig?.arms) return

    const arm = robotConfig.arms.right_arm || robotConfig.arms.left_arm
    if (!arm) return

    elements.jointSliders.innerHTML = ''

    const joints = ['θ1', 'θ2', 'θ3', 'θ4', 'θ5', 'θ6']
    const defaults = [0, 45, -45, -90, 90, 0]

    joints.forEach((name, i) => {
        const row = document.createElement('div')
        row.className = 'slider-row'
        row.innerHTML = `
            <label>${name}</label>
            <input type="range" min="-180" max="180" value="${defaults[i]}" data-joint="${i}">
            <span class="value">${defaults[i]}°</span>
        `

        const slider = row.querySelector('input')
        const valueSpan = row.querySelector('.value')
        slider.addEventListener('input', () => {
            valueSpan.textContent = slider.value + '°'
        })

        elements.jointSliders.appendChild(row)
    })
}

function displayImage(base64Image) {
    const ctx = elements.videoCanvas.getContext('2d')
    const img = new Image()
    img.onload = () => {
        ctx.drawImage(img, 0, 0, elements.videoCanvas.width, elements.videoCanvas.height)
    }
    img.src = 'data:image/jpeg;base64,' + base64Image
}

function drawTargetOverlay(result) {
    const ctx = elements.arOverlay.getContext('2d')
    const w = elements.arOverlay.width
    const h = elements.arOverlay.height

    // Clear previous
    ctx.clearRect(0, 0, w, h)

    const coords = result.gemini_analysis?.coordinates
    if (!coords) return

    // Gemini returns [y, x] normalized 0-1000
    const targetX = (coords[1] / 1000) * w
    const targetY = (coords[0] / 1000) * h

    // Draw target point
    ctx.fillStyle = '#ff4444'
    ctx.beginPath()
    ctx.arc(targetX, targetY, 10, 0, Math.PI * 2)
    ctx.fill()

    // Draw crosshair
    ctx.strokeStyle = '#ff4444'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(targetX - 20, targetY)
    ctx.lineTo(targetX + 20, targetY)
    ctx.moveTo(targetX, targetY - 20)
    ctx.lineTo(targetX, targetY + 20)
    ctx.stroke()

    // Draw bounding box
    ctx.strokeStyle = '#44ff44'
    ctx.lineWidth = 2
    ctx.strokeRect(targetX - 40, targetY - 40, 80, 80)

    // Label
    ctx.fillStyle = '#ffffff'
    ctx.font = '14px sans-serif'
    ctx.fillText(result.ik_result?.arm || '', targetX + 15, targetY - 25)
}

function clearOverlay() {
    const ctx = elements.arOverlay.getContext('2d')
    ctx.clearRect(0, 0, elements.arOverlay.width, elements.arOverlay.height)
}

// =============================================================================
// Event Listeners
// =============================================================================
elements.estopBtn.addEventListener('click', emergencyStop)
elements.captureBtn.addEventListener('click', captureFrame)
elements.clearArBtn.addEventListener('click', clearOverlay)
elements.sendPromptBtn.addEventListener('click', sendPrompt)
elements.testIkBtn.addEventListener('click', testIK)
elements.sendManualBtn.addEventListener('click', sendManual)

// Keyboard shortcut: Enter to send
elements.promptInput.addEventListener('keydown', (e) => {
    if (e.key == 'Enter' && e.ctrlKey) {
        sendPrompt()
    }
})

// =============================================================================
// Initialize
// =============================================================================
window.addEventListener('load', () => {
    loadConfig()

    // Draw placeholder on canvas
    const ctx = elements.videoCanvas.getContext('2d')
    ctx.fillStyle = '#1a1a2e'
    ctx.fillRect(0, 0, elements.videoCanvas.width, elements.videoCanvas.height)
    ctx.fillStyle = '#58a6ff'
    ctx.font = '20px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('Click "Capture" to start', elements.videoCanvas.width / 2, elements.videoCanvas.height / 2)
})

console.log('Gemini Robotics App initialized')
