"""FastAPI Background Server for EchoScribe.

Provides REST and WebSocket endpoints for audio transcription,
dictionary correction, and background flow orchestration.
"""
import os
import json
import time
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .config import STATIC_DIR, HOST, PORT, HISTORY_FILE
from .dictionary import CorrectionDictionary
from .transcriber import TranscriberEngine
from .audio_capture import AudioCapture

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("echoscribe.server")

app = FastAPI(
    title="EchoScribe API",
    version="1.0.0",
    description="On-device audio transcription, dictation, and developer correction dictionary service.",
)

# Enable CORS for local cross-app connectivity (e.g. cli-workflow, desktop apps, web UIs)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core singletons
dictionary = CorrectionDictionary()
transcriber = TranscriberEngine()
audio_capture = AudioCapture()

# In-memory history buffer (persisted periodically)
history_log: List[Dict[str, Any]] = []
MAX_HISTORY = 50


class WordRequest(BaseModel):
    phrase: str
    replacement: str


class TextProcessRequest(BaseModel):
    text: str


def _log_history(entry: Dict[str, Any]) -> None:
    history_log.insert(0, entry)
    if len(history_log) > MAX_HISTORY:
        history_log.pop()
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_log[:20], f, indent=2)
    except Exception as e:
        logger.debug(f"Could not persist history: {e}")


@app.get("/api/health")
@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """Return backend status, active transcription engine, and dictionary stats."""
    status_info = transcriber.get_status()
    return {
        "status": "healthy",
        "service": "EchoScribe",
        "version": "1.0.0",
        "port": PORT,
        "active_engine": status_info["active_engine"],
        "dictionary_word_count": len(dictionary.words),
        "is_recording": audio_capture.is_recording,
        "parakeet_ready": status_info["parakeet_files_found"],
        "openai_configured": status_info["openai_api_configured"],
    }


@app.post("/api/transcribe")
async def transcribe_audio(
    file: Optional[UploadFile] = File(None),
    apply_dictionary: bool = Form(True),
) -> Dict[str, Any]:
    """
    Transcribe uploaded audio file with automatic dictionary correction.
    Accepts .wav, .mp3, .webm, .m4a audio payloads.
    """
    if file is None:
        raise HTTPException(status_code=400, detail="No audio file uploaded.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 1. Transcribe speech to raw text
    stt_res = await transcriber.transcribe_audio_bytes(content, filename=file.filename or "audio.wav")
    if not stt_res.get("success"):
        return stt_res

    raw_transcript = stt_res.get("transcript", "")

    # 2. Apply dictionary post-processing
    if apply_dictionary:
        dict_res = dictionary.apply(raw_transcript)
        final_text = dict_res["corrected"]
        replacements = dict_res["replacements"]
    else:
        final_text = raw_transcript
        replacements = []

    response_payload = {
        "success": True,
        "transcript": final_text,
        "raw_transcript": raw_transcript,
        "replacements": replacements,
        "engine": stt_res.get("engine", "unknown"),
        "latency_ms": stt_res.get("latency_ms", 0),
        "timestamp": time.time(),
    }

    _log_history(response_payload)
    return response_payload


@app.post("/api/dictate/start")
async def start_dictation() -> Dict[str, Any]:
    """Start background audio capture stream."""
    started = audio_capture.start_recording()
    return {"success": started, "status": "recording"}


@app.post("/api/dictate/stop")
async def stop_dictation(apply_dictionary: bool = True) -> Dict[str, Any]:
    """Stop background audio capture and immediately transcribe the buffer."""
    audio_bytes = audio_capture.stop_recording()
    if not audio_bytes:
        return {"success": False, "error": "No audio buffer captured", "transcript": ""}

    stt_res = await transcriber.transcribe_audio_bytes(audio_bytes, filename="dictation.wav")
    raw_transcript = stt_res.get("transcript", "")

    if apply_dictionary:
        dict_res = dictionary.apply(raw_transcript)
        final_text = dict_res["corrected"]
        replacements = dict_res["replacements"]
    else:
        final_text = raw_transcript
        replacements = []

    response_payload = {
        "success": True,
        "transcript": final_text,
        "raw_transcript": raw_transcript,
        "replacements": replacements,
        "engine": stt_res.get("engine", "unknown"),
        "latency_ms": stt_res.get("latency_ms", 0),
        "timestamp": time.time(),
    }

    _log_history(response_payload)
    return response_payload


@app.post("/api/dictionary/apply")
async def apply_dictionary_to_text(req: TextProcessRequest) -> Dict[str, Any]:
    """Manually apply dictionary correction rules to an arbitrary text string."""
    return dictionary.apply(req.text)


@app.get("/api/dictionary")
async def get_dictionary() -> Dict[str, Any]:
    """List all custom dictionary words and active replacement patterns."""
    return dictionary.get_all()


@app.post("/api/dictionary")
async def add_dictionary_word(req: WordRequest) -> Dict[str, Any]:
    """Add or update a custom word mapping."""
    success = dictionary.add_word(req.phrase, req.replacement)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid phrase or replacement.")
    return {"success": True, "phrase": req.phrase, "replacement": req.replacement}


@app.delete("/api/dictionary/{phrase}")
async def delete_dictionary_word(phrase: str) -> Dict[str, Any]:
    """Delete a word mapping from the dictionary."""
    success = dictionary.remove_word(phrase)
    if not success:
        raise HTTPException(status_code=404, detail=f"Phrase '{phrase}' not found in dictionary.")
    return {"success": True, "removed": phrase}


@app.get("/api/history")
async def get_history() -> List[Dict[str, Any]]:
    """Return recent transcription history."""
    return history_log


# Serve static web interface
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"service": "EchoScribe API", "status": "running"}
