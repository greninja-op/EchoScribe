"""Piper local on-device Text-To-Speech engine."""
import os
import io
import wave
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncIterator

import httpx

from .base import BaseTTSEngine

logger = logging.getLogger("kelvra_voice.tts.piper")

# Default voice catalog with direct HuggingFace resolve URLs
PIPER_VOICE_CATALOG = {
    "en_US-lessac-medium": {
        "name": "Lessac (US English - Balanced)",
        "language": "en-US",
        "gender": "female",
        "quality": "medium",
        "size_mb": 63.2,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
    },
    "en_US-amy-medium": {
        "name": "Amy (US English - Expressive)",
        "language": "en-US",
        "gender": "female",
        "quality": "medium",
        "size_mb": 63.2,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json",
    },
    "en_US-ryan-medium": {
        "name": "Ryan (US English - Clear Male)",
        "language": "en-US",
        "gender": "male",
        "quality": "medium",
        "size_mb": 63.2,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json",
    },
    "en_GB-alan-medium": {
        "name": "Alan (British English)",
        "language": "en-GB",
        "gender": "male",
        "quality": "medium",
        "size_mb": 63.2,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json",
    },
}

DEFAULT_VOICE_ID = "en_US-lessac-medium"


class PiperEngine(BaseTTSEngine):
    """Local, on-device Piper neural TTS engine.

    Requires zero GPU, no account, and maintains complete air-gap compliance with 0 network egress during inference.
    """

    engine_id: str = "piper"
    display_name: str = "Piper (Local On-Device)"
    is_local: bool = True

    def __init__(self, models_dir: Optional[Path] = None):
        if models_dir:
            self.models_dir = Path(models_dir)
        else:
            local_appdata = os.getenv("LOCALAPPDATA", "")
            if local_appdata:
                self.models_dir = Path(local_appdata) / "Murmur" / "models" / "piper"
            else:
                self.models_dir = Path.home() / ".local" / "share" / "kelvra" / "models" / "piper"

        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_voices: Dict[str, Any] = {}
        self._download_tasks: Dict[str, Dict[str, Any]] = {}
        self.default_voice_id = DEFAULT_VOICE_ID

    def get_voice_paths(self, voice_id: str) -> tuple[Path, Path]:
        """Returns (onnx_path, json_path) for given voice_id."""
        onnx_file = self.models_dir / f"{voice_id}.onnx"
        json_file = self.models_dir / f"{voice_id}.onnx.json"
        return onnx_file, json_file

    def is_voice_downloaded(self, voice_id: str) -> bool:
        """Check if model and config exist on disk."""
        onnx_file, json_file = self.get_voice_paths(voice_id)
        return onnx_file.exists() and json_file.exists() and onnx_file.stat().st_size > 1000

    def is_available(self) -> bool:
        """Return True if piper is importable and at least one voice is downloaded."""
        try:
            import piper  # noqa: F401
            # Check if default or any voice is available
            for v_id in PIPER_VOICE_CATALOG.keys():
                if self.is_voice_downloaded(v_id):
                    return True
            return False
        except ImportError:
            return False

    def get_available_voices(self) -> List[Dict[str, Any]]:
        """Return full catalog with local download statuses and download progress."""
        voices = []
        for voice_id, meta in PIPER_VOICE_CATALOG.items():
            is_dl = self.is_voice_downloaded(voice_id)
            dl_info = self._download_tasks.get(voice_id, {})
            voices.append({
                "id": voice_id,
                "name": meta["name"],
                "language": meta["language"],
                "gender": meta["gender"],
                "quality": meta["quality"],
                "size_mb": meta["size_mb"],
                "downloaded": is_dl,
                "is_default": (voice_id == self.default_voice_id),
                "download_status": dl_info.get("status", "ready" if is_dl else "not_downloaded"),
                "progress_percent": dl_info.get("progress", 100 if is_dl else 0),
            })
        return voices

    async def download_voice(self, voice_id: str) -> bool:
        """Download voice ONNX and JSON config asynchronously from catalog."""
        if voice_id not in PIPER_VOICE_CATALOG:
            raise ValueError(f"Unknown Piper voice ID: {voice_id}")

        if self.is_voice_downloaded(voice_id):
            return True

        if voice_id in self._download_tasks and self._download_tasks[voice_id].get("status") == "downloading":
            logger.info(f"Voice {voice_id} already downloading.")
            return True

        meta = PIPER_VOICE_CATALOG[voice_id]
        onnx_file, json_file = self.get_voice_paths(voice_id)

        self._download_tasks[voice_id] = {"status": "downloading", "progress": 0, "error": None}

        try:
            logger.info(f"Starting download for Piper voice {voice_id}...")
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                # 1. Download JSON config
                json_resp = await client.get(meta["json_url"])
                if json_resp.status_code != 200:
                    raise RuntimeError(f"Failed to fetch {meta['json_url']} (HTTP {json_resp.status_code})")
                json_file.write_bytes(json_resp.content)
                self._download_tasks[voice_id]["progress"] = 5

                # 2. Stream download ONNX model with progress tracking
                async with client.stream("GET", meta["onnx_url"]) as response:
                    if response.status_code != 200:
                        raise RuntimeError(f"Failed to fetch {meta['onnx_url']} (HTTP {response.status_code})")

                    total_size = int(response.headers.get("content-length", 0))
                    downloaded = 0
                    temp_onnx = onnx_file.with_suffix(".tmp")

                    with open(temp_onnx, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    pct = int(5 + (downloaded / total_size) * 95)
                                    self._download_tasks[voice_id]["progress"] = min(pct, 99)

                    temp_onnx.replace(onnx_file)

            self._download_tasks[voice_id] = {"status": "ready", "progress": 100, "error": None}
            logger.info(f"Successfully downloaded Piper voice {voice_id} to {onnx_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to download voice {voice_id}: {e}")
            self._download_tasks[voice_id] = {"status": "error", "progress": 0, "error": str(e)}
            # Cleanup broken files
            if onnx_file.exists():
                onnx_file.unlink(missing_ok=True)
            temp_onnx = onnx_file.with_suffix(".tmp")
            if temp_onnx.exists():
                temp_onnx.unlink(missing_ok=True)
            return False

    def get_download_status(self, voice_id: str) -> Dict[str, Any]:
        """Return current download task info for voice_id."""
        if self.is_voice_downloaded(voice_id):
            return {"status": "ready", "progress": 100, "downloaded": True}
        return self._download_tasks.get(voice_id, {"status": "not_downloaded", "progress": 0, "downloaded": False})

    def _load_voice_instance(self, voice_id: str) -> Any:
        """Load and cache PiperVoice instance for memory-efficient synthesis."""
        if voice_id in self._loaded_voices:
            return self._loaded_voices[voice_id]

        onnx_file, json_file = self.get_voice_paths(voice_id)
        if not onnx_file.exists() or not json_file.exists():
            raise FileNotFoundError(f"Voice {voice_id} is not downloaded locally.")

        from piper import PiperVoice
        logger.info(f"Loading Piper voice instance from disk: {voice_id}...")
        voice = PiperVoice.load(onnx_file, config_path=json_file, use_cuda=False)
        self._loaded_voices[voice_id] = voice
        return voice

    async def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        """Synthesize text on CPU to standard 16-bit PCM WAV bytes with zero network calls."""
        v_id = voice_id or self.default_voice_id

        # If selected voice isn't downloaded, try default voice, or trigger download
        if not self.is_voice_downloaded(v_id):
            if v_id != self.default_voice_id and self.is_voice_downloaded(self.default_voice_id):
                v_id = self.default_voice_id
            else:
                # Trigger synchronous download of default voice
                ok = await self.download_voice(v_id)
                if not ok:
                    raise RuntimeError(f"Piper voice model {v_id} is not available and download failed.")

        # Run CPU inference in executor thread to prevent blocking event loop
        loop = asyncio.get_running_loop()
        wav_bytes = await loop.run_in_executor(None, self._sync_synthesize, text, v_id)
        return wav_bytes

    def _sync_synthesize(self, text: str, voice_id: str) -> bytes:
        voice = self._load_voice_instance(voice_id)

        # Collect raw 16-bit PCM chunks
        pcm_buffer = io.BytesIO()
        sample_rate = 22050
        sample_width = 2
        channels = 1

        for chunk in voice.synthesize(text):
            sample_rate = chunk.sample_rate
            sample_width = chunk.sample_width
            channels = chunk.sample_channels
            pcm_buffer.write(chunk.audio_int16_bytes)

        raw_pcm = pcm_buffer.getvalue()

        # Wrap in valid standard WAV container
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(raw_pcm)

        return wav_io.getvalue()

    async def synthesize_stream(self, text: str, voice_id: Optional[str] = None) -> AsyncIterator[bytes]:
        """Yield full synthesized WAV audio."""
        audio = await self.synthesize(text, voice_id=voice_id)
        yield audio
