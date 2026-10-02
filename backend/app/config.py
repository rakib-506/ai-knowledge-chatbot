"""All settings, read from the .env file."""
import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "8"))

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

CHUNK_WORDS = int(os.getenv("CHUNK_WORDS", "180"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "40"))
TOP_K = int(os.getenv("TOP_K", "4"))
MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.25"))
MEMORY_MESSAGES = int(os.getenv("MEMORY_MESSAGES", "6"))
REWRITE_FOLLOWUPS = _bool("REWRITE_FOLLOWUPS", "true")

MAX_UPLOAD_MB = 10
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".html", ".htm"}

DATA_DIR = BACKEND_DIR / "data"                 # SQLite database + vector store
UPLOAD_DIR = DATA_DIR / "uploads"               # copies of uploaded files
LOG_DIR = BACKEND_DIR / "logs"
KNOWLEDGE_DIR = PROJECT_DIR / "knowledge_base"  # starter documents
FRONTEND_DIR = PROJECT_DIR / "frontend"

for d in (DATA_DIR, UPLOAD_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)
