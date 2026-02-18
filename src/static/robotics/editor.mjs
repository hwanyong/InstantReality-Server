// ─────────────────────────────────────────────────────────────────────────────
// Config Editor — Main Controller
// src/static/robotics/editor.mjs
//
// Web-based editor for prompt templates and execution config.
// Files are saved via REST API and auto-reloaded by config_loader's mtime cache.
// ─────────────────────────────────────────────────────────────────────────────

import { showToast, showSuccess, showError } from './lib/toast.mjs'

const API_BASE = ''

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────

let currentFile = null      // { name, path, content, mtime }
let originalContent = null  // for dirty detection + revert
let fileList = []           // [{ name, path, exists, mtime, size }]

// ─────────────────────────────────────────────────────────────────────────────
// DOM Elements
// ─────────────────────────────────────────────────────────────────────────────

const el = {
    fileList: document.getElementById('file-list'),
    filePath: document.getElementById('file-path'),
    textarea: document.getElementById('editor-textarea'),
    saveBtn: document.getElementById('save-btn'),
    revertBtn: document.getElementById('revert-btn'),
    testInput: document.getElementById('test-input'),
    analyzeBtn: document.getElementById('test-analyze-btn'),
    executeBtn: document.getElementById('test-execute-btn'),
    testResult: document.getElementById('test-result'),
    taskSteps: document.getElementById('task-steps'),
}

// Step icons
const STEP_ICONS = {
    move_arm: '🦾', open_gripper: '✋', close_gripper: '✊', go_home: '🏠'
}

// ─────────────────────────────────────────────────────────────────────────────
// File List
// ─────────────────────────────────────────────────────────────────────────────

async function loadFileList() {
    try {
        const res = await fetch(`${API_BASE}/api/config/files`)
        const data = await res.json()
        fileList = data.files || []
        renderFileList()
    } catch (e) {
        showError(`파일 목록 로드 실패: ${e.message}`)
    }
}

function renderFileList() {
    if (!el.fileList) return
    el.fileList.innerHTML = fileList.map(f => {
        const icon = f.path.endsWith('.yaml') ? '⚙️' : '📄'
        const active = currentFile && currentFile.name == f.name ? 'active' : ''
        const dirty = currentFile && currentFile.name == f.name && isDirty() ? 'dirty' : ''
        return `<li class="file-item ${active} ${dirty}" data-name="${f.name}">
            <span class="file-icon">${icon}</span>
            <span class="file-name">${f.name}</span>
            <span class="dirty-dot"></span>
        </li>`
    }).join('')

    // Bind clicks
    el.fileList.querySelectorAll('.file-item').forEach(item => {
        item.addEventListener('click', () => {
            const name = item.dataset.name
            if (name) selectFile(name)
        })
    })
}

// ─────────────────────────────────────────────────────────────────────────────
// File Selection & Edit
// ─────────────────────────────────────────────────────────────────────────────

async function selectFile(name) {
    // Warn if unsaved
    if (isDirty()) {
        if (!confirm('저장하지 않은 변경사항이 있습니다. 계속하시겠습니까?')) return
    }

    try {
        const res = await fetch(`${API_BASE}/api/config/file/${name}`)
        const data = await res.json()
        if (data.error) {
            showError(data.error)
            return
        }

        currentFile = data
        originalContent = data.content
        el.textarea.value = data.content
        el.textarea.disabled = false
        el.filePath.textContent = data.path
        el.saveBtn.disabled = false
        el.revertBtn.disabled = false

        renderFileList()
        showToast(`📄 ${name} 로드됨`)
    } catch (e) {
        showError(`파일 로드 실패: ${e.message}`)
    }
}

function isDirty() {
    if (!currentFile) return false
    return el.textarea.value != originalContent
}

function updateDirtyState() {
    renderFileList()
}

// ─────────────────────────────────────────────────────────────────────────────
// Save / Revert
// ─────────────────────────────────────────────────────────────────────────────

async function saveFile() {
    if (!currentFile) return

    const content = el.textarea.value
    el.saveBtn.disabled = true
    el.saveBtn.textContent = '⏳ Saving...'

    try {
        const res = await fetch(`${API_BASE}/api/config/file/${currentFile.name}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        })
        const data = await res.json()

        if (data.error) {
            showError(data.error)
            return
        }

        originalContent = content
        currentFile.mtime = data.mtime
        renderFileList()
        showSuccess(`💾 ${currentFile.name} 저장됨`)
    } catch (e) {
        showError(`저장 실패: ${e.message}`)
    } finally {
        el.saveBtn.disabled = false
        el.saveBtn.textContent = '💾 Save'
    }
}

async function revertFile() {
    if (!currentFile) return
    if (!isDirty()) {
        showToast('변경사항 없음')
        return
    }

    if (!confirm('변경사항을 되돌리시겠습니까?')) return
    await selectFile(currentFile.name)
    showToast('↩️ 되돌림 완료')
}

// ─────────────────────────────────────────────────────────────────────────────
// Quick Test — Analyze & Execute
// ─────────────────────────────────────────────────────────────────────────────

async function testAnalyze() {
    const instruction = el.testInput?.value?.trim()
    if (!instruction) {
        showError('테스트 명령을 입력해주세요')
        return
    }

    el.analyzeBtn.disabled = true
    el.analyzeBtn.textContent = '⏳...'
    el.testResult.textContent = 'Analyzing...'

    try {
        const res = await fetch(`${API_BASE}/api/gemini/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instruction })
        })
        const data = await res.json()
        el.testResult.textContent = JSON.stringify(data, null, 2)

        if (data.error) {
            showError(data.error)
        } else {
            showSuccess('분석 완료')
        }
    } catch (e) {
        el.testResult.textContent = `Error: ${e.message}`
        showError(`분석 실패: ${e.message}`)
    } finally {
        el.analyzeBtn.disabled = false
        el.analyzeBtn.textContent = '🚀 Analyze'
    }
}

async function testExecute() {
    const instruction = el.testInput?.value?.trim()
    if (!instruction) {
        showError('테스트 명령을 입력해주세요')
        return
    }

    el.executeBtn.disabled = true
    el.executeBtn.textContent = '⏳...'
    el.testResult.textContent = 'Generating and executing plan...'
    renderTaskSteps([])

    try {
        const res = await fetch(`${API_BASE}/api/plan/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instruction })
        })
        const data = await res.json()

        if (data.error) {
            el.testResult.textContent = `Error: ${data.error}`
            showError(data.error)
            el.executeBtn.disabled = false
            el.executeBtn.textContent = '⚡ Execute'
            return
        }

        showSuccess(`Plan ${data.plan_id} 시작됨 (${data.step_count || 0}단계)`)
    } catch (e) {
        el.testResult.textContent = `Error: ${e.message}`
        showError(`실행 실패: ${e.message}`)
        el.executeBtn.disabled = false
        el.executeBtn.textContent = '⚡ Execute'
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Task Step Rendering (reused from app.mjs)
// ─────────────────────────────────────────────────────────────────────────────

function renderTaskSteps(steps) {
    if (!el.taskSteps) return
    if (!steps || steps.length == 0) {
        el.taskSteps.innerHTML = '<span class="step-empty">No plan yet</span>'
        return
    }
    el.taskSteps.innerHTML = steps.map((s, i) => {
        const icon = STEP_ICONS[s.tool] || '⚙️'
        const desc = s.description || s.tool
        return `<div class="step-item" data-index="${i}" data-status="pending">${icon} ${desc}</div>`
    }).join('')
}

function updateStepStatus(index, status) {
    if (!el.taskSteps) return
    const item = el.taskSteps.querySelector(`[data-index="${index}"]`)
    if (!item) return
    item.dataset.status = status
    const prefix = status == 'running' ? '🔄' : status == 'done' ? '✅' : status == 'error' ? '❌' : '⏳'
    item.textContent = `${prefix} ${item.textContent.substring(2)}`
}

// ─────────────────────────────────────────────────────────────────────────────
// WebSocket — Plan Progress (reused pattern from app.mjs)
// ─────────────────────────────────────────────────────────────────────────────

function initPlanWebSocket() {
    const protocol = location.protocol == 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${location.host}/ws`)

    ws.onmessage = (event) => {
        let data
        try { data = JSON.parse(event.data) } catch { return }

        const type = data.type

        if (type == 'plan:ready') {
            renderTaskSteps(data.steps || [])
            el.testResult.textContent = JSON.stringify(data, null, 2)
            showSuccess(`${data.step_count || 0}단계 실행 계획 생성됨`)
        }

        if (type == 'step:start') {
            updateStepStatus(data.index, 'running')
        }

        if (type == 'step:done') {
            updateStepStatus(data.index, 'done')
        }

        if (type == 'step:failed') {
            updateStepStatus(data.index, 'error')
            showError(`Step ${data.index + 1} 실패`)
        }

        if (type == 'plan:complete') {
            showSuccess(`실행 완료 (${data.total_time_sec}s)`)
            _resetExecuteUI()
        }

        if (type == 'plan:failed' || type == 'plan:error') {
            showError(`실행 실패: ${data.error || 'Unknown'}`)
            _resetExecuteUI()
        }

        if (type == 'plan:aborted') {
            showToast('⏹ Plan 중단됨')
            _resetExecuteUI()
        }
    }

    ws.onclose = () => {
        setTimeout(initPlanWebSocket, 3000)
    }
}

function _resetExecuteUI() {
    if (el.executeBtn) {
        el.executeBtn.disabled = false
        el.executeBtn.textContent = '⚡ Execute'
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Event Listeners
// ─────────────────────────────────────────────────────────────────────────────

function initEventListeners() {
    // Save
    if (el.saveBtn) el.saveBtn.addEventListener('click', saveFile)

    // Revert
    if (el.revertBtn) el.revertBtn.addEventListener('click', revertFile)

    // Dirty detection
    if (el.textarea) el.textarea.addEventListener('input', updateDirtyState)

    // Quick Test
    if (el.analyzeBtn) el.analyzeBtn.addEventListener('click', testAnalyze)
    if (el.executeBtn) el.executeBtn.addEventListener('click', testExecute)

    // Enter key in test input
    if (el.testInput) {
        el.testInput.addEventListener('keydown', (e) => {
            if (e.key == 'Enter') {
                e.preventDefault()
                testAnalyze()
            }
        })
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Cmd+S / Ctrl+S → Save
        if ((e.metaKey || e.ctrlKey) && e.key == 's') {
            e.preventDefault()
            if (currentFile) saveFile()
        }
    })

    // Tab key in textarea → insert spaces
    if (el.textarea) {
        el.textarea.addEventListener('keydown', (e) => {
            if (e.key == 'Tab') {
                e.preventDefault()
                const start = el.textarea.selectionStart
                const end = el.textarea.selectionEnd
                el.textarea.value = el.textarea.value.substring(0, start) + '  ' + el.textarea.value.substring(end)
                el.textarea.selectionStart = el.textarea.selectionEnd = start + 2
                updateDirtyState()
            }
        })
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Initialize
// ─────────────────────────────────────────────────────────────────────────────

async function init() {
    console.log('[editor.mjs] Config Editor initializing...')
    initEventListeners()
    initPlanWebSocket()
    await loadFileList()

    // Auto-select first file
    if (fileList.length > 0) {
        await selectFile(fileList[0].name)
    }
}

init()
