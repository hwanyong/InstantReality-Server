import { InstantReality } from '/sdk/instant-reality.mjs'

// ─────────────────────────────────────────────────────────────────────────────
// DOM Elements
// ─────────────────────────────────────────────────────────────────────────────

const streamBtn = document.getElementById('streamBtn')
const videoGrid = document.getElementById('videoGrid')
const template = document.getElementById('video-control-template')

// ─────────────────────────────────────────────────────────────────────────────
// SDK Client
// ─────────────────────────────────────────────────────────────────────────────

const client = new InstantReality({
    serverUrl: window.location.origin,
    maxCameras: 8
})

// ─────────────────────────────────────────────────────────────────────────────
// Event Handlers (using data attributes)
// ─────────────────────────────────────────────────────────────────────────────

const handleAutoToggle = async (e) => {
    const container = e.target.closest('.video-container')
    const role = container.dataset.role
    const rngFocus = container.querySelector('.rng-focus')
    const isAuto = e.target.checked
    rngFocus.disabled = isAuto
    await client.setFocus(role, { auto: isAuto, value: parseInt(rngFocus.value) })
}

const handleFocusInput = async (e) => {
    const container = e.target.closest('.video-container')
    const role = container.dataset.role
    const valSpan = container.querySelector('.val-focus')
    const val = e.target.value
    valSpan.innerText = val
    await client.setFocus(role, { auto: false, value: parseInt(val) })
}

const handleExposureInput = async (e) => {
    const container = e.target.closest('.video-container')
    const role = container.dataset.role
    const valSpan = container.querySelector('.val-exposure')
    const val = e.target.value
    valSpan.innerText = val
    await client.setExposure(role, parseInt(val))
}

const handleAutoExposureToggle = async (e) => {
    const container = e.target.closest('.video-container')
    const role = container.dataset.role
    const rngExposure = container.querySelector('.rng-exposure')
    const rngTarget = container.querySelector('.rng-target')
    const isAuto = e.target.checked
    rngExposure.disabled = isAuto
    rngTarget.disabled = !isAuto
    await client.setAutoExposure(role, { enabled: isAuto, targetBrightness: parseInt(rngTarget.value) })
}

const handleTargetInput = async (e) => {
    const container = e.target.closest('.video-container')
    const role = container.dataset.role
    const valSpan = container.querySelector('.val-target')
    const val = e.target.value
    valSpan.innerText = val
    await client.setAutoExposure(role, { enabled: true, targetBrightness: parseInt(val) })
}

const handleCapture = async (e) => {
    const container = e.target.closest('.video-container')
    const role = container.dataset.role
    const blob = await client.capture(role)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${role}_capture.jpg`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
}

const handleToggleStream = async (e) => {
    const container = e.target.closest('.video-container')
    const role = container.dataset.role
    const btn = container.querySelector('.btn-toggle-stream')

    const isEnabled = client.isTrackEnabled(role)
    const newState = !isEnabled

    await client.setTrackEnabled(role, newState)

    if (newState) {
        container.classList.remove('paused')
        btn.classList.remove('off')
        btn.innerText = '👁 On'
    } else {
        container.classList.add('paused')
        btn.classList.add('off')
        btn.innerText = '👁 Off'
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Video Card Creation
// ─────────────────────────────────────────────────────────────────────────────

const createVideoCard = (track, role) => {
    const clone = template.content.cloneNode(true)

    const label = clone.querySelector('.cam-label')
    label.innerText = `${role} Focus:`

    // Event listeners
    clone.querySelector('.chk-auto').addEventListener('change', handleAutoToggle)
    clone.querySelector('.rng-focus').addEventListener('input', handleFocusInput)
    clone.querySelector('.rng-exposure').addEventListener('input', handleExposureInput)
    clone.querySelector('.chk-auto-exp').addEventListener('change', handleAutoExposureToggle)
    clone.querySelector('.rng-target').addEventListener('input', handleTargetInput)
    clone.querySelector('.btn-capture').addEventListener('click', handleCapture)
    clone.querySelector('.btn-toggle-stream').addEventListener('click', handleToggleStream)

    // Safari fix: Append to DOM FIRST, then set srcObject and play
    videoGrid.appendChild(clone)

    const videoContainers = videoGrid.querySelectorAll('.video-container')
    const lastContainer = videoContainers[videoContainers.length - 1]
    lastContainer.dataset.role = role

    // Handle initial enabled state
    const toggleBtn = lastContainer.querySelector('.btn-toggle-stream')
    if (!track.enabled) {
        lastContainer.classList.add('paused')
        toggleBtn.classList.add('off')
        toggleBtn.innerText = '👁 Off'
    }

    const videoEl = lastContainer.querySelector('video')
    videoEl.srcObject = new MediaStream([track])
    videoEl.play().catch(e => console.warn('Autoplay failed:', e))
}

// ─────────────────────────────────────────────────────────────────────────────
// SDK Event Handlers
// ─────────────────────────────────────────────────────────────────────────────

client.on('track', (track, role) => {
    createVideoCard(track, role)
})

client.on('connected', () => {
    streamBtn.innerText = 'Stop Streaming'
    streamBtn.className = 'btn-stop'
    streamBtn.disabled = false
})

client.on('disconnected', () => {
    streamBtn.innerText = 'Start Streaming'
    streamBtn.className = ''
    streamBtn.disabled = false
    videoGrid.innerHTML = ''
})

client.on('error', (error) => {
    streamBtn.innerText = 'Start Streaming'
    streamBtn.className = ''
    streamBtn.disabled = false
    alert(error.message)
})

client.on('cameraChange', async (cameras) => {
    console.log('Camera change detected, reconnecting...', cameras)

    // Only reconnect if currently connected
    if (client.pc) {
        streamBtn.disabled = true
        streamBtn.innerText = 'Reconnecting...'
        videoGrid.innerHTML = ''

        await client.reconnect()
    }
})

// ─────────────────────────────────────────────────────────────────────────────
// Initialize
// ─────────────────────────────────────────────────────────────────────────────

streamBtn.addEventListener('click', async () => {
    if (client.pc) {
        client.disconnect()
    } else {
        streamBtn.disabled = true
        streamBtn.innerText = 'Connecting...'
        await client.connect()
    }
})
