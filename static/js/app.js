/**
 * EchoScribe System 7 - Vintage Macintosh Pop OS Controller & Wispr Flow Engine
 */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentTone = "clean";
  let isContinuousMode = false;
  let isRecording = false;
  let mediaRecorder = null;
  let audioChunks = [];
  let audioContext = null;
  let analyser = null;
  let animFrameId = null;
  let cachedDictionary = {};
  let cachedSnippets = {};
  let cachedStats = {};

  // DOM Elements - Menubar
  const macClock = document.getElementById("macClock");
  const topTierLabel = document.getElementById("topTierLabel");
  const top10kBadge = document.getElementById("top10kBadge");
  const topEngineLabel = document.getElementById("topEngineLabel");

  // DOM Elements - Dictation Window
  const modePushBtn = document.getElementById("modePushBtn");
  const modeContBtn = document.getElementById("modeContBtn");
  const sessionStatusPill = document.getElementById("sessionStatusPill");
  const mainRecordBtn = document.getElementById("mainRecordBtn");
  const recordBtnLabel = document.getElementById("recordBtnLabel");
  const oscilloscopeCanvas = document.getElementById("oscilloscopeCanvas");
  const audioFileInput = document.getElementById("audioFileInput");
  const transcriptScreen = document.getElementById("transcriptScreen");
  const latencyTag = document.getElementById("latencyTag");
  const toneTag = document.getElementById("toneTag");
  const copyBtn = document.getElementById("copyBtn");
  const replacementsFeed = document.getElementById("replacementsFeed");

  // DOM Elements - Milestones Window
  const totalWordsCount = document.getElementById("totalWordsCount");
  const nextGoalLabel = document.getElementById("nextGoalLabel");
  const milestoneBarFill = document.getElementById("milestoneBarFill");
  const milestonePctText = document.getElementById("milestonePctText");
  const simulate10kBtn = document.getElementById("simulate10kBtn");
  const intentBadge = document.getElementById("intentBadge");
  const intentReasoningText = document.getElementById("intentReasoningText");

  // DOM Elements - Dictionary & Snippets Window
  const dictTabCount = document.getElementById("dictTabCount");
  const snippetTabCount = document.getElementById("snippetTabCount");
  const dictTableBody = document.getElementById("dictTableBody");
  const snippetTableBody = document.getElementById("snippetTableBody");
  const dictSearch = document.getElementById("dictSearch");
  const newPhrase = document.getElementById("newPhrase");
  const newReplacement = document.getElementById("newReplacement");
  const newCategory = document.getElementById("newCategory");
  const addWordBtn = document.getElementById("addWordBtn");
  const newSnippetTrigger = document.getElementById("newSnippetTrigger");
  const newSnippetExpansion = document.getElementById("newSnippetExpansion");
  const addSnippetBtn = document.getElementById("addSnippetBtn");
  const ruleTestInput = document.getElementById("ruleTestInput");
  const runPlaygroundBtn = document.getElementById("runPlaygroundBtn");
  const playgroundOutput = document.getElementById("playgroundOutput");

  // DOM Elements - Analytics
  const statWpm = document.getElementById("statWpm");
  const statHours = document.getElementById("statHours");
  const statStreak = document.getElementById("statStreak");

  // 1. Clock
  function updateClock() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    if (macClock) macClock.textContent = timeStr;
  }
  setInterval(updateClock, 1000);
  updateClock();

  // 2. Window Stacking & Focus
  window.focusWindow = (winId) => {
    const win = document.getElementById(winId);
    if (!win) return;
    document.querySelectorAll(".mac-window").forEach((w) => (w.style.zIndex = "10"));
    win.style.zIndex = "20";
    win.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  // 3. Tone Selector
  document.querySelectorAll(".tone-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tone-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentTone = btn.dataset.tone;
      if (toneTag) toneTag.textContent = `Tone: ${btn.textContent.trim()}`;
    });
  });

  // 4. Mode Switching
  modePushBtn.addEventListener("click", () => {
    isContinuousMode = false;
    modePushBtn.classList.add("active", "mac-btn-cyan");
    modeContBtn.classList.remove("active", "mac-btn-cyan");
    recordBtnLabel.textContent = "HOLD SPACE OR CLICK TO DICTATE";
    sessionStatusPill.textContent = "Push-To-Talk";
    sessionStatusPill.className = "mac-tag mac-tag-green";
  });

  modeContBtn.addEventListener("click", () => {
    isContinuousMode = true;
    modeContBtn.classList.add("active", "mac-btn-cyan");
    modePushBtn.classList.remove("active", "mac-btn-cyan");
    recordBtnLabel.textContent = "CLICK TO START MEETING MODE";
    sessionStatusPill.textContent = "Continuous Mode";
    sessionStatusPill.className = "mac-tag mac-tag-pink";
  });

  // 5. Retro Phosphor Oscilloscope Visualizer
  function startOscilloscope(stream) {
    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(stream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      const canvasCtx = oscilloscopeCanvas.getContext("2d");
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      function drawOscilloscope() {
        if (!isRecording) {
          canvasCtx.fillStyle = "#050807";
          canvasCtx.fillRect(0, 0, oscilloscopeCanvas.width, oscilloscopeCanvas.height);
          // Draw center resting phosphor line
          canvasCtx.strokeStyle = "#48c6ff";
          canvasCtx.lineWidth = 1.5;
          canvasCtx.beginPath();
          canvasCtx.moveTo(0, oscilloscopeCanvas.height / 2);
          canvasCtx.lineTo(oscilloscopeCanvas.width, oscilloscopeCanvas.height / 2);
          canvasCtx.stroke();
          return;
        }

        animFrameId = requestAnimationFrame(drawOscilloscope);
        analyser.getByteTimeDomainData(dataArray);

        canvasCtx.fillStyle = "#050807";
        canvasCtx.fillRect(0, 0, oscilloscopeCanvas.width, oscilloscopeCanvas.height);

        canvasCtx.lineWidth = 2;
        canvasCtx.strokeStyle = "#9ee635";
        canvasCtx.shadowBlur = 8;
        canvasCtx.shadowColor = "#9ee635";

        canvasCtx.beginPath();
        const sliceWidth = (oscilloscopeCanvas.width * 1.0) / bufferLength;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          const v = dataArray[i] / 128.0;
          const y = (v * oscilloscopeCanvas.height) / 2;

          if (i === 0) canvasCtx.moveTo(x, y);
          else canvasCtx.lineTo(x, y);

          x += sliceWidth;
        }

        canvasCtx.lineTo(oscilloscopeCanvas.width, oscilloscopeCanvas.height / 2);
        canvasCtx.stroke();
        canvasCtx.shadowBlur = 0;
      }
      drawOscilloscope();
    } catch (e) {
      console.warn("Oscilloscope canvas error:", e);
    }
  }

  // 6. Recording Engine
  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunks = [];
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
        await sendAudioBlob(audioBlob);
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorder.start();
      isRecording = true;
      mainRecordBtn.classList.add("recording");
      recordBtnLabel.textContent = "DICTATING... RELEASE / CLICK TO FINISH";
      sessionStatusPill.textContent = "Listening";
      sessionStatusPill.className = "mac-tag mac-tag-pink";
      startOscilloscope(stream);
    } catch (e) {
      alert("Microphone permission required for dictation.");
    }
  }

  function stopRecording() {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      isRecording = false;
      mainRecordBtn.classList.remove("recording");
      recordBtnLabel.textContent = isContinuousMode ? "CLICK TO START MEETING MODE" : "HOLD SPACE OR CLICK TO DICTATE";
      sessionStatusPill.textContent = "Processing Speech...";
      sessionStatusPill.className = "mac-tag mac-tag-yellow";
      if (animFrameId) cancelAnimationFrame(animFrameId);
    }
  }

  mainRecordBtn.addEventListener("click", () => {
    if (!isRecording) startRecording();
    else stopRecording();
  });

  // Spacebar push-to-talk (when not in text input)
  window.addEventListener("keydown", (e) => {
    if (e.code === "Space" && !isRecording && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
      e.preventDefault();
      startRecording();
    }
  });

  window.addEventListener("keyup", (e) => {
    if (e.code === "Space" && isRecording && !isContinuousMode && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
      e.preventDefault();
      stopRecording();
    }
  });

  // Audio File Upload
  audioFileInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (file) {
      sessionStatusPill.textContent = `Transcribing ${file.name}...`;
      sessionStatusPill.className = "mac-tag mac-tag-yellow";
      await sendAudioBlob(file);
      audioFileInput.value = "";
    }
  });

  // 7. Send Audio to EchoScribe Server
  async function sendAudioBlob(blob) {
    const formData = new FormData();
    formData.append("file", blob, "speech.wav");
    formData.append("apply_dictionary", "true");
    formData.append("tone", currentTone);
    formData.append("apply_snippets", "true");

    try {
      const startTime = performance.now();
      const res = await fetch("/api/transcribe", { method: "POST", body: formData });
      const clientLatency = Math.round(performance.now() - startTime);

      if (res.ok) {
        const data = await res.json();
        renderTranscript(data, clientLatency);
        sessionStatusPill.textContent = "Completed";
        sessionStatusPill.className = "mac-tag mac-tag-green";
        await fetchStatsAndMilestones();
      } else {
        transcriptScreen.textContent = "Transcription error occurred.";
        sessionStatusPill.textContent = "Error";
        sessionStatusPill.className = "mac-tag mac-tag-pink";
      }
    } catch (e) {
      transcriptScreen.textContent = "Network error connecting to EchoScribe.";
      sessionStatusPill.textContent = "Offline";
    }
  }

  function renderTranscript(data, fallbackLatency) {
    transcriptScreen.classList.remove("placeholder");
    transcriptScreen.textContent = data.transcript || "No words recognized.";
    latencyTag.textContent = `⚡ Latency: ${data.latency_ms || fallbackLatency} ms`;

    // Render Replacements Tags
    replacementsFeed.innerHTML = "";
    if (data.replacements && data.replacements.length > 0) {
      data.replacements.forEach((rep) => {
        const tag = document.createElement("span");
        tag.className = rep.type === "snippet" ? "mac-tag mac-tag-yellow" : "mac-tag mac-tag-green";
        tag.textContent = `✓ ${rep.from} ➔ ${rep.to}`;
        replacementsFeed.appendChild(tag);
      });
    }

    // Render 10K Intent Reasoning
    if (data.intent_prediction) {
      renderIntentCard(data.intent_prediction);
    }
  }

  // 8. Milestones & 10K Adaptive Intent Rendering
  async function fetchStatsAndMilestones() {
    try {
      const res = await fetch("/api/milestones");
      if (res.ok) {
        const stats = await res.json();
        cachedStats = stats;
        renderMilestoneUI(stats);
      }
    } catch (e) {
      console.warn("Could not fetch milestones", e);
    }
  }

  function renderMilestoneUI(stats) {
    if (totalWordsCount) totalWordsCount.textContent = stats.total_words.toLocaleString();
    if (nextGoalLabel) {
      nextGoalLabel.textContent = stats.next_tier
        ? `Goal: ${stats.next_tier.threshold.toLocaleString()} (${stats.next_tier.name.split(" ")[1] || stats.next_tier.name})`
        : "Max Milestone Achieved!";
    }

    if (milestoneBarFill) milestoneBarFill.style.width = `${stats.progress_pct}%`;
    if (milestonePctText) milestonePctText.textContent = `${stats.progress_pct}% to Next Tier`;

    if (statWpm) statWpm.textContent = stats.wpm;
    if (statHours) statHours.textContent = `${stats.time_saved_hours}h`;
    if (statStreak) statStreak.textContent = `${stats.streak_days} 🔥`;

    // Tier Cards
    ["bronze", "silver", "gold", "platinum"].forEach((tierId) => {
      const el = document.getElementById(`tier-${tierId}`);
      if (!el) return;
      const threshold = tierId === "bronze" ? 1000 : tierId === "silver" ? 5000 : tierId === "gold" ? 10000 : 25000;
      if (stats.total_words >= threshold) {
        el.classList.add("unlocked");
      } else {
        el.classList.remove("unlocked");
      }
    });

    // 10K Intent Badge & Status
    if (stats.is_10k_unlocked) {
      top10kBadge.classList.add("unlocked-10k");
      topTierLabel.textContent = "Tier: 10K Gold Legend";
      intentBadge.className = "intent-status-badge active";
      intentBadge.textContent = "Active (10K+ Words Unlocked)";
    } else {
      top10kBadge.classList.remove("unlocked-10k");
      topTierLabel.textContent = `Tier: ${stats.current_tier.toUpperCase()}`;
      intentBadge.className = "intent-status-badge locked";
      intentBadge.textContent = `Locked (${stats.total_words.toLocaleString()} / 10,000 Words)`;
    }
  }

  function renderIntentCard(prediction) {
    if (!prediction) return;
    if (prediction.intent_feature_active) {
      intentBadge.className = "intent-status-badge active";
      intentBadge.textContent = `Active (${prediction.inferred_intent.toUpperCase()})`;
      intentReasoningText.innerHTML = `
        <strong>Inferred Intent:</strong> <code>${prediction.inferred_intent}</code> (Confidence: ${Math.round(prediction.confidence * 100)}%)<br/>
        <strong>Voice Twin Adaptation:</strong> ${prediction.voice_twin_adaptation || "Tailored to developer terminology"}<br/>
        <strong>Actions:</strong> ${(prediction.auto_actions || []).join(", ") || "None"}
      `;
    } else {
      intentBadge.className = "intent-status-badge locked";
      intentBadge.textContent = "Locked (<10K Words)";
      intentReasoningText.textContent = prediction.reason || "Dictate 10,000 words to unlock automatic intent reasoning.";
    }
  }

  // Simulate 10K Words Button
  simulate10kBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/milestones/simulate-10k", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ total_words: 10500 }),
      });
      if (res.ok) {
        const data = await res.json();
        alert(data.message);
        renderMilestoneUI(data.stats);
      }
    } catch (e) {
      alert("Error simulating milestone");
    }
  });

  // 9. Dictionary & Snippets Tabs
  document.querySelectorAll(".mac-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".mac-tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => (c.style.display = "none"));
      btn.classList.add("active");
      const pane = document.getElementById(btn.dataset.tab);
      if (pane) pane.style.display = "flex";
    });
  });

  async function loadDictionary() {
    try {
      const res = await fetch("/api/dictionary");
      if (res.ok) {
        const data = await res.json();
        cachedDictionary = data.words_detailed || {};
        cachedSnippets = data.snippets || {};
        renderDictionaryTable();
        renderSnippetsTable();
        if (dictTabCount) dictTabCount.textContent = data.count || 0;
        if (snippetTabCount) snippetTabCount.textContent = Object.keys(cachedSnippets).length;
      }
    } catch (e) {
      console.warn("Dictionary load failed", e);
    }
  }

  function renderDictionaryTable() {
    const filter = dictSearch ? dictSearch.value.toLowerCase().trim() : "";
    dictTableBody.innerHTML = "";

    const entries = Object.entries(cachedDictionary).sort(([a], [b]) => a.localeCompare(b));
    let matches = 0;

    entries.forEach(([phrase, details]) => {
      const repl = typeof details === "object" ? details.replacement : details;
      const cat = typeof details === "object" ? details.category || "code" : "code";

      if (filter && !phrase.includes(filter) && !repl.toLowerCase().includes(filter)) return;
      matches++;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${escapeHtml(phrase)}</strong></td>
        <td style="color: #b560e8; font-family: var(--font-mono);">${escapeHtml(repl)}</td>
        <td><span class="mac-tag mac-tag-yellow">${escapeHtml(cat)}</span></td>
        <td>
          <button class="mac-btn mac-btn-danger delete-word-btn" data-phrase="${escapeHtml(phrase)}">✕</button>
        </td>
      `;
      dictTableBody.appendChild(tr);
    });

    if (matches === 0) {
      dictTableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: #888;">No dictionary words matched</td></tr>`;
    }

    document.querySelectorAll(".delete-word-btn").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        const phrase = e.target.dataset.phrase;
        if (confirm(`Delete "${phrase}" from dictionary?`)) {
          await fetch(`/api/dictionary/${encodeURIComponent(phrase)}`, { method: "DELETE" });
          await loadDictionary();
        }
      });
    });
  }

  function renderSnippetsTable() {
    snippetTableBody.innerHTML = "";
    const entries = Object.entries(cachedSnippets);
    entries.forEach(([trigger, expansion]) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><span class="mac-tag mac-tag-pink">${escapeHtml(trigger)}</span></td>
        <td style="font-family: var(--font-mono); font-size: 1.05rem;">${escapeHtml(expansion.slice(0, 45))}${expansion.length > 45 ? "..." : ""}</td>
        <td>
          <button class="mac-btn mac-btn-danger delete-snippet-btn" data-trigger="${escapeHtml(trigger)}">✕</button>
        </td>
      `;
      snippetTableBody.appendChild(tr);
    });

    document.querySelectorAll(".delete-snippet-btn").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        const trigger = e.target.dataset.trigger;
        if (confirm(`Delete snippet "${trigger}"?`)) {
          await fetch(`/api/snippets/${encodeURIComponent(trigger)}`, { method: "DELETE" });
          await loadDictionary();
        }
      });
    });
  }

  // Add Word
  addWordBtn.addEventListener("click", async () => {
    const phrase = newPhrase.value.trim();
    const replacement = newReplacement.value.trim();
    const category = newCategory.value;
    if (!phrase || !replacement) return;

    await fetch("/api/dictionary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phrase, replacement, category }),
    });
    newPhrase.value = "";
    newReplacement.value = "";
    await loadDictionary();
  });

  // Add Snippet
  addSnippetBtn.addEventListener("click", async () => {
    const trigger = newSnippetTrigger.value.trim();
    const expansion = newSnippetExpansion.value.trim();
    if (!trigger || !expansion) return;

    await fetch("/api/snippets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trigger, expansion }),
    });
    newSnippetTrigger.value = "";
    newSnippetExpansion.value = "";
    await loadDictionary();
  });

  if (dictSearch) dictSearch.addEventListener("input", renderDictionaryTable);

  // 10. Rule & Tone Playground
  runPlaygroundBtn.addEventListener("click", async () => {
    const text = ruleTestInput.value.trim();
    if (!text) return;
    try {
      const res = await fetch("/api/dictionary/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, tone: currentTone, apply_snippets: true }),
      });
      if (res.ok) {
        const data = await res.json();
        playgroundOutput.textContent = data.corrected;
      }
    } catch (e) {
      playgroundOutput.textContent = "Error evaluating rules.";
    }
  });

  // Copy Clipboard
  copyBtn.addEventListener("click", () => {
    const text = transcriptScreen.textContent.trim();
    if (text && !transcriptScreen.classList.contains("placeholder")) {
      navigator.clipboard.writeText(text);
      copyBtn.textContent = "✓ Copied!";
      setTimeout(() => (copyBtn.textContent = "📋 Copy Text"), 1500);
    }
  });

  function escapeHtml(str) {
    return (str || "").replace(/[&<>"']/g, (m) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    })[m]);
  }

  // 11. Initial Load & Background Polling
  loadDictionary();
  fetchStatsAndMilestones();
  setInterval(fetchStatsAndMilestones, 10000);
});
