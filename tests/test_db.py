"""Unit tests for EchoScribe embedded SQLite database architecture."""
import tempfile
import unittest
from pathlib import Path

from src.db import EchoScribeDB


class TestEchoScribeDB(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_file = Path(self.temp_dir.name) / "test_echoscribe.db"
        self.db = EchoScribeDB(db_path=self.db_file, auto_migrate=False)

    def tearDown(self):
        self.db.conn.close()
        self.temp_dir.cleanup()

    def test_schema_initialization(self):
        """Verify that tables and indexes are created successfully."""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        self.assertIn("dictionary_entries", tables)
        self.assertIn("dictation_sessions", tables)
        self.assertIn("snippets", tables)
        self.assertIn("stats", tables)

    def test_dictionary_crud_and_frequency(self):
        """Verify dictionary additions, self-learning metadata, and usage increments."""
        # Add word
        success = self.db.add_dictionary_word("fast api", "FastAPI", category="code", added_via="auto")
        self.assertTrue(success)

        # Retrieve
        data = self.db.get_all_dictionary()
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(data["words"]["fast api"], "FastAPI")
        entry = data["entries"][0]
        self.assertEqual(entry["added_via"], "auto")
        self.assertEqual(entry["usage_count"], 1)

        # Record usage
        self.db.record_word_usage("fast api")
        self.db.record_word_usage("fast api")
        updated = self.db.get_all_dictionary()["entries"][0]
        self.assertEqual(updated["usage_count"], 3)

        # Remove word
        removed = self.db.remove_dictionary_word("fast api")
        self.assertTrue(removed)
        self.assertEqual(self.db.get_all_dictionary()["total_count"], 0)

    def test_session_logging_and_fts_search(self):
        """Verify session logging and FTS5 full-text transcript search."""
        session_1 = {
            "transcript": "Implemented OAuth2 authentication for FastAPI backend.",
            "engine": "windows_local",
            "tone": "clean",
            "word_count": 6,
            "duration_seconds": 3.2,
        }
        session_2 = {
            "transcript": "Refactored Docker Compose configuration with PostgreSQL database.",
            "engine": "macos_native",
            "tone": "code",
            "word_count": 7,
            "duration_seconds": 4.1,
        }

        id1 = self.db.log_session(session_1)
        id2 = self.db.log_session(session_2)
        self.assertGreater(id1, 0)
        self.assertGreater(id2, 0)

        # Retrieve recent sessions
        recent = self.db.get_recent_sessions(limit=10)
        self.assertEqual(len(recent), 2)

        # Search for "OAuth2" via FTS5
        search_res = self.db.search_sessions("OAuth2")
        self.assertEqual(len(search_res), 1)
        self.assertIn("OAuth2", search_res[0]["transcript"])

        # Search for "PostgreSQL" via FTS5
        search_res2 = self.db.search_sessions("PostgreSQL")
        self.assertEqual(len(search_res2), 1)
        self.assertIn("PostgreSQL", search_res2[0]["transcript"])

    def test_cumulative_statistics(self):
        """Verify speech statistics tracking."""
        self.db.increment_stats(word_count=500, duration_seconds=120.0)
        stats = self.db.get_stats()
        self.assertEqual(stats["total_words"], 500)
        self.assertGreater(stats["hours_saved"], 0.0)

    def test_auto_migration_from_json(self):
        """Verify that a new DB automatically ingests existing JSON data when auto_migrate=True."""
        db_migrated = EchoScribeDB(db_path=Path(self.temp_dir.name) / "migrated.db", auto_migrate=True)
        try:
            data = db_migrated.get_all_dictionary()
            self.assertGreater(data["total_count"], 0)
        finally:
            db_migrated.conn.close()


if __name__ == "__main__":
    unittest.main()
