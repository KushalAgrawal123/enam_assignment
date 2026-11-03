"""Bull vs bear (P11, strong tier) and the verdict line (P12, cheap tier), from finished cards only.

Without a key both are assembled by rules from the same inputs: each point is one signal from a finished
card, with that card's citations, and every number in it is copied from the card.
"""
from __future__ import annotations

import json
import logging

from .. import llm
from . import numcheck
from .prompts import P11_SYSTEM, P11_USER, P12_SYSTEM, P12_USER

log = logging.getLogger("finn.bullbear")


def _item(card: dict | None, label: str) -> dict | None:
    return next((i for i in ((card or {}).get("data") or {}).get("items", []) if i["label"] == label), None)


def _ids(x: dict | None) -> list[str]:
    if not x:
        return []
    return [x["citation"]] if x.get("citation") else list(x.get("citations") or [])


def signals(cards: dict, is_financial: bool) -> tuple[list[dict], list[dict]]:
    """(bull, bear) points, strongest first."""
    bull, bear = [], []
    tr = (cards.get("trajectory") or {}).get("data") or {}
    cagr = tr.get("cagr") or {}
    r5 = cagr.get("revenue_5y")
    if r5:
        if r5["value"] >= 12:
            bull.append((3, f"Revenue compounded {r5['value']:g}% a year over five years.", r5["citations"]))
        elif r5["value"] < 6:
            bear.append((3, f"Revenue grew only {r5['value']:g}% a year over five years.", r5["citations"]))
    p3 = cagr.get("net_profit_3y")
    if p3:
        if p3["value"] >= 15:
            bull.append((2, f"Net profit compounded {p3['value']:g}% a year over three years.", p3["citations"]))
        elif p3["value"] < 0:
            bear.append((3, f"Net profit shrank {abs(p3['value']):g}% a year over three years.", p3["citations"]))
    margins = (tr.get("annual") or {}).get("margin") or []
    tag = (tr.get("last_8_quarters") or {}).get("margin")
    if margins and tag in ("growing", "compressing") and not is_financial:
        cite = [margins[-1]["citation"]]
        (bull if tag == "growing" else bear).append(
            (2, f"Operating margin is {'widening' if tag == 'growing' else 'narrowing'} over the last eight quarters; "
                f"{margins[-1]['value']:g}% last year.", cite))
    cash = (cards.get("cash_quality") or {}).get("data") or {}
    avg = cash.get("cfo_pat_avg_3y")
    if avg is not None and not is_financial:
        cites = [c for y in (cash.get("years") or [])[-3:] for c in y.get("cfo_pat_citations") or []]
        if avg >= 0.9:
            bull.append((2, f"Profits turn into cash: CFO/PAT averaged {avg:g} over three years.", cites))
        elif avg < 0.7:
            bear.append((3, f"Cash lags profit: CFO/PAT averaged {avg:g} over three years.", cites))
    de = _item(cards.get("balance_sheet"), "Debt / equity")
    if de and not is_financial:
        if de["value"] <= 0.2:
            bull.append((1, f"Little debt: debt/equity {de['value']:g}.", _ids(de)))
        elif de["value"] >= 1:
            bear.append((3, f"Leveraged: debt/equity {de['value']:g}.", _ids(de)))
    roce = _item(cards.get("financials"), "ROCE") or _item(cards.get("financials"), "ROE")
    if roce:
        if roce["value"] >= 20:
            bull.append((1, f"{roce['label']} of {roce['value']:g}%.", _ids(roce)))
        elif roce["value"] < 10:
            bear.append((2, f"{roce['label']} of only {roce['value']:g}%.", _ids(roce)))
    led = (cards.get("ledger") or {}).get("data") or {}
    for it in led.get("items") or []:
        ids = [it["quarters"][-1]["said_citation"]] + it.get("actual_citations", [])
        if it["verdict"] in ("delivered", "beat"):
            bull.append((4, f"Kept its word on {it['metric']}: {it['note']}", ids))
        elif it["verdict"] in ("partial", "missed"):
            bear.append((4, f"Fell short on {it['metric']}: {it['note']}", ids))
    nar = (cards.get("narrative") or {}).get("data") or {}
    for r in nar.get("rows") or []:
        if r["status"] == "diverges":
            bear.append((4, f"Talk vs numbers on {r['topic'].replace('_', ' ')}: {r['evidence']}",
                         [r["claim_citation"]] + r["evidence_citations"]))
    key = lambda x: -x[0]  # noqa: E731
    fmt = lambda xs: [{"point": p, "citations": c} for _, p, c in sorted(xs, key=key)[:3]]  # noqa: E731
    return fmt(bull), fmt(bear)


def swing(cards: dict) -> str:
    led = (cards.get("ledger") or {}).get("data") or {}
    from .ledger import target_text
    for it in led.get("items") or []:
        q = it["quarters"][-1]
        if it["verdict"] == "pending" and q["target"]["lo"] is not None and q["target"]["horizon"] != "multi-year":
            return f"Whether {it['metric']} lands at the guided {target_text(q['target']['lo'], q['target']['hi'], q['target']['unit'])}."
    tag = (((cards.get("trajectory") or {}).get("data") or {}).get("last_8_quarters") or {}).get("margin")
    return f"Whether the {tag} margin trend of the last eight quarters holds." if tag else \
        "Whether the next results confirm the recent trend."


def build(cards: dict, company: str, is_financial: bool) -> dict:
    bull, bear = signals(cards, is_financial)
    out = {"bull": bull, "bear": bear, "swing_factor": swing(cards), "method": "rules"}
    if llm.available("strong"):
        def j(*ids):
            return json.dumps({i: {"data": (cards.get(i) or {}).get("data"),
                                   "citations": [c["id"] for c in (cards.get(i) or {}).get("citations", [])]} for i in ids})
        try:
            res = llm.complete_json("strong", P11_SYSTEM, P11_USER.format(
                company=company, snapshot_json=j("snapshot"), financials_json=j("financials", "trajectory"),
                balance_cash_json=j("balance_sheet", "cash_quality"), guidance_json=j("guidance"),
                ledger_json=j("ledger"), narrative_json=j("narrative")))
            allowed = numcheck.harvest({k: (v or {}).get("data") for k, v in cards.items()})
            known = {c["id"] for v in cards.values() if v for c in v.get("citations", [])}
            b, db_ = numcheck.filter_items(res.get("bull") or [], ("point",), allowed, known, label="P11 bull")
            r, dr = numcheck.filter_items(res.get("bear") or [], ("point",), allowed, known, label="P11 bear")
            if b and r and not numcheck.failed(len(b) + len(r), db_ + dr):
                sw = res.get("swing_factor") or ""
                out = {"bull": b[:3], "bear": r[:3], "method": "model",
                       "swing_factor": sw if not numcheck.bad_numbers(sw, allowed) else out["swing_factor"]}
        except Exception as e:
            log.warning("P11 %s: %s", company, e)
    return out


def verdict(cards: dict, company: str) -> dict:
    led = (cards.get("ledger") or {}).get("data") or {}
    s = led.get("summary") or {}
    cash = (cards.get("cash_quality") or {}).get("data") or {}
    nar = (cards.get("narrative") or {}).get("data") or {}
    inputs = {"delivered": s.get("delivered", 0), "beat": s.get("beat", 0), "partial": s.get("partial", 0),
              "missed": s.get("missed", 0), "pending": s.get("pending", 0), "pattern": led.get("pattern") or "none",
              "cfo_pat_3y_avg": cash.get("cfo_pat_avg_3y"), "cash_flag": f"; {cash['flag']}" if cash.get("flag") else "",
              "narrative_headline": nar.get("headline") or "none"}
    if llm.available("cheap"):
        try:
            v = llm.complete_json("cheap", P12_SYSTEM, P12_USER.format(**inputs)).get("verdict") or ""
            if v and not numcheck.bad_numbers(v, numcheck.harvest(inputs)):
                return {"verdict": v, "method": "model", "inputs": inputs}
        except Exception as e:
            log.warning("P12 %s: %s", company, e)
    checked = inputs["delivered"] + inputs["beat"] + inputs["partial"] + inputs["missed"]
    parts = []
    if checked:
        parts.append(f"Met {inputs['delivered'] + inputs['beat']} of {checked} checkable guidance targets")
    elif led.get("items"):
        parts.append(f"{inputs['pending']} guidance targets still pending")
    if inputs["cfo_pat_3y_avg"] is not None:
        parts.append(f"CFO/PAT {inputs['cfo_pat_3y_avg']:g} over three years")
    head = nar.get("headline")
    line = "; ".join(parts) + "." if parts else ""
    if head and head != "No testable claims found.":
        line += f" {head}"
    return {"verdict": line.strip() or "Not enough sourced material for a verdict.", "method": "rules", "inputs": inputs}
