"""EchoScribe Multi-Engine Transcription Package.

Provides swappable ASR engines:
- Mode A: macOS Native (Apple Speech framework)
- Mode B: Windows Local (Open-weight Whisper / Parakeet)
- Mode C: Model/API (Cloud Whisper API or Local Ollama)
"""
import platform
import logging
from typing import Dict, Any, List, Optional

from .base import TranscriptionEngine
from .windows_local import WindowsLocalEngine
from .macos_native import MacOSNativeEngine
from .model_api import ModelApiEngine

logger = logging.getLogger("echoscribe.transcription")


def select_default_engine() -> str:
    """Auto-detect host OS and select the optimal default engine."""
    system = platform.system()
    if system == "Darwin":
        return "macos_native"  # Mode A
    elif system == "Windows":
        return "windows_local"  # Mode B
    else:
        return "windows_local"  # Mode B (Linux fallback)


class EngineRegistry:
    """Manages active transcription engines and user overrides."""

    def __init__(self, default_preference: str = "auto"):
        self.preference = default_preference
        self.engines: Dict[str, TranscriptionEngine] = {
            "windows_local": WindowsLocalEngine(),
            "macos_native": MacOSNativeEngine(),
            "model_api": ModelApiEngine(),
        }
        self.active_engine_id = self._resolve_engine_id(default_preference)

    def _resolve_engine_id(self, pref: str) -> str:
        if pref == "auto":
            auto_id = select_default_engine()
            # If auto picked macos_native but on non-Darwin or bridge absent, fallback to windows_local
            if auto_id == "macos_native" and not self.engines["macos_native"].is_ready:
                return "windows_local"
            return auto_id
        if pref in self.engines:
            return pref
        return "windows_local"

    def set_engine(self, engine_id: str) -> Dict[str, Any]:
        """Switch active engine override."""
        self.preference = engine_id
        self.active_engine_id = self._resolve_engine_id(engine_id)
        active_engine = self.get_active_engine()
        logger.info(f"Switched active transcription engine to {active_engine.display_name}")
        return {
            "success": True,
            "preference": self.preference,
            "active_engine_id": self.active_engine_id,
            "display_name": active_engine.display_name,
            "streaming_type": active_engine.streaming_type,
        }

    def get_active_engine(self) -> TranscriptionEngine:
        return self.engines.get(self.active_engine_id, self.engines["windows_local"])

    def list_engines(self) -> List[Dict[str, Any]]:
        """Return all available engines, readiness status, and auto-detect recommendation."""
        system_default = select_default_engine()
        res = []
        for eid, eng in self.engines.items():
            info = eng.status_info
            info["is_active"] = eid == self.active_engine_id
            info["is_system_default"] = eid == system_default
            res.append(info)
        return res


# Global singleton registry
engine_registry = EngineRegistry()


def get_engine(engine_id: Optional[str] = None) -> TranscriptionEngine:
    """Return engine instance by id or active singleton."""
    if engine_id and engine_id in engine_registry.engines:
        return engine_registry.engines[engine_id]
    return engine_registry.get_active_engine()
