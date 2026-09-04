"""Deepgram Aura-2 Cloud Text-To-Speech engine."""
import logging
from typing import Dict, Any, List, Optional, AsyncIterator

import httpx

from .base import BaseTTSEngine
from ..auth.credential_vault import CredentialVault

logger = logging.getLogger("kelvra_voice.tts.deepgram")

DEEPGRAM_SPEAK_URL = "https://api.deepgram.com/v1/speak"
DEEPGRAM_PROJECTS_URL = "https://api.deepgram.com/v1/projects"

# Official Deepgram Aura-2 Voice Models
DEEPGRAM_AURA_VOICES = [
    {"id": "aura-asteria-en", "name": "Asteria (US English - Conversational)", "gender": "female", "language": "en-US"},
    {"id": "aura-luna-en", "name": "Luna (US English - Calm & Friendly)", "gender": "female", "language": "en-US"},
    {"id": "aura-stella-en", "name": "Stella (US English - Professional)", "gender": "female", "language": "en-US"},
    {"id": "aura-athena-en", "name": "Athena (UK English - Authoritative)", "gender": "female", "language": "en-GB"},
    {"id": "aura-hera-en", "name": "Hera (US English - Confident)", "gender": "female", "language": "en-US"},
    {"id": "aura-orion-en", "name": "Orion (US English - Warm & Natural)", "gender": "male", "language": "en-US"},
    {"id": "aura-arcas-en", "name": "Arcas (US English - Neutral Informative)", "gender": "male", "language": "en-US"},
    {"id": "aura-perseus-en", "name": "Perseus (US English - Expressive)", "gender": "male", "language": "en-US"},
    {"id": "aura-angus-en", "name": "Angus (Irish English - Conversational)", "gender": "male", "language": "en-IE"},
    {"id": "aura-orpheus-en", "name": "Orpheus (US English - Confident)", "gender": "male", "language": "en-US"},
    {"id": "aura-helios-en", "name": "Helios (UK English - Clear & Direct)", "gender": "male", "language": "en-GB"},
    {"id": "aura-zeus-en", "name": "Zeus (US English - Deep & Resonant)", "gender": "male", "language": "en-US"},
]

DEFAULT_AURA_VOICE = "aura-asteria-en"


class DeepgramEngine(BaseTTSEngine):
    """Cloud-based Deepgram Aura-2 neural TTS engine.

    Connects to Deepgram REST and streaming TTS endpoints. Uses CredentialVault
    for secure OS keyring token storage.
    """

    engine_id: str = "deepgram"
    display_name: str = "Deepgram Aura-2 (Cloud API)"
    is_local: bool = False

    def __init__(self, vault: Optional[CredentialVault] = None):
        self.vault = vault or CredentialVault()
        self.default_voice_id = DEFAULT_AURA_VOICE

    def get_api_key(self) -> Optional[str]:
        return self.vault.get_key("deepgram")

    def is_available(self) -> bool:
        """Available if a non-empty Deepgram API key is configured."""
        key = self.get_api_key()
        return bool(key and len(key.strip()) > 0)

    def get_available_voices(self) -> List[Dict[str, Any]]:
        """Return available Aura voices with default indicator."""
        return [
            {
                "id": v["id"],
                "name": v["name"],
                "gender": v["gender"],
                "language": v["language"],
                "is_default": (v["id"] == self.default_voice_id),
                "is_cloud": True,
            }
            for v in DEEPGRAM_AURA_VOICES
        ]

    async def validate_key(self, api_key: Optional[str] = None) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        """Validate API key against Deepgram's API. Returns (is_valid, message, metadata)."""
        key = api_key or self.get_api_key()
        if not key:
            return False, "No Deepgram API key provided.", None

        cleaned_key = key.strip()
        headers = {
            "Authorization": f"Token {cleaned_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(DEEPGRAM_PROJECTS_URL, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    projects = data.get("projects", [])
                    project_name = projects[0].get("name", "Default Project") if projects else "Deepgram Project"
                    project_id = projects[0].get("project_id", "") if projects else ""

                    balance_info = None
                    if project_id:
                        try:
                            bal_resp = await client.get(f"{DEEPGRAM_PROJECTS_URL}/{project_id}/balances", headers=headers)
                            if bal_resp.status_code == 200:
                                bal_data = bal_resp.json()
                                balances = bal_data.get("balances", [])
                                if balances:
                                    balance_info = {
                                        "amount": balances[0].get("amount"),
                                        "units": balances[0].get("units", "USD"),
                                    }
                        except Exception as e:
                            logger.debug(f"Could not retrieve project balances: {e}")

                    meta = {
                        "project_name": project_name,
                        "project_id": project_id,
                        "balance": balance_info,
                    }
                    return True, "Deepgram API key verified successfully.", meta
                elif resp.status_code == 401:
                    return False, "Authentication failed: Invalid Deepgram API key.", None
                else:
                    return False, f"Deepgram validation returned HTTP {resp.status_code}: {resp.text}", None
        except httpx.ConnectError:
            return False, "Could not connect to Deepgram API (offline or network error).", None
        except Exception as e:
            return False, f"Validation error: {str(e)}", None

    async def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        """Synthesize speech using Deepgram Aura REST endpoint."""
        key = self.get_api_key()
        if not key:
            raise ValueError("Deepgram API key is not configured in CredentialVault.")

        voice = voice_id or self.default_voice_id
        url = f"{DEEPGRAM_SPEAK_URL}?model={voice}&encoding=linear16&sample_rate=24000"
        headers = {
            "Authorization": f"Token {key.strip()}",
            "Content-Type": "application/json",
        }
        payload = {"text": text}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    raise RuntimeError(f"Deepgram TTS API returned {response.status_code}: {response.text}")
                return response.content
        except httpx.RequestError as e:
            raise RuntimeError(f"Deepgram network request failed: {e}")

    async def synthesize_stream(self, text: str, voice_id: Optional[str] = None) -> AsyncIterator[bytes]:
        """Stream synthesized audio chunks from Deepgram."""
        key = self.get_api_key()
        if not key:
            raise ValueError("Deepgram API key is not configured in CredentialVault.")

        voice = voice_id or self.default_voice_id
        url = f"{DEEPGRAM_SPEAK_URL}?model={voice}&encoding=linear16&sample_rate=24000"
        headers = {
            "Authorization": f"Token {key.strip()}",
            "Content-Type": "application/json",
        }
        payload = {"text": text}

        async with httpx.AsyncClient(timeout=20.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"Deepgram TTS streaming returned {response.status_code}")
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if chunk:
                        yield chunk
