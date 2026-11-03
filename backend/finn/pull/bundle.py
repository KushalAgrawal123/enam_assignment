"""Primary documents for Pull: concall transcripts and the latest annual report's key sections, stored in `docs`.

Stage 1 (seconds): the screener page -> number cards; the parsed page itself is stored as kind 'screener' so
receipts and ingestion can reuse it without re-fetching.
Stage 2 (up to minutes, resumable): download PDFs, extract text per page, flag scanned ones, keep AR sections.
"""
from __future__ import annotations

import logging
import time

from psycopg.types.json import Jsonb

from .. import db
from ..sources import fetchers

log = logging.getLogger("finn.bundle")
MAX_TRANSCRIPTS = 6
OCR_MIN_CHARS = 300            # average characters per page below this means a scanned PDF
AR_STOP = ("corporate governance", "business responsibility", "report on corporate", "directors' report",
           "board's report", "independent auditor")


def screener_url(symbol: str) -> str:
    return f"https://www.screener.in/company/{symbol}/"


def save_screener(symbol: str, bundle: dict) -> None:
    db.upsert("docs", [dict(url=screener_url(symbol), symbol=symbol, kind="screener", period=bundle.get("basis"),
                            pages=Jsonb([]), sections=Jsonb(bundle))], key=["url"])


def load_screener(symbol: str) -> dict | None:
    rows = db.select("select sections from docs where url = %s", (screener_url(symbol),))
    return rows[0]["sections"] if rows else None


def wanted_docs(bundle: dict) -> list[dict]:
    seen: set[str] = set()
    docs = []
    for c in bundle["documents"]["concalls"]:      # newest first; companies sometimes link one PDF twice
        if c.get("transcript") and c["transcript"] not in seen and len(docs) < MAX_TRANSCRIPTS:
            seen.add(c["transcript"])
            docs.append({"kind": "transcript", "url": c["transcript"], "period": c["period"]})
    ar = next((a for a in bundle["documents"]["annual_reports"] if a.get("url")), None)
    if ar:
        docs.append({"kind": "annual_report", "url": ar["url"], "period": ar.get("year")})
    return docs


def ar_sections(pages: list[str]) -> dict[str, list[int]]:
    """Locate MD&A and segment pages in an annual report (1-based page numbers)."""
    heads = [" ".join(p[:600].lower().split()) for p in pages]

    def is_contents(i: int) -> bool:       # the contents page names every section, MD&A included
        low = pages[i].lower()
        return "contents" in heads[i] or sum(s in low for s in AR_STOP + ("financial statements", "notice")) >= 3

    # MD&A pages carry the section name as a running header/footer; other sections only cross-reference it.
    # So: every page that mentions it (minus the contents page), then the longest near-contiguous run.
    hits = [i for i, p in enumerate(pages) if "management discussion" in p.lower() and not is_contents(i)]
    runs: list[list[int]] = []
    for i in hits:
        if runs and i - runs[-1][-1] <= 2:
            runs[-1].append(i)
        else:
            runs.append([i])
    best = max(runs, key=len) if runs else []
    if len(best) >= 3:
        mdna = list(range(best[0] + 1, best[-1] + 2))
    elif hits:                              # no running header: the opening page and what follows it
        start, mdna = hits[0], []
        for i in range(start, min(start + 40, len(pages))):
            if i > start + 2 and any(s in heads[i][:200] for s in AR_STOP):
                break
            mdna.append(i + 1)
    else:
        mdna = []
    segments = [i + 1 for i, p in enumerate(pages)
                if any(k in p.lower() for k in ("operating segment", "segment information", "segment reporting"))][:8]
    return {"mdna": mdna[:60], "segments": segments}


def ingest_one(symbol: str, d: dict) -> dict:
    pages = [p.replace("\x00", "") for p in fetchers.pdf_pages(d["url"])]
    avg = sum(len(p.strip()) for p in pages) / max(1, len(pages))
    sections = None
    if d["kind"] == "annual_report":
        sections = ar_sections(pages)
        keep = set(sections["mdna"] + sections["segments"])
        pages = [p if i + 1 in keep else "" for i, p in enumerate(pages)]   # store only what Pull reads
    row = dict(url=d["url"], symbol=symbol, kind=d["kind"], period=d["period"], pages=Jsonb(pages),
               sections=Jsonb(sections) if sections else None,
               ocr_needed=avg < OCR_MIN_CHARS)
    db.upsert("docs", [row], key=["url"])
    return {"kind": d["kind"], "period": d["period"], "pages": len(pages), "ocr_needed": row["ocr_needed"],
            "sections": {k: len(v) for k, v in (sections or {}).items()}}


def ingest(symbol: str, budget_s: float = 240) -> dict:
    """Fetch the documents not yet stored, oldest-first within the budget. Safe to call repeatedly."""
    bundle = load_screener(symbol)
    if not bundle:
        return {"done": False, "error": "run the number cards first"}
    want = wanted_docs(bundle)
    have = {r["url"] for r in db.select("select url from docs where symbol = %s", (symbol,))}
    todo = [d for d in want if d["url"] not in have]
    t0, done, failed, processed = time.time(), [], [], set()
    for d in todo:
        if time.time() - t0 > budget_s:
            break
        processed.add(d["url"])
        try:
            done.append(ingest_one(symbol, d))
        except Exception as e:  # one bad PDF must not block the rest
            log.warning("ingest %s %s: %s", symbol, d["url"], e)
            failed.append({"url": d["url"], "error": str(e)[:200]})
            db.upsert("docs", [dict(url=d["url"], symbol=symbol, kind=d["kind"], period=d["period"], pages=Jsonb([]),
                                    sections=Jsonb({"error": str(e)[:200]}))], key=["url"])
    return {"done": len(processed) == len(todo), "ingested": done, "failed": failed}


def doc_status(symbol: str) -> dict:
    rows = db.select("""select kind, period, ocr_needed, jsonb_array_length(pages) n,
                               coalesce(sections ? 'error', false) failed
                        from docs where symbol = %s and kind <> 'screener'""", (symbol,))
    bundle = load_screener(symbol)
    want = len(wanted_docs(bundle)) if bundle else 0
    ok = [r for r in rows if not r["failed"]]
    return {"transcripts": sum(1 for r in ok if r["kind"] == "transcript"),
            "annual_report": next((r["period"] for r in ok if r["kind"] == "annual_report"), None),
            "ocr_needed": sum(1 for r in ok if r["ocr_needed"]), "failed": sum(1 for r in rows if r["failed"]),
            "pending": max(0, want - len(rows))}
