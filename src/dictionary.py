"""Correction Dictionary, Tone Transformer, and Snippets Engine for EchoScribe.

Handles domain vocabulary, phonetic normalization, voice casing macros,
custom snippet expansions, and Wispr Flow-style tone styling.
"""
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from .config import DICTIONARY_FILE, SNIPPETS_FILE

logger = logging.getLogger("echoscribe.dictionary")

FILLER_WORDS_PATTERN = re.compile(
    r"\b(um+|uh+|er+|ah+|like,\s*|you know,\s*|basically,\s*|literally,\s*)\b",
    re.IGNORECASE,
)


class CorrectionDictionary:
    """Manages dictionary terms, category tags, snippets, and tone formatting."""

    def __init__(
        self,
        filepath: Path = DICTIONARY_FILE,
        snippets_path: Path = SNIPPETS_FILE,
    ):
        self.filepath = Path(filepath)
        self.snippets_path = Path(snippets_path)
        self.words: Dict[str, Dict[str, str]] = {}  # {phrase: {"replacement": "...", "category": "..."}}
        self.patterns: List[Dict[str, str]] = []
        self.snippets: Dict[str, str] = {}
        self._compiled_regexes: List[Tuple[re.Pattern, str]] = []
        self.load()
        self.load_snippets()

    def load(self) -> None:
        """Load dictionary from disk."""
        if not self.filepath.exists():
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            self._save_defaults()

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_words = data.get("words", {})
                # Normalize schema to support category tags
                normalized = {}
                for k, v in raw_words.items():
                    if isinstance(v, dict):
                        normalized[k] = v
                    else:
                        normalized[k] = {"replacement": str(v), "category": "code"}
                self.words = normalized
                self.patterns = data.get("patterns", [])
                self._recompile()
        except Exception as e:
            logger.error(f"Failed to load dictionary: {e}")
            self.words = {}
            self.patterns = []

    def load_snippets(self) -> None:
        """Load custom text snippets."""
        if not self.snippets_path.exists():
            self._save_default_snippets()
        try:
            with open(self.snippets_path, "r", encoding="utf-8") as f:
                self.snippets = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load snippets: {e}")
            self.snippets = {}

    def _save_default_snippets(self) -> None:
        defaults = {
            "!sign": "Best regards,\nAthul\nLead Engineer",
            "!pr": "### Description\n- Implements speech-to-text integration with dictionary correction.\n\n### Testing\n- Tested with unittest suite.\n- Verified in browser.",
            "!todo": "- [ ] **Action Item**: Implement task and verify against spec.",
            "!bug": "### Bug Report\n**Expected:** Proper audio capture\n**Actual:** Truncated buffer\n**Fix:** Resample to 16kHz mono",
        }
        try:
            self.snippets_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.snippets_path, "w", encoding="utf-8") as f:
                json.dump(defaults, f, indent=2)
            self.snippets = defaults
        except Exception as e:
            logger.error(f"Failed to save default snippets: {e}")

    def _save_defaults(self) -> None:
        default_data = {
            "version": "2.0",
            "words": {
                "fast api": {"replacement": "FastAPI", "category": "code"},
                "fastapi": {"replacement": "FastAPI", "category": "code"},
                "git hub": {"replacement": "GitHub", "category": "tech"},
                "github": {"replacement": "GitHub", "category": "tech"},
                "open ai": {"replacement": "OpenAI", "category": "tech"},
                "openai": {"replacement": "OpenAI", "category": "tech"},
                "whisper": {"replacement": "Whisper", "category": "tech"},
                "wispr flow": {"replacement": "Wispr Flow", "category": "tech"},
                "docker compose": {"replacement": "docker-compose", "category": "code"},
                "k eight s": {"replacement": "k8s", "category": "tech"},
                "kubernetes": {"replacement": "Kubernetes", "category": "tech"},
                "typescript": {"replacement": "TypeScript", "category": "code"},
                "javascript": {"replacement": "JavaScript", "category": "code"},
                "async await": {"replacement": "async/await", "category": "code"},
                "next js": {"replacement": "Next.js", "category": "code"},
                "vue js": {"replacement": "Vue.js", "category": "code"},
                "echoscribe": {"replacement": "EchoScribe", "category": "names"},
                "echo scribe": {"replacement": "EchoScribe", "category": "names"},
                "bridgemind": {"replacement": "BridgeMind", "category": "names"},
                "bridge mind": {"replacement": "BridgeMind", "category": "names"},
                "tauri": {"replacement": "Tauri", "category": "tech"},
                "pydantic": {"replacement": "Pydantic", "category": "code"},
                "uvicorn": {"replacement": "Uvicorn", "category": "code"},
                "pytest": {"replacement": "pytest", "category": "code"},
            },
            "patterns": [
                {"pattern": r"\bcamel\s+case\s+([a-zA-Z0-9_ ]+)\b", "action": "camelCase"},
                {"pattern": r"\bsnake\s+case\s+([a-zA-Z0-9_ ]+)\b", "action": "snake_case"},
                {"pattern": r"\bkebab\s+case\s+([a-zA-Z0-9_ ]+)\b", "action": "kebab-case"},
            ],
        }
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=2)

    def _recompile(self) -> None:
        """Compile regexes for dictionary words, sorting phrases longest first."""
        self._compiled_regexes = []
        sorted_keys = sorted(self.words.keys(), key=lambda k: len(k), reverse=True)
        for key in sorted_keys:
            val_obj = self.words[key]
            replacement = val_obj["replacement"] if isinstance(val_obj, dict) else str(val_obj)
            pattern_str = r"\b" + re.escape(key) + r"\b"
            try:
                rx = re.compile(pattern_str, re.IGNORECASE)
                self._compiled_regexes.append((rx, replacement))
            except Exception as e:
                logger.warning(f"Invalid regex for word '{key}': {e}")

    def save(self) -> bool:
        """Persist dictionary to disk."""
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "version": "2.0",
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

    def add_word(self, spoken_phrase: str, replacement: str, category: str = "code") -> bool:
        clean_key = spoken_phrase.strip().lower()
        clean_val = replacement.strip()
        if not clean_key or not clean_val:
            return False
        self.words[clean_key] = {"replacement": clean_val, "category": category}
        return self.save()

    def remove_word(self, spoken_phrase: str) -> bool:
        clean_key = spoken_phrase.strip().lower()
        if clean_key in self.words:
            del self.words[clean_key]
            return self.save()
        return False

    def add_snippet(self, trigger: str, expansion: str) -> bool:
        clean_trigger = trigger.strip().lower()
        if not clean_trigger.startswith("!"):
            clean_trigger = "!" + clean_trigger
        self.snippets[clean_trigger] = expansion.strip()
        try:
            with open(self.snippets_path, "w", encoding="utf-8") as f:
                json.dump(self.snippets, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save snippet: {e}")
            return False

    def remove_snippet(self, trigger: str) -> bool:
        clean_trigger = trigger.strip().lower()
        if clean_trigger in self.snippets:
            del self.snippets[clean_trigger]
            try:
                with open(self.snippets_path, "w", encoding="utf-8") as f:
                    json.dump(self.snippets, f, indent=2)
                return True
            except Exception as e:
                logger.error(f"Failed to delete snippet: {e}")
        return False

    def get_all(self) -> Dict[str, Any]:
        flat_words = {}
        for k, v in self.words.items():
            flat_words[k] = v["replacement"] if isinstance(v, dict) else v

        return {
            "count": len(self.words),
            "words": flat_words,
            "words_detailed": self.words,
            "patterns": self.patterns,
            "snippets": self.snippets,
        }

    def apply(
        self,
        text: str,
        tone: str = "clean",
        apply_snippets: bool = True,
    ) -> Dict[str, Any]:
        """Apply all dictionary rules, casing macros, snippets, and tone styling."""
        if not text:
            return {"original": "", "corrected": "", "replacements": [], "tone": tone}

        corrected = text
        replacements_applied: List[Dict[str, str]] = []

        # 0. Raw Verbatim Mode (bypass all processing)
        if tone == "raw":
            return {
                "original": text,
                "corrected": text,
                "replacements": [],
                "tone": "raw",
            }

        # 1. Expand Snippets (e.g. !sign, !pr)
        if apply_snippets:
            for trigger, expansion in self.snippets.items():
                if trigger in corrected.lower():
                    rx = re.compile(re.escape(trigger), re.IGNORECASE)
                    corrected = rx.sub(expansion, corrected)
                    replacements_applied.append(
                        {"from": trigger, "to": "[Snippet Expansion]", "type": "snippet"}
                    )

        # 2. Apply dictionary word substitutions
        for rx, replacement in self._compiled_regexes:
            if rx.search(corrected):
                matched = rx.findall(corrected)
                for m in set(matched):
                    replacements_applied.append(
                        {"from": m, "to": replacement, "type": "dictionary"}
                    )
                corrected = rx.sub(replacement, corrected)

        # 3. Apply casing macros (camelCase, snake_case, kebab-case)
        def _to_camel(m):
            words = m.group(1).strip().split()
            if not words:
                return ""
            res = words[0].lower() + "".join(w.capitalize() for w in words[1:])
            replacements_applied.append(
                {"from": m.group(0), "to": res, "type": "casing_macro"}
            )
            return res

        def _to_snake(m):
            words = m.group(1).strip().split()
            res = "_".join(w.lower() for w in words)
            replacements_applied.append(
                {"from": m.group(0), "to": res, "type": "casing_macro"}
            )
            return res

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

        # 4. Apply Tone Transformations (Wispr Flow Styles)
        if tone == "clean":
            # Remove filler words and fix whitespace/capitalization
            corrected = FILLER_WORDS_PATTERN.sub("", corrected)
            corrected = re.sub(r"\s+", " ", corrected).strip()
            if corrected and corrected[0].islower():
                corrected = corrected[0].upper() + corrected[1:]
            if corrected and corrected[-1] not in ".!?`)]}":
                corrected += "."

        elif tone == "professional":
            corrected = FILLER_WORDS_PATTERN.sub("", corrected)
            corrected = re.sub(r"\s+", " ", corrected).strip()
            # Polish common casual terms into executive language
            prof_replacements = {
                r"\bgonna\b": "going to",
                r"\bwanna\b": "wish to",
                r"\bgotta\b": "need to",
                r"\bkinda\b": "somewhat",
                r"\byeah\b": "yes",
                r"\bhey\b": "Greetings",
            }
            for pattern, repl in prof_replacements.items():
                corrected = re.sub(pattern, repl, corrected, flags=re.IGNORECASE)
            if corrected and corrected[0].islower():
                corrected = corrected[0].upper() + corrected[1:]
            if corrected and corrected[-1] not in ".!?":
                corrected += "."

        elif tone == "bullets":
            # Break sentences or list items into clear bullet points
            sentences = [s.strip() for s in re.split(r"[.!?\n]+|\band\s+also\s+|\bnext\s+", corrected) if s.strip()]
            if len(sentences) > 1:
                bullets = [f"- {s[0].upper() + s[1:]}" for s in sentences]
                corrected = "\n".join(bullets)
            else:
                corrected = f"- {corrected}"

        elif tone == "code":
            # Wrap keywords or identifiers in backticks where helpful
            corrected = FILLER_WORDS_PATTERN.sub("", corrected)
            # e.g., "return status code 200"
            corrected = re.sub(r"\b(status\s+code\s+\d+)\b", r"`\1`", corrected, flags=re.IGNORECASE)
            corrected = re.sub(r"\b(GET|POST|PUT|DELETE|PATCH)\b", r"`\1`", corrected)

        return {
            "original": text,
            "corrected": corrected.strip(),
            "replacements": replacements_applied,
            "tone": tone,
        }
