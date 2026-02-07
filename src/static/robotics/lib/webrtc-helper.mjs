// ─────────────────────────────────────────────────────────────────────────────
// WebRTC Helper Module
// src/static/robotics/lib/webrtc-helper.mjs
//
// Shared WebRTC connection helper wrapping InstantReality SDK.
// Handles role-based track mapping, video/canvas binding, and camera pause.
// ─────────────────────────────────────────────────────────────────────────────

import InstantReality from '/sdk/instant-reality.mjs'

const DEFAULT_ROLE_ORDER = ['TopView', 'QuarterView', 'RightRobot', 'LeftRobot']
const API_BASE = ''

export class WebRTCHelper {
    constructor(options = {}) {
        this.ir = new InstantReality({ serverUrl: options.serverUrl || API_BASE })
        this.roleOrder = options.roleOrder || DEFAULT_ROLE_ORDER
        this.roles = []              // Populated after connect
        this._handlers = {}          // event -> [handler, ...]
        this._pausedRoles = new Set()
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Connection
    // ─────────────────────────────────────────────────────────────────────────

    async connect(options = {}) {
        const fetchRoles = options.fetchRoles !== false  // default: true

        // 1. Optionally fetch role mapping from server
        if (fetchRoles) {
            try {
                const roleMap = await this.ir.getRoles()
                this.roles = this.roleOrder.filter(r => roleMap[r] && roleMap[r].connected)
                console.log('WebRTCHelper: Dynamic roles:', this.roles)
            } catch (err) {
                console.error('WebRTCHelper: Failed to fetch roles, using fallback:', err)
                this.roles = options.roles || this.roleOrder
            }
        } else {
            this.roles = options.roles || this.roleOrder
        }

        // 2. Wire up SDK events
        this.ir.on('track', (track, index, roleName) => {
            const role = roleName || this.roles[index]
            console.log(`WebRTCHelper: Received track ${index}, role: ${role}`)
            this._emit('track', track, index, role)
        })

        this.ir.on('connected', () => {
            console.log('WebRTCHelper: connected')
            this._emit('connected')
        })

        this.ir.on('disconnected', () => {
            console.log('WebRTCHelper: disconnected')
            this._emit('disconnected')
        })

        // 3. Connect with roles
        await this.ir.connect({ roles: this.roles })
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Event Handling
    // ─────────────────────────────────────────────────────────────────────────

    on(event, handler) {
        if (!this._handlers[event]) {
            this._handlers[event] = []
        }
        this._handlers[event].push(handler)
    }

    _emit(event, ...args) {
        if (this._handlers[event]) {
            this._handlers[event].forEach(fn => fn(...args))
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Video Binding
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * Bind a role to a <video> element. Automatically plays when track arrives.
     * @param {string} role - Role name (e.g. 'TopView')
     * @param {HTMLVideoElement} videoEl - Target video element
     */
    bindVideo(role, videoEl) {
        this.on('track', (track, index, trackRole) => {
            if (trackRole != role) return
            videoEl.srcObject = new MediaStream([track])
            videoEl.play().catch(e => console.warn('Autoplay prevented:', e))
        })
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Camera Pause (Per-Client)
    // ─────────────────────────────────────────────────────────────────────────

    get clientId() {
        return this.ir?.clientId
    }

    isRolePaused(role) {
        return this._pausedRoles.has(role)
    }

    async pauseCamera(role, paused) {
        if (!this.ir || !this.ir.clientId) {
            throw new Error('WebRTC 연결 필요')
        }

        const res = await fetch(`${API_BASE}/pause_camera_client`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                client_id: this.ir.clientId,
                role: role,
                paused: paused
            })
        })

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`)
        }

        if (paused) {
            this._pausedRoles.add(role)
        } else {
            this._pausedRoles.delete(role)
        }
    }

    async togglePause(role) {
        const paused = !this._pausedRoles.has(role)
        await this.pauseCamera(role, paused)
        return paused
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Utilities
    // ─────────────────────────────────────────────────────────────────────────

    getRoleIndex(role) {
        return this.roles.indexOf(role)
    }

    disconnect() {
        this.ir.disconnect()
    }
}

export default WebRTCHelper
