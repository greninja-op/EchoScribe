"""Kelvra Voice TTS Module."""
from .base import BaseTTSEngine
from .piper_engine import PiperEngine, PIPER_VOICE_CATALOG, DEFAULT_VOICE_ID as DEFAULT_PIPER_VOICE
from .deepgram_engine import DeepgramEngine, DEEPGRAM_AURA_VOICES, DEFAULT_AURA_VOICE as DEFAULT_DEEPGRAM_VOICE
from .tts_manager import TTSManager

__all__ = [
    "BaseTTSEngine",
    "PiperEngine",
    "PIPER_VOICE_CATALOG",
    "DEFAULT_PIPER_VOICE",
    "DeepgramEngine",
    "DEEPGRAM_AURA_VOICES",
    "DEFAULT_DEEPGRAM_VOICE",
    "TTSManager",
]
