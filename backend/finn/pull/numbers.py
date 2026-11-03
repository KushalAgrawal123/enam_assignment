"""Deterministic number cards D2–D5 (BUILD_PLAN §5 "Deterministic cards"). No LLM anywhere in this file.

Every number shown carries a citation id TBL-<section>-<metric>-<period> pointing at the screener table cell it
came from. Values that code derives (D/E, CAGR, CFO/PAT) cite every cell they were computed from.
Banks and NBFCs report differently (no OPM, debt is their raw material), so their cards swap metrics.
"""
from __future__ import annotations

from typing import Any

Card = dict[str, Any]


class Tables:
    def __init__(self, bundle: dict):
        self.t = bundle.get("tables", {})
        self.top = bundle.get("top", {})
        self.citations: dict[str, dict] = {}

    def series(self, section: str, *names: str) -> tuple[str | None, list[str], list[float | None]]:
        """(metric name found, periods, values) for the first of `names` present in `section`."""
        tab = self.t.get(section)
        if not tab:
            return None, [], []
        for n in names:
            if n in tab["rows"]:
                return n, tab["periods"], tab["rows"][n]
        return None, tab["periods"], []

    def cite(self, section: str, metric: str, period: str, value: float | None) -> str:
        cid = f"TBL-{section}-{metric}-{period}"
        self.citations[cid] = {"id": cid, "kind": "table",
                               "table_ref": {"section": section, "metric": metric, "period": period, "value": value}}
        return cid

    def point(self, section: str, names: tuple[str, ...], period: str | None = None, *, latest: bool = True) -> dict | None:
        """One cell: the given period, else the latest non-empty value (TTM counts for profit-loss)."""
        metric, periods, vals = self.series(section, *names)
        if not metric:
            return None
        pairs = list(zip(periods, vals))
        if period:
            pairs = [p for p in pairs if p[0] == period]
        pairs = [p for p in pairs if p[1] is not None]
        if not pairs:
            return None
        per, v = pairs[-1] if latest else pairs[0]
        return {"value": v, "period": per, "metric": metric, "citation": self.cite(section, metric, per, v)}

    def annual(self, section: str, *names: str, n: int = 10) -> list[dict]:
        metric, periods, vals = self.series(section, *names)
        if not metric:
            return []
        out = [{"period": p, "value": v, "citation": self.cite(section, metric, p, v)}
               for p, v in zip(periods, vals) if p != "TTM" and v is not None]
        return out[-n:]


def _card(cid: str, data: Any, t: Tables, gaps: list[str]) -> Card:
    used = _collect_ids(data)
    return {"id": cid, "status": "ready" if data else "gap", "data": data or None,
            "citations": [t.citations[c] for c in sorted(used) if c in t.citations], "gaps": gaps}


def _collect_ids(x: Any) -> set[str]:
    if isinstance(x, dict):
        return set().union(*[_collect_ids(v) for v in x.values()], {x["citation"]} if isinstance(x.get("citation"), str) else set(),
                           set(x.get("citations") or []) if isinstance(x.get("citations"), list) else set())
    if isinstance(x, list):
        return set().union(*[_collect_ids(v) for v in x]) if x else set()
    return set()


def _cagr(series: list[dict], years: int) -> dict | None:
    if len(series) < years + 1:
        return None
    a, b = series[-years - 1], series[-1]
    if not a["value"] or not b["value"] or a["value"] <= 0 or b["value"] <= 0:
        return None
    return {"value": round(((b["value"] / a["value"]) ** (1 / years) - 1) * 100, 1), "years": years,
            "citations": [a["citation"], b["citation"]]}


def _slope_tag(values: list[float], *, flat_band: float) -> str | None:
    """Least-squares slope over the points: 'growing', 'compressing' or 'flat'."""
    v = [x for x in values if x is not None]
    if len(v) < 4:
        return None
    n = len(v)
    xm, ym = (n - 1) / 2, sum(v) / n
    slope = sum((i - xm) * (y - ym) for i, y in enumerate(v)) / sum((i - xm) ** 2 for i in range(n))
    if abs(slope) <= flat_band:
        return "flat"
    return "growing" if slope > 0 else "compressing"


def financials(t: Tables, is_financial: bool) -> Card:
    rev = ("Revenue", "Sales") if is_financial else ("Sales", "Revenue")
    items = []
    for label, sec, names in [("Revenue (TTM)", "profit-loss", rev), ("Net profit (TTM)", "profit-loss", ("Net Profit",))]:
        p = t.point(sec, names, "TTM") or t.point(sec, names)
        if p:
            items.append({"label": label, "unit": "₹ cr", **p})
    if is_financial:
        p = t.point("profit-loss", ("Financing Margin %",), "TTM") or t.point("profit-loss", ("Financing Margin %",))
        if p:
            items.append({"label": "Financing margin", "unit": "%", **p})
        npa = t.point("quarters", ("Gross NPA %",))
        if npa:
            items.append({"label": "Gross NPA", "unit": "%", **npa})
    else:
        p = t.point("profit-loss", ("OPM %",), "TTM") or t.point("profit-loss", ("OPM %",))
        if p:
            items.append({"label": "EBITDA margin (OPM)", "unit": "%", **p})
    for label, key in [("ROCE", "ROCE"), ("ROE", "ROE"), ("Market cap", "Market Cap")]:
        if key == "ROCE" and is_financial:
            continue
        v = t.top.get(key)
        if isinstance(v, (int, float)):
            items.append({"label": label, "unit": "₹ cr" if key == "Market Cap" else "%", "value": v, "period": "current",
                          "metric": key, "citation": t.cite("top", key, "current", v)})
    if not is_financial:
        de = _de(t)
        if de:
            items.append(de)
    qsales = t.series("quarters", *rev)
    spark = [{"period": p, "value": v} for p, v in zip(qsales[1], qsales[2]) if v is not None]
    gaps = [] if items else ["No financial tables found on screener for this company."]
    return _card("financials", {"items": items, "quarterly_revenue": spark} if items else None, t, gaps)


def _de(t: Tables) -> dict | None:
    eq, debt = t.point("balance-sheet", ("Equity Capital",)), t.point("balance-sheet", ("Borrowings", "Borrowing"))
    res = t.point("balance-sheet", ("Reserves",))
    if not (eq and debt and res) or not (eq["period"] == debt["period"] == res["period"]):
        return None
    equity = (eq["value"] or 0) + (res["value"] or 0)
    if equity <= 0:
        return None
    return {"label": "Debt / equity", "unit": "x", "value": round(debt["value"] / equity, 2), "period": debt["period"],
            "metric": "D/E", "derived": "Borrowings ÷ (Equity capital + Reserves)",
            "citations": [debt["citation"], eq["citation"], res["citation"]]}


def trajectory(t: Tables, is_financial: bool) -> Card:
    rev = ("Revenue", "Sales") if is_financial else ("Sales", "Revenue")
    margin = ("Financing Margin %",) if is_financial else ("OPM %",)
    sales, pat = t.annual("profit-loss", *rev), t.annual("profit-loss", "Net Profit")
    opm = t.annual("profit-loss", *margin)
    if not sales:
        return _card("trajectory", None, t, ["No annual P&L table on screener."])
    q_rev = [v for v in t.series("quarters", *rev)[2][-8:]]
    q_margin = [v for v in t.series("quarters", *margin)[2][-8:]]
    q_pat = [v for v in t.series("quarters", "Net Profit")[2][-8:]]
    data = {
        "annual": {"revenue": sales, "margin": opm, "net_profit": pat, "margin_label": "Financing margin %" if is_financial else "OPM %"},
        "cagr": {"revenue_3y": _cagr(sales, 3), "revenue_5y": _cagr(sales, 5),
                 "net_profit_3y": _cagr(pat, 3), "net_profit_5y": _cagr(pat, 5)},
        "last_8_quarters": {"revenue": _slope_tag(q_rev, flat_band=0.002 * (max([x for x in q_rev if x] or [1]))),
                            "margin": _slope_tag(q_margin, flat_band=0.15),
                            "net_profit": _slope_tag(q_pat, flat_band=0.005 * (max([abs(x) for x in q_pat if x] or [1])))},
    }
    gaps = [] if len(sales) >= 6 else [f"Only {len(sales)} years of history on screener; 5-year CAGR unavailable."]
    return _card("trajectory", data, t, gaps)


def balance_sheet(t: Tables, is_financial: bool) -> Card:
    items = []
    for label, names in [("Borrowings", ("Borrowings", "Borrowing")), ("Deposits", ("Deposits",)),
                         ("Equity capital", ("Equity Capital",)), ("Reserves", ("Reserves",)),
                         ("Total assets", ("Total Assets",))]:
        p = t.point("balance-sheet", names)
        if p:
            items.append({"label": label, "unit": "₹ cr", **p})
    de = None if is_financial else _de(t)
    if de:
        items.append(de)
    wc = {}
    for label, metric in [("debtor_days", "Debtor Days"), ("inventory_days", "Inventory Days"),
                          ("payable_days", "Days Payable"), ("cash_conversion_cycle", "Cash Conversion Cycle"),
                          ("working_capital_days", "Working Capital Days")]:
        s = t.annual("ratios", metric, n=5)
        if s:
            wc[label] = s
    debt = t.annual("balance-sheet", "Borrowings", "Borrowing", n=5)
    data = {"items": items, "working_capital": wc, "borrowings_5y": debt}
    gaps = []
    if is_financial:
        gaps.append("Bank/NBFC: borrowings and deposits fund the loan book, so debt/equity and working-capital days "
                    "don't apply.")
    elif not wc:
        gaps.append("Working-capital days are not published on screener for this company.")
    return _card("balance_sheet", data if items else None, t, gaps)


def cash_quality(t: Tables, is_financial: bool) -> Card:
    cfo = {r["period"]: r for r in t.annual("cash-flow", "Cash from Operating Activity", n=10)}
    pat = {r["period"]: r for r in t.annual("profit-loss", "Net Profit", n=12)}
    fcf = {r["period"]: r for r in t.annual("cash-flow", "Free Cash Flow", n=10)}
    inv = {r["period"]: r for r in t.annual("cash-flow", "Cash from Investing Activity", n=10)}
    years = [p for p in cfo if p in pat][-5:]
    if not years:
        return _card("cash_quality", None, t, ["No cash-flow table on screener."])
    rows = []
    for y in years:
        c, p = cfo[y], pat[y]
        ratio = round(c["value"] / p["value"], 2) if p["value"] and p["value"] > 0 else None
        row = {"period": y, "cfo": c, "pat": p, "cfo_pat": ratio,
               "cfo_pat_citations": [c["citation"], p["citation"]] if ratio is not None else []}
        if y in fcf:
            row["fcf"] = {**fcf[y], "label": "Free cash flow (screener)"}
        elif y in inv:
            row["fcf"] = {"value": round(c["value"] + inv[y]["value"], 1), "label": "CFO + investing cash flow",
                          "citations": [c["citation"], inv[y]["citation"]]}
        rows.append(row)
    ratios = [r["cfo_pat"] for r in rows if r["cfo_pat"] is not None]
    streak = 0
    worst = 0
    for r in ratios:
        streak = streak + 1 if r < 0.7 else 0
        worst = max(worst, streak)
    data = {"years": rows, "cfo_pat_avg_3y": round(sum(ratios[-3:]) / len(ratios[-3:]), 2) if len(ratios) >= 3 else None,
            "flag": "CFO/PAT below 0.7 for 3+ years running: profits are not turning into cash"
            if worst >= 3 and not is_financial else None}
    gaps = ["For lenders, operating cash flow swings with loan growth, so CFO/PAT says little about earnings "
            "quality."] if is_financial else []
    return _card("cash_quality", data, t, gaps)


def number_cards(bundle: dict, is_financial: bool) -> dict[str, Card]:
    t = Tables(bundle)
    return {c["id"]: c for c in (financials(t, is_financial), trajectory(t, is_financial),
                                 balance_sheet(t, is_financial), cash_quality(t, is_financial))}


def looks_financial(bundle: dict) -> bool:
    """Screener's bank/NBFC layout has Financing Profit instead of Operating Profit."""
    rows = (bundle.get("tables", {}).get("profit-loss") or {}).get("rows", {})
    return "Financing Profit" in rows or "Financing Margin %" in rows
