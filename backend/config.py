"""TenderIQ Backend Configuration"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "bidders").mkdir(exist_ok=True)
(DATA_DIR / "reports").mkdir(exist_ok=True)
(DATA_DIR / "uploads").mkdir(exist_ok=True)

# ── Database ─────────────────────────────────────────────────────────────────
# asyncpg driver is required for async SQLAlchemy with PostgreSQL
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:1234@localhost:5432/tenderiq",
)

# ── OCR / AI ─────────────────────────────────────────────────────────────────
TESSERACT_PATH = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
AI_PROVIDER = os.getenv("AI_PROVIDER", "none")
OCR_ENGINE = os.getenv("OCR_ENGINE", "tesseract")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
BORDERLINE_MARGIN = float(os.getenv("BORDERLINE_MARGIN", "0.05"))

# ── LLM Hybrid Extraction (free tier) ────────────────────────────────────────
# Set at least one of these to enable the LLM confidence gateway.

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")


LLM_HIGH_CONF: float = float(os.getenv("LLM_HIGH_CONF", "0.85"))
LLM_MED_CONF: float = float(os.getenv("LLM_MED_CONF", "0.60"))
