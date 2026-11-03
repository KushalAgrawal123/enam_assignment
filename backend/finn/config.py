"""Environment, company universe and defaults. Secrets come from finn/.env (never printed)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]          # finn/
load_dotenv(ROOT / ".env")

# Database: SUPABASE_DB_URL in production; local Postgres for development.
DB_URL = os.getenv("FINN_DB_URL") or os.getenv("SUPABASE_DB_URL") or "postgresql:///finn_dev"

# LLM routing (PLAN Delta 4). Prices are ₹ per million tokens; 0 means free tier.
CHEAP_MODEL = os.getenv("FINN_CHEAP_MODEL", "gemini-2.5-flash")
STRONG_MODEL = os.getenv("FINN_STRONG_MODEL", "claude-sonnet-5")
PROMPT_VERSION = os.getenv("FINN_PROMPT_VERSION", "v1")
# ₹ per million tokens (input, output) at ₹88/US$: Gemini 2.5 Flash $0.30/$2.50, Claude Sonnet 5 $2/$10.
PRICE_INR = {
    "cheap": (float(os.getenv("FINN_CHEAP_IN", "26.4")), float(os.getenv("FINN_CHEAP_OUT", "220"))),
    "strong": (float(os.getenv("FINN_STRONG_IN", "176")), float(os.getenv("FINN_STRONG_OUT", "880"))),
}
CACHE_DIR = Path(os.getenv("FINN_CACHE", ROOT / ".cache"))

# Filing feeds. BSE refuses automated requests (docs/sources.md); NSE is the primary feed.
USE_NSE = os.getenv("FINN_USE_NSE", "1") == "1"
USE_BSE = os.getenv("FINN_USE_BSE", "0") == "1"

# Portfolio (19) and research set (5), approved 3 Nov 2026 (PLAN.md "Companies").
PORTFOLIO = [
    "RELIANCE", "ICICIBANK", "BAJFINANCE", "INFY", "BHARTIARTL", "LT", "MARUTI", "SUNPHARMA", "ITC",
    "TITAN", "ETERNAL", "TRENT", "BEL", "DIXON", "POLYCAB", "PERSISTENT", "SUZLON", "NAZARA", "RATEGAIN",
]
RESEARCH = ["BEL", "POLYCAB", "PERSISTENT", "KPITTECH", "HCLTECH"]
FINANCIALS = {"ICICIBANK", "BAJFINANCE", "HDFCBANK"}
INDEX_TICKER = "^NSEI"                               # NIFTY 50, for relative moves

IST_OFFSET_MIN = 330
