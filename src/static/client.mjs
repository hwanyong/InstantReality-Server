// ─────────────────────────────────────────────────────────────────────────────
// Module State
// ─────────────────────────────────────────────────────────────────────────────

let pc = null
let trackCounter = 0

// ─────────────────────────────────────────────────────────────────────────────
// DOM Elements
// ─────────────────────────────────────────────────────────────────────────────

const streamBtn = document.getElementById('streamBtn')
const videoGrid = document.getElementById('videoGrid')
const logsEl = document.getElementById('logs')
const template = document.getElementById('video-control-template')

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

const log = (msg) => {
    logsEl.innerText += msg + '\n'
    console.log(msg)
}

const waitForIceGathering = (peerConnection, timeoutMs = 2000) => {
    if (peerConnection.iceGatheringState == 'complete') return Promise.resolve()

    return new Promise(resolve => {
        const cleanup = () => peerConnection.removeEventListener('icecandidate', onCandidate)

        const onCandidate = () => {
            if (peerConnection.iceGatheringState != 'complete') return
            cleanup()
            resolve()
        }

        peerConnection.addEventListener('icecandidate', onCandidate)

        setTimeout(() => {
            console.warn('ICE gathering timed out, proceeding with available candidates')
            cleanup()
            resolve()
        }, timeoutMs)
    })
}

// ─────────────────────────────────────────────────────────────────────────────
// API Functions
// ─────────────────────────────────────────────────────────────────────────────

const sendFocus = async (camIndex, isAuto, value) => {
    const response = await fetch('/set_focus', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            camera_index: camIndex,
            auto: isAuto,
            value: parseInt(value)
        })
    })
    if (!response.ok) {
        console.error('Failed to set focus')
    }
}

const sendExposure = async (camIndex, value) => {
    const response = await fetch('/set_exposure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            camera_index: camIndex,
            value: parseInt(value)
        })
    })
    if (!response.ok) {
        console.error('Failed to set exposure')
    }
}

const sendAutoExposure = async (camIndex, enabled, targetBrightness) => {
    const response = await fetch('/set_auto_exposure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            camera_index: camIndex,
            enabled: enabled,
            target_brightness: parseInt(targetBrightness)
        })
    })
    if (!response.ok) {
        console.error('Failed to set auto exposure')
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Event Handlers
// ─────────────────────────────────────────────────────────────────────────────

const handleFocusInput = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)
    const valSpan = container.querySelector('.val-focus')

    const val = e.target.value
    valSpan.innerText = val
    await sendFocus(camIndex, false, val)
}

const handleAutoToggle = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)
    const rngFocus = container.querySelector('.rng-focus')

    const isAuto = e.target.checked
    rngFocus.disabled = isAuto
    await sendFocus(camIndex, isAuto, rngFocus.value)
}

const handleExposureInput = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)
    const valSpan = container.querySelector('.val-exposure')

    const val = e.target.value
    valSpan.innerText = val
    await sendExposure(camIndex, val)
}

const handleAutoExposureToggle = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)
    const rngExposure = container.querySelector('.rng-exposure')
    const rngTarget = container.querySelector('.rng-target')

    const isAuto = e.target.checked
    rngExposure.disabled = isAuto
    rngTarget.disabled = !isAuto
    await sendAutoExposure(camIndex, isAuto, rngTarget.value)
}

const handleTargetInput = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)
    const valSpan = container.querySelector('.val-target')

    const val = e.target.value
    valSpan.innerText = val
    await sendAutoExposure(camIndex, true, val)
}

const handleCapture = async (e) => {
    const container = e.target.closest('.video-container')
    const camIndex = parseInt(container.dataset.camIndex)

    const response = await fetch(`/capture?camera_index=${camIndex}`)
    if (!response.ok) {
        console.error('Capture failed')
        return
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)

    // Get filename from Content-Disposition header or generate default
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = `camera_${camIndex}_capture.jpg`
    if (contentDisposition) {
        const match = contentDisposition.match(/filename="(.+)"/)
        if (match) filename = match[1]
    }

    // Trigger download
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)

    URL.revokeObjectURL(url)
    log(`Captured Camera ${camIndex}: ${filename}`)
}

// ─────────────────────────────────────────────────────────────────────────────
// Video Card Creation
// ─────────────────────────────────────────────────────────────────────────────

const createVideoCard = (track) => {
    const camIndex = trackCounter++
    log(`Assigning Camera Index: ${camIndex}`)

    const clone = template.content.cloneNode(true)

    const label = clone.querySelector('.cam-label')
    label.innerText = `Camera ${camIndex} Focus:`

    // Event listeners
    clone.querySelector('.chk-auto').addEventListener('change', handleAutoToggle)
    clone.querySelector('.rng-focus').addEventListener('input', handleFocusInput)
    clone.querySelector('.rng-exposure').addEventListener('input', handleExposureInput)
    clone.querySelector('.chk-auto-exp').addEventListener('change', handleAutoExposureToggle)
    clone.querySelector('.rng-target').addEventListener('input', handleTargetInput)
    clone.querySelector('.btn-capture').addEventListener('click', handleCapture)

    // Safari fix: Append to DOM FIRST, then set srcObject and play
    videoGrid.appendChild(clone)

    // Get the last appended container
    const videoContainers = videoGrid.querySelectorAll('.video-container')
    const lastContainer = videoContainers[videoContainers.length - 1]

    // Set data attribute for event handlers
    lastContainer.dataset.camIndex = camIndex

    const videoEl = lastContainer.querySelector('video')
    videoEl.srcObject = new MediaStream([track])

    // Safari workaround: explicit play() call after element is in DOM
    videoEl.play().catch(e => console.warn('Autoplay failed:', e))
}

// ─────────────────────────────────────────────────────────────────────────────
// WebRTC Core Functions
// ─────────────────────────────────────────────────────────────────────────────

const handleNegotiation = async (peerConnection) => {
    const offer = await peerConnection.createOffer()
    await peerConnection.setLocalDescription(offer)

    await waitForIceGathering(peerConnection)

    const response = await fetch('/offer', {
        body: JSON.stringify({
            sdp: peerConnection.localDescription.sdp,
            type: peerConnection.localDescription.type
        }),
        headers: { 'Content-Type': 'application/json' },
        method: 'POST'
    })

    const answer = await response.json()
    await peerConnection.setRemoteDescription(answer)

    streamBtn.innerText = 'Stop Streaming'
    streamBtn.className = 'btn-stop'
    streamBtn.disabled = false
}

const startStream = async () => {
    streamBtn.disabled = true
    streamBtn.innerText = 'Connecting...'

    const config = {
        sdpSemantics: 'unified-plan',
        iceServers: [{ urls: ['stun:stun.l.google.com:19302'] }]
    }

    const peerConnection = new RTCPeerConnection(config)
    pc = peerConnection
    trackCounter = 0

    peerConnection.ontrack = (evt) => {
        log(`Track received: ${evt.track.kind}`)
        if (evt.track.kind != 'video') return
        createVideoCard(evt.track)
    }

    // Support up to 4 cameras dynamically
    for (let i = 0; i < 4; i++) {
        peerConnection.addTransceiver('video', { direction: 'recvonly' })
    }

    await handleNegotiation(peerConnection).catch(e => {
        streamBtn.innerText = 'Start Streaming'
        streamBtn.className = ''
        streamBtn.disabled = false
        alert(e)
    })
}

const stopStream = () => {
    if (pc) {
        pc.close()
        pc = null
    }

    videoGrid.innerHTML = ''
    streamBtn.innerText = 'Start Streaming'
    streamBtn.className = ''
    streamBtn.disabled = false
    log('Streaming stopped.')
}

const toggleStream = () => {
    if (pc) {
        stopStream()
    } else {
        startStream()
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Initialize
// ─────────────────────────────────────────────────────────────────────────────

streamBtn.addEventListener('click', toggleStream)
