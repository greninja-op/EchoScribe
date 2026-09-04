"""FastAPI Background Server for EchoScribe.

Provides REST and WebSocket endpoints for streaming audio transcription,
Wispr Flow-style tone formatting, auto-learning dictionary, in-place voice editing,
local-only privacy toggle, and direct bridge dispatch to CLI-Workflow.
"""
import os
import json
import time
import asyncio
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from .config import STATIC_DIR, HOST, PORT, HISTORY_FILE, CLI_WORKFLOW_URL, DATA_DIR, LOCAL_PIPER_DIR
from .dictionary import CorrectionDictionary
from .transcriber import TranscriberEngine
from .transcription import select_default_engine
from .audio_capture import AudioCapture
from .flow_intelligence import FlowIntelligence
from .db import db
from .tts import TTSManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("echoscribe.server")

app = FastAPI(
    title="EchoScribe API",
    version="2.1.0",
    description="High-performance streaming on-device transcription, auto-learning dictionary, and Wispr Flow intelligence.",
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
tts_manager = TTSManager(data_dir=DATA_DIR, models_dir=LOCAL_PIPER_DIR)

# In-memory history buffer
history_log: List[Dict[str, Any]] = []
MAX_HISTORY = 50
last_finalized_transcript: str = ""


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


class LocalOnlyRequest(BaseModel):
    enabled: bool = True


class SuggestionActionRequest(BaseModel):
    phrase: str
    replacement: Optional[str] = None


class BridgeDispatchRequest(BaseModel):
    transcript: str
    cli_preference: str = "auto"
    difficulty: str = "auto"


class CommandApplyRequest(BaseModel):
    selected_text: str
    instruction: str
    surrounding_context: str = ""


class FlowCorrectRequest(BaseModel):
    text: str
    context: str = ""
    app_id: str = "default"
    correction_strength: str = "full"
    prosody_hints: Optional[Dict[str, Any]] = None


class AutoAddWatcherRequest(BaseModel):
    original_inserted: str
    current_field_text: str


class EngineSelectRequest(BaseModel):
    engine_id: str


class TTSSpeakRequest(BaseModel):
    text: str
    engine: Optional[str] = None
    voice_id: Optional[str] = None


class TTSEngineSelectRequest(BaseModel):
    engine: str


class TTSVoiceSelectRequest(BaseModel):
    engine: str
    voice_id: str


class TTSPiperDownloadRequest(BaseModel):
    voice_id: str


class TTSDeepgramKeyRequest(BaseModel):
    api_key: str
    do_validate: bool = True


def _log_history(entry: Dict[str, Any]) -> None:
    global last_finalized_transcript
    last_finalized_transcript = entry.get("transcript", "")
    history_log.insert(0, entry)
    if len(history_log) > MAX_HISTORY:
        history_log.pop()
    try:
        db.log_session(entry)
    except Exception as e:
        logger.debug(f"Could not persist session to SQLite: {e}")
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
        "version": "2.1.0",
        "port": PORT,
        "active_engine": status_info["active_engine"],
        "local_only_mode": status_info["local_only_mode"],
        "network_egress_guarantee": status_info["network_egress_guarantee"],
        "dictionary_word_count": len(dictionary.words),
        "snippets_count": len(dictionary.snippets),
        "pending_suggestions_count": len(dictionary.get_suggestions()),
        "is_recording": audio_capture.is_recording,
        "parakeet_ready": status_info["parakeet_files_found"],
        "openai_configured": status_info["openai_api_configured"],
        "stats": stats_summary,
        "bridge_target": CLI_WORKFLOW_URL,
    }


@app.post("/api/config/local-only")
async def toggle_local_only(req: LocalOnlyRequest) -> Dict[str, Any]:
    """Toggle strict air-gap / local-only mode."""
    transcriber.set_local_only(req.enabled)
    return {
        "success": True,
        "local_only_mode": transcriber.local_only,
        "network_egress_guarantee": "0 bytes outbound (air-gapped)" if transcriber.local_only else "Cloud allowed",
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
    in-place voice editing intent, tone styling, and snippet expansion.
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

    # 2. Check for In-Place Voice Editing intent (e.g. 'make this shorter', 'format as bullets')
    in_place_edit = dictionary.detect_and_apply_in_place_edit(raw_transcript, last_finalized_transcript)
    if in_place_edit:
        final_text = in_place_edit["corrected"]
        replacements = in_place_edit.get("replacements", [])
        tone = in_place_edit.get("tone", tone)
    elif apply_dictionary:
        dict_res = dictionary.apply(raw_transcript, tone=tone, apply_snippets=apply_snippets)
        final_text = dict_res["corrected"]
        replacements = dict_res["replacements"]
    else:
        final_text = raw_transcript
        replacements = []

    # 3. Apply Auto-Intent Reasoning
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
        "in_place_edit_applied": bool(in_place_edit),
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

    in_place_edit = dictionary.detect_and_apply_in_place_edit(raw_transcript, last_finalized_transcript)
    if in_place_edit:
        final_text = in_place_edit["corrected"]
        replacements = in_place_edit.get("replacements", [])
        tone = in_place_edit.get("tone", tone)
    else:
        # Wispr Flow intelligence pass: self-correction, stutter removal, disfluency cleanup, structure
        intel_cleaned = flow_intel.correct_transcript(raw_transcript, strength="full")
        intel_cleaned = flow_intel.detect_structure(intel_cleaned)
        if apply_dictionary:
            dict_res = dictionary.apply(intel_cleaned, tone=tone, apply_snippets=apply_snippets)
            final_text = dict_res["corrected"]
            replacements = dict_res["replacements"]
        else:
            final_text = intel_cleaned
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
        "in_place_edit_applied": bool(in_place_edit),
        "intent_prediction": intent_prediction,
        "timestamp": time.time(),
    }

    _log_history(response_payload)
    return response_payload


@app.websocket("/ws/transcribe")
async def websocket_transcribe_endpoint(websocket: WebSocket):
    """
    Real-time chunked audio streaming transcription WebSocket.
    Receives live audio chunks and emits immediate partial tokens.
    """
    await websocket.accept()
    cumulative_buffer = bytearray()
    chunk_index = 0

    try:
        await websocket.send_text(json.dumps({
            "type": "STREAM_READY",
            "active_engine": transcriber.active_engine_name,
            "local_only": transcriber.local_only,
        }))

        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"]:
                chunk_bytes = msg["bytes"]
                cumulative_buffer.extend(chunk_bytes)
                chunk_index += 1

                stream_res = await transcriber.transcribe_chunk_stream(
                    chunk_bytes, bytes(cumulative_buffer), chunk_index
                )
                await websocket.send_text(json.dumps({
                    "type": "PARTIAL_TRANSCRIPT",
                    "text": stream_res["partial"],
                    "chunk_index": chunk_index,
                    "is_final": stream_res.get("is_final", False),
                }))

            elif "text" in msg and msg["text"]:
                data = json.loads(msg["text"])
                if data.get("action") == "FINISH":
                    tone = data.get("tone", "clean")
                    apply_dict = data.get("apply_dictionary", True)
                    apply_snips = data.get("apply_snippets", True)

                    # Final pass
                    stt_res = await transcriber.transcribe_audio_bytes(
                        bytes(cumulative_buffer) if cumulative_buffer else b"dummy",
                        filename="stream_finish.wav"
                    )
                    raw_text = stt_res.get("transcript", "")

                    in_place_edit = dictionary.detect_and_apply_in_place_edit(raw_text, last_finalized_transcript)
                    if in_place_edit:
                        final_text = in_place_edit["corrected"]
                        reps = in_place_edit.get("replacements", [])
                    elif apply_dict:
                        dict_res = dictionary.apply(raw_text, tone=tone, apply_snippets=apply_snips)
                        final_text = dict_res["corrected"]
                        reps = dict_res["replacements"]
                    else:
                        final_text = raw_text
                        reps = []

                    flow_intel.add_transcription(final_text, latency_ms=stt_res.get("latency_ms", 0))

                    payload = {
                        "success": True,
                        "transcript": final_text,
                        "raw_transcript": raw_text,
                        "replacements": reps,
                        "tone": tone,
                        "engine": stt_res.get("engine", "unknown"),
                        "timestamp": time.time(),
                    }
                    _log_history(payload)

                    await websocket.send_text(json.dumps({
                        "type": "FINAL_TRANSCRIPT",
                        "payload": payload,
                    }))
                    cumulative_buffer.clear()
                    chunk_index = 0

    except WebSocketDisconnect:
        logger.info("Streaming client disconnected from /ws/transcribe")
    except Exception as e:
        logger.error(f"WebSocket transcription error: {e}")


@app.post("/api/dictionary/apply")
async def apply_dictionary_to_text(req: TextProcessRequest) -> Dict[str, Any]:
    """Manually apply dictionary correction, tone styling, and snippets to a text string."""
    dict_res = dictionary.apply(req.text, tone=req.tone, apply_snippets=req.apply_snippets)
    intent_res = flow_intel.predict_and_adapt_intent(dict_res["corrected"])
    dict_res["intent_prediction"] = intent_res
    return dict_res


@app.get("/api/dictionary")
@app.get("/api/dictionary/entries")
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


@app.get("/api/dictionary/suggestions")
async def get_dictionary_suggestions() -> List[Dict[str, Any]]:
    """Return auto-learned pending dictionary suggestions."""
    return dictionary.get_suggestions()


@app.post("/api/dictionary/suggestions/accept")
async def accept_dictionary_suggestion(req: SuggestionActionRequest) -> Dict[str, Any]:
    """Accept an auto-learned term into active vocabulary."""
    ok = dictionary.accept_suggestion(req.phrase, req.replacement)
    if not ok:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    return {"success": True, "phrase": req.phrase, "action": "accepted"}


@app.post("/api/dictionary/suggestions/dismiss")
async def dismiss_dictionary_suggestion(req: SuggestionActionRequest) -> Dict[str, Any]:
    """Dismiss an auto-learned suggestion."""
    ok = dictionary.dismiss_suggestion(req.phrase)
    if not ok:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    return {"success": True, "phrase": req.phrase, "action": "dismissed"}


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


@app.post("/api/bridge/dispatch")
async def bridge_dispatch_to_swarm(req: BridgeDispatchRequest) -> Dict[str, Any]:
    """
    Direct bridge webhook: Post finalized voice transcript directly to
    CLI-Workflow Swarm Control Room (/api/workflow/dispatch).
    """
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            form_data = {
                "prompt": req.transcript,
                "cli_preference": req.cli_preference,
                "difficulty": req.difficulty,
                "provenance": f"EchoScribe Voice Direct ({time.strftime('%H:%M:%S')})",
            }
            resp = await client.post(f"{CLI_WORKFLOW_URL}/api/workflow/dispatch", data=form_data)
            if resp.status_code == 200:
                return {"success": True, "dispatched": True, "swarm_response": resp.json()}
            else:
                return {
                    "success": False,
                    "dispatched": False,
                    "error": f"CLI-Workflow returned {resp.status_code}: {resp.text}",
                }
    except Exception as e:
        logger.warning(f"Bridge dispatch connection failure: {e}")
        return {
            "success": False,
            "dispatched": False,
            "error": f"Could not reach CLI-Workflow at {CLI_WORKFLOW_URL}: {str(e)}",
        }


@app.post("/api/flow/correct")
async def flow_correct_endpoint(req: FlowCorrectRequest) -> Dict[str, Any]:
    """Runs multi-stage intelligence pass: self-correction, disfluency, structure, and app tone."""
    cleaned = flow_intel.correct_transcript(
        req.text,
        context=req.context,
        prosody_hints=req.prosody_hints,
        strength=req.correction_strength,
    )
    structured = flow_intel.detect_structure(cleaned)
    adapted = flow_intel.app_tone_adaptation(structured, req.app_id)
    return {
        "success": True,
        "original": req.text,
        "corrected": adapted,
        "strength": req.correction_strength,
        "app_id": req.app_id,
    }


@app.post("/api/command/apply")
async def apply_command_endpoint(req: CommandApplyRequest) -> Dict[str, Any]:
    """Voice-driven editing of selected text with inline diff preview."""
    res = flow_intel.apply_command(
        req.selected_text,
        req.instruction,
        surrounding_context=req.surrounding_context,
    )
    return res


@app.post("/api/dictionary/auto-add")
async def auto_add_watcher_endpoint(req: AutoAddWatcherRequest) -> Dict[str, Any]:
    """Captures post-paste edits to automatically add homophone corrections."""
    res = dictionary.detect_post_paste_correction(req.original_inserted, req.current_field_text)
    return {
        "success": bool(res),
        "detected_correction": res,
    }


@app.get("/api/app-profiles")
async def get_app_profiles_endpoint() -> Dict[str, Any]:
    """Returns app tone directives for IDEs, email clients, and chat apps."""
    return {
        "profiles": {
            "code": {
                "apps": ["VS Code", "Cursor", "Terminal", "PyCharm", "IntelliJ"],
                "directives": "Code-comment syntax, symbol translation active, variable identifiers preserved",
            },
            "formal": {
                "apps": ["Gmail", "Outlook", "Thunderbird"],
                "directives": "Formal tone, complete sentences, professional punctuation",
            },
            "casual": {
                "apps": ["Slack", "Discord", "Teams", "iMessage"],
                "directives": "Concise, conversational, short sentences",
            },
        }
    }


@app.get("/api/transcription/engines")
async def list_transcription_engines() -> Dict[str, Any]:
    """List all available transcription engines, active engine, and auto-detect default."""
    return {
        "active_engine_id": transcriber.registry.active_engine_id,
        "preference": transcriber.registry.preference,
        "active_engine_name": transcriber.active_engine_name,
        "system_default": select_default_engine(),
        "engines": transcriber.registry.list_engines(),
    }


@app.post("/api/transcription/engine/select")
async def select_transcription_engine_endpoint(req: EngineSelectRequest) -> Dict[str, Any]:
    """Switch active transcription engine."""
    res = transcriber.select_engine(req.engine_id)
    return res


@app.get("/api/transcription/ollama/status")
async def get_ollama_status_endpoint() -> Dict[str, Any]:
    """Probe Ollama connectivity on localhost:11434."""
    model_api_engine = transcriber.registry.engines.get("model_api")
    is_alive = await model_api_engine.check_ollama_alive() if model_api_engine else False
    return {
        "ollama_alive": is_alive,
        "ollama_url": "http://localhost:11434",
        "notice": "Ollama ready" if is_alive else "Ollama not detected — install from ollama.com",
    }


@app.get("/api/history")
async def get_history_endpoint(limit: int = 50) -> List[Dict[str, Any]]:
    """Return recent dictation session records from embedded SQLite."""
    try:
        sessions = db.get_recent_sessions(limit=limit)
        if sessions:
            return sessions
    except Exception as e:
        logger.warning(f"Could not retrieve sessions from SQLite: {e}")
    return history_log[:limit]


@app.get("/api/history/search")
async def search_history_endpoint(q: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    """Full-Text Search (FTS5) across recorded speech transcripts."""
    try:
        return db.search_sessions(q, limit=limit)
    except Exception as e:
        logger.warning(f"Full text search error: {e}")
        return []


@app.get("/api/stats")
async def get_stats_endpoint() -> Dict[str, Any]:
    """Return cumulative speech statistics from SQLite."""
    try:
        return db.get_stats()
    except Exception as e:
        logger.warning(f"Could not retrieve stats: {e}")
        return {"total_words": 0, "total_duration_seconds": 0.0, "wpm": 145, "hours_saved": 0.0}


# --- Talkback TTS Endpoints (Piper & Deepgram) ---

@app.post("/api/tts/speak")
async def tts_speak_endpoint(req: TTSSpeakRequest):
    """Synthesize speech audio for Talkback response with cloud-to-local fallback."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Speech text cannot be empty.")
    try:
        audio_bytes, meta = await tts_manager.synthesize(
            req.text,
            engine_override=req.engine,
            voice_id=req.voice_id,
        )
        headers = {
            "X-TTS-Engine": meta["engine_used"],
            "X-TTS-Fallback": str(meta["fallback_triggered"]).lower(),
            "X-TTS-Fallback-Reason": meta.get("fallback_reason") or "",
            "X-TTS-Latency-Ms": str(meta["latency_ms"]),
            "X-TTS-Voice": meta["voice_id"],
            "Access-Control-Expose-Headers": "X-TTS-Engine, X-TTS-Fallback, X-TTS-Fallback-Reason, X-TTS-Latency-Ms, X-TTS-Voice",
        }
        return Response(content=audio_bytes, media_type="audio/wav", headers=headers)
    except Exception as e:
        logger.error(f"TTS synthesis endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tts/status")
async def tts_status_endpoint() -> Dict[str, Any]:
    """Get runtime status, active engines, fallback state, and masked credentials."""
    return tts_manager.get_status()


@app.post("/api/tts/engine/select")
async def tts_select_engine_endpoint(req: TTSEngineSelectRequest) -> Dict[str, Any]:
    """Switch preferred engine ('piper' or 'deepgram')."""
    try:
        return tts_manager.select_engine(req.engine)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/tts/voice/select")
async def tts_select_voice_endpoint(req: TTSVoiceSelectRequest) -> Dict[str, Any]:
    """Switch active voice for given engine."""
    try:
        return tts_manager.select_voice(req.engine, req.voice_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/tts/voices")
async def tts_voices_endpoint() -> Dict[str, Any]:
    """List available voices for Piper and Deepgram."""
    return {
        "preferred_engine": tts_manager.preferred_engine,
        "piper": {
            "active_voice": tts_manager.active_piper_voice,
            "voices": tts_manager.piper.get_available_voices(),
        },
        "deepgram": {
            "active_voice": tts_manager.active_deepgram_voice,
            "voices": tts_manager.deepgram.get_available_voices(),
        },
    }


@app.post("/api/tts/piper/download")
async def tts_piper_download_endpoint(req: TTSPiperDownloadRequest) -> Dict[str, Any]:
    """Initiate background download of a Piper voice model."""
    asyncio.create_task(tts_manager.piper.download_voice(req.voice_id))
    return {"success": True, "voice_id": req.voice_id, "status": "downloading"}


@app.get("/api/tts/piper/download/status")
async def tts_piper_download_status_endpoint(voice_id: str) -> Dict[str, Any]:
    """Get download progress for a Piper voice."""
    return tts_manager.piper.get_download_status(voice_id)


@app.post("/api/tts/deepgram/key")
async def tts_deepgram_key_endpoint(req: TTSDeepgramKeyRequest) -> Dict[str, Any]:
    """Store Deepgram API key in OS Keyring with validation."""
    key = req.api_key.strip()
    if not key:
        tts_manager.vault.delete_key("deepgram")
        return {"success": True, "masked_key": "", "message": "Deepgram API key removed."}

    is_valid = True
    message = "Key saved successfully."
    meta = None

    if req.do_validate:
        is_valid, message, meta = await tts_manager.deepgram.validate_key(key)
        if not is_valid:
            return {
                "success": False,
                "message": message,
                "masked_key": tts_manager.vault.get_masked_key("deepgram"),
            }

    tts_manager.vault.set_key("deepgram", key)
    return {
        "success": True,
        "message": message,
        "masked_key": tts_manager.vault.get_masked_key("deepgram"),
        "meta": meta,
    }


@app.delete("/api/tts/deepgram/key")
async def tts_deepgram_delete_key_endpoint() -> Dict[str, Any]:
    """Remove Deepgram API key from OS Keyring."""
    tts_manager.vault.delete_key("deepgram")
    return {"success": True, "message": "Deepgram API key removed."}


@app.post("/api/tts/deepgram/validate")
async def tts_deepgram_validate_endpoint() -> Dict[str, Any]:
    """Test currently stored Deepgram API key."""
    is_valid, message, meta = await tts_manager.deepgram.validate_key()
    return {"valid": is_valid, "message": message, "meta": meta}


@app.post("/api/tts/preview")
async def tts_preview_endpoint(req: TTSSpeakRequest):
    """Generate audio sample preview for voice auditioning."""
    sample_text = req.text if (req.text and req.text.strip()) else "Hello, this is a voice preview from Kelvra Talkback."
    try:
        audio_bytes, meta = await tts_manager.synthesize(
            sample_text,
            engine_override=req.engine,
            voice_id=req.voice_id,
        )
        headers = {
            "X-TTS-Engine": meta["engine_used"],
            "X-TTS-Voice": meta["voice_id"],
            "Access-Control-Expose-Headers": "X-TTS-Engine, X-TTS-Voice",
        }
        return Response(content=audio_bytes, media_type="audio/wav", headers=headers)
    except Exception as e:
        logger.error(f"TTS preview endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Serve static web interface
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"service": "EchoScribe API", "status": "running"}
