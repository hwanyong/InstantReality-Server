// src/static/robotics/ar-overlay.mjs
// AR Visualization Module using Canvas 2D API

export class AROverlay {
    constructor(canvas) {
        this.canvas = canvas
        this.ctx = canvas.getContext('2d')
        this.targets = []
        this.reachCircle = { x: 0, y: 0, radius: 0, visible: false }
    }

    clear() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height)
        this.targets = []
    }

    // Draw target point with crosshair
    drawTarget(normX, normY, label = '', color = '#ff4444') {
        const w = this.canvas.width
        const h = this.canvas.height
        const x = (normX / 1000) * w
        const y = (normY / 1000) * h

        const ctx = this.ctx

        // Point
        ctx.fillStyle = color
        ctx.beginPath()
        ctx.arc(x, y, 8, 0, Math.PI * 2)
        ctx.fill()

        // Crosshair
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.setLineDash([5, 5])
        ctx.beginPath()
        ctx.moveTo(x - 30, y)
        ctx.lineTo(x + 30, y)
        ctx.moveTo(x, y - 30)
        ctx.lineTo(x, y + 30)
        ctx.stroke()
        ctx.setLineDash([])

        // Label
        if (label) {
            ctx.fillStyle = '#ffffff'
            ctx.font = 'bold 14px sans-serif'
            ctx.textAlign = 'left'
            ctx.fillText(label, x + 15, y - 10)
        }

        this.targets.push({ x, y, label })
    }

    // Draw bounding box
    drawBoundingBox(normX, normY, normW, normH, color = '#44ff44') {
        const w = this.canvas.width
        const h = this.canvas.height

        const x = (normX / 1000) * w
        const y = (normY / 1000) * h
        const bw = (normW / 1000) * w
        const bh = (normH / 1000) * h

        const ctx = this.ctx
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.strokeRect(x - bw / 2, y - bh / 2, bw, bh)
    }

    // Draw approach vector (arrow from current to target)
    drawApproachVector(fromX, fromY, toX, toY, color = '#58a6ff') {
        const ctx = this.ctx
        const w = this.canvas.width
        const h = this.canvas.height

        const x1 = (fromX / 1000) * w
        const y1 = (fromY / 1000) * h
        const x2 = (toX / 1000) * w
        const y2 = (toY / 1000) * h

        // Line
        ctx.strokeStyle = color
        ctx.lineWidth = 3
        ctx.beginPath()
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
        ctx.stroke()

        // Arrowhead
        const angle = Math.atan2(y2 - y1, x2 - x1)
        const headLen = 15
        ctx.fillStyle = color
        ctx.beginPath()
        ctx.moveTo(x2, y2)
        ctx.lineTo(
            x2 - headLen * Math.cos(angle - Math.PI / 6),
            y2 - headLen * Math.sin(angle - Math.PI / 6)
        )
        ctx.lineTo(
            x2 - headLen * Math.cos(angle + Math.PI / 6),
            y2 - headLen * Math.sin(angle + Math.PI / 6)
        )
        ctx.closePath()
        ctx.fill()
    }

    // Draw reach circle (robot workspace boundary)
    drawReachCircle(centerNormX, centerNormY, radiusNorm, color = 'rgba(88, 166, 255, 0.3)') {
        const w = this.canvas.width
        const h = this.canvas.height

        const cx = (centerNormX / 1000) * w
        const cy = (centerNormY / 1000) * h
        const r = (radiusNorm / 1000) * Math.min(w, h)

        const ctx = this.ctx
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.setLineDash([10, 5])
        ctx.beginPath()
        ctx.arc(cx, cy, r, 0, Math.PI * 2)
        ctx.stroke()
        ctx.setLineDash([])

        this.reachCircle = { x: cx, y: cy, radius: r, visible: true }
    }

    // Draw coordinate axes (for debugging)
    drawAxes(originNormX, originNormY) {
        const w = this.canvas.width
        const h = this.canvas.height
        const ox = (originNormX / 1000) * w
        const oy = (originNormY / 1000) * h

        const ctx = this.ctx
        const len = 80

        // X axis (red)
        ctx.strokeStyle = '#ff0000'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(ox, oy)
        ctx.lineTo(ox + len, oy)
        ctx.stroke()
        ctx.fillStyle = '#ff0000'
        ctx.fillText('X', ox + len + 5, oy + 5)

        // Y axis (green, pointing up in camera = down in robot)
        ctx.strokeStyle = '#00ff00'
        ctx.beginPath()
        ctx.moveTo(ox, oy)
        ctx.lineTo(ox, oy - len)
        ctx.stroke()
        ctx.fillStyle = '#00ff00'
        ctx.fillText('Y', ox - 10, oy - len - 5)
    }

    // Full visualization from Gemini result
    visualizeResult(geminiResult) {
        this.clear()

        if (!geminiResult) return

        const coords = geminiResult.gemini_analysis?.coordinates
        if (!coords) return

        // Target point (Gemini returns [y, x])
        const targetX = coords[1]
        const targetY = coords[0]

        this.drawTarget(targetX, targetY, geminiResult.ik_result?.arm || '')
        this.drawBoundingBox(targetX, targetY, 100, 100)

        // Draw approach vector from robot base
        // Robot base is at bottom center
        const robotBaseX = 500  // Center
        const robotBaseY = 950  // Bottom
        this.drawApproachVector(robotBaseX, robotBaseY, targetX, targetY)

        // Draw reach circles for workspace
        this.drawReachCircle(500, 950, 400)  // Approximate reach
    }
}

// Export singleton for simple use
let overlayInstance = null
export function getAROverlay(canvas) {
    if (!overlayInstance) {
        overlayInstance = new AROverlay(canvas)
    }
    return overlayInstance
}
