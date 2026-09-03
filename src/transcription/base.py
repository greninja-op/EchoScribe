"""Core TranscriptionEngine abstract base class for EchoScribe.

Defines the asynchronous interface all transcription backends must satisfy:
- Mode A: macOS Native (Apple Speech framework)
- Mode B: Windows Local (Open-weight Whisper / Parakeet fallback)
- Mode C: Model/API (Cloud Whisper API or Local Ollama LLM)
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, Optional


class TranscriptionEngine(ABC):
    """
    Abstract interface for swappable speech-to-text engines.
    DictationController / server.py talks only to this interface.
    All outputs flow downstream into dictionary.py and flow_intelligence.py.
    """

    @abstractmethod
    async def start_session(self) -> None:
        """Initialize and arm the audio session for a new utterance."""
        ...

    @abstractmethod
    async def feed_audio(self, chunk: bytes) -> None:
        """Feed a raw PCM or WAV audio chunk into the engine."""
        ...

    @abstractmethod
    async def stream_transcript(self) -> AsyncIterator[str]:
        """
        Yield partial or volatile transcript chunks as they become available.
        Mode A streams live partial tokens; Mode B updates windowed chunks.
        """
        ...

    @abstractmethod
    async def end_session(self) -> str:
        """Finalize and return the complete raw transcript for the utterance."""
        ...

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Identifier: 'macos_native' | 'windows_local' | 'model_api'"""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable engine title (e.g. 'Windows Local (Whisper)')"""
        ...

    @property
    def is_ready(self) -> bool:
        """Whether this engine is loaded, configured, and ready to transcribe."""
        return True

    @property
    def streaming_type(self) -> str:
        """'smooth' (per-token live partials) or 'chunked' (~1-2s window updates)"""
        return "chunked"

    @property
    def status_info(self) -> Dict[str, Any]:
        """Diagnostic metadata for UI status line and settings."""
        return {
            "engine_id": self.engine_id,
            "display_name": self.display_name,
            "is_ready": self.is_ready,
            "streaming_type": self.streaming_type,
        }
