// ─────────────────────────────────────────────────────────────────────────────
// Camera Viewer Module
// src/static/robotics/lib/camera-viewer.mjs
// ─────────────────────────────────────────────────────────────────────────────

import InstantReality from '/sdk/instant-reality.mjs'

export class CameraViewer {
    constructor(options = {}) {
        this.ir = new InstantReality({ serverUrl: options.serverUrl || '' })
        this.canvases = new Map()      // cameraIndex -> canvas
        this.videoElements = new Map() // cameraIndex -> hidden video element
        this.roles = options.roles || ['TopView']
        this.roleToIndex = {}          // role -> cameraIndex
        this.connected = false
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Connection Management
    // ─────────────────────────────────────────────────────────────────────────

    async connect() {
        // Track received handler
        this.ir.on('track', (track, index) => {
            console.log(`CameraViewer: Received track ${index}`)
            this.roleToIndex[this.roles[index]] = index
            this._setupVideoForTrack(track, index)
        })

        this.ir.on('connected', () => {
            this.connected = true
            console.log('CameraViewer: WebRTC connected')
        })

        this.ir.on('disconnected', () => {
            this.connected = false
            console.log('CameraViewer: WebRTC disconnected')
        })

        // Connect with roles
        await this.ir.connect({ roles: this.roles })
        await this._connectWebSocket()
    }

    async _connectWebSocket() {
        await this.ir._connectWebSocket()
        // Forward WebSocket events
        this.ir.on('cameraChange', (cameras) => {
            if (this.onCameraChange) this.onCameraChange(cameras)
        })
        this.ir.on('calibrationProgress', (data) => {
            if (this.onCalibrationProgress) this.onCalibrationProgress(data)
        })
    }

    disconnect() {
        this.ir.disconnect()
        this.connected = false
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Canvas Binding
    // ─────────────────────────────────────────────────────────────────────────

    bindCanvas(roleOrIndex, canvasId) {
        const canvas = document.getElementById(canvasId)
        if (!canvas) {
            console.error(`CameraViewer: Canvas ${canvasId} not found`)
            return
        }

        const index = typeof roleOrIndex == 'string'
            ? this.roles.indexOf(roleOrIndex)
            : roleOrIndex

        if (index == -1) {
            console.error(`CameraViewer: Role ${roleOrIndex} not found`)
            return
        }

        this.canvases.set(index, canvas)

        // If video already exists, start rendering
        if (this.videoElements.has(index)) {
            this._startRendering(index)
        }
    }

    _setupVideoForTrack(track, index) {
        // Create hidden video element
        const video = document.createElement('video')
        video.autoplay = true
        video.muted = true
        video.playsInline = true
        video.srcObject = new MediaStream([track])
        video.style.display = 'none'
        document.body.appendChild(video)

        this.videoElements.set(index, video)

        // Start rendering if canvas is bound
        if (this.canvases.has(index)) {
            video.onloadedmetadata = () => this._startRendering(index)
        }
    }

    _startRendering(index) {
        const video = this.videoElements.get(index)
        const canvas = this.canvases.get(index)
        if (!video || !canvas) return

        const ctx = canvas.getContext('2d')

        const render = () => {
            if (video.readyState >= 2) {
                // Match canvas to video dimensions
                if (canvas.width != video.videoWidth || canvas.height != video.videoHeight) {
                    canvas.width = video.videoWidth
                    canvas.height = video.videoHeight
                }
                ctx.drawImage(video, 0, 0)
            }
            requestAnimationFrame(render)
        }
        render()
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Camera Controls (Delegate to SDK)
    // ─────────────────────────────────────────────────────────────────────────

    getIndexByRole(role) {
        return this.roles.indexOf(role)
    }

    async setFocus(roleOrIndex, options = {}) {
        const index = typeof roleOrIndex == 'string'
            ? this.getIndexByRole(roleOrIndex)
            : roleOrIndex
        return this.ir.setFocus(index, options)
    }

    async setExposure(roleOrIndex, value) {
        const index = typeof roleOrIndex == 'string'
            ? this.getIndexByRole(roleOrIndex)
            : roleOrIndex
        return this.ir.setExposure(index, value)
    }

    async setAutoExposure(roleOrIndex, options = {}) {
        const index = typeof roleOrIndex == 'string'
            ? this.getIndexByRole(roleOrIndex)
            : roleOrIndex
        return this.ir.setAutoExposure(index, options)
    }

    async capture(roleOrIndex) {
        const index = typeof roleOrIndex == 'string'
            ? this.getIndexByRole(roleOrIndex)
            : roleOrIndex
        return this.ir.capture(index)
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Event Handlers (To be overridden)
    // ─────────────────────────────────────────────────────────────────────────

    onCameraChange = null
    onCalibrationProgress = null
}

export default CameraViewer
