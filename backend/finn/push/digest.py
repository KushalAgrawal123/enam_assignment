"""The Brief: a finite, ranked digest of one time window (reference implementation).

web/lib/digest.ts is a line-for-line port; tests/fixtures/digest_*.json pins both to the same output.

Rules:
- Results family: when a company files its results in the window, its results, call and deck filings fold into
  one card. The results filing leads; everything else becomes an attachment.
- Exact repeats (same company, same subject, same day) fold into the first one.
- Act and Know are sorted by score, then newest first. Routine is collapsed and grouped by company.
"""
from __future__ import annotations

from functools import cmp_to_key
from typing import Any

TIER_RANK = {"act": 2, "know": 1, "routine": 0}
FAMILY = {"results", "earnings_call"}
LEADS = {"filing", "board_outcome"}


def _card(f: dict, attachments: list[dict] | None = None) -> dict:
    return dict(kind="filing", id=f["id"], symbol=f["symbol"], category=f["category"], subtype=f.get("subtype"),
                tier=f["tier"], score=float(f["score"]), ts=f["ts"], title=f["subject"], card=f.get("card"),
                reasons=list(f.get("reasons") or []), url=f.get("url"), attachments=attachments or [])


def _attachment(f: dict) -> dict:
    return dict(subject=f["subject"], url=f.get("url"), category=f["category"], ts=f["ts"])


def build_digest(filings: list[dict], start: str, end: str, alerts: list[dict] | None = None) -> dict[str, Any]:
    """filings: rows with ts as ISO-8601 UTC strings. Returns the Digest contract (BUILD_PLAN §4.2)."""
    inside = sorted((f for f in filings if start <= f["ts"] <= end), key=lambda f: (f["ts"], f["id"]), reverse=True)

    # 1. Fold exact repeats.
    seen: dict[tuple, dict] = {}
    unique: list[dict] = []
    for f in inside:
        key = (f["symbol"], f["subject"].strip().lower(), f["ts"][:10])
        if key in seen:
            seen[key].setdefault("_dups", []).append(f)
            continue
        seen[key] = f
        unique.append(f)

    # 2. Results family per company.
    cards: list[dict] = []
    by_symbol: dict[str, list[dict]] = {}
    for f in unique:
        by_symbol.setdefault(f["symbol"], []).append(f)
    for symbol, fs in by_symbol.items():
        fam = [f for f in fs if f["category"] in FAMILY]
        has_results = any(f["category"] == "results" and f.get("subtype") in LEADS for f in fam)
        rest = [f for f in fs if not (has_results and f["category"] in FAMILY)]
        if has_results:
            fam.sort(key=lambda f: (f["category"] != "results" or f.get("subtype") not in LEADS,
                                    -float(f["score"]), f["ts"]))
            lead, others = fam[0], fam[1:]
            atts = [_attachment(o) for o in others] + [_attachment(d) for o in fam for d in o.get("_dups", [])]
            c = _card(lead, atts)
            c["tier"] = max((f["tier"] for f in fam), key=TIER_RANK.get)
            c["score"] = max(float(f["score"]) for f in fam)
            if atts:
                c["reasons"].append(f"{len(atts)} related filing{'s' if len(atts) > 1 else ''} folded in "
                                    "(deck, call, press release)")
            cards.append(c)
        for f in rest:
            cards.append(_card(f, [_attachment(d) for d in f.get("_dups", [])]))

    act = sorted((c for c in cards if c["tier"] == "act"), key=cmp_to_key(_by_score))
    know = sorted((c for c in cards if c["tier"] == "know"), key=cmp_to_key(_by_score))
    routine = sorted((c for c in cards if c["tier"] == "routine"), key=cmp_to_key(_by_time))

    alert_cards = sorted(alerts or [], key=lambda a: a["ts"], reverse=True)
    by_company: dict[str, list[dict]] = {}
    for c in routine:
        by_company.setdefault(c["symbol"], []).append(dict(title=c["title"], url=c["url"], ts=c["ts"]))
    return dict(
        window=dict(start=start, end=end),
        headline=dict(act=len(act) + len(alert_cards), know=len(know), routine=len(routine), filings=len(inside),
                      companies=len({f["symbol"] for f in inside})),
        alerts=alert_cards, act=act, know=know,
        routine=dict(count=len(routine), companies=len(by_company),
                     by_company=dict(sorted(by_company.items()))),
    )


def _by_time(a: dict, b: dict) -> int:
    """Newest first, then id ascending: a total order, so Python and TypeScript agree exactly."""
    if a["ts"] != b["ts"]:
        return -1 if a["ts"] > b["ts"] else 1
    return -1 if a["id"] < b["id"] else (1 if a["id"] > b["id"] else 0)


def _by_score(a: dict, b: dict) -> int:
    if a["score"] != b["score"]:
        return -1 if a["score"] > b["score"] else 1
    return _by_time(a, b)
