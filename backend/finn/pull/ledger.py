"""Promised vs delivered (BUILD_PLAN §5 P9). Code decides every verdict it can; the strong model only judges the
rest and writes notes, and only when a key is configured.

1. Merge per-call guidance into threads (same metric + horizon), oldest call first.
2. Map each thread to a table metric: revenue_growth -> Sales YoY, pat_growth -> Net Profit YoY,
   ebitda_margin -> OPM %, all from the annual profit-loss table.
3. Verdicts once the year is reported: inside [lo, hi] delivered; above hi beat; below lo by <= 10% relative
   partial; else missed. Horizon not reported yet -> pending. No table line -> not_verifiable.
   Point targets ("around 27%") get +/-0.5 points, because screener prints OPM % as whole numbers.
4. Revisions: the same thread with a different target in a later call.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re

from .. import llm
from . import numcheck
from .numbers import Tables
from .prompts import P9_SYSTEM, P9_USER

log = logging.getLogger("finn.ledger")
TABLE_METRIC = {"revenue_growth": ("Sales", "Revenue"), "pat_growth": ("Net Profit",), "ebitda_margin": ("OPM %",),
                "ebit_margin": ("Operating Profit",)}
UNIT = {"%": "%", "INR cr": " cr", "USD bn": " bn"}
ORDER = {"revenue_growth": 0, "ebitda_margin": 1, "ebit_margin": 1, "pat_growth": 2, "revenue_usd": 3, "order_inflow": 4, "capex": 5,
         "volume_growth": 6}


def decide(actual: float, lo: float, hi: float | None, unit: str = "%") -> str:
    if hi is not None and hi == lo and unit == "%":
        lo, hi = lo - 0.5, hi + 0.5
    if actual < lo:
        return "partial" if actual >= lo - 0.10 * abs(lo) else "missed"
    if hi is not None and actual > hi:
        return "beat"
    return "delivered"


def target_text(lo: float | None, hi: float | None, unit: str) -> str:
    u = UNIT.get(unit, f" {unit}")
    f = lambda v: f"{v:,.2f}".rstrip("0").rstrip(".")  # noqa: E731
    if lo is None:
        return "—"
    if hi is None:
        return f"{f(lo)}{u}+"
    return f"{f(lo)}{u}" if lo == hi else f"{f(lo)}–{f(hi)}{u}"


def _fy_period(t: Tables, horizon: str) -> tuple[str | None, str | None]:
    """(this FY's annual period, the year before) from the profit-loss table, for 'FY27'-style horizons."""
    m = re.fullmatch(r"FY(\d{2})", horizon)
    if not m:
        return None, None
    _, periods, _ = t.series("profit-loss", "Sales", "Revenue")
    annual = [p for p in periods if p != "TTM"]
    cur = next((p for p in annual if p.startswith(f"20{m.group(1)}-")), None)
    if not cur:
        return None, None
    i = annual.index(cur)
    return cur, annual[i - 1] if i > 0 else None


def actual_for(t: Tables, metric: str, horizon: str, is_financial: bool) -> tuple[float | None, list[str], str | None]:
    """(actual, citation ids, reason when there is none)."""
    names = TABLE_METRIC.get(metric)
    if not names or (metric in ("ebitda_margin", "ebit_margin") and is_financial):
        return None, [], "not_verifiable"
    if not re.fullmatch(r"FY\d{2}", horizon):
        return None, [], "pending" if horizon in ("multi-year",) or _future(horizon) else "not_verifiable"
    cur, prev = _fy_period(t, horizon)
    if not cur:
        return None, [], "pending"
    name, periods, vals = t.series("profit-loss", *names)
    v = dict(zip(periods, vals))
    if metric == "ebitda_margin":
        if v.get(cur) is None:
            return None, [], "pending"
        return float(v[cur]), [t.cite("profit-loss", name, cur, v[cur])], None
    if metric == "ebit_margin":   # (operating profit − depreciation) / sales, from the same year's rows
        cols = {n: dict(zip(*t.series("profit-loss", n)[1:])).get(cur) for n in ("Operating Profit", "Depreciation", "Sales")}
        if None in cols.values() or not cols["Sales"]:
            return None, [], "not_verifiable"
        val = round((cols["Operating Profit"] - cols["Depreciation"]) / cols["Sales"] * 100, 1)
        return val, [t.cite("profit-loss", n, cur, x) for n, x in cols.items()], None
    if not prev or not v.get(prev) or v.get(cur) is None:
        return None, [], "not_verifiable"
    growth = round((v[cur] / v[prev] - 1) * 100, 1)
    return growth, [t.cite("profit-loss", name, prev, v[prev]), t.cite("profit-loss", name, cur, v[cur])], None


def _future(horizon: str) -> bool:
    m = re.search(r"FY(\d{2})", horizon)
    return bool(m) and dt.date(2000 + int(m.group(1)), 3, 31) >= dt.date.today()


def threads(per_call: list[tuple[dict, list[dict]]]) -> list[dict]:
    """per_call: [(call, guidance items)] oldest first -> threads with one mention per call."""
    out: dict[str, dict] = {}
    for call, items in per_call:
        for g in items:
            tid = f"{g['metric']}:{g['horizon']}"
            th = out.setdefault(tid, {"id": tid, "metric": g["metric"], "metric_label": g.get("metric_label") or g["metric"],
                                      "horizon": g["horizon"], "unit": g.get("unit") or "%", "mentions": []})
            if any(m["period"] == call["period"] for m in th["mentions"]):
                continue
            th["mentions"].append({"period": call["period"], "key": call["key"], "url": call["url"],
                                   "quote": g["quote"], "citation": g["citation"], "page": g.get("page"),
                                   "lo": g.get("target_lo"), "hi": g.get("target_hi"), "direction": g.get("direction")})
    return list(out.values())


def revisions(th: dict) -> list[dict]:
    out = []
    ms = th["mentions"]
    for a, b in zip(ms, ms[1:]):
        if (a["lo"], a["hi"]) != (b["lo"], b["hi"]) and a["lo"] is not None and b["lo"] is not None:
            out.append({"from_period": a["period"], "to_period": b["period"],
                        "change": f"{target_text(a['lo'], a['hi'], th['unit'])} → {target_text(b['lo'], b['hi'], th['unit'])}"})
    return out


def build(per_call: list[tuple[dict, list[dict]]], t: Tables, is_financial: bool, company: str) -> dict:
    """Returns {"items": [LedgerItem], "pattern", "summary", "method", "citations": [Citation]}."""
    ths = threads(per_call)
    doc_cites: dict[str, dict] = {}
    items = []
    for th in ths:
        last = th["mentions"][-1]
        actual, act_ids, reason = actual_for(t, th["metric"], th["horizon"], is_financial)
        if last.get("direction"):
            prior = actual_for(t, th["metric"], f"FY{int(th['horizon'][2:]) - 1:02d}", is_financial) \
                if re.fullmatch(r"FY\d{2}", th["horizon"]) and "growth" not in th["metric"] else (None, [], None)
            if actual is not None and (prior[0] is not None or "growth" in th["metric"]):
                base = 0.0 if "growth" in th["metric"] else prior[0]
                moved = "up" if actual > base else "down" if actual < base else "flat"
                verdict = "delivered" if moved == last["direction"] else "missed"
                act_ids = prior[1] + act_ids
                note = f"Said it would go {last['direction']}; {th['horizon']} came in at " \
                       f"{target_text(actual, actual, th['unit'])}" + \
                       (f" vs {target_text(prior[0], prior[0], th['unit'])}." if prior[0] is not None else ".")
            else:
                verdict = reason or "not_verifiable"
                note = f"Said it would go {last['direction']}; " + ("not reported yet." if verdict == "pending" else
                                                                      "the tables can't confirm it.")
        elif actual is not None and last["lo"] is not None:
            verdict = decide(actual, last["lo"], last["hi"], th["unit"])
            note = f"Guided {target_text(last['lo'], last['hi'], th['unit'])}; {th['horizon']} came in at " \
                   f"{target_text(actual, actual, th['unit'])}."
        else:
            verdict = reason or "not_verifiable"
            note = {"pending": f"{th['horizon']} isn't reported yet." if th["horizon"] != "multi-year"
                    else "Multi-year goal; too early to judge.",
                    "not_verifiable": "The reported tables don't carry this line."}[verdict]
        revs = revisions(th)
        quarters = []
        for m in th["mentions"]:
            doc_cites[m["citation"]] = {"id": m["citation"], "kind": "transcript", "doc_url": m["url"],
                                        "period": m["period"], "page": m["page"], "quote": m["quote"]}
            quarters.append({"period": m["period"], "said": m["quote"], "said_citation": m["citation"],
                             "target": {"lo": m["lo"], "hi": m["hi"], "unit": th["unit"], "horizon": th["horizon"],
                                        "direction": m.get("direction")},
                             "actual": actual, "actual_citation": act_ids[-1] if act_ids else None,
                             "actual_citations": act_ids, "verdict": verdict, "note": None})
        quarters[-1]["note"] = note
        items.append({"id": th["id"], "metric": f"{th['metric_label']} · {th['horizon']}", "metric_key": th["metric"],
                      "table_metric": "/".join(TABLE_METRIC[th["metric"]][:1]) if th["metric"] in TABLE_METRIC else None,
                      "quarters": quarters, "revisions": revs, "verdict": verdict, "note": note,
                      "actual_citations": act_ids})
    rank = {"delivered": 0, "beat": 0, "partial": 0, "missed": 0, "pending": 1, "not_verifiable": 2}
    items.sort(key=lambda i: (rank[i["verdict"]], ORDER.get(i["metric_key"], 9), -len(i["quarters"])))
    items = items[:8]
    method = "rules"
    pattern = rule_pattern(items)
    if llm.available("strong") and items:
        judged = _p9(items, t, company, doc_cites)
        if judged:
            pattern, method = judged, "model"
    summary = {v: sum(1 for i in items if i["verdict"] == v) for v in rank}
    used_tbl = {c for i in items for c in i["actual_citations"]}
    cites = list(doc_cites.values()) + [t.citations[c] for c in sorted(used_tbl) if c in t.citations]
    return {"items": items, "pattern": pattern, "summary": summary, "method": method,
            "calls": [c["period"] for c, _ in per_call], "citations": cites}


def rule_pattern(items: list[dict]) -> str:
    checked = [i for i in items if i["verdict"] in ("delivered", "beat", "partial", "missed")]
    if not checked:
        return "Nothing guided has been reported against yet."
    met = [i for i in checked if i["verdict"] in ("delivered", "beat")]
    short = [i["metric"] for i in checked if i["verdict"] in ("partial", "missed")]
    s = f"Met {len(met)} of {len(checked)} checkable targets"
    s += f"; fell short on {', '.join(short[:2])}." if short else "."
    revised = [i for i in items if i["revisions"]]
    if revised:
        s += f" Revised {len(revised)} target{'s' if len(revised) > 1 else ''} between calls."
    return s


def _p9(items: list[dict], t: Tables, company: str, doc_cites: dict) -> str | None:
    payload = [{"id": i["id"], "metric_label": i["metric"], "verdict": None if i["verdict"] == "not_verifiable" else i["verdict"],
                "per_call": [{"period": q["period"], "quote": q["said"], "citation": q["said_citation"], "target": q["target"]}
                             for q in i["quarters"]], "actual": i["quarters"][-1]["actual"],
                "actual_citations": i["actual_citations"], "revisions": i["revisions"]} for i in items]
    rows = [f"{cid} = {c['table_ref']['value']}" for cid, c in t.citations.items()]
    try:
        out = llm.complete_json("strong", P9_SYSTEM, P9_USER.format(company=company, threads_json=json.dumps(payload),
                                                                    actuals_table="\n".join(rows)))
    except Exception as e:
        log.warning("P9 %s: %s", company, e)
        return None
    allowed = numcheck.harvest(payload) | numcheck.harvest(rows)
    known = set(doc_cites) | set(t.citations)
    kept, _ = numcheck.filter_items(out.get("items") or [], ("note",), allowed, known, label="P9")
    by_id = {i["id"]: i for i in items}
    for k in kept:
        it = by_id.get(k.get("id"))
        if not it:
            continue
        if it["verdict"] == "not_verifiable" and k.get("verdict") in ("delivered", "beat", "partial", "missed", "pending"):
            it["verdict"] = k["verdict"]
            for q in it["quarters"]:
                q["verdict"] = k["verdict"]
        if k.get("note"):
            it["note"] = it["quarters"][-1]["note"] = k["note"]
    pat = out.get("pattern") or ""
    return pat if not numcheck.bad_numbers(pat, allowed) else None
