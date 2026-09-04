"""Abstract base class for Talkback TTS engines."""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncIterator


class BaseTTSEngine(ABC):
    """Base interface for all TTS engines (local Piper, cloud Deepgram)."""

    engine_id: str = "base"
    display_name: str = "Base TTS Engine"
    is_local: bool = False

    @abstractmethod
    async def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        """Synthesize text into WAV or MP3 audio bytes."""
        pass

    @abstractmethod
    async def synthesize_stream(self, text: str, voice_id: Optional[str] = None) -> AsyncIterator[bytes]:
        """Stream synthesized audio chunks."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the engine is ready to synthesize immediately."""
        pass

    @abstractmethod
    def get_available_voices(self) -> List[Dict[str, Any]]:
        """Return a list of supported voices with id, name, accent/language, and download status."""
        pass
