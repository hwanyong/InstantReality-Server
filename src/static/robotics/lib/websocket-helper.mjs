// ─────────────────────────────────────────────────────────────────────────────
// WebSocket Helper Module
// src/static/robotics/lib/websocket-helper.mjs
//
// Auto-reconnecting WebSocket with message-type routing.
// ─────────────────────────────────────────────────────────────────────────────

export class WebSocketHelper {
    constructor(options = {}) {
        this.reconnectInterval = options.reconnectInterval || 3000
        this.ws = null
        this._handlers = {}     // { type: [handler, ...] }
        this._anyHandlers = []  // handlers for all messages
        this._closed = false    // explicit close flag
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Connection
    // ─────────────────────────────────────────────────────────────────────────

    connect() {
        this._closed = false
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
        this.ws = new WebSocket(`${protocol}//${location.host}/ws`)

        this.ws.onopen = () => {
            console.log('WebSocketHelper: connected')
        }

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                const type = data.type

                // Dispatch to type-specific handlers
                if (type && this._handlers[type]) {
                    this._handlers[type].forEach(fn => fn(data))
                }

                // Dispatch to catch-all handlers
                this._anyHandlers.forEach(fn => fn(data))
            } catch (err) {
                console.error('WebSocketHelper: message parse error:', err)
            }
        }

        this.ws.onclose = () => {
            console.log('WebSocketHelper: disconnected')
            if (!this._closed) {
                console.log(`WebSocketHelper: reconnecting in ${this.reconnectInterval}ms...`)
                setTimeout(() => this.connect(), this.reconnectInterval)
            }
        }

        this.ws.onerror = (err) => {
            console.error('WebSocketHelper: error:', err)
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Event Registration
    // ─────────────────────────────────────────────────────────────────────────

    on(messageType, handler) {
        if (!this._handlers[messageType]) {
            this._handlers[messageType] = []
        }
        this._handlers[messageType].push(handler)
    }

    onAny(handler) {
        this._anyHandlers.push(handler)
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Disconnect
    // ─────────────────────────────────────────────────────────────────────────

    close() {
        this._closed = true
        if (this.ws) {
            this.ws.close()
            this.ws = null
        }
    }
}

export default WebSocketHelper
