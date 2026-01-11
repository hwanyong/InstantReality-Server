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
    maxCameras: 4
})

// ─────────────────────────────────────────────────────────────────────────────
// Event Handlers (using data attributes)
// ─────────────────────────────────────────────────────────────────────────────

const handleAutoToggle = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)
    const rngFocus = container.querySelector('.rng-focus')
    const isAuto = e.target.checked
    rngFocus.disabled = isAuto
    await client.setFocus(camIndex, { auto: isAuto, value: parseInt(rngFocus.value) })
}

const handleFocusInput = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)
    const valSpan = container.querySelector('.val-focus')
    const val = e.target.value
    valSpan.innerText = val
    await client.setFocus(camIndex, { auto: false, value: parseInt(val) })
}

const handleExposureInput = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)
    const valSpan = container.querySelector('.val-exposure')
    const val = e.target.value
    valSpan.innerText = val
    await client.setExposure(camIndex, parseInt(val))
}

const handleAutoExposureToggle = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)
    const rngExposure = container.querySelector('.rng-exposure')
    const rngTarget = container.querySelector('.rng-target')
    const isAuto = e.target.checked
    rngExposure.disabled = isAuto
    rngTarget.disabled = !isAuto
    await client.setAutoExposure(camIndex, { enabled: isAuto, targetBrightness: parseInt(rngTarget.value) })
}

const handleTargetInput = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)
    const valSpan = container.querySelector('.val-target')
    const val = e.target.value
    valSpan.innerText = val
    await client.setAutoExposure(camIndex, { enabled: true, targetBrightness: parseInt(val) })
}

const handleCapture = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)
    const blob = await client.capture(camIndex)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `camera_${camIndex}_capture.jpg`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
}

const handleToggleStream = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)
    const btn = container.querySelector('.btn-toggle-stream')

    const isEnabled = client.isTrackEnabled(camIndex)
    const newState = !isEnabled

    await client.setTrackEnabled(camIndex, newState)

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

const createVideoCard = (track, cameraIndex) => {
    const clone = template.content.cloneNode(true)

    const label = clone.querySelector('.cam-label')
    label.innerText = `Camera ${cameraIndex} Focus:`

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
    lastContainer.dataset.camIndex = cameraIndex

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

client.on('track', (track, cameraIndex) => {
    createVideoCard(track, cameraIndex)
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
