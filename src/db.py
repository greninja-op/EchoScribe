"""Embedded SQLite Database Module for EchoScribe.

Provides zero-dependency, local-first storage using Python's built-in sqlite3:
- Crash-proof Write-Ahead Logging (WAL)
- Dictionary entries with self-learning usage frequency tracking
- Unlimited dictation session storage with FTS5 Full-Text Search
- Snippets & cumulative metrics
- Automatic migration from legacy JSON files
"""
import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import (
    DB_PATH,
    DICTIONARY_FILE,
    HISTORY_FILE,
    SNIPPETS_FILE,
    STATS_FILE,
)

logger = logging.getLogger("echoscribe.db")


class EchoScribeDB:
    def __init__(self, db_path: Optional[Path] = None, auto_migrate: bool = True):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None  # autocommit mode; manage transactions explicitly when needed
        )
        self.conn.row_factory = sqlite3.Row
        self._setup_pragmas()
        self._init_schema()
        if auto_migrate:
            self._migrate_from_json()

    def _setup_pragmas(self) -> None:
        """Configure SQLite pragmas for high performance and durability."""
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    def _init_schema(self) -> None:
        """Create tables, indexes, and full-text search triggers."""
        cursor = self.conn.cursor()
        
        # 1. Dictionary Entries Table (with self-learning frequency metadata)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dictionary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phrase TEXT UNIQUE NOT NULL,
                replacement TEXT NOT NULL,
                category TEXT DEFAULT 'tech',
                added_via TEXT DEFAULT 'manual',
                usage_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dict_phrase ON dictionary_entries(phrase);")

        # 2. Dictation Sessions Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dictation_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                transcript TEXT NOT NULL,
                raw_transcript TEXT,
                engine TEXT,
                tone TEXT DEFAULT 'clean',
                word_count INTEGER DEFAULT 0,
                duration_seconds REAL DEFAULT 0.0,
                latency_ms REAL DEFAULT 0.0,
                timestamp REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_timestamp ON dictation_sessions(timestamp DESC);")

        # 3. Snippets Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snippets (
                trigger TEXT PRIMARY KEY,
                replacement TEXT NOT NULL,
                description TEXT,
                category TEXT DEFAULT 'template'
            );
        """)

        # 4. Key-Value Stats Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value REAL DEFAULT 0.0
            );
        """)

        # 5. Full-Text Search (FTS5) for instant search across all transcripts
        try:
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
                    transcript,
                    content='dictation_sessions',
                    content_rowid='id'
                );
            """)

            # Triggers to keep FTS in sync with dictation_sessions
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS sessions_ai AFTER INSERT ON dictation_sessions BEGIN
                    INSERT INTO transcripts_fts(rowid, transcript) VALUES (new.id, new.transcript);
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS sessions_ad AFTER DELETE ON dictation_sessions BEGIN
                    INSERT INTO transcripts_fts(transcripts_fts, rowid, transcript) VALUES('delete', old.id, old.transcript);
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS sessions_au AFTER UPDATE ON dictation_sessions BEGIN
                    INSERT INTO transcripts_fts(transcripts_fts, rowid, transcript) VALUES('delete', old.id, old.transcript);
                    INSERT INTO transcripts_fts(rowid, transcript) VALUES (new.id, new.transcript);
                END;
            """)
        except sqlite3.OperationalError as e:
            logger.warning(f"FTS5 setup note: {e}")

        cursor.close()

    def _migrate_from_json(self) -> None:
        """Automatically migrate data from existing legacy JSON files on startup."""
        cursor = self.conn.cursor()

        # Check if dictionary_entries is empty
        cursor.execute("SELECT COUNT(*) FROM dictionary_entries;")
        dict_count = cursor.fetchone()[0]

        if dict_count == 0 and DICTIONARY_FILE.exists():
            try:
                with open(DICTIONARY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                words = data.get("words", {})
                for phrase, rep in words.items():
                    category = "tech"
                    added_via = "manual"
                    if isinstance(rep, dict):
                        rep_text = rep.get("replacement", "")
                        category = rep.get("category", "tech")
                        added_via = rep.get("added_via", "manual")
                    else:
                        rep_text = str(rep)
                    cursor.execute("""
                        INSERT OR IGNORE INTO dictionary_entries (phrase, replacement, category, added_via)
                        VALUES (?, ?, ?, ?);
                    """, (phrase.lower().strip(), rep_text, category, added_via))
                logger.info(f"Migrated {len(words)} dictionary words from {DICTIONARY_FILE} to SQLite.")
            except Exception as e:
                logger.warning(f"Could not migrate legacy dictionary.json: {e}")

        # Check if dictation_sessions is empty
        cursor.execute("SELECT COUNT(*) FROM dictation_sessions;")
        sess_count = cursor.fetchone()[0]

        if sess_count == 0 and HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
                if isinstance(history, list):
                    for entry in history:
                        s_id = entry.get("id") or str(uuid.uuid4())
                        transcript = entry.get("transcript", "")
                        raw = entry.get("raw_transcript", transcript)
                        engine = entry.get("engine", "windows_local")
                        tone = entry.get("tone", "clean")
                        latency = entry.get("latency_ms", 0.0)
                        ts = entry.get("timestamp", time.time())
                        words_len = len(transcript.split()) if transcript else 0
                        cursor.execute("""
                            INSERT OR IGNORE INTO dictation_sessions 
                            (session_id, transcript, raw_transcript, engine, tone, word_count, latency_ms, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """, (s_id, transcript, raw, engine, tone, words_len, latency, ts))
                    logger.info(f"Migrated {len(history)} sessions from {HISTORY_FILE} to SQLite.")
            except Exception as e:
                logger.warning(f"Could not migrate legacy history.json: {e}")

        # Check snippets
        cursor.execute("SELECT COUNT(*) FROM snippets;")
        snip_count = cursor.fetchone()[0]
        if snip_count == 0 and SNIPPETS_FILE.exists():
            try:
                with open(SNIPPETS_FILE, "r", encoding="utf-8") as f:
                    snips = json.load(f)
                for trigger, val in snips.items():
                    rep = val if isinstance(val, str) else val.get("replacement", "")
                    desc = "" if isinstance(val, str) else val.get("description", "")
                    cursor.execute("""
                        INSERT OR IGNORE INTO snippets (trigger, replacement, description)
                        VALUES (?, ?, ?);
                    """, (trigger, rep, desc))
            except Exception as e:
                logger.warning(f"Could not migrate snippets.json: {e}")

        # Check stats
        cursor.execute("SELECT COUNT(*) FROM stats;")
        stat_count = cursor.fetchone()[0]
        if stat_count == 0 and STATS_FILE.exists():
            try:
                with open(STATS_FILE, "r", encoding="utf-8") as f:
                    stats = json.load(f)
                for k, v in stats.items():
                    if isinstance(v, (int, float)):
                        cursor.execute("INSERT OR REPLACE INTO stats (key, value) VALUES (?, ?);", (k, float(v)))
            except Exception as e:
                logger.warning(f"Could not migrate stats.json: {e}")

        cursor.close()

    # =========================================================================
    # DICTIONARY REPOSITORY
    # =========================================================================

    def get_all_dictionary(self) -> Dict[str, Any]:
        """Fetch all dictionary entries formatted for compatibility with CorrectionDictionary."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT phrase, replacement, category, added_via, usage_count, last_used_at 
            FROM dictionary_entries 
            ORDER BY usage_count DESC, phrase ASC;
        """)
        rows = cursor.fetchall()
        cursor.close()

        words_map = {}
        entries_list = []
        for r in rows:
            words_map[r["phrase"]] = r["replacement"]
            entries_list.append({
                "phrase": r["phrase"],
                "replacement": r["replacement"],
                "category": r["category"],
                "added_via": r["added_via"],
                "usage_count": r["usage_count"],
                "last_used_at": r["last_used_at"],
            })

        return {
            "words": words_map,
            "entries": entries_list,
            "total_count": len(words_map),
        }

    def add_dictionary_word(
        self,
        phrase: str,
        replacement: str,
        category: str = "tech",
        added_via: str = "manual"
    ) -> bool:
        """Add or update a technical homophone word mapping."""
        norm_phrase = phrase.lower().strip()
        norm_rep = replacement.strip()
        if not norm_phrase or not norm_rep:
            return False

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO dictionary_entries (phrase, replacement, category, added_via, usage_count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(phrase) DO UPDATE SET
                replacement = excluded.replacement,
                category = excluded.category,
                added_via = excluded.added_via;
        """, (norm_phrase, norm_rep, category, added_via))
        cursor.close()
        return True

    def remove_dictionary_word(self, phrase: str) -> bool:
        """Delete a word mapping from the dictionary."""
        norm_phrase = phrase.lower().strip()
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM dictionary_entries WHERE phrase = ?;", (norm_phrase,))
        changed = cursor.rowcount > 0
        cursor.close()
        return changed

    def record_word_usage(self, phrase: str) -> None:
        """Increment usage count and update last_used_at timestamp when a replacement is applied."""
        norm_phrase = phrase.lower().strip()
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE dictionary_entries 
            SET usage_count = usage_count + 1, last_used_at = CURRENT_TIMESTAMP
            WHERE phrase = ?;
        """, (norm_phrase,))
        cursor.close()

    # =========================================================================
    # DICTATION SESSIONS REPOSITORY & FTS5 SEARCH
    # =========================================================================

    def log_session(self, entry: Dict[str, Any]) -> int:
        """Store a finalized dictation session turn."""
        s_id = entry.get("id") or str(uuid.uuid4())
        transcript = entry.get("transcript", "").strip()
        if not transcript:
            return 0

        raw = entry.get("raw_transcript", transcript)
        engine = entry.get("engine", "windows_local")
        tone = entry.get("tone", "clean")
        word_count = entry.get("word_count", len(transcript.split()))
        duration = float(entry.get("duration_seconds", 0.0))
        latency = float(entry.get("latency_ms", 0.0))
        ts = float(entry.get("timestamp", time.time()))

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO dictation_sessions 
            (session_id, transcript, raw_transcript, engine, tone, word_count, duration_seconds, latency_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (s_id, transcript, raw, engine, tone, word_count, duration, latency, ts))
        row_id = cursor.lastrowid
        cursor.close()

        # Update running cumulative stats
        self.increment_stats(word_count=word_count, duration_seconds=duration)
        return row_id

    def get_recent_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent dictation sessions ordered chronologically."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT session_id as id, transcript, raw_transcript, engine, tone, word_count, duration_seconds, latency_ms, timestamp, created_at
            FROM dictation_sessions 
            ORDER BY timestamp DESC
            LIMIT ?;
        """, (limit,))
        rows = cursor.fetchall()
        cursor.close()
        return [dict(r) for r in rows]

    def search_sessions(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Full-Text Search (FTS5) across all stored transcripts."""
        clean_query = query.strip()
        if not clean_query:
            return self.get_recent_sessions(limit=limit)

        # Sanitize query for FTS5 syntax
        fts_query = f'"{clean_query}"*' if " " in clean_query else f"{clean_query}*"

        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT s.session_id as id, s.transcript, s.engine, s.tone, s.word_count, s.timestamp,
                       snippet(transcripts_fts, 0, '<mark class="fts-match">', '</mark>', '...', 12) as highlighted_snippet
                FROM transcripts_fts f
                JOIN dictation_sessions s ON f.rowid = s.id
                WHERE transcripts_fts MATCH ?
                ORDER BY rank
                LIMIT ?;
            """, (fts_query, limit))
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"FTS5 query error for '{query}': {e}. Falling back to LIKE.")
            cursor.execute("""
                SELECT session_id as id, transcript, engine, tone, word_count, timestamp
                FROM dictation_sessions
                WHERE transcript LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?;
            """, (f"%{clean_query}%", limit))
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]

    # =========================================================================
    # STATS & METRICS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Return cumulative usage metrics."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value FROM stats;")
        rows = cursor.fetchall()
        cursor.close()

        stats_map = {r["key"]: r["value"] for r in rows}
        total_words = int(stats_map.get("total_words", 0))
        total_seconds = stats_map.get("total_duration_seconds", 0.0)

        # Average speaking speed calculation
        wpm = int((total_words / (total_seconds / 60.0))) if total_seconds > 10 else 145
        # Estimated time saved typing vs speaking (typing ~40 wpm vs speaking ~140 wpm)
        hours_saved = round((total_words / 40.0 - total_words / max(wpm, 100)) / 60.0, 1)
        if hours_saved <= 0:
            hours_saved = round(total_words / 1400.0, 1)

        return {
            "total_words": total_words,
            "total_duration_seconds": total_seconds,
            "wpm": wpm,
            "hours_saved": max(hours_saved, 0.1) if total_words > 0 else 0.0,
        }

    def increment_stats(self, word_count: int, duration_seconds: float) -> None:
        """Increment cumulative speech statistics."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO stats (key, value) VALUES ('total_words', ?)
            ON CONFLICT(key) DO UPDATE SET value = value + excluded.value;
        """, (float(word_count),))
        cursor.execute("""
            INSERT INTO stats (key, value) VALUES ('total_duration_seconds', ?)
            ON CONFLICT(key) DO UPDATE SET value = value + excluded.value;
        """, (float(duration_seconds),))
        cursor.close()


# Singleton application instance
db = EchoScribeDB()
