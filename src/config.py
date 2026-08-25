"""Configuration module for EchoScribe."""
import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
DICTIONARY_FILE = DATA_DIR / "dictionary.json"
HISTORY_FILE = DATA_DIR / "history.json"

# Server configuration
HOST = os.getenv("ECHOSCRIBE_HOST", "0.0.0.0")
PORT = int(os.getenv("ECHOSCRIBE_PORT", "8765"))

# Model & Provider configuration
# Supported providers: "sherpa-onnx", "whisper-api", "auto", "mock"
STT_PROVIDER = os.getenv("ECHOSCRIBE_PROVIDER", "auto")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Local Parakeet / Sherpa ONNX Model Directory
LOCAL_PARAKEET_DIR = os.getenv(
    "ECHOSCRIBE_MODEL_DIR",
    os.path.expandvars(r"%LOCALAPPDATA%\Murmur\models\parakeet-v2")
)
