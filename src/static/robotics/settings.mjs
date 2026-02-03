// ─────────────────────────────────────────────────────────────────────────────
// Camera Settings Page Controller
// src/static/robotics/settings.mjs
// ─────────────────────────────────────────────────────────────────────────────

import { showToast, showSuccess, showError } from './lib/toast.mjs'

// ─────────────────────────────────────────────────────────────────────────────
// Globals
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE = ''
const VALID_ROLES = ['TopView', 'QuarterView', 'LeftRobot', 'RightRobot']

let devices = []
let currentRoles = {}   // {devicePath: role}
let roleToDevice = {}   // {role: devicePath}
let cameraSettings = {} // {role: {settings, index, connected}}

// UI Elements
const scanBtn = document.getElementById('scanBtn')
const refreshBtn = document.getElementById('refreshBtn')
const cameraGrid = document.getElementById('cameraGrid')

// ─────────────────────────────────────────────────────────────────────────────
// WebSocket for Real-time Camera Updates
// ─────────────────────────────────────────────────────────────────────────────

let ws = null

function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${protocol}//${location.host}/ws`)

    ws.onopen = () => {
        console.log('WebSocket connected for camera updates')
    }

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data)
            if (data.type === 'camera_change') {
                console.log('Camera change detected:', data.cameras)
                showToast('카메라 변경 감지됨 - 새로고침 중...')
                scanCameras()  // Auto-refresh camera grid
            }
        } catch (err) {
            console.error('WebSocket message parse error:', err)
        }
    }

    ws.onclose = () => {
        console.log('WebSocket disconnected, reconnecting in 3s...')
        setTimeout(connectWebSocket, 3000)
    }

    ws.onerror = (err) => {
        console.error('WebSocket error:', err)
    }
}

// Initialize WebSocket connection
connectWebSocket()


// ─────────────────────────────────────────────────────────────────────────────
// Settings Management
// ─────────────────────────────────────────────────────────────────────────────

async function loadSettings() {
    try {
        const res = await fetch(`${API_BASE}/api/cameras/settings`)
        cameraSettings = await res.json()
        console.log('Loaded settings:', cameraSettings)
    } catch (err) {
        console.error('Failed to load settings:', err)
    }
}

function getSettingsForRole(role) {
    if (cameraSettings[role]) {
        return cameraSettings[role].settings
    }
    return {
        focus: { auto: true, value: 0 },
        exposure: { auto: false, value: -5, target_brightness: 128 }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Camera Scanning
// ─────────────────────────────────────────────────────────────────────────────

async function scanCameras() {
    scanBtn.disabled = true
    scanBtn.textContent = '⏳ Scanning...'

    try {
        await loadSettings()

        const res = await fetch(`${API_BASE}/api/cameras/scan`, { method: 'POST' })
        const data = await res.json()

        devices = data.devices || []
        currentRoles = {}
        roleToDevice = {}

        // Build role lookup from current mappings
        for (const [role, info] of Object.entries(data.roles || {})) {
            if (info.path) {
                currentRoles[info.path] = role
                roleToDevice[role] = info.path
            }
        }

        renderCameraGrid()
        showSuccess(`${devices.length}개 카메라 발견됨`)
    } catch (err) {
        showError('카메라 스캔 실패')
        console.error(err)
    } finally {
        scanBtn.disabled = false
        scanBtn.textContent = '🔍 Scan Cameras'
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Role Assignment
// ─────────────────────────────────────────────────────────────────────────────

async function assignRole(devicePath, role) {
    if (!role) return

    try {
        const res = await fetch(`${API_BASE}/api/cameras/assign`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_path: devicePath, role: role })
        })

        if (res.ok) {
            // Remove old assignment for this role
            for (const [path, r] of Object.entries(currentRoles)) {
                if (r == role) delete currentRoles[path]
            }
            currentRoles[devicePath] = role
            roleToDevice[role] = devicePath
            renderCameraGrid()
            showSuccess(`${role} 할당됨`)
        } else {
            const err = await res.json()
            showError(err.error || '역할 할당 실패')
        }
    } catch (err) {
        showError('역할 할당 실패')
        console.error(err)
    }
}

// Make assignRole globally accessible for inline onchange
window.assignRole = assignRole

// ─────────────────────────────────────────────────────────────────────────────
// Camera Controls
// ─────────────────────────────────────────────────────────────────────────────

async function setFocus(role, auto, value) {
    try {
        await fetch(`${API_BASE}/api/cameras/focus`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role, auto, value })
        })
        showToast('포커스 업데이트됨')
    } catch (err) {
        console.error('Failed to set focus:', err)
    }
}

async function setExposure(role, auto, value, targetBrightness) {
    try {
        await fetch(`${API_BASE}/api/cameras/exposure`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role, auto, value, target_brightness: targetBrightness })
        })
        showToast('노출 업데이트됨')
    } catch (err) {
        console.error('Failed to set exposure:', err)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// UI Handlers
// ─────────────────────────────────────────────────────────────────────────────

function handleFocusAutoChange(role, deviceIndex, auto) {
    const slider = document.getElementById(`focus-slider-${deviceIndex}`)
    slider.disabled = auto
    const value = parseInt(slider.value)
    setFocus(role, auto, value)
}

function handleFocusChange(role, value) {
    setFocus(role, false, parseInt(value))
}

function handleExposureAutoChange(role, deviceIndex, auto) {
    const slider = document.getElementById(`exp-slider-${deviceIndex}`)
    const brightnessRow = document.getElementById(`brightness-row-${deviceIndex}`)
    const brightnessSlider = document.getElementById(`brightness-slider-${deviceIndex}`)

    slider.disabled = auto
    brightnessRow.style.display = auto ? '' : 'none'

    const value = parseInt(slider.value)
    const target = parseInt(brightnessSlider.value)
    setExposure(role, auto, value, target)
}

function handleExposureChange(role, deviceIndex, value) {
    const brightnessSlider = document.getElementById(`brightness-slider-${deviceIndex}`)
    const target = parseInt(brightnessSlider.value)
    setExposure(role, false, parseInt(value), target)
}

function handleBrightnessChange(role, deviceIndex, target) {
    const expSlider = document.getElementById(`exp-slider-${deviceIndex}`)
    const value = parseInt(expSlider.value)
    setExposure(role, true, value, parseInt(target))
}

// Make handlers globally accessible
window.handleFocusAutoChange = handleFocusAutoChange
window.handleFocusChange = handleFocusChange
window.handleExposureAutoChange = handleExposureAutoChange
window.handleExposureChange = handleExposureChange
window.handleBrightnessChange = handleBrightnessChange

// ─────────────────────────────────────────────────────────────────────────────
// Grid Rendering
// ─────────────────────────────────────────────────────────────────────────────

function renderCameraGrid() {
    if (devices.length == 0) {
        cameraGrid.innerHTML = `
            <div class="empty-state">
                <p>No cameras detected. Check USB connections.</p>
            </div>
        `
        return
    }

    cameraGrid.innerHTML = devices.map(device => {
        const currentRole = currentRoles[device.path] || ''
        const settings = currentRole ? getSettingsForRole(currentRole) : null
        const escapedPath = device.path.replace(/\\/g, '\\\\')

        return `
            <div class="camera-card" data-path="${device.path}" data-index="${device.index}">
                <div class="camera-preview">
                    <img src="/api/stream/${device.index}" 
                         alt="Camera ${device.index}"
                         onerror="this.style.display='none'; this.parentElement.innerHTML='<span>No preview available</span>'">
                </div>
                <div class="camera-info">
                    <div class="camera-name">
                        Camera ${device.index}: ${device.name}
                        <span class="status-badge status-connected">Connected</span>
                    </div>
                    <div class="camera-details">
                        VID: ${device.vid} | PID: ${device.pid}
                    </div>
                    <select class="role-select" 
                            onchange="assignRole('${escapedPath}', this.value)">
                        <option value="">-- Select Role --</option>
                        ${VALID_ROLES.map(role => `
                            <option value="${role}" ${currentRole == role ? 'selected' : ''}>
                                ${role}
                            </option>
                        `).join('')}
                    </select>
                    
                    ${currentRole ? `
                    <div class="camera-controls">
                        <!-- Focus Control -->
                        <div class="control-row">
                            <span class="control-label">Focus</span>
                            <label class="control-checkbox">
                                <input type="checkbox" 
                                       id="focus-auto-${device.index}"
                                       ${settings.focus.auto ? 'checked' : ''}
                                       onchange="handleFocusAutoChange('${currentRole}', ${device.index}, this.checked)">
                                Auto
                            </label>
                            <input type="range" 
                                   class="control-slider" 
                                   id="focus-slider-${device.index}"
                                   min="0" max="255" 
                                   value="${settings.focus.value}"
                                   ${settings.focus.auto ? 'disabled' : ''}
                                   onchange="handleFocusChange('${currentRole}', this.value)">
                            <span class="control-value" id="focus-value-${device.index}">${settings.focus.value}</span>
                        </div>
                        
                        <!-- Exposure Control -->
                        <div class="control-row">
                            <span class="control-label">Exposure</span>
                            <label class="control-checkbox">
                                <input type="checkbox" 
                                       id="exp-auto-${device.index}"
                                       ${settings.exposure.auto ? 'checked' : ''}
                                       onchange="handleExposureAutoChange('${currentRole}', ${device.index}, this.checked)">
                                Auto
                            </label>
                            <input type="range" 
                                   class="control-slider" 
                                   id="exp-slider-${device.index}"
                                   min="-13" max="0" 
                                   value="${settings.exposure.value}"
                                   ${settings.exposure.auto ? 'disabled' : ''}
                                   onchange="handleExposureChange('${currentRole}', ${device.index}, this.value)">
                            <span class="control-value" id="exp-value-${device.index}">${settings.exposure.value}</span>
                        </div>
                        
                        <!-- Target Brightness (for Auto Exposure) -->
                        <div class="control-row" id="brightness-row-${device.index}" style="${settings.exposure.auto ? '' : 'display:none'}">
                            <span class="control-label">Target</span>
                            <input type="range" 
                                   class="control-slider" 
                                   id="brightness-slider-${device.index}"
                                   min="0" max="255" 
                                   value="${settings.exposure.target_brightness}"
                                   onchange="handleBrightnessChange('${currentRole}', ${device.index}, this.value)">
                            <span class="control-value" id="brightness-value-${device.index}">${settings.exposure.target_brightness}</span>
                        </div>
                    </div>
                    ` : ''}
                </div>
            </div>
        `
    }).join('')

    // Add input event listeners for real-time value display
    setupSliderListeners()
}

function setupSliderListeners() {
    devices.forEach(device => {
        const focusSlider = document.getElementById(`focus-slider-${device.index}`)
        const expSlider = document.getElementById(`exp-slider-${device.index}`)
        const brightnessSlider = document.getElementById(`brightness-slider-${device.index}`)

        if (focusSlider) {
            focusSlider.addEventListener('input', (e) => {
                document.getElementById(`focus-value-${device.index}`).textContent = e.target.value
            })
        }
        if (expSlider) {
            expSlider.addEventListener('input', (e) => {
                document.getElementById(`exp-value-${device.index}`).textContent = e.target.value
            })
        }
        if (brightnessSlider) {
            brightnessSlider.addEventListener('input', (e) => {
                document.getElementById(`brightness-value-${device.index}`).textContent = e.target.value
            })
        }
    })
}

// ─────────────────────────────────────────────────────────────────────────────
// Preview Refresh
// ─────────────────────────────────────────────────────────────────────────────

function refreshPreview() {
    const images = document.querySelectorAll('.camera-preview img')
    images.forEach(img => {
        const src = img.src.split('?')[0]
        img.src = src + '?t=' + Date.now()
    })
    showToast('프리뷰 새로고침됨')
}

// ─────────────────────────────────────────────────────────────────────────────
// Event Listeners & Initialization
// ─────────────────────────────────────────────────────────────────────────────

scanBtn.addEventListener('click', scanCameras)
refreshBtn.addEventListener('click', refreshPreview)

// Auto-scan on load
scanCameras()
