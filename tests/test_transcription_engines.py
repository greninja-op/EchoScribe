"""Unit Tests for EchoScribe Multi-Engine Transcription Architecture."""
import unittest
import asyncio
from unittest.mock import patch

from src.transcription.base import TranscriptionEngine
from src.transcription.windows_local import WindowsLocalEngine
from src.transcription.macos_native import MacOSNativeEngine
from src.transcription.model_api import ModelApiEngine
from src.transcription import select_default_engine, EngineRegistry
from src.transcriber import TranscriberEngine


class TestTranscriptionEngines(unittest.TestCase):

    def test_default_engine_selection(self):
        """Verify OS auto-detection rules."""
        with patch("platform.system", return_value="Darwin"):
            self.assertEqual(select_default_engine(), "macos_native")

        with patch("platform.system", return_value="Windows"):
            self.assertEqual(select_default_engine(), "windows_local")

        with patch("platform.system", return_value="Linux"):
            self.assertEqual(select_default_engine(), "windows_local")

    def test_engine_registry_lifecycle(self):
        """Verify EngineRegistry lists engines and switches overrides."""
        registry = EngineRegistry()
        engines = registry.list_engines()
        self.assertEqual(len(engines), 3)
        ids = [e["engine_id"] for e in engines]
        self.assertIn("windows_local", ids)
        self.assertIn("macos_native", ids)
        self.assertIn("model_api", ids)

        # Switch to windows_local explicitly
        res = registry.set_engine("windows_local")
        self.assertTrue(res["success"])
        self.assertEqual(registry.active_engine_id, "windows_local")

        # Switch to model_api
        res2 = registry.set_engine("model_api")
        self.assertTrue(res2["success"])
        self.assertEqual(registry.active_engine_id, "model_api")

    def test_windows_local_engine(self):
        """Verify WindowsLocalEngine session lifecycle and sliding window buffering."""
        engine = WindowsLocalEngine()
        self.assertEqual(engine.engine_id, "windows_local")
        self.assertEqual(engine.streaming_type, "chunked")

        async def run_session():
            await engine.start_session()
            # Feed 1.5 seconds of dummy PCM audio
            dummy_pcm = b"\x00\x00" * 24000
            await engine.feed_audio(dummy_pcm)
            final = await engine.end_session()
            return final

        final_transcript = asyncio.run(run_session())
        self.assertIsInstance(final_transcript, str)

    def test_model_api_engine(self):
        """Verify ModelApiEngine status and Ollama probe."""
        engine = ModelApiEngine(sub_mode="cloud")
        self.assertEqual(engine.engine_id, "model_api")
        status = engine.status_info
        self.assertIn("sub_mode", status)

        # Probe Ollama on unmapped port (should return False cleanly without raising)
        engine_ollama = ModelApiEngine(sub_mode="ollama", ollama_url="http://127.0.0.1:59999")
        alive = asyncio.run(engine_ollama.check_ollama_alive())
        self.assertFalse(alive)

    def test_macos_native_engine_fallback(self):
        """Verify MacOSNativeEngine status info and simulation behavior."""
        engine = MacOSNativeEngine()
        self.assertEqual(engine.engine_id, "macos_native")
        self.assertEqual(engine.streaming_type, "smooth")

        status = engine.status_info
        self.assertIn("is_darwin", status)

        async def run_macos():
            await engine.start_session()
            await engine.feed_audio(b"\x00\x00" * 1000)
            return await engine.end_session()

        result = asyncio.run(run_macos())
        self.assertIsInstance(result, str)

    def test_transcriber_facade_integration(self):
        """Verify backward-compatible TranscriberEngine facade."""
        facade = TranscriberEngine()
        status = facade.get_status()
        self.assertIn("active_engine", status)
        self.assertIn("local_only_mode", status)

        # Transcribe buffer
        dummy_wav = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        res = asyncio.run(facade.transcribe_audio_bytes(dummy_wav))
        self.assertTrue(res["success"])
        self.assertIn("transcript", res)
        self.assertIn("latency_ms", res)
        self.assertIn("engine", res)


if __name__ == "__main__":
    unittest.main()
