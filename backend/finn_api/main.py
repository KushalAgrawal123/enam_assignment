"""FINN Pull API on Vercel (BUILD_PLAN §4.3, Phase 2 endpoints).

POST /research/{symbol}          number cards now (cached 24 h; ?refresh=1 rebuilds)
GET  /research/{symbol}          the ResearchPayload so far
POST /research/{symbol}/ingest   fetch transcripts + annual report; resumable, call until done=true.
                                 When the documents are all in, it runs the analysis cards too.
POST /research/{symbol}/analyse  (re)build guidance, ledger, narrative, snapshot, bull/bear, verdict
GET  /receipt?symbol=&citation_id=[&q=]   the table row or document page behind a number or claim
POST /ask                        Ask FINN, grounded in the company's own documents (token required)
"""
from __future__ import annotations

import logging
import os

from fastapi import Body, FastAPI, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from finn import db
from finn.pull import ask as ask_mod
from finn.pull import bundle, run
from finn.sources.fetchers import SourceError

logging.basicConfig(level=logging.INFO)
VERSION = "phase5"
app = FastAPI(title="FINN Pull API", version=VERSION)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in os.getenv("FINN_WEB_ORIGINS", "*").split(",") if o.strip()],
                   allow_methods=["GET", "POST", "PUT"], allow_headers=["*"])


def err(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse({"error": code, "detail": detail}, status_code=status)


@app.get("/health")
def health():
    return {"ok": True, "version": VERSION}


@app.post("/research/{symbol}")
def start(symbol: str, refresh: int = 0):
    try:
        return run.build_numbers(symbol, refresh=bool(refresh))
    except run.UnknownSymbol:
        return err(404, "unknown_symbol", f"{symbol.upper()} is not an NSE-listed equity symbol.")
    except SourceError as e:
        return err(502, "source_unavailable", str(e))


@app.get("/research/{symbol}")
def get(symbol: str):
    p = run.payload(symbol)
    return p or err(404, "not_started", f"No research for {symbol.upper()} yet. POST /research/{symbol.upper()} first.")


@app.post("/research/{symbol}/ingest")
def ingest(symbol: str):
    s = symbol.upper()
    out = bundle.ingest(s, budget_s=float(os.getenv("FINN_INGEST_BUDGET", "200")))
    if out.get("done"):
        out["analysis"] = run.build_analysis(s)
    return out


@app.post("/research/{symbol}/analyse")
def analyse(symbol: str, refresh: int = 0):
    out = run.build_analysis(symbol.upper(), refresh=bool(refresh))
    return err(409, "not_started", out["error"]) if out.get("error") else out


@app.get("/receipt")
def receipt(symbol: str = Query(...), citation_id: str = Query(...), q: str | None = Query(default=None)):
    r = run.receipt(symbol, citation_id, q)
    return r or err(404, "unknown_citation", f"No source found for {citation_id}.")


@app.post("/ask")
def ask(body: dict = Body(...), x_finn_token: str | None = Header(default=None)):
    if not authorised(x_finn_token):
        return err(401, "unauthorised", "Missing or wrong X-FINN-Token.")
    symbol, question = str(body.get("symbol") or "").upper(), str(body.get("question") or "").strip()
    if not symbol or not question or len(question) > 500:
        return err(400, "bad_request", "Send a symbol and a question of at most 500 characters.")
    return ask_mod.ask(symbol, question, body.get("context") or {})


# ---- writes (Phase 3): shared-token auth, adequate for a single-user demo (BUILD_PLAN §3) -------------------

SETTINGS_FIELDS = {"vol_multiple": float, "vol_lookback": int, "min_avg_volume": float, "price_move_pct": float,
                   "relative_to_index": bool, "alert_categories": list, "min_category_tier": str,
                   "overrides": dict, "weights": dict}
LIMITS = {"vol_multiple": (1.0, 20), "vol_lookback": (5, 120), "min_avg_volume": (0, 1e9), "price_move_pct": (0.5, 50)}


def authorised(token: str | None) -> bool:
    expected = os.getenv("FINN_API_TOKEN")
    return bool(expected) and token == expected


@app.get("/settings")
def get_settings():
    s = db.settings()
    return {k: (float(v) if hasattr(v, "is_finite") else v) for k, v in s.items() if k != "updated_at"}


@app.put("/settings")
def put_settings(patch: dict = Body(...), x_finn_token: str | None = Header(default=None)):
    if not authorised(x_finn_token):
        return err(401, "unauthorised", "Missing or wrong X-FINN-Token.")
    clean = {}
    for k, v in patch.items():
        if k not in SETTINGS_FIELDS:
            return err(400, "bad_field", f"Unknown setting {k}.")
        try:
            v = SETTINGS_FIELDS[k](v) if SETTINGS_FIELDS[k] in (float, int, bool, str) else v
        except (TypeError, ValueError):
            return err(400, "bad_value", f"{k} must be {SETTINGS_FIELDS[k].__name__}.")
        if not isinstance(v, SETTINGS_FIELDS[k]):
            return err(400, "bad_value", f"{k} must be {SETTINGS_FIELDS[k].__name__}.")
        if k in LIMITS and not (LIMITS[k][0] <= v <= LIMITS[k][1]):
            return err(400, "out_of_range", f"{k} must be between {LIMITS[k][0]:g} and {LIMITS[k][1]:g}.")
        clean[k] = db.Jsonb(v) if isinstance(v, dict) else v
    if clean:
        sets = ", ".join(f"{k} = %s" for k in clean)
        db.execute(f"update settings set {sets}, updated_at = now() where id = 1", list(clean.values()))
    return get_settings()


@app.post("/alerts/{alert_id}/seen")
def alert_seen(alert_id: int, x_finn_token: str | None = Header(default=None)):
    if not authorised(x_finn_token):
        return err(401, "unauthorised", "Missing or wrong X-FINN-Token.")
    db.execute("update alerts set seen = true where id = %s", (alert_id,))
    return {"ok": True}
