"""Configuration for the SHL Assessment Recommender."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CATALOG_PATH = DATA_DIR / "catalog_clean.json"
INDEX_DIR = DATA_DIR / "catalog_index"

# LLM Provider: "groq" or "gemini"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")

# Groq Configuration (Supports multiple keys separated by commas)
_groq_keys_str = os.environ.get("GROQ_API_KEYS") or os.getenv("GROQ_API_KEYS", "")
GROQ_API_KEYS = [k.strip() for k in _groq_keys_str.split(",") if k.strip()]
if not GROQ_API_KEYS:
    _single_key = os.environ.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY", "")
    if _single_key:
        GROQ_API_KEYS = [_single_key]

GROQ_MODEL = os.environ.get("GROQ_MODEL") or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Gemini Configuration (Supports multiple keys separated by commas)
_gemini_keys_str = os.environ.get("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEYS", "")
GEMINI_API_KEYS = [k.strip() for k in _gemini_keys_str.split(",") if k.strip()]
if not GEMINI_API_KEYS:
    _single_gemini = os.environ.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "")
    if _single_gemini:
        GEMINI_API_KEYS = [_single_gemini]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Retrieval Configuration
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
TOP_K_RETRIEVAL = 20  # Retrieve more, then let LLM rank
MAX_RECOMMENDATIONS = 10
MIN_RECOMMENDATIONS = 1

# Conversation limits
MAX_TURNS = 8  # Total turns including user + assistant
RESPONSE_TIMEOUT = 30  # seconds
