"""Automated Unit Tests for EchoScribe Wispr Flow Intelligence Upgrade."""
import unittest
from src.flow_intelligence import FlowIntelligence
from src.dictionary import CorrectionDictionary


class TestFlowIntelligence(unittest.TestCase):

    def setUp(self):
        self.flow = FlowIntelligence()
        self.dict = CorrectionDictionary()

    def test_self_correction_resolution(self):
        """Test #1 Priority: resolving speaker pivots and abandoned phrases."""
        # 1. 'wait, no' pivot
        raw1 = "let's meet Tuesday — wait, no, Friday"
        corrected1 = self.flow.handle_self_corrections(raw1)
        self.assertIn("Friday", corrected1)
        self.assertNotIn("Tuesday", corrected1)

        # 2. 'sorry, I mean' pivot
        raw2 = "send the email to Bob, sorry, I mean Alice"
        corrected2 = self.flow.handle_self_corrections(raw2)
        self.assertIn("Alice", corrected2)
        self.assertNotIn("Bob", corrected2)

        # 3. 'scratch that' pivot
        raw3 = "deploy to staging — scratch that, deploy directly to production"
        corrected3 = self.flow.handle_self_corrections(raw3)
        self.assertIn("production", corrected3)
        self.assertNotIn("staging", corrected3)

    def test_stutter_and_word_repetition_collapse(self):
        """Test collapsing stutters and immediate duplicate words."""
        raw = "I I I want to to check the the server"
        collapsed = self.flow.handle_self_corrections(raw)
        self.assertEqual(collapsed, "I want to check the server")

        hyphen_raw = "th-th-this is clean"
        collapsed_hyphen = self.flow.handle_self_corrections(hyphen_raw)
        self.assertEqual(collapsed_hyphen, "This is clean")

    def test_disfluency_and_filler_cleanup(self):
        """Test stripping verbal fillers without dropping technical terms."""
        raw = "um, like, we should basically test the database"
        cleaned = self.flow.clean_disfluencies(raw)
        self.assertEqual(cleaned, "We should test the database")

    def test_correction_strength_levels(self):
        """Test 'off', 'light', and 'full' correction strength."""
        raw = "um, I I want to to deploy"

        # Off = raw passthrough
        off_res = self.flow.correct_transcript(raw, strength="off")
        self.assertEqual(off_res, raw)

        # Light = stutter & filler removal without prosody sentence period
        light_res = self.flow.correct_transcript(raw, strength="light")
        self.assertEqual(light_res, "I want to deploy")

        # Full = self-correction, filler cleanup, prosody trailing period
        full_res = self.flow.correct_transcript(raw, strength="full")
        self.assertEqual(full_res, "I want to deploy.")

    def test_automatic_list_detection(self):
        """Test detecting ordinal sequence words and formatting as Markdown lists."""
        raw_ordinals = "First verify authentication, second run assertions, finally deploy containers"
        structured = self.flow.detect_structure(raw_ordinals)
        self.assertIn("- First:", structured)
        self.assertIn("- Second:", structured)
        self.assertIn("- Finally:", structured)

        raw_explicit = "make this a list: user auth, database migration, api router"
        structured_explicit = self.flow.detect_structure(raw_explicit)
        self.assertIn("- User auth", structured_explicit)
        self.assertIn("- Database migration", structured_explicit)
        self.assertIn("- Api router", structured_explicit)

    def test_command_mode_editing(self):
        """Test voice-driven editing on selected text."""
        selected = "apples, bananas, oranges"
        res = self.flow.apply_command(selected, "format as a bulleted list")
        self.assertTrue(res["success"])
        self.assertIn("- Apples", res["replacement"])
        self.assertIn("<del", res["diff_html"])
        self.assertIn("<ins", res["diff_html"])

        selected_fluff = "we really simply basically just want to deploy"
        res_concise = self.flow.apply_command(selected_fluff, "make this concise")
        self.assertNotIn("basically", res_concise["replacement"])
        self.assertIn("deploy", res_concise["replacement"])

    def test_code_syntax_dictation(self):
        """Test mapping spoken programming tokens into code literals."""
        spoken = "def process open paren x comma y close paren arrow bool colon"
        code = self.flow.apply_code_syntax(spoken)
        self.assertEqual(code, "def process(x, y) -> bool:")

        spoken_comp = "if a double equals b and c not equals d"
        code_comp = self.flow.apply_code_syntax(spoken_comp)
        self.assertEqual(code_comp, "if a == b and c != d")

    def test_post_paste_auto_add_watcher(self):
        """Test auto-learning watcher capturing post-paste corrections."""
        orig = "we configured fast api"
        edited = "we configured FastAPI"
        res = self.dict.detect_post_paste_correction(orig, edited)
        self.assertIsNotNone(res)
        self.assertEqual(res["spoken"], "fast api")
        self.assertEqual(res["replacement"], "FastAPI")
        self.assertEqual(res["added_via"], "auto")


if __name__ == "__main__":
    unittest.main()
