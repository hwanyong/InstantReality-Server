// ─────────────────────────────────────────────────────────────────────────────
// Toast Notification Module
// src/static/robotics/lib/toast.mjs
// ─────────────────────────────────────────────────────────────────────────────

let toastElement = null

function ensureToastElement() {
    if (toastElement) return toastElement

    toastElement = document.getElementById('toast')
    if (!toastElement) {
        toastElement = document.createElement('div')
        toastElement.id = 'toast'
        toastElement.className = 'toast'
        document.body.appendChild(toastElement)
    }
    return toastElement
}

export function showToast(message, duration = 2000) {
    const toast = ensureToastElement()
    toast.textContent = message
    toast.classList.add('show')
    setTimeout(() => toast.classList.remove('show'), duration)
}

export function showError(message, duration = 3000) {
    const toast = ensureToastElement()
    toast.textContent = `❌ ${message}`
    toast.style.background = 'var(--danger, #f85149)'
    toast.classList.add('show')
    setTimeout(() => {
        toast.classList.remove('show')
        toast.style.background = ''
    }, duration)
}

export function showSuccess(message, duration = 2000) {
    const toast = ensureToastElement()
    toast.textContent = `✓ ${message}`
    toast.style.background = 'var(--success, #3fb950)'
    toast.classList.add('show')
    setTimeout(() => {
        toast.classList.remove('show')
        toast.style.background = ''
    }, duration)
}
