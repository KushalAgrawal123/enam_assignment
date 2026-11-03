"""Ask FINN (BUILD_PLAN §5 P13): BM25 over the company's cached transcript and annual-report text, plus table rows.

With a cheap-tier key, P13 writes an answer of at most 80 words from the top excerpts (number-checked).
Without one, the answer is extractive: the best-matching management sentences, quoted verbatim with their
sources. Either way, a question the sources don't cover returns not_found and says what's missing.
"""
from __future__ import annotations

import logging
import math
import re
import time
from collections import Counter

from .. import db, llm
from . import bundle as docs
from . import calls as C
from . import numcheck
from .chunks import ar_chunks
from .guidance import clean
from .numbers import Tables
from .prompts import P13_SYSTEM, P13_USER

log = logging.getLogger("finn.ask")
STOP = set("""a an the of to in on for and or is are was were be been it its this that what which who whom how why when
where did does do has have had with by at from as about over our their they them you your we i me my can could would
should will shall may might much many more most any some there here than then so if not no yes management company
companies tell say said give gave""".split())
FORWARD_Q = re.compile(r"\b(guid\w*|outlook|expect\w*|target\w*|plan\w*|forecast\w*|aim\w*|aspir\w*)\b", re.I)
TABLE_WORDS = {"revenue": ("profit-loss", "Sales"), "sales": ("profit-loss", "Sales"), "margin": ("profit-loss", "OPM %"),
               "opm": ("profit-loss", "OPM %"), "profit": ("profit-loss", "Net Profit"), "pat": ("profit-loss", "Net Profit"),
               "debt": ("balance-sheet", "Borrowings"), "borrowing": ("balance-sheet", "Borrowings"),
               "cash": ("cash-flow", "Cash from Operating Activity"), "debtor": ("ratios", "Debtor Days")}


def stem(w: str) -> str:
    w = w.lower()
    for suf in ("ance", "ing", "ed", "es", "s", "e"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def terms(text: str) -> list[str]:
    return [stem(w) for w in re.findall(r"[a-zA-Z][a-zA-Z&]+", text) if w.lower() not in STOP]


class BM25:
    def __init__(self, docs_: list[list[str]], k1: float = 1.4, b: float = 0.75):
        self.docs, self.k1, self.b = docs_, k1, b
        self.avg = sum(map(len, docs_)) / max(1, len(docs_))
        df = Counter(t for d in docs_ for t in set(d))
        n = len(docs_)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in docs_]

    def score(self, q: list[str], i: int) -> float:
        d, tf = self.docs[i], self.tf[i]
        return sum(self.idf.get(t, 0) * tf[t] * (self.k1 + 1) /
                   (tf[t] + self.k1 * (1 - self.b + self.b * len(d) / self.avg)) for t in set(q) if t in tf)


_CACHE: dict[str, tuple[float, list[dict]]] = {}


def passages(symbol: str) -> list[dict]:
    """Management sentences from the last four calls, and the annual report's stored pages (cached 10 min)."""
    hit = _CACHE.get(symbol)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    out = _passages(symbol)
    _CACHE[symbol] = (time.time(), out)
    return out


def _passages(symbol: str) -> list[dict]:
    out = []
    for c in C.load_calls(symbol, limit=4):
        for ch in c["chunks"]:
            if ch.get("speaker") not in c["management"]:
                continue
            for s in C.sentences({"text": clean(ch["text"])}):
                out.append({"id": ch["id"], "kind": "transcript", "period": c["period"], "page": ch["page"],
                            "doc_url": c["url"], "text": s})
    for r in db.select("""select url, period, pages, sections from docs where symbol = %s and kind = 'annual_report'
                          and jsonb_array_length(pages) > 0""", (symbol,)):
        secs = r["sections"] or {}
        for ch in ar_chunks(r["pages"], str(r["period"]), (secs.get("mdna") or []) + (secs.get("segments") or [])):
            for s in C.sentences({"text": ch["text"]}):
                out.append({"id": ch["id"], "kind": "annual_report", "period": str(r["period"]), "page": ch["page"],
                            "doc_url": r["url"], "text": s})
    return out


def table_rows(symbol: str, question: str) -> list[dict]:
    bundle = docs.load_screener(symbol)
    if not bundle:
        return []
    t, rows, q = Tables(bundle), [], {stem(w) for w in re.findall(r"[a-zA-Z]+", question.lower())}
    for word, (section, metric) in TABLE_WORDS.items():
        if stem(word) in q:
            name, periods, vals = t.series(section, metric, "Revenue" if metric == "Sales" else metric)
            pts = [(p, v) for p, v in zip(periods, vals) if v is not None and p != "TTM"][-3:]
            rows += [{"id": t.cite(section, name, p, v), "kind": "table", "metric": name, "period": p, "value": v,
                      "table_ref": {"section": section, "metric": name, "period": p, "value": v}} for p, v in pts]
    return list({r["id"]: r for r in rows}.values())


def ask(symbol: str, question: str, context: dict | None = None) -> dict:
    s = symbol.upper()
    q = terms(question)
    ps = passages(s)
    if not q:
        return {"answer": "Ask about the company's numbers, guidance or what management said.", "citations": [],
                "not_found": True, "method": "rules"}
    if not ps:
        return {"answer": "No call transcripts or annual report are on file for this company yet.", "citations": [],
                "not_found": True, "method": "rules"}
    bm = BM25([terms(p["text"]) for p in ps])
    fwd = bool(FORWARD_Q.search(question))
    scored = []
    for i, p in enumerate(ps):
        sc = bm.score(q, i)
        if fwd and re.search(r"\b(will|expect\w*|guid\w*|target\w*|should|aspir\w*)\b", p["text"], re.I):
            sc *= 1.5
        hits = len(set(q) & set(bm.docs[i]))
        scored.append((sc, hits, i))
    scored.sort(reverse=True)
    pinned = [i for i, p in enumerate(ps) if context and p["id"] == context.get("citation_id")]
    top = pinned[:1] + [i for _, _, i in scored if i not in pinned][:8]
    need = 1 if len(set(q)) == 1 else 2
    best = scored[0]
    if best[1] < need or best[0] < 3.0:
        missing = ", ".join(sorted(set(question.lower().split()) - STOP)[:4])
        return {"answer": f"The calls and annual report on file don't cover this ({missing}).", "citations": [],
                "not_found": True, "method": "rules"}
    excerpts = [ps[i] for i in top]
    rows = table_rows(s, question)
    if llm.available("cheap"):
        comp = db.select("select name from companies where symbol = %s", (s,))
        name = comp[0]["name"] if comp else s
        try:
            out = llm.complete_json("cheap", P13_SYSTEM.format(company=name), P13_USER.format(
                question=question,
                excerpts="\n".join(f"[{e['id']}] ({e['kind']}, {e['period']}, page {e['page']}): {e['text']}" for e in excerpts),
                table_rows="\n".join(f"{r['id']} = {r['value']}" for r in rows) or "none"))
            allowed = numcheck.harvest([e["text"] for e in excerpts]) | numcheck.harvest([r["value"] for r in rows])
            ids = {e["id"]: e for e in excerpts} | {r["id"]: r for r in rows}
            if not numcheck.bad_numbers(out.get("answer") or "", allowed):
                cites = [_cite(ids[c]) for c in out.get("citations") or [] if c in ids]
                return {"answer": out.get("answer") or "", "citations": cites,
                        "not_found": bool(out.get("not_found")), "method": "model"}
            log.warning("P13 answer failed the number check; falling back to quotes")
        except Exception as e:
            log.warning("P13 %s: %s", s, e)
    chosen, seen = [], set()
    for _, hits, i in scored:
        if hits < need or len(chosen) == 3:
            break
        key = ps[i]["text"][:60]
        if key in seen:
            continue
        seen.add(key)
        chosen.append(ps[i])
    answer = " ".join(f"{p['period']}: “{C.quote(p['text'], 40)}”" for p in chosen)
    return {"answer": answer, "citations": [_cite(p) for p in chosen] + [_cite(r) for r in rows[-2:]],
            "not_found": False, "method": "rules"}


def _cite(x: dict) -> dict:
    if x["kind"] == "table":
        return {"id": x["id"], "kind": "table", "table_ref": x["table_ref"]}
    return {"id": x["id"], "kind": x["kind"], "doc_url": x["doc_url"], "period": x["period"], "page": x["page"],
            "quote": C.quote(x["text"])}
