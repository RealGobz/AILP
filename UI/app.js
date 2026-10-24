/**
 * AILP Agent Frontend Application Logic
 * Implements Phase 1 Config, Phase 2 Chat, Collapsible Tool Cards, and Latency Tracing.
 */

// Active state
let activeConfig = {
    thread_id: "31",
    user_id: "1",
    name: "Ahmed",
    age: "16",
    gender: "Male",
    grade: "10",
    language: "Arabic",
    country: "Egypt",
    exam_prep: false,
    images: ["F:\\Projects\\AILP\\tests\\data\\image.png"]
};

let attachedImage = "F:\\Projects\\AILP\\tests\\data\\image.png";

// DOM Elements
const configSection = document.getElementById("config-section");
const btnToggleConfig = document.getElementById("btn-toggle-config");
const btnSaveConfig = document.getElementById("btn-save-config");
const btnClearChat = document.getElementById("btn-clear-chat");
const chatFeed = document.getElementById("chat-feed");
const userInputText = document.getElementById("user-input-text");
const btnSendMessage = document.getElementById("btn-send-message");
const fileUploadInput = document.getElementById("file-upload-input");
const chatImageUpload = document.getElementById("chat-image-upload");
const attachedChipRow = document.getElementById("attached-chip-row");
const chipFilename = document.getElementById("chip-filename");
const btnRemoveChip = document.getElementById("btn-remove-chip");
const cfgImagePath = document.getElementById("cfg-image-path");
const imgPreviewContainer = document.getElementById("image-preview-container");
const imgPreviewName = document.getElementById("img-preview-name");
const btnClearImage = document.getElementById("btn-clear-image");

// Pill Elements
const pillUserName = document.getElementById("pill-user-name");
const pillGrade = document.getElementById("pill-grade");
const pillThread = document.getElementById("pill-thread");

// Initialize on Load
document.addEventListener("DOMContentLoaded", async () => {
    await loadDefaultConfig();
    setupEventListeners();
    updateUIFromConfig();
});

// Load Config from Server
async function loadDefaultConfig() {
    try {
        const res = await fetch("/api/config");
        if (res.ok) {
            const data = await res.json();
            activeConfig = { ...activeConfig, ...data };
            if (activeConfig.images && activeConfig.images.length > 0) {
                attachedImage = activeConfig.images[0];
            }
        }
    } catch (e) {
        console.warn("Using offline default config:", e);
    }
}

// Populate UI Fields
function updateUIFromConfig() {
    document.getElementById("cfg-name").value = activeConfig.name || "Ahmed";
    document.getElementById("cfg-grade").value = activeConfig.grade || "10";
    document.getElementById("cfg-thread-id").value = activeConfig.thread_id || "31";
    document.getElementById("cfg-user-id").value = activeConfig.user_id || "1";
    document.getElementById("cfg-age").value = activeConfig.age || "16";
    document.getElementById("cfg-gender").value = activeConfig.gender || "Male";
    document.getElementById("cfg-language").value = activeConfig.language || "Arabic";
    document.getElementById("cfg-country").value = activeConfig.country || "Egypt";
    document.getElementById("cfg-exam-prep").checked = Boolean(activeConfig.exam_prep);

    if (attachedImage) {
        cfgImagePath.value = attachedImage;
        const basename = attachedImage.split(/[\\/]/).pop();
        imgPreviewName.textContent = basename;
        chipFilename.textContent = basename;
        imgPreviewContainer.style.display = "flex";
        attachedChipRow.style.display = "flex";
    } else {
        cfgImagePath.value = "";
        imgPreviewContainer.style.display = "none";
        attachedChipRow.style.display = "none";
    }

    // Header Pill
    pillUserName.textContent = activeConfig.name || "Ahmed";
    pillGrade.textContent = activeConfig.grade || "10";
    pillThread.textContent = activeConfig.thread_id || "31";
}

// Read Form into activeConfig
function saveFormToConfig() {
    activeConfig.name = document.getElementById("cfg-name").value.trim() || "Ahmed";
    activeConfig.grade = document.getElementById("cfg-grade").value.trim() || "10";
    activeConfig.thread_id = document.getElementById("cfg-thread-id").value.trim() || "31";
    activeConfig.user_id = document.getElementById("cfg-user-id").value.trim() || "1";
    activeConfig.age = document.getElementById("cfg-age").value.trim() || "16";
    activeConfig.gender = document.getElementById("cfg-gender").value;
    activeConfig.language = document.getElementById("cfg-language").value;
    activeConfig.country = document.getElementById("cfg-country").value.trim() || "Egypt";
    activeConfig.exam_prep = document.getElementById("cfg-exam-prep").checked;

    const imgVal = cfgImagePath.value.trim();
    if (imgVal) {
        attachedImage = imgVal;
        activeConfig.images = [imgVal];
    } else {
        attachedImage = null;
        activeConfig.images = [];
    }

    updateUIFromConfig();
}

// Event Listeners
function setupEventListeners() {
    // Toggle Phase 1 Config Panel
    btnToggleConfig.addEventListener("click", () => {
        configSection.classList.toggle("collapsed");
    });

    // Save Config & Proceed to Phase 2 Chat
    btnSaveConfig.addEventListener("click", () => {
        saveFormToConfig();
        configSection.classList.add("collapsed");
        userInputText.focus();
        showToast("Configuration saved! You are now in Phase 2 Chat.");
    });

    // Clear Chat
    btnClearChat.addEventListener("click", () => {
        if (confirm("Clear current conversation feed?")) {
            const welcome = document.getElementById("system-welcome");
            chatFeed.innerHTML = "";
            if (welcome) chatFeed.appendChild(welcome);
            showToast("Chat cleared.");
        }
    });

    // Send Message
    btnSendMessage.addEventListener("click", sendMessage);

    // Textarea input auto-grow & keyboard triggers
    userInputText.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    userInputText.addEventListener("input", () => {
        userInputText.style.height = "auto";
        userInputText.style.height = Math.min(userInputText.scrollHeight, 160) + "px";
    });

    // Image Uploads
    fileUploadInput.addEventListener("change", (e) => handleFileUpload(e.target.files[0]));
    chatImageUpload.addEventListener("change", (e) => handleFileUpload(e.target.files[0]));

    // Remove Image
    btnClearImage.addEventListener("click", () => {
        attachedImage = null;
        activeConfig.images = [];
        updateUIFromConfig();
    });

    btnRemoveChip.addEventListener("click", () => {
        attachedImage = null;
        activeConfig.images = [];
        updateUIFromConfig();
    });
}

// Handle File Upload to Server
async function handleFileUpload(file) {
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
        showToast("Uploading image...");
        const res = await fetch("/api/upload", {
            method: "POST",
            body: formData
        });

        if (res.ok) {
            const data = await res.json();
            attachedImage = data.path;
            activeConfig.images = [data.path];
            updateUIFromConfig();
            showToast(`Attached: ${data.filename}`);
        } else {
            showToast("Failed to upload image", "error");
        }
    } catch (e) {
        showToast("Upload error: " + e.message, "error");
    }
}

// Quick Prompt Handler
window.quickPrompt = function (text) {
    userInputText.value = text;
    sendMessage();
};

// Main Send Message Function
async function sendMessage() {
    const text = userInputText.value.trim();
    if (!text && !attachedImage) return;

    // Make sure latest config is captured
    saveFormToConfig();

    // 1. Render User Message Bubble
    appendUserMessage(text, attachedImage);

    // Clear input
    userInputText.value = "";
    userInputText.style.height = "auto";

    // 2. Render Agent Thinking Placeholder
    const thinkingRow = appendThinkingMessage();
    chatFeed.scrollTop = chatFeed.scrollHeight;

    btnSendMessage.disabled = true;

    try {
        const payload = {
            message: text,
            config: activeConfig,
            images: attachedImage ? [attachedImage] : []
        };

        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        thinkingRow.remove();

        if (res.ok) {
            const data = await res.json();
            appendAgentMessage(data);
        } else {
            const err = await res.json();
            appendErrorMessage(err.error || "Server error occurred");
        }
    } catch (e) {
        thinkingRow.remove();
        appendErrorMessage("Network error: " + e.message);
    } finally {
        btnSendMessage.disabled = false;
        chatFeed.scrollTop = chatFeed.scrollHeight;
    }
}

// Render User Message
function appendUserMessage(text, imagePath) {
    const row = document.createElement("div");
    row.className = "message-row user";

    let imgHtml = "";
    if (imagePath) {
        const basename = imagePath.split(/[\\/]/).pop();
        imgHtml = `
            <div class="msg-image-attachment">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
                <span>Attached: ${escapeHtml(basename)}</span>
            </div>
        `;
    }

    row.innerHTML = `
        <div class="avatar user-avatar">${escapeHtml((activeConfig.name || "U")[0].toUpperCase())}</div>
        <div class="message-body">
            <div class="bubble">
                ${imgHtml}
                <div>${escapeHtml(text)}</div>
            </div>
        </div>
    `;

    chatFeed.appendChild(row);
}

// Render Thinking Dots
function appendThinkingMessage() {
    const row = document.createElement("div");
    row.className = "message-row agent";
    row.innerHTML = `
        <div class="avatar agent-avatar">AI</div>
        <div class="message-body">
            <div class="bubble">
                <div class="typing-dots">
                    <span></span><span></span><span></span>
                </div>
                <span style="font-size: 13px; color: var(--text-muted); margin-left: 8px;">Agent reasoning & executing graph...</span>
            </div>
        </div>
    `;
    chatFeed.appendChild(row);
    return row;
}

// Render Agent Message with Collapsible Tools, Latencies, Citations, and Quizzes
function appendAgentMessage(data) {
    const row = document.createElement("div");
    row.className = "message-row agent";

    const body = document.createElement("div");
    body.className = "message-body";

    // 1. Collapsible Inspection Cards Container
    const inspectionPanel = document.createElement("div");
    inspectionPanel.className = "agent-inspection-panel";

    // A. Tools & Arguments Collapsible Card
    if (data.tools_used && data.tools_used.length > 0) {
        const toolCard = createCollapsibleCard({
            tag: "TOOLS EXECUTED",
            tagClass: "tag-tools",
            title: `${data.tools_used.length} Tool Call(s): ${data.tools_used.map(t => t.name).join(", ")}`,
            contentHtml: renderToolsContent(data.tools_used)
        });
        inspectionPanel.appendChild(toolCard);
    }

    // B. Graph Node Latency Collapsible Card
    if (data.latencies && data.latencies.length > 0) {
        const latencyCard = createCollapsibleCard({
            tag: "LATENCY TRACE",
            tagClass: "tag-latency",
            title: `Graph Nodes Total: ${data.total_latency_ms || 0} ms`,
            contentHtml: renderLatenciesContent(data.latencies, data.total_latency_ms)
        });
        inspectionPanel.appendChild(latencyCard);
    }

    // C. Long-Term Memory (Preferences) Collapsible Card
    const hasPrefs = (data.preferences && data.preferences.length > 0) || (data.study_preferences && data.study_preferences.length > 0);
    if (hasPrefs) {
        const ltmCard = createCollapsibleCard({
            tag: "LTM MEMORY",
            tagClass: "tag-ltm",
            title: `Learned Preferences (${(data.preferences || []).length + (data.study_preferences || []).length})`,
            contentHtml: renderLTMContent(data.preferences, data.study_preferences)
        });
        inspectionPanel.appendChild(ltmCard);
    }

    body.appendChild(inspectionPanel);

    // 2. Citations Widget (if present)
    if (data.citations && data.citations.length > 0) {
        const citBox = document.createElement("div");
        citBox.className = "citations-box";
        citBox.innerHTML = `
            <div class="citations-title">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
                <span>Curriculum Citations:</span>
            </div>
            <div class="citations-list">
                ${data.citations.map(c => `
                    <div class="citation-badge">
                        📚 Book ID: <b>${c.book_id || c.book_ids || 'Curriculum'}</b> • Page: <b>${c.page_number || c.page_numbers || 'N/A'}</b> • Grade: <b>${c.grade || activeConfig.grade}</b>
                    </div>
                `).join('')}
            </div>
        `;
        body.appendChild(citBox);
    }

    // 3. Quiz Interactive Widget (if present)
    if (data.quiz && data.quiz.length > 0) {
        const quizBox = document.createElement("div");
        quizBox.className = "quiz-box";
        quizBox.innerHTML = `
            <div class="quiz-header-title">📝 Practice Quiz (${data.quiz.length} Questions)</div>
            ${data.quiz.map((q, idx) => `
                <div class="quiz-question-card">
                    <div class="quiz-q-text">Q${idx + 1}: ${escapeHtml(q.question_text || q.question || '')}</div>
                    <div class="quiz-options">
                        ${(q.options || []).map((opt, oIdx) => `
                            <button type="button" class="quiz-option-btn" onclick="selectQuizOption(this)">
                                ${escapeHtml(opt)}
                            </button>
                        `).join('')}
                    </div>
                </div>
            `).join('')}
        `;
        body.appendChild(quizBox);
    }

    // 4. Main Agent Response Text
    if (data.response) {
        const bubble = document.createElement("div");
        bubble.className = "bubble";
        bubble.innerHTML = formatMarkdown(data.response);
        body.appendChild(bubble);
    }

    row.innerHTML = `<div class="avatar agent-avatar">AI</div>`;
    row.appendChild(body);
    chatFeed.appendChild(row);
}

// Collapsible Card Component Builder
function createCollapsibleCard({ tag, tagClass, title, contentHtml }) {
    const card = document.createElement("div");
    card.className = "collapsible-card";

    card.innerHTML = `
        <div class="collapsible-header">
            <div class="header-left-meta">
                <span class="tool-tag ${tagClass}">${escapeHtml(tag)}</span>
                <span class="tool-title">${escapeHtml(title)}</span>
            </div>
            <svg class="chevron-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
        </div>
        <div class="collapsible-content">
            ${contentHtml}
        </div>
    `;

    const header = card.querySelector(".collapsible-header");
    header.addEventListener("click", () => {
        card.classList.toggle("open");
    });

    return card;
}

// Render Tools Detail Inside Collapsible
function renderToolsContent(tools) {
    return tools.map((t, idx) => {
        let argsStr = "{}";
        try {
            argsStr = JSON.stringify(t.args || {}, null, 2);
        } catch (e) {
            argsStr = String(t.args);
        }

        let outStr = t.output ? escapeHtml(t.output) : "<em>(Executed without return text)</em>";

        return `
            <div class="tool-detail-item">
                <div class="tool-detail-head">
                    <span class="tool-call-name">⚙️ #${idx + 1} ${escapeHtml(t.name)}</span>
                    <span class="badge-step" style="font-size: 10px;">ID: ${escapeHtml(t.id ? t.id.slice(-8) : 'call')}</span>
                </div>
                <div class="section-label">Tool Arguments:</div>
                <pre class="code-block">${escapeHtml(argsStr)}</pre>
                ${t.name !== 'respond' ? `
                    <div class="section-label" style="margin-top: 8px;">Execution Result:</div>
                    <pre class="code-block" style="color: #cbd5e1;">${outStr}</pre>
                ` : ''}
            </div>
        `;
    }).join('');
}

// Render Latencies Table Inside Collapsible
function renderLatenciesContent(latencies, totalMs) {
    let rowsHtml = latencies.map((l, idx) => {
        const ms = l.duration_ms !== undefined ? l.duration_ms.toFixed(2) : (l.duration_s * 1000).toFixed(2);
        const s = l.duration_s !== undefined ? l.duration_s.toFixed(4) : (l.duration_ms / 1000).toFixed(4);
        const statusColor = (l.status === 'success' || !l.status) ? '#34d399' : '#f87171';

        return `
            <div class="latency-row">
                <span class="node-name-code">#${idx + 1} ${escapeHtml(l.node)}</span>
                <div>
                    <span class="node-time-badge" style="color: ${statusColor};">${ms} ms</span>
                    <span style="color: var(--text-muted); font-size: 11px; margin-left: 6px;">(${s}s)</span>
                </div>
            </div>
        `;
    }).join('');

    return `
        <div class="latency-timeline">
            ${rowsHtml}
            <div class="latency-total-row">
                <span>Total Latency (sum of nodes)</span>
                <span class="node-time-badge">${Number(totalMs || 0).toFixed(2)} ms</span>
            </div>
        </div>
    `;
}

// Render LTM Inside Collapsible
function renderLTMContent(prefs = [], studyPrefs = []) {
    return `
        <div style="font-size: 13px;">
            <div style="margin-bottom: 8px;">
                <b>Personal Facts:</b>
                ${prefs.length ? `<ul>${prefs.map(p => `<li>${escapeHtml(p)}</li>`).join('')}</ul>` : '<p style="color: var(--text-muted);">None recorded yet.</p>'}
            </div>
            <div>
                <b>Study Preferences:</b>
                ${studyPrefs.length ? `<ul>${studyPrefs.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>` : '<p style="color: var(--text-muted);">None recorded yet.</p>'}
            </div>
        </div>
    `;
}

// Render Error Message
function appendErrorMessage(errorText) {
    const row = document.createElement("div");
    row.className = "message-row agent";
    row.innerHTML = `
        <div class="avatar agent-avatar" style="background: var(--danger);">!</div>
        <div class="message-body">
            <div class="bubble" style="border-color: rgba(239, 68, 68, 0.4); background: rgba(239, 68, 68, 0.1);">
                <div style="color: #fca5a5; font-weight: 700; margin-bottom: 4px;">Error from Agent Execution</div>
                <div style="font-size: 13px;">${escapeHtml(errorText)}</div>
            </div>
        </div>
    `;
    chatFeed.appendChild(row);
}

// Interactive Quiz Option Selection
window.selectQuizOption = function (btn) {
    const parent = btn.parentElement;
    parent.querySelectorAll(".quiz-option-btn").forEach(b => {
        b.style.background = "rgba(255, 255, 255, 0.04)";
        b.style.borderColor = "var(--border-color)";
    });
    btn.style.background = "rgba(99, 102, 241, 0.35)";
    btn.style.borderColor = "var(--accent-primary)";
    showToast("Choice selected: " + btn.textContent.trim().slice(0, 25) + "...");
};

// Simple Markdown Formatter
function formatMarkdown(text) {
    if (!text) return "";
    let safe = escapeHtml(text);

    // Bold **text**
    safe = safe.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
    // Bullet points
    safe = safe.replace(/^- (.*$)/gim, '• $1<br>');
    // Line breaks
    safe = safe.replace(/\n\n/g, '<br><br>');
    safe = safe.replace(/\n/g, '<br>');

    return safe;
}

// Utility: Escape HTML
function escapeHtml(str) {
    if (typeof str !== "string") str = String(str || "");
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Utility: Toast Notification
function showToast(msg, type = "info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = msg;

    if (type === "error") {
        toast.style.borderColor = "var(--danger)";
        toast.style.color = "#fca5a5";
    }

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
