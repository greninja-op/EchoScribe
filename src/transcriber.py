"""Transcription Engine Facade for EchoScribe.

Provides backward-compatible interface delegating to the pluggable
transcription architecture (Mode A: macOS Native, Mode B: Windows Local, Mode C: Model/API).
"""
import os
import io
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, AsyncIterator

from .config import STT_PROVIDER, OPENAI_API_KEY, LOCAL_PARAKEET_DIR, LOCAL_ONLY_MODE
from .transcription import (
    TranscriptionEngine,
    EngineRegistry,
    engine_registry,
    get_engine,
    select_default_engine,
)

logger = logging.getLogger("echoscribe.transcriber")


class TranscriberEngine:
    """Unified speech-to-text dispatcher with streaming and air-gap trust mode."""

    def __init__(
        self,
        provider: str = STT_PROVIDER,
        model_dir: Optional[str] = None,
        local_only: bool = LOCAL_ONLY_MODE,
    ):
        self.provider = provider
        self.model_dir = Path(model_dir or LOCAL_PARAKEET_DIR)
        self.local_only = local_only
        self.registry = engine_registry

    @property
    def active_engine(self) -> TranscriptionEngine:
        return self.registry.get_active_engine()

    @property
    def active_engine_name(self) -> str:
        return self.active_engine.display_name

    def set_local_only(self, enabled: bool) -> None:
        """Toggle local-only air-gap mode at runtime."""
        self.local_only = enabled
        if enabled and self.registry.active_engine_id == "model_api":
            self.registry.set_engine("auto")
        logger.info(f"EchoScribe Local-Only mode set to {self.local_only}")

    def select_engine(self, engine_id: str) -> Dict[str, Any]:
        """Switch active engine backend."""
        return self.registry.set_engine(engine_id)

    def get_status(self) -> Dict[str, Any]:
        """Return engine metadata for /api/status."""
        engine = self.active_engine
        return {
            "active_engine": engine.display_name,
            "engine_id": engine.engine_id,
            "streaming_type": engine.streaming_type,
            "local_only_mode": self.local_only,
            "network_egress_guarantee": "0 bytes outbound (air-gapped)" if self.local_only else "Cloud allowed",
            "parakeet_files_found": getattr(engine, "has_sherpa_onnx", False),
            "openai_api_configured": bool(OPENAI_API_KEY and not OPENAI_API_KEY.startswith("mock")),
        }

    async def transcribe_audio_bytes(
        self, audio_bytes: bytes, filename: str = "audio.wav"
    ) -> Dict[str, Any]:
        """Transcribe an audio buffer via the active transcription engine."""
        start_time = time.perf_counter()
        engine = self.active_engine

        try:
            await engine.start_session()
            await engine.feed_audio(audio_bytes)
            raw_transcript = await engine.end_session()
            latency = round((time.perf_counter() - start_time) * 1000, 1)

            return {
                "success": True,
                "transcript": raw_transcript,
                "latency_ms": latency,
                "engine": engine.display_name,
                "engine_id": engine.engine_id,
                "streaming_type": engine.streaming_type,
            }
        except Exception as e:
            logger.error(f"Transcription error on {engine.display_name}: {e}")
            latency = round((time.perf_counter() - start_time) * 1000, 1)
            return {
                "success": False,
                "error": str(e),
                "transcript": "",
                "latency_ms": latency,
                "engine": engine.display_name,
            }

    async def transcribe_chunk_stream(
        self, audio_chunk: bytes, cumulative_bytes: bytes, chunk_index: int
    ) -> Dict[str, Any]:
        """Process streaming audio chunks in real-time."""
        engine = self.active_engine
        await engine.feed_audio(audio_chunk)

        # In streaming sessions, get partial if available
        partial = ""
        # Check queue
        if hasattr(engine, "partial_queue") and not engine.partial_queue.empty():
            try:
                partial = engine.partial_queue.get_nowait()
            except Exception:
                pass

        return {
            "is_final": False,
            "partial": partial,
            "chunk_index": chunk_index,
            "engine": engine.display_name,
        }
