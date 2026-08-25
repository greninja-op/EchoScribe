"""Unit tests for EchoScribe dictionary engine, Wispr Flow tones, snippets, and 10K intent."""
import unittest
import tempfile
from pathlib import Path
from src.dictionary import CorrectionDictionary
from src.flow_intelligence import FlowIntelligence


class TestEchoScribeSuite(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dict_file = Path(self.temp_dir.name) / "test_dictionary.json"
        self.snippets_file = Path(self.temp_dir.name) / "test_snippets.json"
        self.stats_file = Path(self.temp_dir.name) / "test_stats.json"

        self.cd = CorrectionDictionary(filepath=self.dict_file, snippets_path=self.snippets_file)
        self.fi = FlowIntelligence(stats_path=self.stats_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_dictionary_loaded(self):
        self.assertGreater(len(self.cd.words), 0)
        self.assertIn("fast api", self.cd.words)

    def test_dictionary_word_replacement(self):
        raw_text = "I am creating a fast api endpoint with git hub actions and open ai models"
        res = self.cd.apply(raw_text, tone="clean")
        self.assertEqual(
            res["corrected"],
            "I am creating a FastAPI endpoint with GitHub actions and OpenAI models."
        )
        self.assertGreaterEqual(len(res["replacements"]), 3)

    def test_casing_macros(self):
        res1 = self.cd.apply("define a function called camel case user profile status", tone="clean")
        self.assertIn("userProfileStatus", res1["corrected"])

        res2 = self.cd.apply("query database using snake case get all active records", tone="clean")
        self.assertIn("get_all_active_records", res2["corrected"])

        res3 = self.cd.apply("deploy to kebab case internal auth service", tone="clean")
        self.assertIn("internal-auth-service", res3["corrected"])

    def test_snippets_expansion(self):
        self.cd.add_snippet("!sign", "Best regards, Athul")
        res = self.cd.apply("Please review the PR. !sign")
        self.assertIn("Best regards, Athul", res["corrected"])

    def test_wispr_flow_tones(self):
        # Clean tone: removes filler words
        res_clean = self.cd.apply("um, basically, we need to, like, deploy the fast api router", tone="clean")
        self.assertNotIn("basically", res_clean["corrected"])
        self.assertIn("FastAPI", res_clean["corrected"])

        # Professional tone
        res_prof = self.cd.apply("hey we gotta push the docker compose build", tone="professional")
        self.assertIn("Greetings", res_prof["corrected"])
        self.assertIn("need to", res_prof["corrected"])

        # Bullet points tone
        res_bullets = self.cd.apply("first item. second item. third item", tone="bullets")
        self.assertTrue(res_bullets["corrected"].startswith("- "))

    def test_10k_milestone_auto_intent(self):
        # 1. Under 10K words: Intent reasoning is locked
        self.fi.set_words(3500)
        summary_low = self.fi.get_summary()
        self.assertFalse(summary_low["is_10k_unlocked"])
        res_locked = self.fi.predict_and_adapt_intent("def compute_metrics(x): return x * 2")
        self.assertFalse(res_locked["intent_feature_active"])

        # 2. Cross 10K milestone: Unlocks Personal Voice Twin & Intent
        self.fi.set_words(10200)
        summary_high = self.fi.get_summary()
        self.assertTrue(summary_high["is_10k_unlocked"])

        # Test Code definition intent
        res_code = self.fi.predict_and_adapt_intent("create a fast api endpoint function called get_user")
        self.assertTrue(res_code["intent_feature_active"])
        self.assertEqual(res_code["inferred_intent"], "code_definition")

        # Test Git workflow intent
        res_git = self.fi.predict_and_adapt_intent("fix broken authentication token in middleware")
        self.assertEqual(res_git["inferred_intent"], "git_workflow")
        self.assertTrue(res_git["adapted_text"].startswith("feat: "))


if __name__ == "__main__":
    unittest.main()
