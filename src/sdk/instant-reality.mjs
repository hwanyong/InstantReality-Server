// ─────────────────────────────────────────────────────────────────────────────
// InstantReality WebRTC Client Library
// ESM Module for external services
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// Helper: Wait for ICE Gathering
// ─────────────────────────────────────────────────────────────────────────────

const waitForIceGathering = (pc, timeoutMs = 2000) => {
    if (pc.iceGatheringState == 'complete') return Promise.resolve()

    return new Promise(resolve => {
        const cleanup = () => pc.removeEventListener('icecandidate', onCandidate)

        const onCandidate = () => {
            if (pc.iceGatheringState != 'complete') return
            cleanup()
            resolve()
        }

        pc.addEventListener('icecandidate', onCandidate)

        setTimeout(() => {
            console.warn('ICE gathering timed out, proceeding with available candidates')
            cleanup()
            resolve()
        }, timeoutMs)
    })
}

// ─────────────────────────────────────────────────────────────────────────────
// InstantReality Class
// ─────────────────────────────────────────────────────────────────────────────

export class InstantReality {
    constructor(options = {}) {
        this.serverUrl = options.serverUrl || ''
        this.maxCameras = options.maxCameras || 4
        this.iceServers = options.iceServers || [{ urls: 'stun:stun.l.google.com:19302' }]
        this.pc = null
        this.ws = null
        this.trackCounter = 0
        this.listeners = {}
        this.tracks = new Map()
        this.clientId = null
        this._lastConnectOptions = {}
    }

    // ─────────────────────────────────────────────────────────────────────────
    // EventEmitter Methods
    // ─────────────────────────────────────────────────────────────────────────

    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = []
        }
        this.listeners[event].push(callback)
        return this
    }

    off(event, callback) {
        if (!this.listeners[event]) return this
        this.listeners[event] = this.listeners[event].filter(cb => cb != callback)
        return this
    }

    emit(event, ...args) {
        if (!this.listeners[event]) return
        this.listeners[event].forEach(callback => {
            callback(...args)
        })
    }

    // ─────────────────────────────────────────────────────────────────────────
    // WebRTC Core Methods
    // ─────────────────────────────────────────────────────────────────────────

    async connect(options = {}) {
        const config = {
            sdpSemantics: 'unified-plan',
            iceServers: this.iceServers
        }

        const pc = new RTCPeerConnection(config)
        this.pc = pc
        this.trackCounter = 0
        this.tracks.clear()

        const enabledCameras = options.cameras

        pc.ontrack = (evt) => {
            if (evt.track.kind != 'video') return
            const cameraIndex = this.trackCounter++
            this.tracks.set(cameraIndex, evt.track)

            // Set initial enabled state
            if (enabledCameras != null) {
                evt.track.enabled = enabledCameras.includes(cameraIndex)
            }

            this.emit('track', evt.track, cameraIndex)
        }

        pc.onconnectionstatechange = () => {
            if (pc.connectionState == 'connected') {
                this.emit('connected')
            } else if (pc.connectionState == 'disconnected' || pc.connectionState == 'failed') {
                this.emit('disconnected')
            }
        }

        // Request video tracks
        for (let i = 0; i < this.maxCameras; i++) {
            pc.addTransceiver('video', { direction: 'recvonly' })
        }

        // SDP Negotiation
        const offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        await waitForIceGathering(pc)

        const response = await fetch(`${this.serverUrl}/offer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sdp: pc.localDescription.sdp,
                type: pc.localDescription.type,
                roles: options.roles || []
            })
        })

        if (!response.ok) {
            const error = new Error(`Connection failed: ${response.status}`)
            this.emit('error', error)
            throw error
        }

        const answer = await response.json()
        this.clientId = answer.client_id
        await pc.setRemoteDescription(answer)

        // Connect WebSocket for real-time camera updates
        this._connectWebSocket()
        this._lastConnectOptions = options

        return this
    }

    _connectWebSocket() {
        if (this.ws) {
            this.ws.close()
        }

        const wsProtocol = window.location.protocol == 'https:' ? 'wss:' : 'ws:'
        const wsUrl = `${wsProtocol}//${window.location.host}/ws`

        this.ws = new WebSocket(wsUrl)

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data)
            if (data.type == 'camera_change') {
                console.log('Camera change detected:', data.cameras)
                this.emit('cameraChange', data.cameras)
            }
        }

        this.ws.onerror = (error) => {
            console.warn('WebSocket error:', error)
        }

        this.ws.onclose = () => {
            console.log('WebSocket closed')
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close()
            this.ws = null
        }
        if (this.pc) {
            this.pc.close()
            this.pc = null
        }
        this.tracks.clear()
        this.trackCounter = 0
        this.emit('disconnected')
        return this
    }

    async reconnect() {
        console.log('Reconnecting due to camera change...')
        this.disconnect()
        await this.connect(this._lastConnectOptions)
        return this
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Track On/Off Methods
    // ─────────────────────────────────────────────────────────────────────────

    async setTrackEnabled(cameraIndex, enabled) {
        const track = this.tracks.get(cameraIndex)
        if (!track) return false
        track.enabled = enabled

        // Call server to pause/resume (saves bandwidth)
        await fetch(`${this.serverUrl}/pause_camera`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                camera_index: cameraIndex,
                paused: !enabled,
                client_id: this.clientId
            })
        })

        this.emit(enabled ? 'trackEnabled' : 'trackDisabled', cameraIndex)
        return true
    }

    isTrackEnabled(cameraIndex) {
        const track = this.tracks.get(cameraIndex)
        return track ? track.enabled : false
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Camera Control Methods
    // ─────────────────────────────────────────────────────────────────────────

    async setFocus(cameraIndex, options = {}) {
        const response = await fetch(`${this.serverUrl}/set_focus`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                camera_index: cameraIndex,
                auto: options.auto ?? true,
                value: options.value ?? 0
            })
        })
        if (!response.ok) {
            throw new Error('Failed to set focus')
        }
        return response.json()
    }

    async setExposure(cameraIndex, value) {
        const response = await fetch(`${this.serverUrl}/set_exposure`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                camera_index: cameraIndex,
                value: value
            })
        })
        if (!response.ok) {
            throw new Error('Failed to set exposure')
        }
        return response.json()
    }

    async setAutoExposure(cameraIndex, options = {}) {
        const response = await fetch(`${this.serverUrl}/set_auto_exposure`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                camera_index: cameraIndex,
                enabled: options.enabled ?? false,
                target_brightness: options.targetBrightness ?? 128
            })
        })
        if (!response.ok) {
            throw new Error('Failed to set auto exposure')
        }
        return response.json()
    }

    async capture(cameraIndex) {
        const response = await fetch(`${this.serverUrl}/capture?camera_index=${cameraIndex}`)
        if (!response.ok) {
            throw new Error('Capture failed')
        }
        return response.blob()
    }
}

export default InstantReality
