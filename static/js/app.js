/**
 * EchoScribe — Claude.ai Interface Controller
 * 
 * Implements:
 * - Spacebar & embedded mic streaming dictation
 * - Per-token fade-in animation in the live stream turn
 * - Universal Right-Panel Artifact Viewer for Personal Dictionary ("Corrected / Raw" toggle)
 * - Quiet App-Context indicator line
 * - Direct Swarm Bridge dispatch to CLI Workflow
 */

class EchoScribeApp {
  constructor() {
    this.isRecording = false;
    this.isPaused = false;
    this.activeTone = "clean";
    this.localOnly = true;
    this.swarmArmed = true;
    this.activeAppTarget = "VS Code";
    this.dictionaryData = {};
    this.activeArtifactMode = "corrected"; // "corrected" or "raw"
    this.currentArtifactType = "dictionary"; // "dictionary" or "settings"
    this.correctionStrength = "full";
    this.activeEngineId = "auto";
    this.selectedAudioDeviceId = localStorage.getItem("echoscribe_audio_device") || "default";
    this.pendingCommandReplacement = "";
    this.pendingCommandTargetEl = null;
    this.pulseAnimFrame = null;
    this.mediaStream = null;
    this.audioContext = null;
    this.audioAnalyser = null;

    this.initElements();
    this.initEvents();
    this.loadInitialData();
  }

  initElements() {
    // Window Topbar
    this.btnCommandMode = document.getElementById("btnCommandMode");
    this.bridgeToggleBtn = document.getElementById("bridgeToggleBtn");
    this.airgapBadge = document.getElementById("airgapBadge");

    // Sidebar
    this.btnNewDictation = document.getElementById("btnNewDictation");
    this.btnNavDictionary = document.getElementById("btnNavDictionary");
    this.btnNavSnippets = document.getElementById("btnNavSnippets");
    this.btnNavSettings = document.getElementById("btnNavSettings");
    this.sidebarRecentList = document.getElementById("sidebarRecentList");

    // Main Pane
    this.conversationThread = document.getElementById("conversationThread");
    this.liveStreamingTurn = document.getElementById("liveStreamingTurn");
    this.liveTranscriptText = document.getElementById("liveTranscriptText");
    this.liveReplacementsContainer = document.getElementById("liveReplacementsContainer");
    this.liveStreamMeta = document.getElementById("liveStreamMeta");

    // Composer & App-Context Line
    this.currentAppTarget = document.getElementById("currentAppTarget");
    this.currentToneLabel = document.getElementById("currentToneLabel");
    this.currentEngineLabel = document.getElementById("currentEngineLabel");
    this.currentEgressLabel = document.getElementById("currentEgressLabel");
    this.composerPill = document.getElementById("composerPill");
    this.composerMicBtn = document.getElementById("composerMicBtn");
    this.composerPauseBtn = document.getElementById("composerPauseBtn");
    this.copyLatestBtn = document.getElementById("copyLatestBtn");
    this.dispatchSwarmBtn = document.getElementById("dispatchSwarmBtn");
    this.suggestionsChipsRow = document.getElementById("suggestionsChipsRow");

    // Command Mode Diff Elements
    this.commandDiffContainer = document.getElementById("commandDiffContainer");
    this.commandDiffBody = document.getElementById("commandDiffBody");
    this.btnDiscardCommand = document.getElementById("btnDiscardCommand");
    this.btnAcceptCommand = document.getElementById("btnAcceptCommand");

    // Universal Right-Panel Artifact Viewer
    this.rightPanel = document.getElementById("rightArtifactPanel");
    this.artifactViewToggle = document.getElementById("artifactViewToggle");
    this.btnArtifactCorrected = document.getElementById("btnArtifactCorrected");
    this.btnArtifactRaw = document.getElementById("btnArtifactRaw");
    this.artifactTitle = document.getElementById("artifactTitle");
    this.artifactBadge = document.getElementById("artifactBadge");
    this.btnArtifactCopy = document.getElementById("btnArtifactCopy");
    this.btnArtifactClose = document.getElementById("btnArtifactClose");
    this.artifactContentBody = document.getElementById("artifactContentBody");

    // Command Palette Modal
    this.paletteOverlay = document.getElementById("paletteOverlay");
    this.paletteSearchInput = document.getElementById("paletteSearchInput");
  }

  initEvents() {
    // Topbar Actions
    this.btnCommandMode?.addEventListener("click", () => this.triggerCommandMode());
    this.bridgeToggleBtn?.addEventListener("click", () => this.toggleSwarmBridge());

    // Sidebar Nav
    this.btnNewDictation?.addEventListener("click", () => this.startRecording());
    this.btnNavDictionary?.addEventListener("click", () => this.openDictionaryArtifact());
    this.btnNavSnippets?.addEventListener("click", () => this.openPalette());
    this.btnNavSettings?.addEventListener("click", () => this.openSettingsArtifact());

    // Mic Button, Pause Button & Composer Actions
    this.composerMicBtn?.addEventListener("click", () => this.toggleRecording());
    this.composerPauseBtn?.addEventListener("click", () => this.togglePause());
    this.copyLatestBtn?.addEventListener("click", () => this.copyLatestTranscript());
    this.dispatchSwarmBtn?.addEventListener("click", () => this.dispatchLatestToSwarm());
    this.btnDiscardCommand?.addEventListener("click", () => this.discardCommandEdit());
    this.btnAcceptCommand?.addEventListener("click", () => this.acceptCommandEdit());

    // Right-Panel Controls
    this.btnArtifactClose?.addEventListener("click", () => this.closeArtifact());
    this.btnArtifactCorrected?.addEventListener("click", () => this.setArtifactMode("corrected"));
    this.btnArtifactRaw?.addEventListener("click", () => this.setArtifactMode("raw"));
    this.btnArtifactCopy?.addEventListener("click", () => this.copyArtifactData());

    // Global Hotkeys: Spacebar (Hold-to-talk), ⌘K, Alt+C
    let spaceDown = false;
    window.addEventListener("keydown", (e) => {
      // ⌘K or Ctrl+K opens palette
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        this.openPalette();
        return;
      }

      // Alt+C toggles Command Mode
      if (e.altKey && e.key.toLowerCase() === "c") {
        e.preventDefault();
        this.triggerCommandMode();
        return;
      }

      // Escape closes palette, artifact, or diff preview
      if (e.key === "Escape") {
        this.closePalette();
        this.closeArtifact();
        this.discardCommandEdit();
        return;
      }

      // Spacebar hold-to-talk if not in an input
      if (e.code === "Space" && !spaceDown && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
        spaceDown = true;
        this.startRecording();
      }
    });

    window.addEventListener("keyup", (e) => {
      if (e.code === "Space" && spaceDown) {
        spaceDown = false;
        this.stopRecording();
      }
    });

    // Command Palette backdrop close & item clicks
    this.paletteOverlay?.addEventListener("click", (e) => {
      if (e.target === this.paletteOverlay) this.closePalette();
    });

    document.querySelectorAll(".palette-item").forEach((item) => {
      item.addEventListener("click", () => {
        const action = item.getAttribute("data-action");
        const val = item.getAttribute("data-value");
        this.handlePaletteAction(action, val);
      });
    });
  }

  // ==========================================
  // STREAMING DICTATION & TOKEN FADE-IN
  // ==========================================

  toggleRecording() {
    if (this.isRecording) {
      this.stopRecording();
    } else {
      this.startRecording();
    }
  }

  startRecording() {
    if (this.isRecording) return;
    this.isRecording = true;
    this.isPaused = false;

    this.composerMicBtn.classList.add("recording");
    this.composerMicBtn.classList.remove("is-paused");
    this.composerPill.classList.add("recording");
    if (this.composerPauseBtn) {
      this.composerPauseBtn.style.display = "inline-flex";
      this.composerPauseBtn.classList.remove("active-paused");
      this.composerPauseBtn.title = "Pause Recording";
      this.composerPauseBtn.innerHTML = `
        <svg class="pause-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="6" y="4" width="4" height="16"/>
          <rect x="14" y="4" width="4" height="16"/>
        </svg>
      `;
    }

    this.liveStreamingTurn.style.display = "flex";
    this.liveTranscriptText.innerHTML = "";
    this.liveReplacementsContainer.innerHTML = "";
    this.liveStreamMeta.innerText = `Recording · Tone: ${this.activeTone}`;

    // Initialize audio reactivity for integrated mic pulse
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      const audioConstraints = (this.selectedAudioDeviceId && this.selectedAudioDeviceId !== "default")
        ? { audio: { deviceId: { exact: this.selectedAudioDeviceId } } }
        : { audio: true };

      navigator.mediaDevices.getUserMedia(audioConstraints)
        .then((stream) => {
          this.mediaStream = stream;
          try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (AudioCtx) {
              this.audioContext = new AudioCtx();
              this.audioAnalyser = this.audioContext.createAnalyser();
              this.audioAnalyser.fftSize = 64;
              const source = this.audioContext.createMediaStreamSource(stream);
              source.connect(this.audioAnalyser);
              const dataArray = new Uint8Array(this.audioAnalyser.frequencyBinCount);

              const updatePulse = () => {
                if (!this.isRecording || this.isPaused) return;
                this.audioAnalyser.getByteFrequencyData(dataArray);
                let sum = 0;
                for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
                const avg = sum / dataArray.length;
                const intensity = Math.min(2.2, Math.max(0.7, avg / 24));
                this.composerMicBtn?.style.setProperty("--audio-intensity", intensity.toFixed(2));
                this.pulseAnimFrame = requestAnimationFrame(updatePulse);
              };
              this.pulseAnimFrame = requestAnimationFrame(updatePulse);
            }
          } catch (e) {
            console.debug("Audio analyzer note:", e);
          }
        })
        .catch((err) => {
          console.debug("Microphone stream note:", err);
        });
    }

    // Stream simulated tokens with smooth fade-in
    this.simulateStreamingTokens();
  }

  togglePause() {
    if (!this.isRecording) return;
    this.isPaused = !this.isPaused;

    if (this.isPaused) {
      this.composerMicBtn.classList.add("is-paused");
      this.composerPauseBtn?.classList.add("active-paused");
      if (this.composerPauseBtn) {
        this.composerPauseBtn.title = "Resume Recording";
        this.composerPauseBtn.innerHTML = `
          <svg class="play-icon" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
        `;
      }
      this.liveStreamMeta.innerText = "Paused";
    } else {
      this.composerMicBtn.classList.remove("is-paused");
      this.composerPauseBtn?.classList.remove("active-paused");
      if (this.composerPauseBtn) {
        this.composerPauseBtn.title = "Pause Recording";
        this.composerPauseBtn.innerHTML = `
          <svg class="pause-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="6" y="4" width="4" height="16"/>
            <rect x="14" y="4" width="4" height="16"/>
          </svg>
        `;
      }
      this.liveStreamMeta.innerText = `Recording · Tone: ${this.activeTone}`;

      // Resume pulse loop
      if (this.audioAnalyser) {
        const dataArray = new Uint8Array(this.audioAnalyser.frequencyBinCount);
        const updatePulse = () => {
          if (!this.isRecording || this.isPaused) return;
          this.audioAnalyser.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
          const avg = sum / dataArray.length;
          const intensity = Math.min(2.2, Math.max(0.7, avg / 24));
          this.composerMicBtn?.style.setProperty("--audio-intensity", intensity.toFixed(2));
          this.pulseAnimFrame = requestAnimationFrame(updatePulse);
        };
        this.pulseAnimFrame = requestAnimationFrame(updatePulse);
      }
    }
  }

  stopRecording() {
    if (!this.isRecording) return;
    this.isRecording = false;
    this.isPaused = false;

    if (this.pulseAnimFrame) {
      cancelAnimationFrame(this.pulseAnimFrame);
      this.pulseAnimFrame = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    if (this.audioContext) {
      try { this.audioContext.close(); } catch(e) {}
      this.audioContext = null;
    }

    this.composerMicBtn.classList.remove("recording", "is-paused");
    this.composerMicBtn.style.removeProperty("--audio-intensity");
    this.composerPill.classList.remove("recording");
    if (this.composerPauseBtn) {
      this.composerPauseBtn.style.display = "none";
      this.composerPauseBtn.classList.remove("active-paused");
    }
    this.liveStreamingTurn.style.display = "none";

    const text = this.liveTranscriptText.innerText.trim();
    if (text) {
      this.commitTranscriptTurn(text);
      if (this.swarmArmed) {
        this.dispatchToSwarm(text);
      }
    }
  }

  simulateStreamingTokens() {
    const samplePhrases = [
      ["Create", " a", " unified", " UserAuthService", " in", " FastAPI", " and", " assert", " with", " pytest"],
      ["Refactor", " the", " shared", " design", " tokens", " to", " use", " warm", " charcoal", " surfaces"],
      ["Implement", " the", " universal", " artifact", " viewer", " with", " a", " Corrected", " Raw", " toggle"]
    ];
    const phrase = samplePhrases[Math.floor(Math.random() * samplePhrases.length)];
    let idx = 0;

    const interval = setInterval(() => {
      if (!this.isRecording) {
        clearInterval(interval);
        return;
      }
      if (this.isPaused) {
        return; // Hold streaming while paused
      }
      if (idx >= phrase.length) {
        clearInterval(interval);
        return;
      }

      const tokenSpan = document.createElement("span");
      tokenSpan.className = "live-token";
      tokenSpan.innerText = phrase[idx];
      this.liveTranscriptText.appendChild(tokenSpan);
      idx++;
    }, 180);
  }

  commitTranscriptTurn(text) {
    const turn = document.createElement("div");
    turn.className = "dictation-turn";
    turn.innerHTML = `
      <div class="turn-header">
        <span class="app-source-icon">💻</span>
        <span class="turn-author">Dictation Entry</span>
        <span class="turn-meta">just now · ${text.split(" ").length} words · ${this.activeTone}</span>
      </div>
      <div class="turn-body">
        <p>${this.escapeHtml(text)}</p>
      </div>
    `;
    this.conversationThread.appendChild(turn);
    turn.scrollIntoView({ behavior: "smooth" });

    // Update stats if element exists
    if (this.statWordCount) {
      const current = parseInt(this.statWordCount.innerText.replace(/,/g, "")) || 10050;
      this.statWordCount.innerText = (current + text.split(" ").length).toLocaleString() + " words";
    }
  }

  copyLatestTranscript() {
    const turns = this.conversationThread.querySelectorAll(".dictation-turn p");
    if (turns.length > 0) {
      const last = turns[turns.length - 1].innerText;
      navigator.clipboard.writeText(last);
      alert("Latest transcript copied to clipboard!");
    }
  }

  dispatchLatestToSwarm() {
    const turns = this.conversationThread.querySelectorAll(".dictation-turn p");
    if (turns.length > 0) {
      const last = turns[turns.length - 1].innerText;
      this.dispatchToSwarm(last);
    }
  }

  async dispatchToSwarm(text) {
    try {
      const formData = new FormData();
      formData.append("prompt", text);
      formData.append("preset", "swarm");
      formData.append("cli_preference", "auto");

      await fetch("http://127.0.0.1:8099/api/workflow/dispatch", {
        method: "POST",
        body: formData
      });
      console.log("Dispatched to Swarm:", text);
    } catch (e) {
      console.warn("Direct Swarm dispatch fallback notice:", e);
    }
  }

  // ==========================================
  // COMMAND MODE (VOICE-DRIVEN EDITING)
  // ==========================================

  async triggerCommandMode() {
    let targetText = "";
    let targetEl = null;

    const selection = window.getSelection();
    if (selection && selection.toString().trim()) {
      targetText = selection.toString().trim();
      targetEl = selection.anchorNode.parentElement;
    } else {
      const turns = this.conversationThread.querySelectorAll(".dictation-turn p");
      if (turns.length > 0) {
        targetEl = turns[turns.length - 1];
        targetText = targetEl.innerText.trim();
      }
    }

    if (!targetText) {
      alert("Please select text or dictate an entry to use Command Mode.");
      return;
    }

    const instruction = prompt(
      `⚡ Command Mode\nTarget: "${targetText.slice(0, 40)}..."\n\nEnter voice/edit instruction:\n(e.g. 'make this concise', 'format as bullet points', 'fix grammar', 'formal tone')`,
      "make this more concise"
    );

    if (!instruction || !instruction.trim()) return;

    try {
      const res = await fetch("/api/command/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          selected_text: targetText,
          instruction: instruction.trim()
        })
      });
      const data = await res.json();
      if (data.success) {
        this.pendingCommandReplacement = data.replacement;
        this.pendingCommandTargetEl = targetEl;
        this.commandDiffBody.innerHTML = data.diff_html;
        this.commandDiffContainer.style.display = "flex";
      } else {
        alert("Command edit error: " + (data.error || "Unknown"));
      }
    } catch (e) {
      alert("Command Mode request failed: " + e);
    }
  }

  acceptCommandEdit() {
    if (this.pendingCommandTargetEl && this.pendingCommandReplacement) {
      this.pendingCommandTargetEl.innerText = this.pendingCommandReplacement;
      // Post-paste auto add watcher simulation
      fetch("/api/dictionary/auto-add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          original_inserted: this.pendingCommandTargetEl.innerText,
          current_field_text: this.pendingCommandReplacement
        })
      }).catch(() => {});
    }
    this.discardCommandEdit();
  }

  discardCommandEdit() {
    this.commandDiffContainer.style.display = "none";
    this.pendingCommandReplacement = "";
    this.pendingCommandTargetEl = null;
  }

  // ==========================================
  // UNIVERSAL RIGHT-PANEL (PERSONAL DICTIONARY)
  // ==========================================

  async loadInitialData() {
    try {
      const res = await fetch("/api/dictionary/entries");
      this.dictionaryData = await res.json();
      this.loadRecentSessions();
      this.loadSuggestions();
    } catch (e) {
      this.dictionaryData = {
        "fast api": "FastAPI",
        "pie test": "pytest",
        "docker compose": "Docker Compose",
        "post gres": "PostgreSQL",
        "type script": "TypeScript",
        "claude code": "Claude Code"
      };
      this.loadRecentSessions();
    }

    // Load active transcription engine info
    try {
      const engRes = await fetch("/api/transcription/engines");
      const engData = await engRes.json();
      if (engData && engData.active_engine_name) {
        if (this.currentEngineLabel) {
          this.currentEngineLabel.innerText = `Engine: ${engData.active_engine_name}`;
        }
        if (this.transcriptionEngineSelect) {
          this.transcriptionEngineSelect.value = engData.preference || "auto";
        }
      }
    } catch (e) {
      console.warn("Could not load transcription engine status:", e);
    }
  }

  async switchEngine(engineId) {
    try {
      this.activeEngineId = engineId;
      const res = await fetch("/api/transcription/engine/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ engine_id: engineId })
      });
      const data = await res.json();
      if (data.success && this.currentEngineLabel) {
        this.currentEngineLabel.innerText = `Engine: ${data.display_name}`;
      }
    } catch (e) {
      console.warn("Failed to switch engine:", e);
    }
  }

  async openSettingsArtifact() {
    this.currentArtifactType = "settings";
    this.artifactTitle.innerText = "Settings";
    this.artifactBadge.innerText = "· CONFIG";
    if (this.artifactViewToggle) this.artifactViewToggle.style.display = "none";
    this.rightPanel.classList.add("open");
    await this.renderSettingsContent();
  }

  openDictionaryArtifact() {
    this.currentArtifactType = "dictionary";
    this.artifactTitle.innerText = "Personal Dictionary";
    this.artifactBadge.innerText = "· DICT";
    if (this.artifactViewToggle) this.artifactViewToggle.style.display = "flex";
    this.rightPanel.classList.add("open");
    this.renderDictionaryContent();
  }

  closeArtifact() {
    this.rightPanel.classList.remove("open", "fullscreen");
  }

  setArtifactMode(mode) {
    this.activeArtifactMode = mode;
    this.btnArtifactCorrected?.classList.toggle("active", mode === "corrected");
    this.btnArtifactRaw?.classList.toggle("active", mode === "raw");
    if (this.currentArtifactType === "dictionary") {
      this.renderDictionaryContent();
    }
  }

  async renderSettingsContent() {
    // Enumerate audio input devices
    let audioDeviceOptions = `<option value="default">Default System Microphone</option>`;
    try {
      if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const audioInputs = devices.filter((d) => d.kind === "audioinput");
        if (audioInputs.length > 0) {
          audioDeviceOptions = audioInputs.map((d, i) => {
            const isSel = d.deviceId === this.selectedAudioDeviceId ? "selected" : "";
            const label = d.label || `Microphone ${i + 1}`;
            return `<option value="${d.deviceId}" ${isSel}>${this.escapeHtml(label)}</option>`;
          }).join("");
        }
      }
    } catch (e) {
      console.debug("Could not enumerate audio devices:", e);
    }

    const html = `
      <div class="settings-view-container">
        <!-- Audio Input Device -->
        <div class="settings-card">
          <div class="settings-card-header">
            <span class="settings-card-label">Microphone Input Device</span>
          </div>
          <p class="settings-card-desc">Select the physical audio input stream used for speech dictation.</p>
          <div class="settings-card-control">
            <select class="settings-field-select" id="settingAudioDevice">
              ${audioDeviceOptions}
            </select>
          </div>
        </div>

        <!-- Transcription Engine Selection -->
        <div class="settings-card">
          <div class="settings-card-header">
            <span class="settings-card-label">Transcription Engine</span>
          </div>
          <p class="settings-card-desc">Choose between local on-device Whisper, macOS Native Speech, or cloud Model API.</p>
          <div class="settings-card-control">
            <select class="settings-field-select" id="settingTranscriptionEngine">
              <option value="auto" ${this.activeEngineId === "auto" ? "selected" : ""}>Auto: OS Detected</option>
              <option value="windows_local" ${this.activeEngineId === "windows_local" ? "selected" : ""}>Windows Local (Whisper on-device)</option>
              <option value="macos_native" ${this.activeEngineId === "macos_native" ? "selected" : ""}>macOS Native (Apple Speech.framework)</option>
              <option value="model_api" ${this.activeEngineId === "model_api" ? "selected" : ""}>Model/API (Cloud Whisper / Local Ollama)</option>
            </select>
          </div>
        </div>

        <!-- Correction Strength -->
        <div class="settings-card">
          <div class="settings-card-header">
            <span class="settings-card-label">Correction Intelligence Strength</span>
          </div>
          <p class="settings-card-desc">Controls how aggressively speech fillers ("um", "uh", stutters, false starts) are removed.</p>
          <div class="settings-card-control">
            <select class="settings-field-select" id="settingCorrectionStrength">
              <option value="full" ${this.correctionStrength === "full" ? "selected" : ""}>Full Correction (Disfluencies & Stutters)</option>
              <option value="light" ${this.correctionStrength === "light" ? "selected" : ""}>Light (Stutters & Repeats Only)</option>
              <option value="off" ${this.correctionStrength === "off" ? "selected" : ""}>Off (Literal Verbatim Speech)</option>
            </select>
          </div>
        </div>

        <!-- Air-Gap Privacy Mode Toggle -->
        <div class="settings-card">
          <div class="settings-card-header">
            <span class="settings-card-label">Air-Gap Local Guarantee</span>
            <label class="settings-toggle-switch">
              <input type="checkbox" id="settingAirGapToggle" ${this.localOnly ? "checked" : ""} />
              <span class="toggle-slider"></span>
            </label>
          </div>
          <p class="settings-card-desc">When enabled, EchoScribe strictly forbids external cloud network egress (0 bytes outbound).</p>
        </div>

        <!-- Swarm Bridge Target -->
        <div class="settings-card">
          <div class="settings-card-header">
            <span class="settings-card-label">CLI Workflow Swarm Bridge</span>
            <span class="coral-chip" style="font-size: 11px;">Port 8099</span>
          </div>
          <p class="settings-card-desc">Direct dispatch destination for multi-agent swarm task execution.</p>
          <input type="text" class="dict-input" style="margin-top: 4px;" value="http://localhost:8099" readonly />
        </div>
      </div>
    `;

    this.artifactContentBody.innerHTML = html;

    // Bind Settings View Controls
    const deviceSelect = this.artifactContentBody.querySelector("#settingAudioDevice");
    deviceSelect?.addEventListener("change", (e) => {
      this.selectedAudioDeviceId = e.target.value;
      localStorage.setItem("echoscribe_audio_device", this.selectedAudioDeviceId);
    });

    const engineSelect = this.artifactContentBody.querySelector("#settingTranscriptionEngine");
    engineSelect?.addEventListener("change", (e) => {
      this.switchEngine(e.target.value);
    });

    const strengthSelect = this.artifactContentBody.querySelector("#settingCorrectionStrength");
    strengthSelect?.addEventListener("change", (e) => {
      this.correctionStrength = e.target.value;
    });

    const airGapToggle = this.artifactContentBody.querySelector("#settingAirGapToggle");
    airGapToggle?.addEventListener("change", async (e) => {
      const enabled = e.target.checked;
      this.localOnly = enabled;
      if (this.currentEgressLabel) {
        this.currentEgressLabel.innerText = enabled ? "0 bytes egress (Air-Gapped)" : "Cloud egress allowed";
      }
      try {
        await fetch("/api/config/local-only", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled })
        });
      } catch (err) {}
    });
  }

  renderDictionaryContent() {
    if (this.activeArtifactMode === "raw") {
      this.artifactContentBody.innerHTML = `
        <h2 class="display-serif">Dictionary Mapping Schema</h2>
        <div class="diff-container" style="background: var(--bg-secondary); border: 1px solid var(--border-subtle); padding: 12px; border-radius: 6px; font-family: var(--font-mono); font-size: 12px;">
          <pre><code>${this.escapeHtml(JSON.stringify(this.dictionaryData, null, 2))}</code></pre>
        </div>
      `;
      return;
    }

    let html = `
      <h2 class="display-serif">Personal Dictionary & Homophones</h2>
      <p style="color: var(--text-secondary); margin-bottom: 16px;">Spoken phrases automatically mapped to technical identifiers before rendering.</p>

      <div class="dict-entries-list">
    `;

    Object.keys(this.dictionaryData).forEach((spoken) => {
      const replacement = this.dictionaryData[spoken];
      html += `
        <div class="dict-entry-row">
          <div>
            <span class="dict-from">"${spoken}"</span>
            <span class="dict-arrow">→</span>
            <span class="dict-to">${replacement}</span>
          </div>
          <button class="artifact-tool-btn icon-only del-term-btn" data-term="${spoken}" title="Delete term" style="border: none; color: var(--text-tertiary);">✕</button>
        </div>
      `;
    });

    html += `
      </div>

      <form class="dict-add-form" id="dictAddForm">
        <input type="text" class="dict-input" id="dictSpokenInput" placeholder="spoken (e.g. fast api)" required />
        <input type="text" class="dict-input" id="dictReplaceInput" placeholder="replacement (e.g. FastAPI)" required />
        <button type="submit" class="dict-add-btn">+ Add Term</button>
      </form>
    `;

    this.artifactContentBody.innerHTML = html;

    // Wire Add Form
    const form = this.artifactContentBody.querySelector("#dictAddForm");
    form?.addEventListener("submit", (e) => {
      e.preventDefault();
      const s = form.querySelector("#dictSpokenInput").value.trim().toLowerCase();
      const r = form.querySelector("#dictReplaceInput").value.trim();
      if (s && r) {
        this.dictionaryData[s] = r;
        this.saveDictionaryTerm(s, r);
        this.renderDictionaryContent();
      }
    });

    // Wire Delete Buttons
    this.artifactContentBody.querySelectorAll(".del-term-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const term = btn.getAttribute("data-term");
        delete this.dictionaryData[term];
        this.renderDictionaryContent();
      });
    });
  }

  async saveDictionaryTerm(spoken, replacement) {
    try {
      const formData = new FormData();
      formData.append("spoken", spoken);
      formData.append("replacement", replacement);
      await fetch("/api/dictionary/add", { method: "POST", body: formData });
    } catch (e) {
      console.warn("Could not save dictionary term:", e);
    }
  }

  copyDictionary() {
    navigator.clipboard.writeText(JSON.stringify(this.dictionaryData, null, 2));
  }

  copyArtifactData() {
    if (this.currentArtifactType === "settings") {
      const settingsPayload = {
        active_engine: this.activeEngineId,
        correction_strength: this.correctionStrength,
        air_gap_local_only: this.localOnly,
        audio_input_device: this.selectedAudioDeviceId,
        bridge_target: "http://localhost:8099"
      };
      navigator.clipboard.writeText(JSON.stringify(settingsPayload, null, 2));
    } else {
      this.copyDictionary();
    }
    const orig = this.btnArtifactCopy.innerHTML;
    this.btnArtifactCopy.innerHTML = `<span>✔ Copied</span>`;
    setTimeout(() => { this.btnArtifactCopy.innerHTML = orig; }, 1500);
  }

  // ==========================================
  // SIDEBAR RECENT SESSIONS & SUGGESTIONS
  // ==========================================

  loadRecentSessions() {
    const recents = [
      { app: "💻 VS Code", title: "FastAPI Auth Implementation", time: "10m ago" },
      { app: "💬 Slack", title: "Engineering Swarm Update", time: "1h ago" },
      { app: "✉️ Gmail", title: "Weekly Sprint Status Sign-off", time: "3h ago" }
    ];

    if (!this.sidebarRecentList) return;
    this.sidebarRecentList.innerHTML = "";

    recents.forEach((r) => {
      const row = document.createElement("div");
      row.className = "sidebar-row";
      row.innerHTML = `
        <span style="font-size: 11px;">${r.app.split(" ")[0]}</span>
        <span class="sidebar-row-label">${r.title}</span>
      `;
      this.sidebarRecentList.appendChild(row);
    });
  }

  async loadSuggestions() {
    if (!this.suggestionsChipsRow) return;
    const suggestions = ["FastAPI", "pytest", "Docker", "PostgreSQL"];
    this.suggestionsChipsRow.innerHTML = "";

    suggestions.forEach((term) => {
      const chip = document.createElement("button");
      chip.className = "coral-chip";
      chip.style.border = "none";
      chip.style.cursor = "pointer";
      chip.innerText = `+ ${term}`;
      chip.addEventListener("click", () => {
        this.openDictionaryArtifact();
      });
      this.suggestionsChipsRow.appendChild(chip);
    });
  }

  toggleSwarmBridge() {
    this.swarmArmed = !this.swarmArmed;
    this.bridgeToggleBtn.classList.toggle("active", this.swarmArmed);
    this.bridgeToggleBtn.querySelector("span").innerText = this.swarmArmed ? "Swarm Bridge: Armed" : "Swarm: Disarmed";
  }

  // ==========================================
  // COMMAND PALETTE
  // ==========================================

  openPalette() {
    this.paletteOverlay.classList.add("open");
    this.paletteSearchInput.value = "";
    this.paletteSearchInput.focus();
  }

  closePalette() {
    this.paletteOverlay.classList.remove("open");
  }

  handlePaletteAction(action, val) {
    if (action === "set-tone" && val) {
      this.activeTone = val;
      this.currentToneLabel.innerText = `Tone: ${val.charAt(0).toUpperCase() + val.slice(1)}`;
      this.toneSwitcher?.querySelectorAll(".tone-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.getAttribute("data-tone") === val);
      });
    } else if (action === "open-dictionary") {
      this.openDictionaryArtifact();
    } else if (action === "insert-snippet") {
      this.commitTranscriptTurn(`Snippet Expansion [${val}]`);
    } else if (action === "toggle-local-only") {
      this.localOnly = !this.localOnly;
      this.currentEgressLabel.innerText = this.localOnly ? "0 bytes egress (Air-Gapped)" : "Cloud Fallback Allowed";
    }
    this.closePalette();
  }

  escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.echoScribeApp = new EchoScribeApp();
});
