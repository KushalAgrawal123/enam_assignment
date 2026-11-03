"""Narrative vs numbers (BUILD_PLAN §5 P10). Each testable claim is checked against the table that bears on it.

Rule path: code reads the metric's latest value against a year earlier and compares the direction with the
claim's polarity: agrees, diverges, or mixed (flat). With a strong-tier key, P10 writes the rows instead and
the number check strips anything it didn't get from the tables.
"""
from __future__ import annotations

import datetime as dt
import json
import logging

from .. import llm
from . import numcheck
from .numbers import Tables
from .prompts import P10_SYSTEM, P10_USER

log = logging.getLogger("finn.narrative")
# metric -> (section, row names, lower is better, unit, how far back "a year earlier" is in columns)
CHECKS = {
    "OPM %": ("quarters", ("OPM %",), False, "%", 4),
    "Sales growth": ("quarters", ("Sales", "Revenue"), False, "₹ cr", 4),
    "Debtor Days": ("ratios", ("Debtor Days",), True, " days", 1),
    "Cash from Operating Activity": ("cash-flow", ("Cash from Operating Activity",), False, "₹ cr", 1),
    "Borrowings": ("balance-sheet", ("Borrowings",), True, "₹ cr", 1),
}
FLAT = {"%": 0.5, " days": 3}


def label(period: str) -> str:
    try:
        return dt.date.fromisoformat(period).strftime("%b %Y")
    except ValueError:
        return period


def _fmt(v: float, unit: str) -> str:
    if unit == "₹ cr":
        return f"₹{v:,.0f} cr"
    return f"{v:g}{unit}"


def evidence(t: Tables, metric: str) -> dict | None:
    spec = CHECKS.get(metric)
    if not spec:
        return None
    section, names, lower_better, unit, back = spec
    name, periods, vals = t.series(section, *names)
    pts = [(p, v) for p, v in zip(periods, vals) if v is not None and p not in ("TTM",)]
    if not name or len(pts) <= back:
        return None
    (p0, v0), (p1, v1) = pts[-1 - back], pts[-1]
    if metric == "Sales growth" and v0:
        change = (v1 / v0 - 1) * 100
        flat = 2.0
        text = f"Sales {_fmt(v1, unit)} in {label(p1)} vs {_fmt(v0, unit)} a year earlier ({change:+.1f}%)."
    else:
        change = v1 - v0
        flat = FLAT.get(unit, 0.05 * abs(v0) if v0 else 1)
        text = f"{name} {_fmt(v1, unit)} in {label(p1)} vs {_fmt(v0, unit)} a year earlier."
    direction = "flat" if abs(change) <= flat else ("up" if change > 0 else "down")
    good = None if direction == "flat" else (direction == "down") == lower_better
    return {"text": text, "good": good, "citations": [t.cite(section, name, p0, v0), t.cite(section, name, p1, v1)]}


def rule_rows(claims: list[dict], t: Tables) -> list[dict]:
    rows, seen = [], set()
    for c in reversed(claims):             # newest call first; one row per topic
        if c["topic"] in seen:
            continue
        ev = evidence(t, c.get("testable_metric") or "")
        if not ev:
            continue
        seen.add(c["topic"])
        if ev["good"] is None or c["polarity"] == "neutral":
            status = "mixed"
        else:
            status = "agrees" if ev["good"] == (c["polarity"] == "positive") else "diverges"
        rows.append({"topic": c["topic"], "claim": c["claim"], "claim_citation": c["citation"],
                     "evidence": ev["text"], "evidence_citations": ev["citations"], "status": status})
    order = {"diverges": 0, "mixed": 1, "agrees": 2, "untestable": 3}
    return sorted(rows, key=lambda r: order[r["status"]])[:6]


def headline(rows: list[dict]) -> str:
    d = next((r for r in rows if r["status"] == "diverges"), None)
    if d:
        return f"On {d['topic'].replace('_', ' ')}, the tone runs ahead of the numbers."
    return "Narrative broadly matches the numbers." if rows else "No testable claims found."


def build(claims: list[dict], t: Tables, company: str, doc_cites: dict) -> dict:
    rows, method, head = rule_rows(claims, t), "rules", None
    if llm.available("strong") and claims:
        trends = {m: evidence(t, m) for m in CHECKS}
        try:
            out = llm.complete_json("strong", P10_SYSTEM, P10_USER.format(
                company=company, claims_json=json.dumps(claims),
                metric_trends="\n".join(f"{c} = {t.citations[c]['table_ref']['value']}" for c in t.citations)))
            allowed = numcheck.harvest(claims) | numcheck.harvest([x["table_ref"]["value"] for x in t.citations.values()]) \
                | numcheck.harvest(trends)
            kept, dropped = numcheck.filter_items(out.get("rows") or [], ("claim", "evidence"), allowed,
                                                  set(doc_cites) | set(t.citations), label="P10")
            if kept and not numcheck.failed(len(kept), dropped):
                rows, method = kept[:6], "model"
                h = out.get("headline") or ""
                head = h if not numcheck.bad_numbers(h, allowed) else None
        except Exception as e:
            log.warning("P10 %s: %s", company, e)
    used = {c for r in rows for c in r.get("evidence_citations") or []}
    cites = [doc_cites[r["claim_citation"]] for r in rows if r["claim_citation"] in doc_cites] + \
            [t.citations[c] for c in sorted(used) if c in t.citations]
    return {"rows": rows, "headline": head or headline(rows), "method": method, "citations": cites}
