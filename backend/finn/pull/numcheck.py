"""Number post-check (BUILD_PLAN §6.4): model-written text may only repeat numbers it was given.

Every number in a text field must match, within 1% relative or 0.5 absolute, a number in the card's inputs.
Years and quarter labels are exempt. Items with citation ids that weren't provided are dropped too.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Iterable

log = logging.getLogger("finn.numcheck")

# ₹1,234.5 crore · 12.5% · 150 bps · 3.2x · -4 · (12) ; lakh/crore words don't change the number itself.
NUM = re.compile(r"(?<![\w.])[-−]?(?:₹\s?)?\d[\d,]*(?:\.\d+)?")
EXEMPT = re.compile(r"\b(?:FY|Q[1-4]\s?FY|H[12]\s?FY|Q[1-4]|H[12])\s?'?\d{2,4}\b|\b(?:19|20)\d{2}\b|\bFY\d{2}\b", re.I)


def numbers_in(text: str) -> list[float]:
    text = EXEMPT.sub(" ", text or "")
    out = []
    for m in NUM.finditer(text):
        s = m.group(0).replace("₹", "").replace(",", "").replace("−", "-").strip()
        try:
            out.append(float(s))
        except ValueError:
            continue
    return out


def harvest(x: Any) -> set[float]:
    """Every number that appears anywhere in the inputs (values and numbers inside strings)."""
    found: set[float] = set()
    if isinstance(x, bool) or x is None:
        return found
    if isinstance(x, (int, float)):
        found.add(float(x))
    elif isinstance(x, str):
        found.update(numbers_in(x))
    elif isinstance(x, dict):
        for v in x.values():
            found |= harvest(v)
    elif isinstance(x, (list, tuple, set)):
        for v in x:
            found |= harvest(v)
    return found


def _ok(n: float, allowed: Iterable[float]) -> bool:
    if abs(n) < 1 and float(n).is_integer():      # 0 and small counts ("one of") carry no claim
        return True
    return any(abs(n - a) <= max(0.5, 0.01 * abs(a)) for a in allowed) or \
        any(abs(-n - a) <= max(0.5, 0.01 * abs(a)) for a in allowed)   # "fell 4%" for a -4 input


def bad_numbers(text: str, allowed: set[float]) -> list[float]:
    return [n for n in numbers_in(text) if not _ok(n, allowed)]


def filter_items(items: list[dict], fields: tuple[str, ...], allowed: set[float], known_ids: set[str],
                 cite_fields: tuple[str, ...] = ("citations", "citation", "claim_citation", "evidence_citations"),
                 label: str = "") -> tuple[list[dict], int]:
    """Drop items with unsupported numbers or unknown citations. Returns (kept, dropped)."""
    kept = []
    for it in items:
        bad = [n for f in fields for n in bad_numbers(str(it.get(f) or ""), allowed)]
        ids = []
        for f in cite_fields:
            v = it.get(f)
            ids += v if isinstance(v, list) else [v] if isinstance(v, str) else []
        unknown = [i for i in ids if i and i not in known_ids]
        if bad or unknown:
            log.warning("numcheck %s dropped item: numbers %s, citations %s", label, bad, unknown)
            continue
        kept.append(it)
    return kept, len(items) - len(kept)


def failed(kept: int, dropped: int) -> bool:
    """A card that lost more than half its content is marked failed ("number check failed")."""
    return dropped > 0 and dropped > (kept + dropped) / 2
