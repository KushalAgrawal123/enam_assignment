"""Research job (BUILD_PLAN §6.2): validate -> number cards -> documents -> analysis.

Number cards are built synchronously (a screener fetch plus arithmetic, ~1–3 s). Document ingestion is a
separate, resumable call, because an annual report can take a minute to download and read. Analysis
(guidance, ledger, narrative, snapshot, bull/bear, verdict) runs once the documents are in.
Results are reused for 24 hours unless refresh=True.
"""
from __future__ import annotations

import datetime as dt
import difflib
import logging
import re

from .. import config, db, llm
from ..sources import fetchers
from . import bullbear, claims, guidance, ledger, narrative, snapshot
from . import bundle as docs
from . import calls as C
from .chunks import call_key
from .numbers import Tables, looks_financial, number_cards

log = logging.getLogger("finn.run")
FRESH = dt.timedelta(hours=24)
NUMBER_CARDS = ["financials", "trajectory", "balance_sheet", "cash_quality"]
ANALYSIS_CARDS = ["guidance", "ledger", "narrative", "snapshot", "bull_bear", "verdict"]


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
                                gaps=c["gaps"], prompt_version="numbers-v1", updated_at=dt.datetime.now(dt.timezone.utc))
                           for c in cards.values()],
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
    ready = all(cards.get(c, {}).get("status") in ("ready", "gap", "failed") for c in NUMBER_CARDS)
    analysed = "verdict" in cards
    return {"symbol": s, "name": comp[0]["name"] if comp else s, "basis": screener.get("basis"),
            "is_financial": bool(comp and comp[0]["is_financial"]),
            "as_of": max(r["updated_at"] for r in rows).astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "ready" if ready and analysed and not status["pending"] else "partial" if ready else "running",
            "cards": cards, "documents": status, "gaps": []}


# ---- stage 2: analysis (Phase 4) ---------------------------------------------------------------------------

def _card(cid: str, data, citations=None, gaps=None, status=None) -> dict:
    return {"id": cid, "status": status or ("ready" if data else "gap"), "data": data,
            "citations": citations or [], "gaps": gaps or []}


def analysed_fresh(symbol: str) -> bool:
    rows = db.select("select updated_at from analyses where symbol = %s and card = 'verdict'", (symbol,))
    newest_doc = db.select("select max(fetched_at) t from docs where symbol = %s and kind = 'transcript'", (symbol,))
    if not rows:
        return False
    t = rows[0]["updated_at"]
    return dt.datetime.now(dt.timezone.utc) - t < FRESH and not (newest_doc and newest_doc[0]["t"] and newest_doc[0]["t"] > t)


def build_analysis(symbol: str, refresh: bool = False) -> dict:
    """Guidance -> ledger -> narrative -> snapshot -> bull/bear -> verdict. Each card degrades on its own."""
    s = symbol.upper()
    if not refresh and analysed_fresh(s):
        return {"skipped": "fresh", "llm_calls": 0}
    before = dict(llm.CALLS)
    comp = db.select("select name, is_financial from companies where symbol = %s", (s,))
    bundle = docs.load_screener(s)
    if not comp or not bundle:
        return {"error": "run the number cards first"}
    name, fin = comp[0]["name"], bool(comp[0]["is_financial"])
    t = Tables(bundle)
    cards: dict[str, dict] = {r["id"]: r for r in
                              db.select("select card id, status, data, citations, gaps from analyses where symbol = %s", (s,))}
    out: dict[str, dict] = {}
    calls = C.load_calls(s, limit=4)
    recent = [c for c in calls if (dt.date.today() - c["date"]).days <= 400]
    if not recent:
        why = ("No concall transcripts filed in the last 12 months." if not calls else
               f"No concall transcript in the last 12 months; the latest on file is {calls[-1]['period']}.")
        for cid in ("guidance", "ledger", "narrative"):
            out[cid] = _card(cid, None, gaps=[why])
    else:
        per_call, all_claims, methods = [], [], set()
        for c in recent:
            g, m1 = guidance.extract(c, name)
            cl, m2 = claims.extract(c, name)
            per_call.append((c, g))
            all_claims += cl
            methods |= {m1, m2}
        latest_call, latest = per_call[-1]
        doc_cites = {}
        for c, items in per_call:
            for g in items:
                doc_cites[g["citation"]] = {"id": g["citation"], "kind": "transcript", "doc_url": c["url"],
                                            "period": c["period"], "page": g.get("page"), "quote": g["quote"]}
        for cl in all_claims:
            c = next(x for x in recent if cl["citation"].startswith(f"T{x['key']}-"))
            doc_cites[cl["citation"]] = {"id": cl["citation"], "kind": "transcript", "doc_url": c["url"],
                                         "period": c["period"], "page": cl.get("page"), "quote": cl["quote"]}
        method = "model" if methods == {"model"} else "rules"
        gdata = {"call": latest_call["period"], "items": latest, "method": method} if latest else None
        out["guidance"] = _card("guidance", gdata, [doc_cites[g["citation"]] for g in latest],
                                gaps=[] if latest else [f"No numeric guidance found on the {latest_call['period']} call."])
        led = ledger.build(per_call, t, fin, name)
        lc = led.pop("citations")
        out["ledger"] = _card("ledger", led if led["items"] else None, lc,
                              gaps=[] if led["items"] else ["No numeric guidance found in the last four calls."])
        nar = narrative.build(all_claims, t, name, doc_cites)
        nc = nar.pop("citations")
        out["narrative"] = _card("narrative", nar if nar["rows"] else None, nc,
                                 gaps=[] if nar["rows"] else ["No claims on the calls could be tested against the tables."])
    snap, sc, sg = snapshot.build(s, name)
    out["snapshot"] = _card("snapshot", snap, sc, sg)
    merged = {**cards, **out}
    bb = bullbear.build(merged, name, fin)
    known = {c["id"]: c for v in merged.values() if v for c in (v.get("citations") or [])}
    bb_ids = {i for side in ("bull", "bear") for p in bb[side] for i in p["citations"]}
    out["bull_bear"] = _card("bull_bear", bb if bb["bull"] or bb["bear"] else None,
                             [known[i] for i in sorted(bb_ids) if i in known],
                             gaps=[] if bb["bull"] or bb["bear"] else ["Not enough finished cards to argue either side."])
    merged["bull_bear"] = out["bull_bear"]
    v = bullbear.verdict(merged, name)
    calls_made = {k: llm.CALLS[k] - before[k] for k in before}
    v["llm_calls"] = calls_made
    out["verdict"] = _card("verdict", v)
    db.upsert("analyses", [dict(symbol=s, card=c["id"], status=c["status"], data=db.Jsonb(c["data"]) if c["data"] else None,
                                citations=db.Jsonb(c["citations"]), gaps=c["gaps"],
                                prompt_version=f"{config.PROMPT_VERSION}-{(c['data'] or {}).get('method', 'rules')}",
                                updated_at=dt.datetime.now(dt.timezone.utc))
                           for c in out.values()], key=["symbol", "card"])
    log.info("analysis %s: %s, llm calls %s", s, {k: v["status"] for k, v in out.items()}, calls_made)
    return {"cards": {k: v["status"] for k, v in out.items()}, "llm_calls": calls_made}


_TBL = re.compile(r"^TBL-(profit-loss|balance-sheet|cash-flow|quarters|ratios|top)-(.+)-(\d{4}-\d{2}-\d{2}|TTM|current)$")


_DOC = re.compile(r"^(?:T(\d{4}-\d{2}|\w+)|AR(\w+))-p(\d+)(?:-\d+)?$")


def highlight(text: str, quote: str | None) -> list[int] | None:
    """[start, end] of the quote in the page text: exact, then on its opening words, then the closest block."""
    if not quote:
        return None
    q = quote.replace(" …", "").strip()
    low = text.lower()
    i = low.find(q.lower())
    if i >= 0:
        return [i, i + len(q)]
    head = " ".join(q.split()[:8]).lower()
    i = low.find(head)
    if i >= 0:
        return [i, min(len(text), i + len(q))]
    m = difflib.SequenceMatcher(None, low, q.lower(), autojunk=False).find_longest_match(0, len(low), 0, len(q))
    if m.size >= 25:
        start = max(0, m.a - m.b)
        return [start, min(len(text), start + len(q))]
    return None


def doc_receipt(symbol: str, citation_id: str, quote: str | None = None) -> dict | None:
    m = _DOC.match(citation_id)
    if not m:
        return None
    key, year, page = m.group(1), m.group(2), int(m.group(3))
    kind = "transcript" if key else "annual_report"
    rows = db.select("select url, period from docs where symbol = %s and kind = %s", (symbol.upper(), kind))
    doc = next((r for r in rows if (call_key(r["period"]) == key if key else str(r["period"]) == year)), None)
    if not doc or page < 1:
        return None
    got = db.select("select pages ->> %s as text from docs where url = %s", (page - 1, doc["url"]))  # one page only
    if not got or got[0]["text"] is None:
        return None
    text = " ".join(got[0]["text"].split())
    return {"kind": kind, "doc_url": doc["url"], "period": doc["period"], "page": page, "text": text,
            "highlight": highlight(text, quote), "citation_id": citation_id}


def receipt(symbol: str, citation_id: str, quote: str | None = None) -> dict | None:
    """Table receipt: the whole row the number came from, with the cited cell marked. Document ids return the page."""
    if not citation_id.startswith("TBL-"):
        return doc_receipt(symbol, citation_id, quote)
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
