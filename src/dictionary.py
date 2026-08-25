"""Correction Dictionary Engine for EchoScribe.

Enforces accurate developer terms, canonical casing, and voice macro expansions
so audio transcripts are free of domain misinterpretations.
"""
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
from .config import DICTIONARY_FILE

logger = logging.getLogger("echoscribe.dictionary")


class CorrectionDictionary:
    """Manages word substitutions, phonetic corrections, and casing rules."""

    def __init__(self, filepath: Path = DICTIONARY_FILE):
        self.filepath = Path(filepath)
        self.words: Dict[str, str] = {}
        self.patterns: List[Dict[str, str]] = []
        self._compiled_regexes: List[Tuple[re.Pattern, str]] = []
        self.load()

    def load(self) -> None:
        """Load dictionary from disk."""
        if not self.filepath.exists():
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            self._save_defaults()

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.words = data.get("words", {})
                self.patterns = data.get("patterns", [])
                self._recompile()
        except Exception as e:
            logger.error(f"Failed to load dictionary from {self.filepath}: {e}")
            self.words = {}
            self.patterns = []

    def save(self) -> bool:
        """Persist dictionary to disk."""
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "version": "1.0",
                        "words": self.words,
                        "patterns": self.patterns,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
            self._recompile()
            return True
        except Exception as e:
            logger.error(f"Failed to save dictionary: {e}")
            return False

    def _save_defaults(self) -> None:
        default_data = {
            "version": "1.0",
            "words": {
                "fast api": "FastAPI",
                "fastapi": "FastAPI",
                "git hub": "GitHub",
                "github": "GitHub",
                "open ai": "OpenAI",
                "openai": "OpenAI",
                "whisper": "Whisper",
                "wispr flow": "Wispr Flow",
                "docker compose": "docker-compose",
                "k eight s": "k8s",
                "kubernetes": "Kubernetes",
                "typescript": "TypeScript",
                "javascript": "JavaScript",
                "async await": "async/await",
                "next js": "Next.js",
                "echoscribe": "EchoScribe",
                "echo scribe": "EchoScribe",
                "bridgemind": "BridgeMind",
                "bridge mind": "BridgeMind",
                "tauri": "Tauri",
            },
            "patterns": [
                {
                    "pattern": r"\bcamel\s+case\s+([a-zA-Z0-9_ ]+)\b",
                    "action": "camelCase",
                },
                {
                    "pattern": r"\bsnake\s+case\s+([a-zA-Z0-9_ ]+)\b",
                    "action": "snake_case",
                },
                {
                    "pattern": r"\bkebab\s+case\s+([a-zA-Z0-9_ ]+)\b",
                    "action": "kebab-case",
                },
            ],
        }
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=2)

    def _recompile(self) -> None:
        """Compile regexes sorted by length (longer phrases first to avoid greedy collision)."""
        self._compiled_regexes = []
        # Sort words by length descending so multi-word terms match before single words
        sorted_keys = sorted(self.words.keys(), key=lambda k: len(k), reverse=True)
        for key in sorted_keys:
            val = self.words[key]
            pattern_str = r"\b" + re.escape(key) + r"\b"
            try:
                rx = re.compile(pattern_str, re.IGNORECASE)
                self._compiled_regexes.append((rx, val))
            except Exception as e:
                logger.warning(f"Invalid regex for word '{key}': {e}")

    def add_word(self, spoken_phrase: str, replacement: str) -> bool:
        """Add or update a dictionary word mapping."""
        clean_key = spoken_phrase.strip().lower()
        clean_val = replacement.strip()
        if not clean_key or not clean_val:
            return False
        self.words[clean_key] = clean_val
        return self.save()

    def remove_word(self, spoken_phrase: str) -> bool:
        """Remove a dictionary mapping."""
        clean_key = spoken_phrase.strip().lower()
        if clean_key in self.words:
            del self.words[clean_key]
            return self.save()
        return False

    def get_all(self) -> Dict[str, Any]:
        """Return words and patterns."""
        return {
            "count": len(self.words),
            "words": self.words,
            "patterns": self.patterns,
        }

    def apply(self, text: str) -> Dict[str, Any]:
        """Apply all dictionary rules and casing macros to the raw transcript."""
        if not text:
            return {"original": "", "corrected": "", "replacements": []}

        corrected = text
        replacements_applied: List[Dict[str, str]] = []

        # 1. Apply multi-word & single-word dictionary mapping
        for rx, replacement in self._compiled_regexes:
            if rx.search(corrected):
                matched = rx.findall(corrected)
                for m in set(matched):
                    replacements_applied.append(
                        {"from": m, "to": replacement, "type": "dictionary"}
                    )
                corrected = rx.sub(replacement, corrected)

        # 2. Apply code casing transformation voice macros
        # camel case foo bar -> fooBar
        def _to_camel(m):
            words = m.group(1).strip().split()
            if not words:
                return ""
            res = words[0].lower() + "".join(w.capitalize() for w in words[1:])
            replacements_applied.append(
                {"from": m.group(0), "to": res, "type": "casing_macro"}
            )
            return res

        # snake case foo bar -> foo_bar
        def _to_snake(m):
            words = m.group(1).strip().split()
            res = "_".join(w.lower() for w in words)
            replacements_applied.append(
                {"from": m.group(0), "to": res, "type": "casing_macro"}
            )
            return res

        # kebab case foo bar -> foo-bar
        def _to_kebab(m):
            words = m.group(1).strip().split()
            res = "-".join(w.lower() for w in words)
            replacements_applied.append(
                {"from": m.group(0), "to": res, "type": "casing_macro"}
            )
            return res

        corrected = re.sub(
            r"\bcamel\s+case\s+([a-zA-Z0-9_ ]+?)(?=[.,;!?]|$)",
            _to_camel,
            corrected,
            flags=re.IGNORECASE,
        )
        corrected = re.sub(
            r"\bsnake\s+case\s+([a-zA-Z0-9_ ]+?)(?=[.,;!?]|$)",
            _to_snake,
            corrected,
            flags=re.IGNORECASE,
        )
        corrected = re.sub(
            r"\bkebab\s+case\s+([a-zA-Z0-9_ ]+?)(?=[.,;!?]|$)",
            _to_kebab,
            corrected,
            flags=re.IGNORECASE,
        )

        return {
            "original": text,
            "corrected": corrected.strip(),
            "replacements": replacements_applied,
        }
