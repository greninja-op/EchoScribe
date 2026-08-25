"""FastAPI Background Server for EchoScribe.

Provides REST and WebSocket endpoints for audio transcription,
Wispr Flow-style tone formatting, 10K milestone intelligence, and snippets.
"""
import os
import json
import time
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .config import STATIC_DIR, HOST, PORT, HISTORY_FILE
from .dictionary import CorrectionDictionary
from .transcriber import TranscriberEngine
from .audio_capture import AudioCapture
from .flow_intelligence import FlowIntelligence

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("echoscribe.server")

app = FastAPI(
    title="EchoScribe API",
    version="2.0.0",
    description="Vintage Macintosh System 7 styled on-device transcription, dictation, and Wispr Flow intelligence.",
)

# Enable CORS for local cross-app connectivity
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
flow_intel = FlowIntelligence()

# In-memory history buffer
history_log: List[Dict[str, Any]] = []
MAX_HISTORY = 50


class WordRequest(BaseModel):
    phrase: str
    replacement: str
    category: str = "code"


class SnippetRequest(BaseModel):
    trigger: str
    expansion: str


class TextProcessRequest(BaseModel):
    text: str
    tone: str = "clean"
    apply_snippets: bool = True


class SimulateWordsRequest(BaseModel):
    total_words: int = 10050


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
    """Return backend status, active transcription engine, stats, and milestone rank."""
    status_info = transcriber.get_status()
    stats_summary = flow_intel.get_summary()
    return {
        "status": "healthy",
        "service": "EchoScribe",
        "version": "2.0.0",
        "port": PORT,
        "active_engine": status_info["active_engine"],
        "dictionary_word_count": len(dictionary.words),
        "snippets_count": len(dictionary.snippets),
        "is_recording": audio_capture.is_recording,
        "parakeet_ready": status_info["parakeet_files_found"],
        "openai_configured": status_info["openai_api_configured"],
        "stats": stats_summary,
    }


@app.post("/api/transcribe")
async def transcribe_audio(
    file: Optional[UploadFile] = File(None),
    apply_dictionary: bool = Form(True),
    tone: str = Form("clean"),
    apply_snippets: bool = Form(True),
) -> Dict[str, Any]:
    """
    Transcribe uploaded audio file with automatic dictionary correction,
    tone styling (clean/professional/casual/code/bullets/raw), and snippet expansion.
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

    # 2. Apply dictionary & tone formatting
    if apply_dictionary:
        dict_res = dictionary.apply(raw_transcript, tone=tone, apply_snippets=apply_snippets)
        final_text = dict_res["corrected"]
        replacements = dict_res["replacements"]
    else:
        final_text = raw_transcript
        replacements = []

    # 3. Apply 10K Auto-Intent Reasoning
    intent_prediction = flow_intel.predict_and_adapt_intent(final_text)

    # 4. Record to statistics
    flow_intel.add_transcription(final_text, latency_ms=stt_res.get("latency_ms", 0))

    response_payload = {
        "success": True,
        "transcript": final_text,
        "raw_transcript": raw_transcript,
        "replacements": replacements,
        "tone": tone,
        "engine": stt_res.get("engine", "unknown"),
        "latency_ms": stt_res.get("latency_ms", 0),
        "intent_prediction": intent_prediction,
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
async def stop_dictation(
    apply_dictionary: bool = True,
    tone: str = "clean",
    apply_snippets: bool = True,
) -> Dict[str, Any]:
    """Stop background audio capture and immediately transcribe the buffer."""
    audio_bytes = audio_capture.stop_recording()
    if not audio_bytes:
        return {"success": False, "error": "No audio buffer captured", "transcript": ""}

    stt_res = await transcriber.transcribe_audio_bytes(audio_bytes, filename="dictation.wav")
    raw_transcript = stt_res.get("transcript", "")

    if apply_dictionary:
        dict_res = dictionary.apply(raw_transcript, tone=tone, apply_snippets=apply_snippets)
        final_text = dict_res["corrected"]
        replacements = dict_res["replacements"]
    else:
        final_text = raw_transcript
        replacements = []

    intent_prediction = flow_intel.predict_and_adapt_intent(final_text)
    flow_intel.add_transcription(final_text, latency_ms=stt_res.get("latency_ms", 0))

    response_payload = {
        "success": True,
        "transcript": final_text,
        "raw_transcript": raw_transcript,
        "replacements": replacements,
        "tone": tone,
        "engine": stt_res.get("engine", "unknown"),
        "latency_ms": stt_res.get("latency_ms", 0),
        "intent_prediction": intent_prediction,
        "timestamp": time.time(),
    }

    _log_history(response_payload)
    return response_payload


@app.post("/api/dictionary/apply")
async def apply_dictionary_to_text(req: TextProcessRequest) -> Dict[str, Any]:
    """Manually apply dictionary correction, tone styling, and snippets to a text string."""
    dict_res = dictionary.apply(req.text, tone=req.tone, apply_snippets=req.apply_snippets)
    intent_res = flow_intel.predict_and_adapt_intent(dict_res["corrected"])
    dict_res["intent_prediction"] = intent_res
    return dict_res


@app.get("/api/dictionary")
async def get_dictionary() -> Dict[str, Any]:
    """List all custom dictionary words, category breakdown, and patterns."""
    return dictionary.get_all()


@app.post("/api/dictionary")
async def add_dictionary_word(req: WordRequest) -> Dict[str, Any]:
    """Add or update a custom word mapping."""
    success = dictionary.add_word(req.phrase, req.replacement, category=req.category)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid phrase or replacement.")
    return {"success": True, "phrase": req.phrase, "replacement": req.replacement, "category": req.category}


@app.delete("/api/dictionary/{phrase}")
async def delete_dictionary_word(phrase: str) -> Dict[str, Any]:
    """Delete a word mapping from the dictionary."""
    success = dictionary.remove_word(phrase)
    if not success:
        raise HTTPException(status_code=404, detail=f"Phrase '{phrase}' not found in dictionary.")
    return {"success": True, "removed": phrase}


@app.get("/api/snippets")
async def get_snippets() -> Dict[str, str]:
    """Return all voice/text snippets."""
    return dictionary.snippets


@app.post("/api/snippets")
async def add_snippet(req: SnippetRequest) -> Dict[str, Any]:
    """Add a snippet shortcut."""
    success = dictionary.add_snippet(req.trigger, req.expansion)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add snippet.")
    return {"success": True, "trigger": req.trigger, "expansion": req.expansion}


@app.delete("/api/snippets/{trigger}")
async def delete_snippet(trigger: str) -> Dict[str, Any]:
    """Remove a snippet shortcut."""
    success = dictionary.remove_snippet(trigger)
    if not success:
        raise HTTPException(status_code=404, detail=f"Snippet '{trigger}' not found.")
    return {"success": True, "removed": trigger}


@app.get("/api/stats")
@app.get("/api/milestones")
async def get_stats_and_milestones() -> Dict[str, Any]:
    """Return word counts, WPM, time saved, and 10K milestone progress."""
    return flow_intel.get_summary()


@app.post("/api/milestones/simulate-10k")
async def simulate_10k_milestone(req: SimulateWordsRequest = SimulateWordsRequest()) -> Dict[str, Any]:
    """Simulate crossing the 10,000 words milestone for instant feature verification."""
    summary = flow_intel.set_words(req.total_words)
    return {
        "success": True,
        "message": f"Total words updated to {req.total_words}. 10K Auto-Intent reasoning active!",
        "stats": summary,
    }


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
