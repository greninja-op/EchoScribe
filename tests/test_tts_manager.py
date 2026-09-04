"""Unit tests for TTSManager, Piper, and Deepgram engines with fallback logic."""
import io
import wave
import shutil
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from src.auth.credential_vault import CredentialVault
from src.tts import TTSManager, PiperEngine, DeepgramEngine, PIPER_VOICE_CATALOG, DEEPGRAM_AURA_VOICES


@pytest.fixture
def temp_env():
    temp_data = Path(tempfile.mkdtemp(prefix="tts_data_"))
    temp_models = Path(tempfile.mkdtemp(prefix="tts_models_"))
    service = f"test-tts-vault-{uuid.uuid4().hex[:8]}"
    vault = CredentialVault(data_dir=temp_data, service_name=service)
    yield temp_data, temp_models, vault
    try:
        vault.delete_key("deepgram")
    except Exception:
        pass
    shutil.rmtree(temp_data, ignore_errors=True)
    shutil.rmtree(temp_models, ignore_errors=True)


def create_dummy_wav(duration_s=0.1, sample_rate=22050):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * int(duration_s * sample_rate))
    return buf.getvalue()


@pytest.mark.asyncio
async def test_piper_engine_catalog_and_availability(temp_env):
    temp_data, temp_models, vault = temp_env
    piper = PiperEngine(models_dir=temp_models)

    voices = piper.get_available_voices()
    assert len(voices) == len(PIPER_VOICE_CATALOG)
    assert any(v["id"] == "en_US-lessac-medium" for v in voices)
    assert any(v["id"] == "en_US-amy-medium" for v in voices)

    # Initially not downloaded
    assert not piper.is_voice_downloaded("en_US-lessac-medium")


@pytest.mark.asyncio
async def test_deepgram_engine_voices_and_status(temp_env):
    temp_data, temp_models, vault = temp_env
    dg = DeepgramEngine(vault=vault)

    voices = dg.get_available_voices()
    assert len(voices) == len(DEEPGRAM_AURA_VOICES)
    assert any(v["id"] == "aura-asteria-en" for v in voices)


@pytest.mark.asyncio
async def test_tts_manager_engine_and_voice_selection(temp_env):
    temp_data, temp_models, vault = temp_env
    manager = TTSManager(data_dir=temp_data, models_dir=temp_models, vault=vault)

    # Defaults
    assert manager.preferred_engine == "piper"
    assert manager.active_piper_voice == "en_US-lessac-medium"

    # Select engine
    manager.select_engine("deepgram")
    assert manager.preferred_engine == "deepgram"

    # Select voice
    manager.select_voice("piper", "en_US-amy-medium")
    assert manager.active_piper_voice == "en_US-amy-medium"

    manager.select_voice("deepgram", "aura-luna-en")
    assert manager.active_deepgram_voice == "aura-luna-en"


@pytest.mark.asyncio
async def test_tts_manager_automatic_fallback_when_deepgram_no_key(temp_env):
    temp_data, temp_models, vault = temp_env
    manager = TTSManager(data_dir=temp_data, models_dir=temp_models, vault=vault)

    # Preferred engine is deepgram, but vault is empty
    manager.select_engine("deepgram")
    assert not manager.deepgram.is_available()

    dummy_wav = create_dummy_wav()

    # Mock Piper synthesis
    with patch.object(manager.piper, "synthesize", new_callable=AsyncMock) as mock_piper_syn:
        mock_piper_syn.return_value = dummy_wav

        audio_bytes, meta = await manager.synthesize("Testing talkback fallback logic")

        assert audio_bytes == dummy_wav
        assert meta["engine_used"] == "piper"
        assert meta["fallback_triggered"] is True
        assert "No Deepgram API key" in meta["fallback_reason"]
        assert manager.last_fallback is not None
        assert manager.last_fallback["engine_used"] == "piper"


@pytest.mark.asyncio
async def test_tts_manager_automatic_fallback_when_deepgram_fails(temp_env):
    temp_data, temp_models, vault = temp_env
    manager = TTSManager(data_dir=temp_data, models_dir=temp_models, vault=vault)
    manager.select_engine("deepgram")

    # Store a dummy key in isolated test vault
    manager.vault.set_key("deepgram", "dg-test-mock-key-1234")
    assert manager.deepgram.is_available()

    dummy_wav = create_dummy_wav()

    # Mock Deepgram throwing a network error, Piper succeeding
    with patch.object(manager.deepgram, "synthesize", new_callable=AsyncMock) as mock_dg_syn:
        mock_dg_syn.side_effect = RuntimeError("503 Service Unavailable: Deepgram network drop")

        with patch.object(manager.piper, "synthesize", new_callable=AsyncMock) as mock_piper_syn:
            mock_piper_syn.return_value = dummy_wav

            audio_bytes, meta = await manager.synthesize("Network failure test")

            assert audio_bytes == dummy_wav
            assert meta["engine_used"] == "piper"
            assert meta["fallback_triggered"] is True
            assert "Deepgram network drop" in meta["fallback_reason"]
            assert manager.last_fallback["reason"] == meta["fallback_reason"]
