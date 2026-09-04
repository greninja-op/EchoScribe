"""High-level TTS Orchestrator & Fallback Manager for Kelvra Voice."""
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from .base import BaseTTSEngine
from .piper_engine import PiperEngine, DEFAULT_VOICE_ID as DEFAULT_PIPER_VOICE
from .deepgram_engine import DeepgramEngine, DEFAULT_AURA_VOICE as DEFAULT_DEEPGRAM_VOICE
from ..auth.credential_vault import CredentialVault

logger = logging.getLogger("kelvra_voice.tts.manager")


class TTSManager:
    """Manages Piper and Deepgram TTS engines with resilient automatic fallback."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        models_dir: Optional[Path] = None,
        vault: Optional[CredentialVault] = None,
    ):
        self.data_dir = data_dir or (Path(__file__).resolve().parent.parent.parent / "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.data_dir / "tts_config.json"

        self.vault = vault or CredentialVault(data_dir=self.data_dir)
        self.piper = PiperEngine(models_dir=models_dir)
        self.deepgram = DeepgramEngine(vault=self.vault)

        # In-memory fallback tracking
        self.last_fallback: Optional[Dict[str, Any]] = None

        # Load persisted config
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        default_config = {
            "preferred_engine": "piper",  # Default is local Piper
            "active_piper_voice": DEFAULT_PIPER_VOICE,
            "active_deepgram_voice": DEFAULT_DEEPGRAM_VOICE,
            "auto_fallback": True,
        }
        if not self.config_file.exists():
            self._save_config(default_config)
            return default_config
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**default_config, **data}
        except Exception as e:
            logger.warning(f"Could not load TTS config, using defaults: {e}")
            return default_config

    def _save_config(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or self.config
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save TTS config: {e}")

    @property
    def preferred_engine(self) -> str:
        return self.config.get("preferred_engine", "piper")

    @property
    def active_piper_voice(self) -> str:
        return self.config.get("active_piper_voice", DEFAULT_PIPER_VOICE)

    @property
    def active_deepgram_voice(self) -> str:
        return self.config.get("active_deepgram_voice", DEFAULT_DEEPGRAM_VOICE)

    def select_engine(self, engine_id: str) -> Dict[str, Any]:
        """Switch user's preferred TTS engine ('piper' or 'deepgram')."""
        if engine_id not in ("piper", "deepgram"):
            raise ValueError(f"Unknown engine: {engine_id}. Must be 'piper' or 'deepgram'.")
        self.config["preferred_engine"] = engine_id
        self._save_config()
        return {"success": True, "preferred_engine": engine_id}

    def select_voice(self, engine: str, voice_id: str) -> Dict[str, Any]:
        """Set active voice for an engine."""
        if engine == "piper":
            self.config["active_piper_voice"] = voice_id
        elif engine == "deepgram":
            self.config["active_deepgram_voice"] = voice_id
        else:
            raise ValueError(f"Unknown engine: {engine}")
        self._save_config()
        return {"success": True, "engine": engine, "active_voice": voice_id}

    def get_status(self) -> Dict[str, Any]:
        """Return runtime status of both engines, credential status, and active voices."""
        dg_available = self.deepgram.is_available()
        piper_available = self.piper.is_available()

        # Determine effective active engine
        if self.preferred_engine == "deepgram" and not dg_available:
            effective_engine = "piper"
            fallback_active = True
            fallback_reason = "No Deepgram API key configured in OS Keyring"
        else:
            effective_engine = self.preferred_engine
            fallback_active = False
            fallback_reason = None

        return {
            "preferred_engine": self.preferred_engine,
            "effective_engine": effective_engine,
            "fallback_active": fallback_active,
            "fallback_reason": fallback_reason,
            "last_fallback": self.last_fallback,
            "piper": {
                "available": piper_available,
                "is_local": True,
                "active_voice": self.active_piper_voice,
                "models_dir": str(self.piper.models_dir),
                "downloaded_voices": [v["id"] for v in self.piper.get_available_voices() if v["downloaded"]],
            },
            "deepgram": {
                "available": dg_available,
                "is_local": False,
                "active_voice": self.active_deepgram_voice,
                "has_key": dg_available,
                "masked_key": self.vault.get_masked_key("deepgram"),
            },
        }

    async def synthesize(
        self,
        text: str,
        engine_override: Optional[str] = None,
        voice_id: Optional[str] = None,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Synthesize text into audio WAV bytes with resilient cloud-to-local fallback.

        Returns (audio_bytes, metadata_dict).
        """
        start_time = time.perf_counter()
        target_engine = engine_override or self.preferred_engine
        fallback_triggered = False
        fallback_reason = None
        engine_used = target_engine
        voice_used = voice_id

        if target_engine == "deepgram":
            if not self.deepgram.is_available():
                logger.warning("Deepgram preferred but no API key configured. Transparently falling back to Piper.")
                fallback_triggered = True
                fallback_reason = "No Deepgram API key set in Keyring"
                engine_used = "piper"
                voice_used = voice_id if (voice_id and not voice_id.startswith("aura-")) else self.active_piper_voice
            else:
                try:
                    dg_voice = voice_id or self.active_deepgram_voice
                    audio_bytes = await self.deepgram.synthesize(text, voice_id=dg_voice)
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    return audio_bytes, {
                        "engine_used": "deepgram",
                        "fallback_triggered": False,
                        "fallback_reason": None,
                        "voice_id": dg_voice,
                        "latency_ms": latency_ms,
                    }
                except Exception as e:
                    logger.warning(f"Deepgram cloud TTS failed: {e}. Transparently falling back to local Piper.")
                    fallback_triggered = True
                    fallback_reason = f"Deepgram API error: {str(e)}"
                    engine_used = "piper"
                    voice_used = self.active_piper_voice

        # Execute Piper synthesis
        p_voice = voice_used or self.active_piper_voice
        try:
            audio_bytes = await self.piper.synthesize(text, voice_id=p_voice)
        except Exception as e:
            logger.error(f"Local Piper TTS synthesis failed: {e}")
            raise RuntimeError(f"All TTS synthesis options failed. Piper error: {e}")

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        meta = {
            "engine_used": "piper",
            "fallback_triggered": fallback_triggered,
            "fallback_reason": fallback_reason,
            "voice_id": p_voice,
            "latency_ms": latency_ms,
        }

        if fallback_triggered:
            self.last_fallback = {
                "timestamp": time.time(),
                "reason": fallback_reason,
                "engine_used": "piper",
            }

        return audio_bytes, meta
