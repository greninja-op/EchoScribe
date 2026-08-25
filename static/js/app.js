/**
 * Flow Pro Modular Synthesizer Controller
 */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentTone = "clean";
  let isRecording = false;
  let mediaRecorder = null;
  let audioChunks = [];
  let audioCtx = null;
  let analyser = null;
  let animFrameId = null;

  let cachedDictionary = {};
  let cachedSnippets = {};
  let cachedStats = {};

  // Timeline History Feed
  let timelineItems = [
    {
      time: "9:02 pm",
      text: "It didn't mean that you should really copy the exact design. I meant the design language only. What I meant was: I will give you the UI place recreated that inside that. The same design should be applied but it should be a layout that should be different, not a Windows period or something like that. I will give you the example.",
      replacements: [],
    },
    {
      time: "8:47 pm",
      text: "Well is the app running bro? Please test it in every possible way. I need to see the app and the interface. Okay do one thing: make the interface of the application the skeuomorphic design that we have given for the portfolio. Check inside that. We have given some design for the portfolio's computer interface sort of things. Check out the my-portfolio folder. Inside that you will find that there are two options: just a visitor as well as a recruiter. Give the design language from the jester visitor. Same design language, same colors and all, same text font. Everything should look like that. For the audio transcripts it should have every feature that is inside. The application should have every single feature inside the Wispr Flow app, like the dictation. Do not include everything, just research it on the Internet what all features the Wispr Flow app provides and keep it inside that.",
      replacements: [],
    },
  ];

  // DOM Elements - Navigation
  const navBtns = document.querySelectorAll(".synth-nav-btn[data-view]");
  const viewPanes = document.querySelectorAll(".synth-view");

  // DOM Elements - Dictation
  const mainMicBtn = document.getElementById("mainMicBtn");
  const micStatusText = document.getElementById("micStatusText");
  const dictationTimelineList = document.getElementById("dictationTimelineList");
  const liveLatencyTag = document.getElementById("liveLatencyTag");
  const sideTotalWords = document.getElementById("sideTotalWords");
  const sideWpm = document.getElementById("sideWpm");
  const sideStreak = document.getElementById("sideStreak");
  const vpBadgeName = document.getElementById("vpBadgeName");
  const liveClockPill = document.getElementById("liveClockPill");
  const oscCanvas = document.getElementById("oscilloscopeCanvas");

  // DOM Elements - Insights
  const insightsWpm = document.getElementById("insightsWpm");
  const insightsTotalFixes = document.getElementById("insightsTotalFixes");
  const insightsTotalWords = document.getElementById("insightsTotalWords");
  const drSeussQuote = document.getElementById("drSeussQuote");
  const gaugeCanvas = document.getElementById("gaugeCanvas");
  const streakHeatmapGrid = document.getElementById("streakHeatmapGrid");

  // DOM Elements - Dictionary & Snippets
  const flowDictTableBody = document.getElementById("flowDictTableBody");
  const flowSnipTableBody = document.getElementById("flowSnipTableBody");
  const addPhraseInput = document.getElementById("addPhraseInput");
  const addReplInput = document.getElementById("addReplInput");
  const addCatSelect = document.getElementById("addCatSelect");
  const submitWordBtn = document.getElementById("submitWordBtn");
  const searchWordsInput = document.getElementById("searchWordsInput");
  const snipTriggerInput = document.getElementById("snipTriggerInput");
  const snipExpInput = document.getElementById("snipExpInput");
  const submitSnipBtn = document.getElementById("submitSnipBtn");
  const toggle10kBtn = document.getElementById("toggle10kBtn");
  const adaptiveStatusTag = document.getElementById("adaptiveStatusTag");

  // Clock Ticker
  function updateClock() {
    if (liveClockPill) {
      const now = new Date();
      liveClockPill.textContent = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    }
  }
  setInterval(updateClock, 1000);
  updateClock();

  // 1. Navigation View Switcher
  window.switchView = (viewId) => {
    navBtns.forEach((btn) => {
      if (btn.dataset.view === viewId) btn.classList.add("active");
      else btn.classList.remove("active");
    });

    viewPanes.forEach((pane) => {
      if (pane.id === viewId) pane.classList.add("active");
      else pane.classList.remove("active");
    });

    if (viewId === "view-insights") {
      renderGauge(85);
      renderHeatmap();
    }
  };

  navBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.view) switchView(btn.dataset.view);
    });
  });

  // 2. Tone Selector Keys
  document.querySelectorAll(".tone-key-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tone-key-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentTone = btn.dataset.tone;
    });
  });

  // 3. Audio Recording Engine & Live CRT Oscilloscope
  function startOscilloscope(stream) {
    if (!oscCanvas) return;
    const ctx = oscCanvas.getContext("2d");
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(stream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function draw() {
      animFrameId = requestAnimationFrame(draw);
      analyser.getByteTimeDomainData(dataArray);

      ctx.fillStyle = "#000000";
      ctx.fillRect(0, 0, oscCanvas.width, oscCanvas.height);

      ctx.lineWidth = 3;
      ctx.strokeStyle = "#98FF44";
      ctx.shadowBlur = 10;
      ctx.shadowColor = "#98FF44";

      ctx.beginPath();
      const sliceWidth = (oscCanvas.width * 1.0) / bufferLength;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * oscCanvas.height) / 2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        x += sliceWidth;
      }

      ctx.lineTo(oscCanvas.width, oscCanvas.height / 2);
      ctx.stroke();
    }

    draw();
  }

  function stopOscilloscope() {
    if (animFrameId) cancelAnimationFrame(animFrameId);
    if (audioCtx) {
      audioCtx.close();
      audioCtx = null;
    }
    if (oscCanvas) {
      const ctx = oscCanvas.getContext("2d");
      ctx.fillStyle = "#000000";
      ctx.fillRect(0, 0, oscCanvas.width, oscCanvas.height);
      ctx.strokeStyle = "#98FF44";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, oscCanvas.height / 2);
      ctx.lineTo(oscCanvas.width, oscCanvas.height / 2);
      ctx.stroke();
    }
  }

  stopOscilloscope(); // draw resting flat line

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunks = [];
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stopOscilloscope();
        const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
        await sendAudioPayload(audioBlob);
        stream.getTracks().forEach((t) => t.stop());
      };

      startOscilloscope(stream);
      mediaRecorder.start();
      isRecording = true;
      mainMicBtn.classList.add("recording");
      micStatusText.textContent = "LISTENING... RELEASE PAD TO TRANSCRIBE";
    } catch (e) {
      alert("Microphone access required for audio transcription.");
    }
  }

  function stopRecording() {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      isRecording = false;
      mainMicBtn.classList.remove("recording");
      micStatusText.textContent = "SYNTHESIZING WITH FLOW AI...";
    }
  }

  mainMicBtn.addEventListener("click", () => {
    if (!isRecording) startRecording();
    else stopRecording();
  });

  // Spacebar Hotkey
  window.addEventListener("keydown", (e) => {
    if (e.code === "Space" && !isRecording && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
      e.preventDefault();
      startRecording();
    }
  });

  window.addEventListener("keyup", (e) => {
    if (e.code === "Space" && isRecording && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
      e.preventDefault();
      stopRecording();
    }
  });

  // 4. Send Audio Payload to EchoScribe API
  async function sendAudioPayload(blob) {
    const formData = new FormData();
    formData.append("file", blob, "recording.wav");
    formData.append("apply_dictionary", "true");
    formData.append("tone", currentTone);
    formData.append("apply_snippets", "true");

    try {
      const startTime = performance.now();
      const res = await fetch("/api/transcribe", { method: "POST", body: formData });
      const latency = Math.round(performance.now() - startTime);

      if (res.ok) {
        const data = await res.json();
        liveLatencyTag.textContent = `⚡ LATENCY: ${data.latency_ms || latency}ms`;
        micStatusText.textContent = "READY TO DICTATE";

        const now = new Date();
        const timeStr = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }).toLowerCase();

        timelineItems.unshift({
          time: timeStr,
          text: data.transcript,
          replacements: data.replacements || [],
        });

        renderTimelineFeed();
        await fetchStats();
      }
    } catch (e) {
      micStatusText.textContent = "SERVER CONNECTION ERROR";
    }
  }

  // 5. Render Timeline Feed
  function renderTimelineFeed() {
    dictationTimelineList.innerHTML = "";
    timelineItems.forEach((item) => {
      const card = document.createElement("div");
      card.className = "feed-synth-card";
      card.innerHTML = `
        <div class="synth-timestamp-badge">${item.time}</div>
        <div class="feed-synth-body">
          <div class="feed-synth-text">${escapeHtml(item.text)}</div>
          <div class="feed-synth-controls">
            <button class="synth-ctrl-btn" title="Play Audio">▷ Play</button>
            <button class="synth-ctrl-btn copy-item-btn" data-text="${escapeHtml(item.text)}" title="Copy to clipboard">⧉ Copy</button>
            <button class="synth-ctrl-btn" title="Flag feedback">⚐ Flag</button>
          </div>
        </div>
      `;
      dictationTimelineList.appendChild(card);
    });

    document.querySelectorAll(".copy-item-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        navigator.clipboard.writeText(btn.dataset.text);
        btn.textContent = "✓ Copied";
        setTimeout(() => (btn.textContent = "⧉ Copy"), 1500);
      });
    });
  }

  // 6. Insights & Gauge Rendering
  function renderGauge(wpmVal) {
    if (!gaugeCanvas) return;
    const ctx = gaugeCanvas.getContext("2d");
    ctx.clearRect(0, 0, gaugeCanvas.width, gaugeCanvas.height);

    const centerX = gaugeCanvas.width / 2;
    const centerY = gaugeCanvas.height;
    const radius = 55;

    // Outer Background Track
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, Math.PI, 2 * Math.PI, false);
    ctx.lineWidth = 14;
    ctx.strokeStyle = "#232532";
    ctx.stroke();

    // Active Neon Arc
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, Math.PI, Math.PI + Math.PI * 0.75, false);
    ctx.lineWidth = 14;
    ctx.strokeStyle = "#98FF44";
    ctx.shadowBlur = 12;
    ctx.shadowColor = "#98FF44";
    ctx.lineCap = "round";
    ctx.stroke();
  }

  function renderHeatmap() {
    if (!streakHeatmapGrid) return;
    streakHeatmapGrid.innerHTML = "";
    for (let i = 0; i < 64; i++) {
      const cell = document.createElement("div");
      cell.className = "seq-cell";
      if (i > 50) {
        const rand = Math.random();
        if (rand > 0.75) cell.classList.add("l4");
        else if (rand > 0.5) cell.classList.add("l3");
        else if (rand > 0.25) cell.classList.add("l2");
        else cell.classList.add("l1");
      }
      streakHeatmapGrid.appendChild(cell);
    }
  }

  // 7. Load Stats & Milestones
  async function fetchStats() {
    try {
      const res = await fetch("/api/stats");
      if (res.ok) {
        const stats = await res.json();
        cachedStats = stats;

        if (sideTotalWords) sideTotalWords.textContent = `${(stats.total_words / 1000).toFixed(1)}K`;
        if (sideWpm) sideWpm.textContent = stats.wpm || 85;
        if (sideStreak) sideStreak.textContent = stats.streak_days || 1;

        if (insightsWpm) insightsWpm.textContent = stats.wpm || 85;
        if (insightsTotalWords) insightsTotalWords.textContent = stats.total_words.toLocaleString();
        if (insightsTotalFixes) insightsTotalFixes.textContent = (Math.round(stats.total_words * 0.14) + 1200).toLocaleString();

        if (stats.total_words >= 10000) {
          if (drSeussQuote) drSeussQuote.textContent = "You've written 1 Dr. Seuss book! (10K+ Unlocked)";
          if (vpBadgeName) vpBadgeName.textContent = "Protocol Investigator (Gold 10K)";
          if (adaptiveStatusTag) adaptiveStatusTag.textContent = "ACTIVE: Gold 10K+ Unlocked";
        }
      }
    } catch (e) {
      console.warn("Could not fetch stats", e);
    }
  }

  // Simulate 10K+ Button
  if (toggle10kBtn) {
    toggle10kBtn.addEventListener("click", async () => {
      await fetch("/api/milestones/simulate-10k", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ total_words: 15470 }),
      });
      await fetchStats();
      alert("10,000+ Words Milestone Unlocked! Adaptive Intent & Personal Voice Twin active.");
    });
  }

  // 8. Dictionary & Snippets Management
  async function loadDictionary() {
    try {
      const res = await fetch("/api/dictionary");
      if (res.ok) {
        const data = await res.json();
        cachedDictionary = data.words_detailed || {};
        cachedSnippets = data.snippets || {};
        renderDictTable();
        renderSnipTable();
      }
    } catch (e) {
      console.warn("Dictionary fetch failed", e);
    }
  }

  function renderDictTable() {
    if (!flowDictTableBody) return;
    const filter = searchWordsInput ? searchWordsInput.value.toLowerCase().trim() : "";
    flowDictTableBody.innerHTML = "";

    const entries = Object.entries(cachedDictionary);
    entries.forEach(([phrase, details]) => {
      const repl = typeof details === "object" ? details.replacement : details;
      const cat = typeof details === "object" ? details.category || "code" : "code";

      if (filter && !phrase.includes(filter) && !repl.toLowerCase().includes(filter)) return;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong style="color: #FFFFFF;">${escapeHtml(phrase)}</strong></td>
        <td><code style="font-family: var(--font-mono); color: var(--synth-lime);">${escapeHtml(repl)}</code></td>
        <td><span class="synth-cat-tag">${escapeHtml(cat)}</span></td>
        <td><button class="synth-ctrl-btn delete-word-btn" style="background: var(--synth-pink); color: #fff;" data-phrase="${escapeHtml(phrase)}">✕</button></td>
      `;
      flowDictTableBody.appendChild(tr);
    });

    document.querySelectorAll(".delete-word-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/dictionary/${encodeURIComponent(btn.dataset.phrase)}`, { method: "DELETE" });
        await loadDictionary();
      });
    });
  }

  function renderSnipTable() {
    if (!flowSnipTableBody) return;
    flowSnipTableBody.innerHTML = "";
    Object.entries(cachedSnippets).forEach(([trigger, expansion]) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong style="color: var(--synth-lime); font-family: var(--font-mono);">${escapeHtml(trigger)}</strong></td>
        <td style="font-size: 0.92rem; color: #D1D5DB;">${escapeHtml(expansion.slice(0, 50))}${expansion.length > 50 ? "..." : ""}</td>
        <td><button class="synth-ctrl-btn delete-snip-btn" style="background: var(--synth-pink); color: #fff;" data-trigger="${escapeHtml(trigger)}">✕</button></td>
      `;
      flowSnipTableBody.appendChild(tr);
    });

    document.querySelectorAll(".delete-snip-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/snippets/${encodeURIComponent(btn.dataset.trigger)}`, { method: "DELETE" });
        await loadDictionary();
      });
    });
  }

  // Add Word
  if (submitWordBtn) {
    submitWordBtn.addEventListener("click", async () => {
      const phrase = addPhraseInput.value.trim();
      const replacement = addReplInput.value.trim();
      const category = addCatSelect.value;
      if (!phrase || !replacement) return;

      await fetch("/api/dictionary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phrase, replacement, category }),
      });
      addPhraseInput.value = "";
      addReplInput.value = "";
      await loadDictionary();
    });
  }

  // Add Snippet
  if (submitSnipBtn) {
    submitSnipBtn.addEventListener("click", async () => {
      const trigger = snipTriggerInput.value.trim();
      const expansion = snipExpInput.value.trim();
      if (!trigger || !expansion) return;

      await fetch("/api/snippets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trigger, expansion }),
      });
      snipTriggerInput.value = "";
      snipExpInput.value = "";
      await loadDictionary();
    });
  }

  if (searchWordsInput) searchWordsInput.addEventListener("input", renderDictTable);

  function escapeHtml(str) {
    return (str || "").replace(/[&<>"']/g, (m) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    })[m]);
  }

  // Init
  renderTimelineFeed();
  fetchStats();
  loadDictionary();
});
