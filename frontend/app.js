const API = "/api";
let currentVideoId = null;
let chatHistory = [];
let libraryPollInterval = null;
let currentSearchQuery = "";
let currentSearchHits = [];  // hits for the currently opened video
let explainCache = {};  // hitId or "video_id:match_type:time" -> explanation string

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

    const ready = videos.filter(v => v.status === "processed").length;
    document.getElementById("library-count").textContent = `${ready}/${videos.length} ready`;

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

function toggleLibrary() {
    const list = document.getElementById("video-list");
    const icon = document.getElementById("library-expand-icon");
    if (list.hidden) {
        list.hidden = false;
        icon.classList.add("expanded");
    } else {
        list.hidden = true;
        icon.classList.remove("expanded");
    }
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

// Threshold slider labels
document.getElementById("text-threshold").addEventListener("input", (e) => {
    document.getElementById("text-threshold-val").textContent = parseFloat(e.target.value).toFixed(2);
});
document.getElementById("semantic-threshold").addEventListener("input", (e) => {
    document.getElementById("semantic-threshold-val").textContent = parseFloat(e.target.value).toFixed(2);
});
document.getElementById("visual-threshold").addEventListener("input", (e) => {
    document.getElementById("visual-threshold-val").textContent = parseFloat(e.target.value).toFixed(2);
});

async function performSearch() {
    const q = document.getElementById("search-input").value.trim();
    const type = document.getElementById("search-type").value;
    if (!q) return;

    const textThreshold = document.getElementById("text-threshold").value;
    const semanticThreshold = document.getElementById("semantic-threshold").value;
    const visualThreshold = document.getElementById("visual-threshold").value;
    const semantic = document.getElementById("semantic-toggle").checked;

    const params = new URLSearchParams({
        q, type,
        text_threshold: textThreshold,
        semantic_threshold: semanticThreshold,
        visual_threshold: visualThreshold,
        semantic: semantic,
    });

    const res = await fetch(`${API}/search?${params}`);
    const data = await res.json();
    currentSearchQuery = q;
    renderSearchResults(data.results);
}

let allSearchResults = [];
let hitDataMap = {};  // hitId -> result object

function renderSearchResults(results) {
    hitDataMap = {};
    allSearchResults = results;
    const container = document.getElementById("search-results");

    if (!results.length) {
        container.innerHTML = '<p class="muted">No results found.</p>';
        return;
    }

    // Deduplicate visual results within 5 seconds of each other per video
    const deduped = [];
    const visualByVideo = {};
    for (const r of results) {
        if (r.match_type === "visual") {
            if (!visualByVideo[r.video_id]) visualByVideo[r.video_id] = [];
            const ts = r.timestamp || 0;
            const tooClose = visualByVideo[r.video_id].some(t => Math.abs(t - ts) < 5);
            if (tooClose) continue;
            visualByVideo[r.video_id].push(ts);
        }
        deduped.push(r);
    }

    // Group results by video
    const groups = new Map();
    for (const r of deduped) {
        if (!groups.has(r.video_id)) {
            groups.set(r.video_id, { filename: r.video_filename, video_id: r.video_id, hits: [] });
        }
        groups.get(r.video_id).hits.push(r);
    }

    container.innerHTML = Array.from(groups.values()).map(group => {
        const hitCount = group.hits.length;
        const bestScore = Math.max(...group.hits.map(h => h.score));
        const types = [...new Set(group.hits.map(h => h.match_type))];
        const badges = types.map(t => `<span class="badge ${t}">${t}</span>`).join("");

        const hitsHtml = group.hits.map((r, idx) => {
            const hitId = `${group.video_id}_${idx}`;
            hitDataMap[hitId] = r;
            const time = r.start_time != null
                ? `${formatTime(r.start_time)} - ${formatTime(r.end_time)}`
                : r.timestamp != null ? formatTime(r.timestamp) : "";
            const frameSrc = r.frame_path
                ? r.frame_path
                : r.start_time != null
                    ? `${API}/library/${r.video_id}/frames/${Math.floor(r.start_time)}`
                    : "";
            const img = frameSrc ? `<img src="${frameSrc}" alt="frame">` : "";
            const badge = `<span class="badge ${r.match_type}">${r.match_type}</span>`;
            const explainBtn = r.match_type !== "exact"
                ? `<button class="explain-btn-small" onclick="event.stopPropagation(); explainSingle('${hitId}')">Explain</button>`
                : "";

            return `
                <div class="hit-item" onclick="event.stopPropagation(); openVideoAt('${r.video_id}', ${r.start_time || r.timestamp || 0}, '${hitId}')">
                    ${img}
                    <div class="hit-info">
                        <p>${badge} ${escapeHtml(r.text || "Visual match")}</p>
                        <div class="result-meta">${time} | Score: ${r.score} ${explainBtn}</div>
                    </div>
                </div>
                <div class="explain-inline" id="explain-${hitId}" hidden></div>
            `;
        }).join("");

        return `
            <div class="result-group">
                <div class="result-group-header" onclick="toggleGroup(this)">
                    <div class="result-group-title">
                        <h4>${escapeHtml(group.filename)}</h4>
                        <span class="hit-count">${hitCount} match${hitCount > 1 ? "es" : ""}</span>
                        ${badges}
                    </div>
                    <span class="expand-icon">&#9654;</span>
                </div>
                <div class="result-group-hits" hidden>
                    ${hitsHtml}
                </div>
            </div>
        `;
    }).join("");
}

function toggleAdvanced() {
    const options = document.getElementById("search-options");
    const icon = document.getElementById("advanced-expand-icon");
    if (options.hidden) {
        options.hidden = false;
        icon.classList.add("expanded");
    } else {
        options.hidden = true;
        icon.classList.remove("expanded");
    }
}

function toggleGroup(header) {
    const hits = header.nextElementSibling;
    const icon = header.querySelector(".expand-icon");
    if (hits.hidden) {
        hits.hidden = false;
        icon.classList.add("expanded");
    } else {
        hits.hidden = true;
        icon.classList.remove("expanded");
    }
}

// --- Video Detail ---
async function openVideo(videoId) {
    currentVideoId = videoId;
    chatHistory = [];
    currentSearchHits = allSearchResults.filter(r => r.video_id === videoId);

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
            <div class="transcript-seg" data-time="${s.start_time}" onclick="seekTo(${s.start_time})">
                <span class="ts">${formatTime(s.start_time)}</span>
                <span class="text">${escapeHtml(s.text)}</span>
            </div>
        `).join("");
    } else {
        transcriptEl.innerHTML = '<p class="muted">No transcript available.</p>';
    }

    const chatMessages = document.getElementById("chat-messages");
    if (chatMessages) chatMessages.innerHTML = "";

    // Show/hide Explanation tab based on the clicked search result
    const explainTabBtn = document.getElementById("explain-tab-btn");
    const explainContent = document.getElementById("explanation-content");
    if (currentExplainHit && currentExplainHit.match_type !== "exact") {
        explainTabBtn.hidden = false;
        const key = cacheKey(currentExplainHit);
        if (explainCache[key]) {
            renderExplainTabSingle(currentExplainHit, explainCache[key]);
        } else {
            const time = currentExplainHit.start_time != null
                ? `${formatTime(currentExplainHit.start_time)} - ${formatTime(currentExplainHit.end_time)}`
                : currentExplainHit.timestamp != null ? formatTime(currentExplainHit.timestamp) : "";
            explainContent.innerHTML = `
                <p class="muted">Explain why this ${currentExplainHit.match_type} match at ${time} relates to "${escapeHtml(currentSearchQuery)}".</p>
                <button onclick="explainCurrentHit()">Explain</button>
            `;
        }
    } else {
        explainTabBtn.hidden = true;
        explainContent.innerHTML = "";
    }

    switchTab("summary");
}

let currentExplainHit = null;
let pendingTranscriptScroll = null;

function openVideoAt(videoId, time, hitId) {
    if (hitId && hitDataMap[hitId]) {
        currentExplainHit = hitDataMap[hitId];
    } else {
        currentExplainHit = null;
    }
    openVideo(videoId).then(() => {
        const player = document.getElementById("video-player");
        player.addEventListener("loadeddata", function onLoaded() {
            player.removeEventListener("loadeddata", onLoaded);
            player.currentTime = time;
            player.play();
        });
        pendingTranscriptScroll = time;
        switchTab("transcript");
    });
}

function hideDetail() {
    const player = document.getElementById("video-player");
    player.pause();
    player.removeAttribute("src");
    player.load();
    document.getElementById("detail-section").hidden = true;
    document.getElementById("library-section").hidden = false;
    document.getElementById("search-section").hidden = false;
    currentVideoId = null;
}

function seekTo(time) {
    const player = document.getElementById("video-player");
    player.currentTime = time;
    player.play();
    scrollTranscriptTo(time);
}

function scrollTranscriptTo(time) {
    const segs = document.querySelectorAll(".transcript-seg");
    let closest = null;
    let closestDiff = Infinity;
    for (const seg of segs) {
        const t = parseFloat(seg.dataset.time);
        const diff = Math.abs(t - time);
        if (diff < closestDiff) {
            closestDiff = diff;
            closest = seg;
        }
    }
    if (closest) {
        segs.forEach(s => s.classList.remove("active"));
        closest.classList.add("active");
        closest.scrollIntoView({ behavior: "smooth", block: "center" });
    }
}

// --- Explanation ---
function renderExplainTabSingle(hit, explanation) {
    const container = document.getElementById("explanation-content");
    const badge = `<span class="badge ${hit.match_type}">${hit.match_type}</span>`;
    const time = hit.start_time != null
        ? `${formatTime(hit.start_time)} - ${formatTime(hit.end_time)}`
        : hit.timestamp != null ? formatTime(hit.timestamp) : "";
    const seekTime = hit.start_time || hit.timestamp || 0;

    container.innerHTML = `
        <div class="explain-item" onclick="seekTo(${seekTime})">
            <div class="explain-header">
                ${badge}
                <span class="explain-time">${time}</span>
            </div>
            ${hit.text ? `<p class="explain-text">"${escapeHtml(hit.text)}"</p>` : ""}
            <p class="explain-reason">${escapeHtml(explanation)}</p>
        </div>
    `;
}

async function explainCurrentHit() {
    if (!currentExplainHit || !currentSearchQuery) return;

    const container = document.getElementById("explanation-content");
    container.innerHTML = '<p class="muted">Generating explanation...</p>';

    const item = {
        video_id: currentExplainHit.video_id,
        match_type: currentExplainHit.match_type,
        text: currentExplainHit.text || null,
        start_time: currentExplainHit.start_time ?? null,
        end_time: currentExplainHit.end_time ?? null,
        timestamp: currentExplainHit.timestamp ?? null,
    };

    try {
        const res = await fetch(`${API}/explain`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: currentSearchQuery, items: [item] }),
        });
        const data = await res.json();
        const explanation = data.results[0]?.explanation || "No explanation available.";
        const key = cacheKey(currentExplainHit);
        explainCache[key] = explanation;
        renderExplainTabSingle(currentExplainHit, explanation);
    } catch (e) {
        container.innerHTML = `<p class="muted">Error: ${e.message}</p>`;
    }
}

function renderExplanationTab(explanations) {
    const container = document.getElementById("explanation-content");
    container.innerHTML = explanations.map(e => {
        const badge = `<span class="badge ${e.match_type}">${e.match_type}</span>`;
        const time = e.start_time != null
            ? `${formatTime(e.start_time)} - ${formatTime(e.end_time)}`
            : e.timestamp != null ? formatTime(e.timestamp) : "";
        const seekTime = e.start_time || e.timestamp || 0;

        return `
            <div class="explain-item" onclick="seekTo(${seekTime})">
                <div class="explain-header">
                    ${badge}
                    <span class="explain-time">${time}</span>
                </div>
                ${e.text ? `<p class="explain-text">"${escapeHtml(e.text)}"</p>` : ""}
                <p class="explain-reason">${escapeHtml(e.explanation)}</p>
            </div>
        `;
    }).join("");
}

async function requestExplanations() {
    const explainableHits = currentSearchHits.filter(r => r.match_type !== "exact");
    if (!explainableHits.length || !currentSearchQuery) return;

    // Deduplicate visual results within 5 seconds
    const filtered = [];
    const visualTimestamps = [];
    for (const r of explainableHits) {
        if (r.match_type === "visual") {
            const ts = r.timestamp || 0;
            if (visualTimestamps.some(t => Math.abs(t - ts) < 5)) continue;
            visualTimestamps.push(ts);
        }
        filtered.push(r);
    }

    // Split into cached and uncached
    const cached = [];
    const uncached = [];
    for (const r of filtered) {
        const key = cacheKey(r);
        if (explainCache[key]) {
            cached.push({ ...r, explanation: explainCache[key] });
        } else {
            uncached.push(r);
        }
    }

    // If all cached, render immediately
    if (!uncached.length) {
        renderExplanationTab(cached);
        return;
    }

    const container = document.getElementById("explanation-content");
    container.innerHTML = `<p class="muted">Generating explanations... (${cached.length} cached, ${uncached.length} new)</p>`;

    const items = uncached.map(r => ({
        video_id: r.video_id,
        match_type: r.match_type,
        text: r.text || null,
        start_time: r.start_time ?? null,
        end_time: r.end_time ?? null,
        timestamp: r.timestamp ?? null,
    }));

    try {
        const res = await fetch(`${API}/explain`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: currentSearchQuery, items }),
        });
        const data = await res.json();

        // Cache new results
        for (let i = 0; i < uncached.length; i++) {
            const key = cacheKey(uncached[i]);
            explainCache[key] = data.results[i]?.explanation || "No explanation available.";
        }

        // Merge all and render in original order
        const all = filtered.map(r => ({
            ...r,
            explanation: explainCache[cacheKey(r)],
        }));
        renderExplanationTab(all);
    } catch (e) {
        container.innerHTML = `<p class="muted">Error: ${e.message}</p>`;
    }
}

function cacheKey(r) {
    const time = r.start_time ?? r.timestamp ?? 0;
    return `${currentSearchQuery}|${r.video_id}|${r.match_type}|${time}`;
}

async function explainSingle(hitId) {
    const r = hitDataMap[hitId];
    if (!r || !currentSearchQuery) return;

    const container = document.getElementById(`explain-${hitId}`);
    container.hidden = false;

    const key = cacheKey(r);
    if (explainCache[key]) {
        container.innerHTML = `<p class="explain-reason">${escapeHtml(explainCache[key])}</p>`;
        return;
    }

    container.innerHTML = '<p class="muted">Generating explanation...</p>';

    const item = {
        video_id: r.video_id,
        match_type: r.match_type,
        text: r.text || null,
        start_time: r.start_time ?? null,
        end_time: r.end_time ?? null,
        timestamp: r.timestamp ?? null,
    };

    try {
        const res = await fetch(`${API}/explain`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: currentSearchQuery, items: [item] }),
        });
        const data = await res.json();
        const explanation = data.results[0]?.explanation || "No explanation available.";
        explainCache[key] = explanation;
        container.innerHTML = `<p class="explain-reason">${escapeHtml(explanation)}</p>`;
    } catch (e) {
        container.innerHTML = `<p class="muted">Error: ${e.message}</p>`;
    }
}

function switchTab(name) {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
    document.querySelector(`.tab-content#tab-${name}`).classList.add("active");
    document.querySelectorAll(".tab").forEach(t => {
        if (t.textContent.toLowerCase() === name) t.classList.add("active");
    });

    if (name === "transcript" && pendingTranscriptScroll !== null) {
        setTimeout(() => {
            scrollTranscriptTo(pendingTranscriptScroll);
            pendingTranscriptScroll = null;
        }, 50);
    }
}

// --- Chat (optional) ---
const chatInput = document.getElementById("chat-input");
if (chatInput) {
    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendChat();
    });
}

async function sendChat() {
    const input = document.getElementById("chat-input");
    if (!input) return;
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
    if (!container) return;
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
