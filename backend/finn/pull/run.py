"""Research job (BUILD_PLAN §6.2), Phase 2 part: validate -> number cards -> documents.

Number cards are built synchronously (a screener fetch plus arithmetic, ~1–3 s). Document ingestion is a
separate, resumable call, because an annual report can take a minute to download and read.
Results are reused for 24 hours unless refresh=True.
"""
from __future__ import annotations

import datetime as dt
import re

from .. import config, db
from ..sources import fetchers
from . import bundle as docs
from .numbers import looks_financial, number_cards

FRESH = dt.timedelta(hours=24)
NUMBER_CARDS = ["financials", "trajectory", "balance_sheet", "cash_quality"]


class UnknownSymbol(ValueError):
    pass


def validate(symbol: str) -> dict:
    eq = fetchers.nse_equity_list()
    s = symbol.upper().strip()
    if s not in eq:
        raise UnknownSymbol(s)
    return {"symbol": s, **eq[s]}


def _fresh(symbol: str) -> bool:
    rows = db.select("select min(updated_at) t, count(*) n from analyses where symbol = %s and card = any(%s)",
                     (symbol, NUMBER_CARDS))
    return bool(rows and rows[0]["n"] == len(NUMBER_CARDS) and
                dt.datetime.now(dt.timezone.utc) - rows[0]["t"] < FRESH)


def build_numbers(symbol: str, refresh: bool = False) -> dict:
    info = validate(symbol)
    s = info["symbol"]
    if not refresh and _fresh(s):
        return payload(s)
    bundle = fetchers.screener_company(s)
    fin = looks_financial(bundle) or s in config.FINANCIALS
    cards = number_cards(bundle, fin)
    docs.save_screener(s, bundle)
    db.upsert("companies", [dict(symbol=s, name=bundle.get("name") or info["name"], isin=info["isin"],
                                 is_financial=fin, mcap_cr=bundle["top"].get("Market Cap"))],
              key=["symbol"], update=["name", "is_financial", "mcap_cr"])
    db.upsert("analyses", [dict(symbol=s, card=c["id"], status=c["status"], data=c["data"], citations=c["citations"],
                                gaps=c["gaps"], prompt_version="numbers-v1") for c in cards.values()],
              key=["symbol", "card"])
    return payload(s)


def payload(symbol: str) -> dict:
    s = symbol.upper()
    comp = db.select("select name, is_financial from companies where symbol = %s", (s,))
    rows = db.select("select card, status, data, citations, gaps, updated_at from analyses where symbol = %s", (s,))
    if not rows:
        return {}
    screener = docs.load_screener(s) or {}
    status = docs.doc_status(s)
    cards = {r["card"]: {"id": r["card"], "status": r["status"], "data": r["data"], "citations": r["citations"] or [],
                         "gaps": r["gaps"] or []} for r in rows}
    ready = all(cards.get(c, {}).get("status") in ("ready", "gap") for c in NUMBER_CARDS)
    return {"symbol": s, "name": comp[0]["name"] if comp else s, "basis": screener.get("basis"),
            "is_financial": bool(comp and comp[0]["is_financial"]),
            "as_of": max(r["updated_at"] for r in rows).astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "ready" if ready and not status["pending"] else "partial" if ready else "running",
            "cards": cards, "documents": status, "gaps": []}


_TBL = re.compile(r"^TBL-(profit-loss|balance-sheet|cash-flow|quarters|ratios|top)-(.+)-(\d{4}-\d{2}-\d{2}|TTM|current)$")


def receipt(symbol: str, citation_id: str) -> dict | None:
    """Table receipt: the whole row the number came from, with the cited cell marked."""
    m = _TBL.match(citation_id)
    bundle = docs.load_screener(symbol.upper())
    if not m or not bundle:
        return None
    section, metric, period = m.groups()
    src = f"https://www.screener.in/company/{symbol.upper()}/" + ("consolidated/" if bundle.get("basis") == "consolidated" else "")
    if section == "top":
        v = bundle["top"].get(metric)
        return {"kind": "table", "doc_url": src, "section": "Key ratios", "metric": metric,
                "periods": ["current"], "values": [v], "highlight": 0, "basis": bundle.get("basis")}
    tab = bundle["tables"].get(section)
    if not tab or metric not in tab["rows"] or period not in tab["periods"]:
        return None
    return {"kind": "table", "doc_url": src + f"#{section}", "section": section, "metric": metric,
            "periods": tab["periods"], "values": tab["rows"][metric], "highlight": tab["periods"].index(period),
            "basis": bundle.get("basis")}
