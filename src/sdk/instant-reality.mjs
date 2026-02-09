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
        this.iceServers = options.iceServers || []  // Local network: no STUN needed
        this.pc = null
        this.ws = null
        this.trackCounter = 0
        this.listeners = {}
        this.tracks = new Map()    // Map<role, {track, index}>
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
    // Role Mapping Methods
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Fetch current role→camera mapping from server.
     * Should be called before connect() to get latest role assignments.
     * 
     * @returns {Promise<Object>} Role map: {TopView: {index, connected, name}, ...}
     */
    async getRoles() {
        const res = await fetch(`${this.serverUrl}/api/cameras/roles`)
        if (!res.ok) {
            throw new Error(`Failed to fetch roles: ${res.status}`)
        }
        this.roleMap = await res.json()
        this.emit('roleMapReady', this.roleMap)
        return this.roleMap
    }

    /**
     * Get roles that are currently connected (have active tracks).
     * 
     * @returns {string[]} Array of connected role names
     */
    getConnectedRoles() {
        return [...this.tracks.keys()]
    }

    /**
     * Get the MediaStreamTrack for a specific role.
     * 
     * @param {string} role - Role name (e.g. 'TopView')
     * @returns {MediaStreamTrack|null}
     */
    getTrack(role) {
        return this.tracks.get(role)?.track || null
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

        const enabledCameras = options.cameras    // Role names to enable initially

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

        // Store mapped roles from server
        this.mappedRoles = answer.mapped_roles || options.roles || []

        // Define ontrack handler AFTER we have mappedRoles
        pc.ontrack = (evt) => {
            if (evt.track.kind != 'video') return
            const cameraIndex = this.trackCounter++
            const role = this.mappedRoles[cameraIndex] || `camera_${cameraIndex}`
            this.tracks.set(role, { track: evt.track, index: cameraIndex })

            // Set initial enabled state
            if (enabledCameras != null) {
                evt.track.enabled = enabledCameras.includes(role)
            }

            this.emit('track', evt.track, role)
        }

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
            // Calibration events
            if (data.type == 'calibration_progress') {
                this.emit('calibrationProgress', data.data)
            }
            if (data.type == 'calibration_complete') {
                this.emit('calibrationComplete', data.data)
            }
            if (data.type == 'calibration_error') {
                this.emit('calibrationError', data.data)
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

    async setTrackEnabled(role, enabled) {
        const entry = this.tracks.get(role)
        if (!entry) return false
        entry.track.enabled = enabled

        // Call server to pause/resume (saves bandwidth)
        await fetch(`${this.serverUrl}/pause_camera`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                camera_index: entry.index,
                paused: !enabled,
                client_id: this.clientId
            })
        })

        this.emit(enabled ? 'trackEnabled' : 'trackDisabled', role)
        return true
    }

    isTrackEnabled(role) {
        const entry = this.tracks.get(role)
        return entry ? entry.track.enabled : false
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Camera Control Methods
    // ─────────────────────────────────────────────────────────────────────────

    async setFocus(role, options = {}) {
        const entry = this.tracks.get(role)
        if (!entry) throw new Error(`Unknown role: ${role}`)
        const response = await fetch(`${this.serverUrl}/set_focus`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                camera_index: entry.index,
                auto: options.auto ?? true,
                value: options.value ?? 0
            })
        })
        if (!response.ok) {
            throw new Error('Failed to set focus')
        }
        return response.json()
    }

    async setExposure(role, value) {
        const entry = this.tracks.get(role)
        if (!entry) throw new Error(`Unknown role: ${role}`)
        const response = await fetch(`${this.serverUrl}/set_exposure`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                camera_index: entry.index,
                value: value
            })
        })
        if (!response.ok) {
            throw new Error('Failed to set exposure')
        }
        return response.json()
    }

    async setAutoExposure(role, options = {}) {
        const entry = this.tracks.get(role)
        if (!entry) throw new Error(`Unknown role: ${role}`)
        const response = await fetch(`${this.serverUrl}/set_auto_exposure`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                camera_index: entry.index,
                enabled: options.enabled ?? false,
                target_brightness: options.targetBrightness ?? 128
            })
        })
        if (!response.ok) {
            throw new Error('Failed to set auto exposure')
        }
        return response.json()
    }

    async capture(role) {
        const entry = this.tracks.get(role)
        if (!entry) throw new Error(`Unknown role: ${role}`)
        const response = await fetch(`${this.serverUrl}/capture?camera_index=${entry.index}`)
        if (!response.ok) {
            throw new Error('Capture failed')
        }
        return response.blob()
    }
}

export default InstantReality
