/**
 * EchoScribe - Frontend Client Controller
 */
document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const engineLabel = document.getElementById("engineLabel");
  const dictCountLabel = document.getElementById("dictCountLabel");
  const micBtn = document.getElementById("micBtn");
  const recordingLabel = document.getElementById("recordingLabel");
  const transcriptOutput = document.getElementById("transcriptOutput");
  const latencyBadge = document.getElementById("latencyBadge");
  const replacementsFeed = document.getElementById("replacementsFeed");
  const copyTranscriptBtn = document.getElementById("copyTranscriptBtn");
  const audioFileInput = document.getElementById("audioFileInput");
  const dropzone = document.getElementById("dropzone");
  const visualizerCanvas = document.getElementById("visualizerCanvas");

  // Dictionary Tab Elements
  const dictTableBody = document.getElementById("dictTableBody");
  const newPhraseInput = document.getElementById("newPhraseInput");
  const newReplacementInput = document.getElementById("newReplacementInput");
  const addWordBtn = document.getElementById("addWordBtn");
  const dictSearchInput = document.getElementById("dictSearchInput");

  // Rule Test Elements
  const testInputText = document.getElementById("testInputText");
  const runRuleTestBtn = document.getElementById("runRuleTestBtn");
  const testResultOutput = document.getElementById("testResultOutput");

  // Audio Recording State
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;
  let audioContext = null;
  let analyser = null;
  let animFrameId = null;

  // Tab Switching
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const targetPane = document.getElementById(btn.dataset.tab);
      if (targetPane) targetPane.classList.add("active");
    });
  });

  // Fetch Status
  async function fetchStatus() {
    try {
      const res = await fetch("/api/status");
      if (res.ok) {
        const data = await res.json();
        engineLabel.textContent = `Engine: ${data.active_engine}`;
        dictCountLabel.textContent = `${data.dictionary_word_count} Words`;
      }
    } catch (e) {
      engineLabel.textContent = "Engine: Offline";
    }
  }

  // Load Dictionary Words
  let cachedDictionary = {};
  async function loadDictionary() {
    try {
      const res = await fetch("/api/dictionary");
      if (res.ok) {
        const data = await res.json();
        cachedDictionary = data.words || {};
        renderDictionaryTable();
        dictCountLabel.textContent = `${data.count || 0} Words`;
      }
    } catch (e) {
      console.error("Failed to load dictionary", e);
    }
  }

  function renderDictionaryTable() {
    const filter = dictSearchInput ? dictSearchInput.value.toLowerCase().trim() : "";
    dictTableBody.innerHTML = "";

    const entries = Object.entries(cachedDictionary).sort(([a], [b]) => a.localeCompare(b));
    let matchCount = 0;

    entries.forEach(([phrase, replacement]) => {
      if (filter && !phrase.includes(filter) && !replacement.toLowerCase().includes(filter)) {
        return;
      }
      matchCount++;
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(phrase)}</td>
        <td>${escapeHtml(replacement)}</td>
        <td>
          <button class="btn btn-danger-sm delete-word-btn" data-phrase="${escapeHtml(phrase)}">Delete</button>
        </td>
      `;
      dictTableBody.appendChild(tr);
    });

    if (matchCount === 0) {
      dictTableBody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No dictionary words found</td></tr>`;
    }

    // Attach delete listeners
    document.querySelectorAll(".delete-word-btn").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        const phrase = e.target.dataset.phrase;
        if (confirm(`Remove "${phrase}" from dictionary?`)) {
          await deleteWord(phrase);
        }
      });
    });
  }

  // Add Word Handler
  addWordBtn.addEventListener("click", async () => {
    const phrase = newPhraseInput.value.trim();
    const replacement = newReplacementInput.value.trim();
    if (!phrase || !replacement) {
      alert("Please specify both the spoken phrase and replacement.");
      return;
    }

    try {
      const res = await fetch("/api/dictionary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phrase, replacement }),
      });
      if (res.ok) {
        newPhraseInput.value = "";
        newReplacementInput.value = "";
        await loadDictionary();
      }
    } catch (e) {
      alert("Failed to add dictionary word");
    }
  });

  async function deleteWord(phrase) {
    try {
      const res = await fetch(`/api/dictionary/${encodeURIComponent(phrase)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        await loadDictionary();
      }
    } catch (e) {
      console.error("Delete failed", e);
    }
  }

  if (dictSearchInput) {
    dictSearchInput.addEventListener("input", renderDictionaryTable);
  }

  // Test Rules Live
  runRuleTestBtn.addEventListener("click", async () => {
    const text = testInputText.value.trim();
    if (!text) return;
    try {
      const res = await fetch("/api/dictionary/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (res.ok) {
        const data = await res.json();
        testResultOutput.textContent = data.corrected;
      }
    } catch (e) {
      testResultOutput.textContent = "Error running rules";
    }
  });

  // Audio Visualizer Setup
  function startVisualizer(stream) {
    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(stream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 64;
      source.connect(analyser);

      const canvasCtx = visualizerCanvas.getContext("2d");
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      function draw() {
        if (!isRecording) {
          canvasCtx.clearRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
          return;
        }
        animFrameId = requestAnimationFrame(draw);
        analyser.getByteFrequencyData(dataArray);

        canvasCtx.fillStyle = "#0a0c14";
        canvasCtx.fillRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);

        const barWidth = (visualizerCanvas.width / bufferLength) * 1.5;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          const barHeight = (dataArray[i] / 255) * visualizerCanvas.height;
          const gradient = canvasCtx.createLinearGradient(0, visualizerCanvas.height, 0, 0);
          gradient.addColorStop(0, "#06b6d4");
          gradient.addColorStop(1, "#8b5cf6");

          canvasCtx.fillStyle = gradient;
          canvasCtx.fillRect(x, visualizerCanvas.height - barHeight, barWidth - 2, barHeight);
          x += barWidth;
        }
      }
      draw();
    } catch (e) {
      console.warn("Visualizer init skipped:", e);
    }
  }

  // Audio Recording Flow
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
      micBtn.classList.add("recording");
      recordingLabel.textContent = "Listening... Click to Finish";
      startVisualizer(stream);
    } catch (e) {
      console.error("Mic access denied or error", e);
      alert("Microphone access is required for live dictation.");
    }
  }

  function stopRecording() {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      isRecording = false;
      micBtn.classList.remove("recording");
      recordingLabel.textContent = "Processing Audio...";
      if (animFrameId) cancelAnimationFrame(animFrameId);
    }
  }

  micBtn.addEventListener("click", () => {
    if (!isRecording) {
      startRecording();
    } else {
      stopRecording();
    }
  });

  // File Upload
  audioFileInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (file) {
      recordingLabel.textContent = `Transcribing ${file.name}...`;
      await sendAudioBlob(file);
      audioFileInput.value = "";
    }
  });

  // Send Audio Payload
  async function sendAudioBlob(blob) {
    const formData = new FormData();
    formData.append("file", blob, "recording.wav");
    formData.append("apply_dictionary", "true");

    try {
      const startTime = performance.now();
      const res = await fetch("/api/transcribe", {
        method: "POST",
        body: formData,
      });

      const clientLatency = Math.round(performance.now() - startTime);

      if (res.ok) {
        const data = await res.json();
        displayTranscript(data, clientLatency);
        recordingLabel.textContent = "Ready to Dictate";
      } else {
        transcriptOutput.textContent = "Transcription error occurred.";
        recordingLabel.textContent = "Error. Click to retry.";
      }
    } catch (e) {
      transcriptOutput.textContent = "Network error connecting to EchoScribe server.";
      recordingLabel.textContent = "Connection Error";
    }
  }

  function displayTranscript(data, fallbackLatency) {
    transcriptOutput.classList.remove("placeholder-text");
    transcriptOutput.textContent = data.transcript || "No speech detected.";
    latencyBadge.textContent = `${data.latency_ms || fallbackLatency} ms (${data.engine || "auto"})`;

    // Render replacement tags
    replacementsFeed.innerHTML = "";
    if (data.replacements && data.replacements.length > 0) {
      data.replacements.forEach((rep) => {
        const span = document.createElement("span");
        span.className = "rep-tag";
        span.textContent = `✓ ${rep.from} ➔ ${rep.to}`;
        replacementsFeed.appendChild(span);
      });
    }
  }

  // Copy to clipboard
  copyTranscriptBtn.addEventListener("click", () => {
    const text = transcriptOutput.textContent.trim();
    if (text && !transcriptOutput.classList.contains("placeholder-text")) {
      navigator.clipboard.writeText(text);
      copyTranscriptBtn.textContent = "✓";
      setTimeout(() => (copyTranscriptBtn.textContent = "📋"), 1500);
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

  // Initialization
  fetchStatus();
  loadDictionary();
  setInterval(fetchStatus, 8000);
});
