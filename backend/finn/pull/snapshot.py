"""Business snapshot (P6, cheap tier) from the annual report's MD&A and segment pages.

There is no rule path: summarising a business needs a model. Without a key the card is a gap that says so.
"""
from __future__ import annotations

import logging

from .. import db, llm
from .chunks import ar_chunks
from .prompts import P6_SYSTEM, P6_USER

log = logging.getLogger("finn.snapshot")
MAX_CHARS = 60_000


def build(symbol: str, company: str) -> tuple[dict | None, list[dict], list[str]]:
    """(data, citations, gaps)."""
    rows = db.select("""select url, period, pages, sections from docs where symbol = %s and kind = 'annual_report'
                        and jsonb_array_length(pages) > 0 and not coalesce(sections ? 'error', false)""", (symbol,))
    if not rows:
        return None, [], ["No readable annual report on file."]
    ar = rows[0]
    secs = ar["sections"] or {}
    chunks = ar_chunks(ar["pages"], str(ar["period"]), (secs.get("mdna") or []) + (secs.get("segments") or []))
    if not chunks:
        return None, [], ["The annual report's MD&A pages couldn't be located."]
    if not llm.available("cheap"):
        return None, [], ["The business summary needs a model key (GEMINI_API_KEY); every other card is built without one."]
    text, used = "", []
    for c in chunks:
        if len(text) > MAX_CHARS:
            break
        text += f"[{c['id']}] (page {c['page']})\n{c['text']}\n"
        used.append(c)
    try:
        out = llm.complete_json("cheap", P6_SYSTEM, P6_USER.format(company=company, year=ar["period"], excerpts=text))
    except Exception as e:
        log.warning("P6 %s: %s", symbol, e)
        return None, [], ["The business summary couldn't be generated this time."]
    ids = {c["id"]: c for c in used}
    for k in ("segments", "geographies", "key_facts"):
        out[k] = [x for x in out.get(k) or [] if x.get("citation") in ids]
    cites = [{"id": i, "kind": "annual_report", "doc_url": ar["url"], "period": str(ar["period"]), "page": ids[i]["page"]}
             for i in sorted({x["citation"] for k in ("segments", "geographies", "key_facts") for x in out[k]})]
    out["method"] = "model"
    return out, cites, []
