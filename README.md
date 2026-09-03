# Kelvra Voice 🎙️

**On-device Audio Transcription, Continuous Dictation & Developer Correction Dictionary Engine**

Kelvra Voice (formerly EchoScribe) is a high-performance, background speech-to-text service designed for developers and workflow tools (such as `kelvra-bench`). It bridges on-device neural transcription (Windows Local Whisper / macOS Native Speech / Model-API) with a programmable domain correction dictionary backed by embedded SQLite with FTS5 search.

---

## Features

- **⚡ Blazing Fast On-Device Transcription**: Multi-engine transcription architecture supporting Windows Local Whisper, macOS Native Speech, and Model/API with zero network egress in Air-Gap mode.
- **📖 Embedded SQLite Correction Dictionary**: Self-learning technical dictionary storing term frequencies, homophone replacements, and fast FTS5 full-text transcript search.
- **🔤 Voice Casing Macros**: Dictate casing in real time (`camelCase`, `snake_case`, `kebab-case`).
- **🌐 Universal REST API**: Background service running on `http://localhost:8765` connects directly to `kelvra-bench` (port 8099).
- **🖥️ Live HUD Dashboard**: Interactive Claude.ai-styled interface with pulsing audio-reactive mic, pause/resume toggle, and dedicated settings view.

---

## Quickstart

### 1. Installation
```powershell
pip install -r requirements.txt
```

### 2. Start Service
```powershell
# Windows Batch
run.bat

# Or Python directly
python main.py
```
* The service starts at **`http://localhost:8765`**
* Interactive Swagger API documentation: **`http://localhost:8765/docs`**

---

## (Optional) On-Device Parakeet STT Model Setup

EchoScribe works out of the box with intelligent local simulation or OpenAI Whisper API. To enable full on-device NVIDIA Parakeet inference without sending audio to the cloud:

1. Install `sherpa-onnx`:
   ```powershell
   pip install sherpa-onnx soundfile
   ```

2. Download the int8 Parakeet weights (approx. 661 MB):
   ```powershell
   $dir = "$env:LOCALAPPDATA\Murmur\models\parakeet-v2"
   $base = "https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/resolve/main"
   New-Item -ItemType Directory -Force $dir | Out-Null
   foreach ($f in "encoder.int8.onnx","decoder.int8.onnx","joiner.int8.onnx","tokens.txt") {
       curl.exe -L --fail --progress-bar -o "$dir\$f" "$base/$f"
   }
   ```

---

## API Reference

### Transcribe Audio
`POST /api/transcribe`
- **Body**: `multipart/form-data` with `file=@recording.wav`
- **Response**:
```json
{
  "success": true,
  "transcript": "Create a FastAPI router with async/await and push to GitHub",
  "raw_transcript": "create a fast api router with async await and push to git hub",
  "replacements": [
    { "from": "fast api", "to": "FastAPI", "type": "dictionary" },
    { "from": "async await", "to": "async/await", "type": "dictionary" },
    { "from": "git hub", "to": "GitHub", "type": "dictionary" }
  ],
  "engine": "parakeet-sherpa-onnx",
  "latency_ms": 145
}
```

### Dictionary Endpoints
- `GET /api/dictionary` - List all active word mappings.
- `POST /api/dictionary` - Add custom word mapping (`{"phrase": "supa base", "replacement": "Supabase"}`).
- `DELETE /api/dictionary/{phrase}` - Remove a mapping.
- `POST /api/dictionary/apply` - Test rules against raw text (`{"text": "my spoken text"}`).

---

## Connecting from External Apps (e.g. Python)

```python
import httpx

async def transcribe_speech(audio_bytes: bytes) -> str:
    async with httpx.AsyncClient(timeout=15.0) as client:
        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        res = await client.post("http://localhost:8765/api/transcribe", files=files)
        data = res.json()
        return data.get("transcript", "")
```

---

## Monorepo Multi-Remote Pushing

EchoScribe is integrated into the planning repository and mirrors to its dedicated repository:
* **Standalone Repo**: `https://github.com/greninja-op/EchoScribe.git`
* **Push Command**:
  ```powershell
  ./scripts/push.ps1 -m "Update EchoScribe dictionary and models"
  ```
