/**
 * EchoScribe Client Application
 * Handles live audio capture, real-time amplitude waveform, WebSocket chunk streaming,
 * Command Palette (⌘K), auto-learning dictionary chips, and Swarm bridge dispatch.
 */

class EchoScribeApp {
  constructor() {
    this.isRecording = false;
    this.currentTone = "clean";
    this.localOnly = true;
    this.bridgeArmed = true;
    this.ws = null;
    this.audioContext = null;
    this.analyser = null;
    this.mediaStream = null;
    this.animationFrameId = null;
    this.mediaRecorder = null;
    this.audioChunks = [];

    this.initElements();
    this.initEvents();
    this.initWaveformPlaceholder();
    this.fetchStatus();
    this.fetchSuggestions();
    this.fetchHistory();
  }

  initElements() {
    this.micRecordBtn = document.getElementById("micRecordBtn");
    this.recordingStatusText = document.getElementById("recordingStatusText");
    this.currentToneTag = document.getElementById("currentToneTag");
    this.waveformCanvas = document.getElementById("liveWaveform");
    this.transcriptContainer = document.getElementById("transcriptStreamingContainer");
    this.replacementsContainer = document.getElementById("replacementsAppliedContainer");
    this.historyFeed = document.getElementById("historyFeed");
    this.historyCountBadge = document.getElementById("historyCountBadge");
    this.paletteOverlay = document.getElementById("paletteOverlay");
    this.paletteSearchInput = document.getElementById("paletteSearchInput");
    this.openPaletteBtn = document.getElementById("openPaletteBtn");
    this.toggleLocalOnlyBtn = document.getElementById("toggleLocalOnlyBtn");
    this.localOnlyText = document.getElementById("localOnlyText");
    this.airgapBadge = document.getElementById("airgapBadge");
    this.bridgeToggleBtn = document.getElementById("bridgeToggleBtn");
    this.activeEngineLabel = document.getElementById("activeEngineLabel");
    this.copyTranscriptBtn = document.getElementById("copyTranscriptBtn");
    this.dispatchNowBtn = document.getElementById("dispatchNowBtn");
    this.suggestionsChipsContainer = document.getElementById("suggestionsChipsContainer");
    this.suggestionsBar = document.getElementById("suggestionsBar");

    // Stats
    this.statWordCount = document.getElementById("statWordCount");
    this.statWpm = document.getElementById("statWpm");
    this.statTimeSaved = document.getElementById("statTimeSaved");
    this.statRankBadge = document.getElementById("statRankBadge");
    this.statEgress = document.getElementById("statEgress");
  }

  initEvents() {
    this.micRecordBtn.addEventListener("click", () => this.toggleRecording());

    // Keyboard Shortcuts
    window.addEventListener("keydown", (e) => {
      // ⌘K or Ctrl+K for command palette
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        this.openPalette();
      }
      // Escape closes palette
      if (e.key === "Escape" && this.paletteOverlay.classList.contains("open")) {
        this.closePalette();
      }
      // Spacebar to toggle recording when not typing in inputs
      if (e.code === "Space" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
        if (!e.repeat) {
          e.preventDefault();
          this.toggleRecording();
        }
      }
    });

    this.openPaletteBtn.addEventListener("click", () => this.openPalette());
    this.paletteOverlay.addEventListener("click", (e) => {
      if (e.target === this.paletteOverlay) this.closePalette();
    });

    this.toggleLocalOnlyBtn.addEventListener("click", () => this.toggleLocalOnly());
    this.bridgeToggleBtn.addEventListener("click", () => this.toggleBridge());

    this.copyTranscriptBtn.addEventListener("click", () => {
      const text = this.transcriptContainer.innerText.trim();
      if (text && !this.transcriptContainer.classList.contains("empty")) {
        navigator.clipboard.writeText(text);
        this.copyTranscriptBtn.querySelector("span").innerText = "Copied!";
        setTimeout(() => (this.copyTranscriptBtn.querySelector("span").innerText = "Copy"), 1500);
      }
    });

    this.dispatchNowBtn.addEventListener("click", () => {
      const text = this.transcriptContainer.innerText.trim();
      if (text && !this.transcriptContainer.classList.contains("empty")) {
        this.dispatchToSwarm(text);
      }
    });

    // Command palette items click
    document.querySelectorAll(".palette-item").forEach((item) => {
      item.addEventListener("click", () => {
        const action = item.getAttribute("data-action");
        const val = item.getAttribute("data-value");
        if (action === "set-tone") {
          this.setTone(val);
        } else if (action === "toggle-local-only") {
          this.toggleLocalOnly();
        }
        this.closePalette();
      });
    });
  }

  setTone(tone) {
    this.currentTone = tone;
    this.currentToneTag.innerText = `Tone: ${tone.charAt(0).toUpperCase() + tone.slice(1)}`;
  }

  toggleBridge() {
    this.bridgeArmed = !this.bridgeArmed;
    if (this.bridgeArmed) {
      this.bridgeToggleBtn.classList.add("active");
      this.bridgeToggleBtn.querySelector("span").innerText = "Swarm Bridge: Armed";
    } else {
      this.bridgeToggleBtn.classList.remove("active");
      this.bridgeToggleBtn.querySelector("span").innerText = "Swarm Bridge: Standby";
    }
  }

  async toggleLocalOnly() {
    this.localOnly = !this.localOnly;
    try {
      const res = await fetch("/api/config/local-only", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: this.localOnly }),
      });
      const data = await res.json();
      this.updateLocalOnlyUI(data.local_only_mode);
    } catch (e) {
      this.updateLocalOnlyUI(this.localOnly);
    }
  }

  updateLocalOnlyUI(enabled) {
    this.localOnly = enabled;
    if (enabled) {
      this.localOnlyText.innerText = "Air-Gap: Active";
      this.airgapBadge.style.display = "inline-flex";
      this.statEgress.innerText = "0 bytes (Air-Gapped)";
      this.statEgress.className = "stat-value text-success";
    } else {
      this.localOnlyText.innerText = "Air-Gap: Disabled";
      this.airgapBadge.style.display = "none";
      this.statEgress.innerText = "Cloud Whisper allowed";
      this.statEgress.className = "stat-value";
    }
  }

  openPalette() {
    this.paletteOverlay.classList.add("open");
    this.paletteSearchInput.value = "";
    this.paletteSearchInput.focus();
  }

  closePalette() {
    this.paletteOverlay.classList.remove("open");
  }

  async fetchStatus() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      this.activeEngineLabel.innerText = data.active_engine;
      this.updateLocalOnlyUI(data.local_only_mode);
      if (data.stats) {
        this.statWordCount.innerText = data.stats.total_words.toLocaleString();
        this.statWpm.innerText = `${data.stats.wpm} WPM`;
        this.statTimeSaved.innerText = `${data.stats.hours_saved} hrs`;
        this.statRankBadge.innerText = data.stats.rank;
      }
    } catch (e) {
      console.warn("Could not fetch status:", e);
    }
  }

  async fetchSuggestions() {
    try {
      const res = await fetch("/api/dictionary/suggestions");
      const suggestions = await res.json();
      this.renderSuggestions(suggestions);
    } catch (e) {
      console.warn("Could not fetch suggestions:", e);
    }
  }

  renderSuggestions(suggestions) {
    this.suggestionsChipsContainer.innerHTML = "";
    if (!suggestions || suggestions.length === 0) {
      this.suggestionsBar.style.display = "none";
      return;
    }
    this.suggestionsBar.style.display = "flex";
    suggestions.slice(0, 4).forEach((s) => {
      const chip = document.createElement("div");
      chip.className = "suggestion-chip";
      chip.innerHTML = `
        <span>Add <strong>"${s.proposed_replacement || s.phrase}"</strong></span>
        <button class="chip-btn accept" title="Add to dictionary">✓</button>
        <button class="chip-btn dismiss" title="Dismiss">✕</button>
      `;
      chip.querySelector(".accept").addEventListener("click", () => this.acceptSuggestion(s.phrase));
      chip.querySelector(".dismiss").addEventListener("click", () => this.dismissSuggestion(s.phrase));
      this.suggestionsChipsContainer.appendChild(chip);
    });
  }

  async acceptSuggestion(phrase) {
    try {
      await fetch("/api/dictionary/suggestions/accept", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phrase }),
      });
      this.fetchSuggestions();
    } catch (e) {
      console.error(e);
    }
  }

  async dismissSuggestion(phrase) {
    try {
      await fetch("/api/dictionary/suggestions/dismiss", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phrase }),
      });
      this.fetchSuggestions();
    } catch (e) {
      console.error(e);
    }
  }

  async fetchHistory() {
    try {
      const res = await fetch("/api/history");
      const history = await res.json();
      this.renderHistory(history);
    } catch (e) {
      console.warn("Could not fetch history:", e);
    }
  }

  renderHistory(history) {
    this.historyFeed.innerHTML = "";
    this.historyCountBadge.innerText = `${history.length} sessions`;
    if (history.length === 0) {
      this.historyFeed.innerHTML = `<div style="color: var(--text-tertiary); font-size: var(--text-sm);">No dictation sessions recorded yet.</div>`;
      return;
    }
    history.forEach((h) => {
      const card = document.createElement("div");
      card.className = "history-card";
      const timeStr = new Date((h.timestamp || Date.now()) * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      card.innerHTML = `
        <div class="history-meta">
          <span>${timeStr} · Engine: ${h.engine || 'local'}</span>
          <span>${h.latency_ms || 12}ms</span>
        </div>
        <div class="history-text">${h.transcript}</div>
      `;
      card.addEventListener("click", () => {
        this.renderFinalTranscript(h.transcript, h.replacements || []);
      });
      this.historyFeed.appendChild(card);
    });
  }

  /* Amplitude Waveform Setup */
  initWaveformPlaceholder() {
    const canvas = this.waveformCanvas;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = "#222630";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();
  }

  startWaveformVisualizer(stream) {
    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = this.audioContext.createMediaStreamSource(stream);
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;
    source.connect(this.analyser);

    const canvas = this.waveformCanvas;
    const ctx = canvas.getContext("2d");
    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      this.animationFrameId = requestAnimationFrame(draw);
      this.analyser.getByteTimeDomainData(dataArray);

      ctx.fillStyle = "#161922";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.lineWidth = 2;
      ctx.strokeStyle = "#6366F1";
      ctx.beginPath();

      const sliceWidth = (canvas.width * 1.0) / bufferLength;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * canvas.height) / 2;

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
        x += sliceWidth;
      }

      ctx.lineTo(canvas.width, canvas.height / 2);
      ctx.stroke();
    };

    draw();
  }

  stopWaveformVisualizer() {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    this.initWaveformPlaceholder();
  }

  /* Recording & Streaming */
  async toggleRecording() {
    if (this.isRecording) {
      this.stopRecording();
    } else {
      await this.startRecording();
    }
  }

  async startRecording() {
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.isRecording = true;
      this.micRecordBtn.classList.add("recording");
      this.recordingStatusText.innerText = "Streaming Audio (Listening...)";

      this.startWaveformVisualizer(this.mediaStream);
      this.initWebSocketStream();

      // MediaRecorder for chunk slices
      this.audioChunks = [];
      this.mediaRecorder = new MediaRecorder(this.mediaStream, { mimeType: "audio/webm" });
      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0 && this.ws && this.ws.readyState === WebSocket.OPEN) {
          e.data.arrayBuffer().then((buf) => {
            this.ws.send(buf);
          });
        }
      };
      this.mediaRecorder.start(250); // Emit chunk every 250ms

      this.transcriptContainer.classList.remove("empty");
      this.transcriptContainer.innerHTML = `<span class="token-fade-in" style="color: var(--text-tertiary);">Streaming speech...</span>`;
    } catch (err) {
      console.error("Microphone access denied or error:", err);
      this.recordingStatusText.innerText = "Microphone Access Denied";
    }
  }

  initWebSocketStream() {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/ws/transcribe`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log("Connected to streaming transcription WebSocket");
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "PARTIAL_TRANSCRIPT") {
          this.renderPartialTranscript(data.text);
        } else if (data.type === "FINAL_TRANSCRIPT") {
          const payload = data.payload;
          this.renderFinalTranscript(payload.transcript, payload.replacements || []);
          this.fetchHistory();
          this.fetchSuggestions();
          this.fetchStatus();

          // Auto-dispatch to Swarm if bridge armed
          if (this.bridgeArmed && payload.transcript) {
            this.dispatchToSwarm(payload.transcript);
          }
        }
      } catch (e) {
        console.error("WS parse error:", e);
      }
    };
  }

  stopRecording() {
    this.isRecording = false;
    this.micRecordBtn.classList.remove("recording");
    this.recordingStatusText.innerText = "Processing Final Audio...";

    if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      this.mediaRecorder.stop();
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    this.stopWaveformVisualizer();

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: "FINISH",
        tone: this.currentTone,
        apply_dictionary: true,
        apply_snippets: true,
      }));
    }

    setTimeout(() => {
      this.recordingStatusText.innerText = "Ready to Dictate";
    }, 800);
  }

  renderPartialTranscript(text) {
    if (!text) return;
    const words = text.split(" ");
    this.transcriptContainer.innerHTML = words
      .map((w, idx) => `<span class="token-fade-in" style="animation-delay: ${idx * 15}ms">${w}</span>`)
      .join(" ");
  }

  renderFinalTranscript(text, replacements = []) {
    this.transcriptContainer.classList.remove("empty");
    this.transcriptContainer.innerHTML = `<span class="token-fade-in">${text}</span>`;

    this.replacementsContainer.innerHTML = "";
    if (replacements && replacements.length > 0) {
      replacements.forEach((r) => {
        const tag = document.createElement("span");
        tag.className = "replacement-tag";
        tag.innerHTML = `${r.from} ➔ <strong>${r.to}</strong> (${r.type})`;
        this.replacementsContainer.appendChild(tag);
      });
    }
  }

  async dispatchToSwarm(transcriptText) {
    try {
      this.dispatchNowBtn.querySelector("span").innerText = "Dispatching...";
      const res = await fetch("/api/bridge/dispatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript: transcriptText,
          cli_preference: "auto",
          difficulty: "auto",
        }),
      });
      const data = await res.json();
      if (data.success && data.dispatched) {
        this.dispatchNowBtn.querySelector("span").innerText = "Dispatched to Swarm ✓";
      } else {
        this.dispatchNowBtn.querySelector("span").innerText = "Dispatch Error";
      }
      setTimeout(() => (this.dispatchNowBtn.querySelector("span").innerText = "Dispatch to Swarm"), 2500);
    } catch (e) {
      this.dispatchNowBtn.querySelector("span").innerText = "Dispatch Failed";
      setTimeout(() => (this.dispatchNowBtn.querySelector("span").innerText = "Dispatch to Swarm"), 2000);
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.echoApp = new EchoScribeApp();
});
