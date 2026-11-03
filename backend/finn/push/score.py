"""Materiality: a transparent weighted table, not a model's opinion (BUILD_PLAN §8.4 "Key decisions").

score = BASE[category.subtype] (falling back to BASE[category]) + modifiers, clipped to [0, 1].
Tier: act >= 0.70, know >= 0.35, otherwise routine. Every point added comes with a reason the user can read,
and settings.weights can override any BASE entry ({"dividend": 0.05} makes dividends routine).
"""
from __future__ import annotations

import re

ACT, KNOW = 0.70, 0.35

BASE: dict[str, float] = {
    "results": 0.50, "results.filing": 0.90, "results.board_outcome": 0.80, "results.press_release": 0.55,
    "results.deck": 0.45, "results.board_notice": 0.25, "results.newspaper_ad": 0.05,
    "M&A": 0.60, "M&A.merger": 0.80, "M&A.acquisition": 0.70, "M&A.stake_sale": 0.70,
    "M&A.restructuring": 0.40, "M&A.subsidiary_incorporation": 0.25,
    "fund_raise": 0.50, "fund_raise.qip": 0.75, "fund_raise.preferential": 0.70, "fund_raise.rights": 0.70,
    "fund_raise.buyback": 0.75, "fund_raise.debt": 0.20,
    "management_change": 0.45, "management_change.senior": 0.85, "management_change.kmp": 0.40,
    "management_change.director": 0.40, "management_change.independent_director": 0.30,
    "litigation": 0.55, "litigation.regulatory_order": 0.60, "litigation.insolvency": 0.65,
    "insider_trading": 0.45,
    "earnings_call": 0.15, "earnings_call.transcript": 0.40, "earnings_call.recording": 0.05,
    "investor_meetings": 0.08,
    "credit_rating": 0.35, "credit_rating.downgrade": 0.80, "credit_rating.upgrade": 0.55,
    "dividend": 0.30, "dividend.record_date": 0.15,
    "bonus_split": 0.55,
    "capex": 0.60,
    "press_release": 0.30, "press_release.order_win": 0.45, "press_release.business_update": 0.40,
    "press_release.clarification": 0.55, "press_release.product": 0.40,
    "postal_ballot": 0.08, "agm_egm": 0.08,
    "pledging": 0.65,
    "unclassified": 0.05,
}

LABEL = {
    "results": "Quarterly results", "M&A": "Deal", "fund_raise": "Fund raise", "management_change": "Management change",
    "litigation": "Legal / regulatory", "insider_trading": "Insider trade", "earnings_call": "Earnings call",
    "investor_meetings": "Investor meeting", "credit_rating": "Credit rating", "dividend": "Dividend",
    "bonus_split": "Bonus / split", "capex": "Capex", "press_release": "Company news", "postal_ballot": "Postal ballot",
    "agm_egm": "Shareholder meeting", "pledging": "Promoter pledge", "unclassified": "Routine filing",
}
SUBTYPE_REASON = {
    "results.filing": "the results filing itself", "results.board_outcome": "board meeting outcome on results day",
    "management_change.senior": "a top-level role (CEO/CFO/MD/Chair) is changing",
    "litigation.regulatory_order": "a regulator or court has acted", "litigation.insolvency": "insolvency proceedings",
    "fund_raise.qip": "new shares to institutions dilute existing holders",
    "fund_raise.preferential": "new shares to specific investors dilute existing holders",
    "fund_raise.debt": "routine debt issuance", "press_release.clarification": "the company is answering a news report",
    "credit_rating.downgrade": "rating downgraded", "credit_rating.upgrade": "rating upgraded",
    "results.newspaper_ad": "statutory newspaper ad of results already filed",
    "earnings_call.recording": "audio of a call, transcript is more useful",
}
SMALL_CAP_CR = 20_000
SIZE_SENSITIVE = {"press_release", "capex", "M&A", "fund_raise"}


def base_weight(category: str, subtype: str | None, weights: dict | None = None) -> float:
    table = {**BASE, **(weights or {})}
    key = f"{category}.{subtype}"
    return float(table.get(key, table.get(category, BASE["unclassified"])))


def _rating_direction(text: str) -> str | None:
    t = text.lower()
    if re.search(r"downgrad|revised (downward|to negative)|outlook.{0,20}negative", t):
        return "downgrade"
    if re.search(r"upgrad|revised upward|outlook.{0,20}positive", t):
        return "upgrade"
    return None


def score_filing(cats: dict, subject: str, text: str, mcap_cr: float | None = None,
                 alert_categories: list[str] | None = None, same_day_move_pct: float | None = None,
                 weights: dict | None = None) -> dict:
    """Return {score, tier, reasons}. `cats` is classify()'s output."""
    category, subtype = cats["category"], cats.get("subtype")
    blob = f"{subject or ''} {text or ''}"
    if category == "credit_rating" and (d := _rating_direction(blob)):
        subtype = d
    score = base_weight(category, subtype, weights)
    reasons = [LABEL.get(category, category) + (f": {SUBTYPE_REASON[f'{category}.{subtype}']}"
                                                  if f"{category}.{subtype}" in SUBTYPE_REASON else "")]

    if category == "management_change" and re.search(r"resign|cessation|step(ped|s)? down", blob, re.I) \
            and subtype in ("senior", "kmp"):
        score += 0.05
        reasons.append("a departure, not an appointment")
    if category in SIZE_SENSITIVE and mcap_cr and mcap_cr < SMALL_CAP_CR and score >= 0.3:
        score += 0.10
        reasons.append(f"small company (₹{mcap_cr:,.0f} cr): news is large relative to its size")
    for sec in cats.get("secondary") or []:
        bump = 0.05 if base_weight(sec, None, weights) >= 0.3 else 0.0
        if bump:
            score += bump
            reasons.append(f"also mentions a {LABEL.get(sec, sec).lower()}")
    if alert_categories and category in alert_categories and score >= KNOW:
        score += 0.05
        reasons.append("on your alert list")
    if same_day_move_pct is not None and abs(same_day_move_pct) >= 3:
        bump = 0.20 if abs(same_day_move_pct) >= 6 else 0.10
        score += bump
        reasons.append(f"stock moved {same_day_move_pct:+.1f}% that day")

    score = round(max(0.0, min(1.0, score)), 3)
    tier = "act" if score >= ACT else "know" if score >= KNOW else "routine"
    return dict(score=score, tier=tier, reasons=reasons, subtype=subtype)
