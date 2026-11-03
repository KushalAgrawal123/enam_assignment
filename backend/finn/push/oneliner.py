"""One-line summaries for the other categories (P5), regex first where the format is fixed.

Every number in the line must appear in the filing text; otherwise the line is dropped and the filing is shown
on its own, at its priority. No key -> regex only.
"""
from __future__ import annotations

import logging
import re

from .. import llm

log = logging.getLogger("finn.oneliner")

FACTS = {
    "M&A": "target, stake_pct, consideration_inr, consideration_type (cash/stock/mixed), related_party (yes/no), expected_completion",
    "fund_raise": "instrument, size_inr, price_per_share, discount_to_cmp_pct (only if printed), investors",
    "capex": "project, amount_inr, capacity_added, location, commissioning_date",
    "litigation": "authority, amount_inr, nature, status (order/notice/appeal), next_date",
    "credit_rating": "agency, instrument, old_rating, new_rating, outlook, action",
    "insider_trading": "person, relation (promoter/director/KMP), buy_or_sell, shares, value_inr, holding_after_pct",
    "pledging": "promoter_entity, shares, action (create/release/invoke), pledged_pct_after",
    "dividend": "type (interim/final/special), per_share_inr, record_date, payment_date",
    "bonus_split": "ratio, record_date",
    "press_release": "headline_fact, value_inr, counterparty, duration",
}
P5_SYSTEM = ("You summarise one Indian stock-exchange filing for a busy investor. Use only the filing text. Copy numbers "
             "exactly as printed. Do not add context, opinions or anything not in the filing.")
P5_USER = """Category: {category}
Extract these facts (null if not stated): {facts}
Then write "line": one sentence, at most 20 words, leading with the single most decision-relevant fact.
Return {{"facts": {{...}}, "line": str, "page": int|null}}

Subject: {subject}
{pages}"""

_NUM = re.compile(r"\d[\d,]*\.?\d*")


def numbers_ok(line: str, source: str) -> bool:
    """Every number in `line` must occur in the source text (commas ignored)."""
    src = {n.replace(",", "").rstrip(".") for n in _NUM.findall(source)}
    return all(n.replace(",", "").rstrip(".") in src for n in _NUM.findall(line))


def regex_line(category: str, text: str) -> dict | None:
    t = text or ""
    if category == "dividend":
        m = re.search(r"(interim|final|special)?\s*dividend of (?:Rs\.?|INR|₹)\s*([\d.]+)", t, re.I)
        rd = re.search(r"record date[^.]*?(\w+ \d{1,2},? \d{4}|\d{1,2}(?:st|nd|rd|th)? \w+,? \d{4})", t, re.I)
        if m:
            kind = (m.group(1) or "").lower() or "a"
            line = f"Declared {kind} dividend of ₹{m.group(2)} per share" + (f"; record date {rd.group(1)}." if rd else ".")
            return {"facts": {"type": m.group(1), "per_share_inr": m.group(2), "record_date": rd.group(1) if rd else None},
                    "line": line}
    if category == "bonus_split":
        m = re.search(r"bonus[^.]*?(\d+\s*:\s*\d+)", t, re.I) or re.search(r"split[^.]*?(\d+\s*:\s*\d+)", t, re.I)
        if m:
            return {"facts": {"ratio": m.group(1).replace(" ", "")}, "line": f"Approved {m.group(0)[:80].strip()}."}
    return None


def oneliner(category: str, subject: str, text: str, url: str | None, pdf_pages: list[str] | None = None) -> dict | None:
    out = regex_line(category, text)
    source = text or ""
    if not out and category in FACTS and llm.available("cheap"):
        pages = "\n".join(f"[page {i + 1}]\n{p[:4000]}" for i, p in enumerate((pdf_pages or [])[:4])) or f"[page 1]\n{text}"
        source = pages
        try:
            out = llm.complete_json("cheap", P5_SYSTEM, P5_USER.format(category=category, facts=FACTS[category],
                                                                       subject=subject, pages=pages), max_tokens=500)
        except Exception as e:
            log.warning("P5 failed: %s", e)
            out = None
    if not out or not out.get("line") or not numbers_ok(out["line"], source + " " + subject):
        return None
    return {"type": "oneliner", "category": category, "line": out["line"], "facts": out.get("facts") or {},
            "url": url, "page": out.get("page")}
