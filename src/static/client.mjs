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

const createVideoCard = (track) => {
    const camIndex = state.trackCounter++
    log(`Assigning Camera Index: ${camIndex}`)

    const clone = dom.template.content.cloneNode(true)
    const videoEl = clone.querySelector('video')
    videoEl.srcObject = new MediaStream([track])

    const label = clone.querySelector('.cam-label')
    label.innerText = `Camera ${camIndex} Focus:`

    const chkAuto = clone.querySelector('.chk-auto')
    const rngFocus = clone.querySelector('.rng-focus')
    const valSpan = clone.querySelector('.val-focus')

    chkAuto.addEventListener('change', (e) => handleAutoToggle(e, camIndex, rngFocus))
    rngFocus.addEventListener('input', (e) => handleFocusInput(e, camIndex, valSpan))

    dom.videoGrid.appendChild(clone)
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
