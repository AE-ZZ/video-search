const API = "/api";
let currentVideoId = null;
let chatHistory = [];
let libraryPollInterval = null;

// --- Init ---
async function init() {
    const res = await fetch(`${API}/settings`);
    const data = await res.json();

    if (!data.video_library_path) {
        document.getElementById("setup-screen").hidden = false;
        document.getElementById("main-app").hidden = true;
    } else {
        document.getElementById("setup-screen").hidden = true;
        document.getElementById("main-app").hidden = false;
        document.getElementById("library-path-display").textContent = data.video_library_path;
        document.getElementById("change-path").value = data.video_library_path;
        loadLibrary();
        startLibraryPolling();
    }
}

// --- Library Path Setup ---
async function setLibraryPath() {
    const path = document.getElementById("setup-path").value.trim();
    if (!path) return;

    const errorEl = document.getElementById("setup-error");
    errorEl.hidden = true;

    try {
        const res = await fetch(`${API}/settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ video_library_path: path }),
        });
        if (!res.ok) {
            const err = await res.json();
            errorEl.textContent = err.detail || "Invalid path";
            errorEl.hidden = false;
            return;
        }
        // Reload page to show main app
        location.reload();
    } catch (e) {
        errorEl.textContent = `Error: ${e.message}`;
        errorEl.hidden = false;
    }
}

function showChangeLibrary() {
    document.getElementById("change-library").hidden = false;
    document.getElementById("library-info").hidden = true;
}

function hideChangeLibrary() {
    document.getElementById("change-library").hidden = true;
    document.getElementById("library-info").hidden = false;
}

async function changeLibraryPath() {
    const path = document.getElementById("change-path").value.trim();
    if (!path) return;

    const errorEl = document.getElementById("change-error");
    errorEl.textContent = "";

    try {
        const res = await fetch(`${API}/settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ video_library_path: path }),
        });
        if (!res.ok) {
            const err = await res.json();
            errorEl.textContent = err.detail || "Invalid path";
            return;
        }
        location.reload();
    } catch (e) {
        errorEl.textContent = `Error: ${e.message}`;
    }
}

// --- Video Library ---
async function loadLibrary() {
    const res = await fetch(`${API}/library`);
    const videos = await res.json();
    const container = document.getElementById("video-list");

    if (!videos.length) {
        container.innerHTML = '<p class="muted">No video files found in library folder.</p>';
        return;
    }

    container.innerHTML = videos.map(v => {
        const statusClass = `status-${v.status}`;
        const statusLabel = {
            processed: "Ready",
            processing: `Processing: ${v.progress || "..."}`,
            pending: "Pending...",
            failed: `Failed: ${v.error || "unknown"}`,
        }[v.status] || v.status;

        const clickable = v.status === "processed" ? `onclick="openVideo('${v.video_id}')"` : "";
        const cursorClass = v.status === "processed" ? "" : "no-click";

        return `
            <div class="video-card ${cursorClass}" ${clickable}>
                <h3>${escapeHtml(v.filename)}</h3>
                <div class="status-badge ${statusClass}">${statusLabel}</div>
                ${v.duration ? `<div class="meta">Duration: ${formatTime(v.duration)}</div>` : ""}
            </div>
        `;
    }).join("");
}

function startLibraryPolling() {
    if (libraryPollInterval) clearInterval(libraryPollInterval);
    libraryPollInterval = setInterval(loadLibrary, 3000);
}

// --- Enter key on setup/change inputs ---
document.getElementById("setup-path").addEventListener("keydown", (e) => {
    if (e.key === "Enter") setLibraryPath();
});
document.getElementById("change-path").addEventListener("keydown", (e) => {
    if (e.key === "Enter") changeLibraryPath();
});

// --- Search ---
document.getElementById("search-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") performSearch();
});

async function performSearch() {
    const q = document.getElementById("search-input").value.trim();
    const type = document.getElementById("search-type").value;
    if (!q) return;

    const res = await fetch(`${API}/search?q=${encodeURIComponent(q)}&type=${type}`);
    const data = await res.json();
    renderSearchResults(data.results);
}

function renderSearchResults(results) {
    const container = document.getElementById("search-results");

    if (!results.length) {
        container.innerHTML = '<p class="muted">No results found.</p>';
        return;
    }

    container.innerHTML = results.map(r => {
        const badge = `<span class="badge ${r.match_type}">${r.match_type}</span>`;
        const time = r.start_time != null
            ? `${formatTime(r.start_time)} - ${formatTime(r.end_time)}`
            : r.timestamp != null ? formatTime(r.timestamp) : "";
        const img = r.frame_path
            ? `<img src="${r.frame_path}" alt="frame">`
            : "";

        return `
            <div class="result-card" onclick="openVideoAt('${r.video_id}', ${r.start_time || r.timestamp || 0})">
                ${img}
                <div class="result-info">
                    <h4>${badge} ${escapeHtml(r.video_filename)}</h4>
                    <p>${escapeHtml(r.text || "Visual match")}</p>
                    <div class="result-meta">${time} | Score: ${r.score}</div>
                </div>
            </div>
        `;
    }).join("");
}

// --- Video Detail ---
async function openVideo(videoId) {
    currentVideoId = videoId;
    chatHistory = [];

    const res = await fetch(`${API}/videos/${videoId}`);
    const data = await res.json();

    document.getElementById("detail-section").hidden = false;
    document.getElementById("library-section").hidden = true;
    document.getElementById("search-section").hidden = true;

    const player = document.getElementById("video-player");
    player.src = `${API}/library/${videoId}/stream`;

    document.getElementById("detail-title").textContent = data.filename || "Video";
    document.getElementById("summary-content").textContent = data.summary || "No summary available.";

    const transcriptEl = document.getElementById("transcript-content");
    if (data.transcript && data.transcript.length) {
        transcriptEl.innerHTML = data.transcript.map(s => `
            <div class="transcript-seg" onclick="seekTo(${s.start_time})">
                <span class="ts">${formatTime(s.start_time)}</span>
                <span class="text">${escapeHtml(s.text)}</span>
            </div>
        `).join("");
    } else {
        transcriptEl.innerHTML = '<p class="muted">No transcript available.</p>';
    }

    document.getElementById("chat-messages").innerHTML = "";
    switchTab("summary");
}

function openVideoAt(videoId, time) {
    openVideo(videoId).then(() => seekTo(time));
}

function hideDetail() {
    document.getElementById("detail-section").hidden = true;
    document.getElementById("library-section").hidden = false;
    document.getElementById("search-section").hidden = false;
    currentVideoId = null;
}

function seekTo(time) {
    const player = document.getElementById("video-player");
    player.currentTime = time;
    player.play();
}

function switchTab(name) {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
    document.querySelector(`.tab-content#tab-${name}`).classList.add("active");
    document.querySelectorAll(".tab").forEach(t => {
        if (t.textContent.toLowerCase() === name) t.classList.add("active");
    });
}

// --- Chat ---
document.getElementById("chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendChat();
});

async function sendChat() {
    const input = document.getElementById("chat-input");
    const question = input.value.trim();
    if (!question || !currentVideoId) return;

    input.value = "";
    appendChatMsg("user", question);

    try {
        const res = await fetch(`${API}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                video_id: currentVideoId,
                question,
                history: chatHistory,
            }),
        });
        const data = await res.json();
        appendChatMsg("assistant", data.answer);

        chatHistory.push({ role: "user", content: question });
        chatHistory.push({ role: "assistant", content: data.answer });
    } catch (e) {
        appendChatMsg("assistant", `Error: ${e.message}`);
    }
}

function appendChatMsg(role, text) {
    const container = document.getElementById("chat-messages");
    const div = document.createElement("div");
    div.className = `chat-msg ${role}`;
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// --- Utils ---
function formatTime(sec) {
    if (sec == null) return "";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
}

function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// Init
init();
