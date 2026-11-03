"""FINN Pull API on Vercel (BUILD_PLAN §4.3, Phase 2 endpoints).

POST /research/{symbol}          number cards now (cached 24 h; ?refresh=1 rebuilds)
GET  /research/{symbol}          the ResearchPayload so far
POST /research/{symbol}/ingest   fetch transcripts + annual report; resumable, call until done=true
GET  /receipt?symbol=&citation_id=   the table row behind a number
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from finn.pull import bundle, run
from finn.sources.fetchers import SourceError

logging.basicConfig(level=logging.INFO)
VERSION = "phase2"
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
    return bundle.ingest(symbol.upper(), budget_s=float(os.getenv("FINN_INGEST_BUDGET", "200")))


@app.get("/receipt")
def receipt(symbol: str = Query(...), citation_id: str = Query(...)):
    r = run.receipt(symbol, citation_id)
    return r or err(404, "unknown_citation", f"No source found for {citation_id}.")
