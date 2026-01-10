const state = {
    pc: null,
    trackCounter: 0
}

const dom = {
    streamBtn: document.getElementById('streamBtn'),
    videoGrid: document.getElementById('videoGrid'),
    logs: document.getElementById('logs'),
    template: document.getElementById('video-control-template')
}

const log = (msg) => {
    dom.logs.innerText += msg + '\n'
    console.log(msg)
}

const sendFocus = (camIndex, isAuto, value) => {
    fetch('/set_focus', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            camera_index: camIndex,
            auto: isAuto,
            value: parseInt(value)
        }),
    }).then(response => {
        if (!response.ok) {
            console.error('Failed to set focus')
        }
    })
}

const handleFocusInput = (e, camIndex, valSpan) => {
    const val = e.target.value
    valSpan.innerText = val
    sendFocus(camIndex, false, val)
}

const handleAutoToggle = (e, camIndex, rngFocus) => {
    const isAuto = e.target.checked
    rngFocus.disabled = isAuto
    sendFocus(camIndex, isAuto, rngFocus.value)
}

const handleCapture = async (camIndex) => {
    try {
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
    } catch (e) {
        console.error('Capture error:', e)
    }
}

const createVideoCard = (track) => {
    const camIndex = state.trackCounter++
    log(`Assigning Camera Index: ${camIndex}`)

    const clone = dom.template.content.cloneNode(true)

    const label = clone.querySelector('.cam-label')
    label.innerText = `Camera ${camIndex} Focus:`

    const chkAuto = clone.querySelector('.chk-auto')
    const rngFocus = clone.querySelector('.rng-focus')
    const valSpan = clone.querySelector('.val-focus')

    chkAuto.addEventListener('change', (e) => handleAutoToggle(e, camIndex, rngFocus))
    rngFocus.addEventListener('input', (e) => handleFocusInput(e, camIndex, valSpan))

    // Capture button handler
    const btnCapture = clone.querySelector('.btn-capture')
    btnCapture.addEventListener('click', () => handleCapture(camIndex))

    // Safari fix: Append to DOM FIRST, then set srcObject and play
    dom.videoGrid.appendChild(clone)

    // Now get the video element that's actually in the DOM (not the template clone)
    const videoContainers = dom.videoGrid.querySelectorAll('.video-container')
    const lastContainer = videoContainers[videoContainers.length - 1]
    const videoEl = lastContainer.querySelector('video')

    videoEl.srcObject = new MediaStream([track])

    // Safari workaround: explicit play() call after element is in DOM
    videoEl.play().catch(e => console.warn('Autoplay failed:', e))
}

const onTrack = (evt) => {
    log(`Track received: ${evt.track.kind}`)
    if (evt.track.kind !== 'video') {
        return
    }
    createVideoCard(evt.track)
}

const stopStream = () => {
    if (state.pc) {
        state.pc.close()
        state.pc = null
    }

    dom.videoGrid.innerHTML = ''
    dom.streamBtn.innerText = 'Start Streaming'
    dom.streamBtn.className = ''
    dom.streamBtn.disabled = false
    log('Streaming stopped.')
}

const handleNegotiation = (pc) => {
    pc.createOffer()
        .then(offer => pc.setLocalDescription(offer))
        .then(() => {
            return new Promise(resolve => {
                if (pc.iceGatheringState === 'complete') {
                    resolve()
                    return
                }

                const checkState = () => {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icecandidate', checkState)
                        resolve()
                    }
                }
                pc.addEventListener('icecandidate', checkState)

                // Safari workaround: ICE gathering often hangs and never reaches 'complete'
                // Proceed with whatever candidates we have after 2 seconds
                setTimeout(() => {
                    if (pc.iceGatheringState !== 'complete') {
                        console.warn('ICE gathering timed out, sending available candidates')
                        pc.removeEventListener('icecandidate', checkState)
                        resolve()
                    }
                }, 2000)
            })
        })
        .then(() => {
            const offer = pc.localDescription
            return fetch('/offer', {
                body: JSON.stringify({
                    sdp: offer.sdp,
                    type: offer.type,
                }),
                headers: {
                    'Content-Type': 'application/json'
                },
                method: 'POST'
            })
        })
        .then(response => response.json())
        .then(answer => {
            dom.streamBtn.innerText = 'Stop Streaming'
            dom.streamBtn.className = 'btn-stop'
            dom.streamBtn.disabled = false
            return pc.setRemoteDescription(answer)
        })
        .catch(e => {
            dom.streamBtn.innerText = 'Start Streaming'
            dom.streamBtn.className = ''
            dom.streamBtn.disabled = false
            alert(e)
        })
}

const startStream = () => {
    dom.streamBtn.disabled = true
    dom.streamBtn.innerText = 'Connecting...'

    const config = {
        sdpSemantics: 'unified-plan',
        iceServers: [{ urls: ['stun:stun.l.google.com:19302'] }]
    }

    const pc = new RTCPeerConnection(config)
    state.pc = pc
    state.trackCounter = 0

    pc.ontrack = onTrack

    // Support up to 4 cameras dynamically
    // We offer to receive 4 video tracks. The server will only use what it has.
    for (let i = 0; i < 4; i++) {
        pc.addTransceiver('video', { direction: 'recvonly' })
    }

    handleNegotiation(pc)
}

const toggleStream = () => {
    if (state.pc) {
        stopStream()
    } else {
        startStream()
    }
}

// Init
dom.streamBtn.addEventListener('click', toggleStream)
