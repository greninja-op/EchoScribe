"""Live API integration test for EchoScribe."""
import unittest
import httpx


class TestLiveEchoScribeAPI(unittest.TestCase):
    BASE_URL = "http://localhost:8765"

    def test_status_endpoint(self):
        resp = httpx.get(f"{self.BASE_URL}/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["service"], "EchoScribe")
        self.assertEqual(data["status"], "healthy")

    def test_milestones_and_10k_simulation(self):
        # 1. Check milestone summary
        resp = httpx.get(f"{self.BASE_URL}/api/milestones")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_words", data)
        self.assertIn("progress_pct", data)

        # 2. Simulate 10K+ words
        resp2 = httpx.post(f"{self.BASE_URL}/api/milestones/simulate-10k", json={"total_words": 10500})
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertTrue(data2["stats"]["is_10k_unlocked"])

    def test_dictionary_and_tones(self):
        payload = {
            "text": "um, basically we gotta build a fast api endpoint with camel case user profile and !sign",
            "tone": "professional",
            "apply_snippets": True
        }
        resp = httpx.post(f"{self.BASE_URL}/api/dictionary/apply", json=payload)
        self.assertEqual(resp.status_code, 200)
        res = resp.json()
        self.assertIn("FastAPI", res["corrected"])
        self.assertIn("userProfile", res["corrected"])
        self.assertIn("Athul", res["corrected"])  # Snippet expanded
        self.assertIn("intent_prediction", res)

    def test_transcribe_endpoint(self):
        dummy_wav = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        files = {"file": ("test.wav", dummy_wav, "audio/wav")}
        data = {"tone": "clean", "apply_dictionary": "true"}
        resp = httpx.post(f"{self.BASE_URL}/api/transcribe", files=files, data=data)
        self.assertEqual(resp.status_code, 200)
        res = resp.json()
        self.assertTrue(res["success"])
        self.assertIn("transcript", res)


if __name__ == "__main__":
    unittest.main()
