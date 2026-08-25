"""Unit tests for EchoScribe dictionary engine and casing macros."""
import unittest
import tempfile
from pathlib import Path
from src.dictionary import CorrectionDictionary


class TestEchoScribeDictionary(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dict_file = Path(self.temp_dir.name) / "test_dictionary.json"
        self.cd = CorrectionDictionary(filepath=self.dict_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_dictionary_loaded(self):
        self.assertGreater(len(self.cd.words), 0)
        self.assertIn("fast api", self.cd.words)
        self.assertEqual(self.cd.words["fast api"], "FastAPI")

    def test_dictionary_word_replacement(self):
        raw_text = "I am creating a fast api endpoint with git hub actions and open ai models"
        res = self.cd.apply(raw_text)
        self.assertEqual(
            res["corrected"],
            "I am creating a FastAPI endpoint with GitHub actions and OpenAI models"
        )
        self.assertGreaterEqual(len(res["replacements"]), 3)

    def test_casing_macros(self):
        # Camel case
        res1 = self.cd.apply("define a function called camel case user profile status")
        self.assertIn("userProfileStatus", res1["corrected"])

        # Snake case
        res2 = self.cd.apply("query database using snake case get all active records")
        self.assertIn("get_all_active_records", res2["corrected"])

        # Kebab case
        res3 = self.cd.apply("deploy to kebab case internal auth service")
        self.assertIn("internal-auth-service", res3["corrected"])

    def test_add_and_remove_word(self):
        self.cd.add_word("super llama", "SuperLlama-3.1")
        self.assertIn("super llama", self.cd.words)

        res = self.cd.apply("run inference on super llama model")
        self.assertIn("SuperLlama-3.1", res["corrected"])

        self.cd.remove_word("super llama")
        self.assertNotIn("super llama", self.cd.words)


if __name__ == "__main__":
    unittest.main()
