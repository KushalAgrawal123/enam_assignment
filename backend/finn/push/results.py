"""Results card: Revenue, EBITDA*, PBT, PAT for the quarter, QoQ and YoY (BUILD_PLAN §4.2 ResultsCard).

Ladder (PLAN Phase 3 cut line: NSE's XBRL index stops in Jan 2025, so that rung is dropped):
  1. results PDF -> P2 (cheap LLM, copy-only), cross-checked against screener;  needs GEMINI_API_KEY
  2. screener's quarterly table (updated within hours of the filing).
Verification is arithmetic, never a model: the table's own identities must hold for the current quarter,
the previous quarter and the same quarter last year. Anything that doesn't add up -> verified=False and the card
says "unverified — open filing".
"""
from __future__ import annotations

import datetime as dt
import logging
import re

from .. import llm

log = logging.getLogger("finn.results")
TOL = 0.03          # identities must hold within 3% (screener rounds to whole crores and whole percent)

_MONTHS = {m: i for i, m in enumerate("january february march april may june july august september october "
                                      "november december".split(), 1)}


def period_end_from_text(text: str) -> str | None:
    """'quarter ended September 30, 2026' / '30th September 2026' -> '2026-09-30'."""
    t = text.lower()
    m = re.search(r"ended,?\s*(?:on\s*)?(\w+)\s+(\d{1,2}),?\s*(\d{4})", t)
    if m and m.group(1) in _MONTHS:
        return dt.date(int(m.group(3)), _MONTHS[m.group(1)], int(m.group(2))).isoformat()
    m = re.search(r"ended,?\s*(?:on\s*)?(\d{1,2})(?:st|nd|rd|th)?\s+(\w+),?\s*(\d{4})", t)
    if m and m.group(2) in _MONTHS:
        return dt.date(int(m.group(3)), _MONTHS[m.group(2)], int(m.group(1))).isoformat()
    return None


def _shift(period: str, months: int) -> str:
    d = dt.date.fromisoformat(period)
    y, m = divmod(d.month - 1 + months, 12)
    first_next = dt.date(d.year + y + (m + 1) // 12, (m + 1) % 12 + 1, 1)
    return (first_next - dt.timedelta(days=1)).isoformat()


def _pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return round((a / b - 1) * 100 * (1 if b > 0 else -1), 1)


def _close(a: float | None, b: float | None, tol: float = TOL, floor: float = 2.0) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= max(floor, tol * max(abs(a), abs(b)))


def quarter_values(quarters: dict, period: str, is_financial: bool) -> dict | None:
    """Headline lines for one quarter from screener's quarterly table, in ₹ crore."""
    if period not in quarters["periods"]:
        return None
    i = quarters["periods"].index(period)
    row = lambda *names: next((quarters["rows"][n][i] for n in names if n in quarters["rows"]), None)  # noqa: E731
    v = {"revenue": row("Revenue", "Sales"), "expenses": row("Expenses"),
         "op": row("Financing Profit") if is_financial else row("Operating Profit"),
         "other_income": row("Other Income"), "interest": row("Interest"), "dep": row("Depreciation"),
         "pbt": row("Profit before tax"), "tax_pct": row("Tax %"), "pat": row("Net Profit")}
    return v if v["revenue"] is not None else None


def check(v: dict, is_financial: bool) -> list[str]:
    """The table's own arithmetic. Returns the identities that fail."""
    issues = []
    if not is_financial and v["expenses"] is not None and not _close(v["revenue"] - v["expenses"], v["op"]):
        issues.append("revenue − expenses ≠ operating profit")
    if None not in (v["op"], v["other_income"], v["dep"], v["pbt"]):
        interest = 0 if is_financial else (v["interest"] or 0)   # banks: interest is inside financing profit
        implied = v["op"] + v["other_income"] - interest - v["dep"]
        if not _close(implied, v["pbt"], tol=0.06, floor=5):      # exceptional items live in this gap
            issues.append("operating profit + other income − interest − depreciation ≠ PBT")
    if None not in (v["pbt"], v["tax_pct"], v["pat"]) and v["pbt"] > 0:
        # Net profit includes associates/minorities, so allow 8% around PBT × (1 − tax rate).
        if not _close(v["pbt"] * (1 - v["tax_pct"] / 100), v["pat"], tol=0.08, floor=5):
            issues.append("PBT after tax ≠ net profit")
    return issues


def results_card(quarters: dict | None, period_end: str | None, is_financial: bool, basis: str | None,
                 url: str | None, pdf_values: dict | None = None) -> dict | None:
    """Build the card, or None when the quarter isn't in the table yet (the caller retries next poll)."""
    if not quarters or not period_end:
        return None
    cur = quarter_values(quarters, period_end, is_financial)
    if not cur:
        return None
    prev = quarter_values(quarters, _shift(period_end, -3), is_financial)
    yago = quarter_values(quarters, _shift(period_end, -12), is_financial)

    issues: list[str] = []
    for label, v in (("this quarter", cur), ("last quarter", prev), ("same quarter last year", yago)):
        if v:
            issues += [f"{label}: {i}" for i in check(v, is_financial)]
    source = "screener"
    if pdf_values:     # the filing's own numbers must agree with the table
        source = "pdf"
        for k in ("revenue", "pbt", "pat"):
            if pdf_values.get(k) is not None and not _close(pdf_values[k], cur[k], tol=0.01, floor=1):
                issues.append(f"filing {k} {pdf_values[k]} ≠ table {cur[k]}")

    # Banks: screener's "financing profit" nets provisions inside expenses (often negative), so it would mislead;
    # operating profit before provisions needs the filing itself (PDF rung).
    lines = [("Revenue", "revenue"), ("PBT", "pbt"), ("PAT", "pat")] if is_financial else \
        [("Revenue", "revenue"), ("EBITDA*", "op"), ("PBT", "pbt"), ("PAT", "pat")]
    rows = [{"metric": m, "value_cr": cur[k], "qoq_pct": _pct(cur[k], prev and prev[k]),
             "yoy_pct": _pct(cur[k], yago and yago[k])} for m, k in lines]
    margin = {}
    if not is_financial and cur["revenue"] and cur["op"] is not None:
        m = round(cur["op"] / cur["revenue"] * 100, 1)
        margin = {"ebitda_margin_pct": m,
                  "qoq_bps": round((m - prev["op"] / prev["revenue"] * 100) * 100) if prev and prev["revenue"] else None,
                  "yoy_bps": round((m - yago["op"] / yago["revenue"] * 100) * 100) if yago and yago["revenue"] else None}
    flags = []
    if not prev:
        flags.append("previous quarter not in the table")
    if not yago:
        flags.append("year-ago quarter not in the table")
    return {"type": "results", "period_end": period_end, "basis": basis, "source": source,
            "verified": not issues and bool(prev and yago), "issues": issues, "flags": flags, "rows": rows,
            "margin": margin, "compare": {"qoq": _shift(period_end, -3) if prev else None,
                                          "yoy": _shift(period_end, -12) if yago else None},
            "ebitda_note": ("Bank: EBITDA doesn't apply; operating profit before provisions is in the filing."
                            if is_financial else "EBITDA* = operating profit before other income "
                                                 "(revenue − operating expenses), as reported in the table."),
            "url": url, "page": None}


# ---- PDF rung (P2), used when a cheap-tier key is configured -------------------------------------------------

P2_SYSTEM = ("You copy numbers from Indian listed-company quarterly results tables. Copy each number exactly as "
             "printed (brackets mean negative). Never compute, round or estimate. Use null when a line is not printed.")
P2_USER = """From the results table below, return JSON:
{{"basis": "consolidated" | "standalone", "unit": "crore" | "lakh" | "million" | "thousand" | "rupees",
 "page": <page number used>, "columns": [{{"label": "<column header as printed>",
 "period_end": "YYYY-MM-DD", "months": 3, {fields}}}]}}
Prefer the consolidated table if both are present. Include every 3-month column (current quarter,
preceding quarter, same quarter last year); skip half-year and full-year columns.

{pages}"""
FIELDS = ('"revenue": number|null (Revenue from operations), "other_income": number|null, '
          '"finance_costs": number|null, "dep": number|null (Depreciation and amortisation), '
          '"exceptional": number|null, "pbt": number|null (Profit before tax), "tax": number|null, '
          '"pat": number|null (Net profit for the period)')
TO_CRORE = {"crore": 1, "lakh": 0.01, "million": 0.1, "thousand": 0.0001, "rupees": 1e-7}


def pdf_values(pages: list[str], period_end: str) -> dict | None:
    """P2 on the results PDF; values normalised to ₹ crore. None when no key or the column isn't found."""
    if not llm.available("cheap"):
        return None
    text = "\n".join(f"[page {i + 1}]\n{p[:6000]}" for i, p in enumerate(pages[:6]) if p.strip())
    try:
        out = llm.complete_json("cheap", P2_SYSTEM, P2_USER.format(fields=FIELDS, pages=text), max_tokens=2000)
    except Exception as e:
        log.warning("P2 failed: %s", e)
        return None
    k = TO_CRORE.get(out.get("unit"), None)
    col = next((c for c in out.get("columns") or [] if c.get("period_end") == period_end), None)
    if not k or not col:
        return None
    return {f: (round(col[f] * k, 2) if isinstance(col.get(f), (int, float)) else None)
            for f in ("revenue", "pbt", "pat", "dep", "finance_costs", "other_income")}
