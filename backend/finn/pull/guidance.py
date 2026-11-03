"""Guidance extraction, once per transcript (P7 on the cheap tier; a rule extractor when no key is set).

Both paths return the P7 shape. The rule path reads management sentences that look forward ("we expect",
"our guidance is", "we are targeting") and carry a figure next to a metric it knows: revenue growth, EBITDA
margin, PAT growth, volume growth, order inflow and capex. It copies figures from the sentence; it never
computes one. Model output is cached by content hash in llm_cache, so each transcript is read once.
"""
from __future__ import annotations

import logging
import re

from .. import llm
from . import calls as C
from .prompts import P7_SYSTEM, P7_USER, turns_block

log = logging.getLogger("finn.guidance")

FORWARD = re.compile(r"\b(expect\w*|guid\w*|target\w*|aim\w*|aspir\w*|will|should|looking at|anticipat\w*|"
                     r"plan\w*|hope\w*|hopeful|confident|envisage\w*|estimate)\b", re.I)
PAST = re.compile(r"\b(had given|had guided|was|were|achieved|achievement|delivered|reported|grew|last year|"
                  r"previous year|last quarter|has been|we did|already|have (actually )?(gone|been|come))\b", re.I)
ANALYST = re.compile(r"\b(street|consensus|analysts?|you (said|mentioned)|industry (is|will))\b", re.I)

METRICS = [   # (metric, keyword pattern, basis, unit). A sentence is cut at each keyword; the figure follows it.
    ("ebit_margin", r"\bebit\b[\w\s-]{0,12}?\bmargins?\b", "level", "%"),
    ("ebitda_margin", r"\b(?:ebitda|operating|opm|ebit)\b[\w\s-]{0,20}?\bmargins?\b|(?<!gross )(?<!net )(?<!pat )\bmargins?\b", "level", "%"),
    ("pat_growth", r"\b(?:pat|net profit|bottom[- ]?line|profit after tax|earnings)\b[\w\s-]{0,25}?\bgrow\w*", "yoy", "%"),
    ("volume_growth", r"\bvolumes?\b[\w\s-]{0,20}?\bgrow\w*", "yoy", "%"),
    ("revenue_growth", r"\b(?:revenue|top[- ]?line|sales|turnover)\b[\w\s-]{0,30}?\bgrow\w*|\bgrow\w*\b[\w\s-]{0,30}?\b(?:revenue|top[- ]?line|sales|turnover)\b|"
                       r"\bgrowth guidance\b|\bguidance (?:of|at|to)\b(?=\s*\d)", "yoy", "%"),
    ("revenue_usd", r"\$\s?\d+(?:\.\d+)?\s*(?:billion|bn)\b", "absolute", "USD bn"),
    ("order_inflow", r"\border(?:s| inflow| intake| booking)", "absolute", "INR cr"),
    ("capex", r"\b(?:capex|capital expenditure|capital investment)\b", "absolute", "INR cr"),
]
KEYWORDS = [(m, re.compile(p, re.I), b, u) for m, p, b, u in METRICS]
SEGMENT = re.compile(r"\b(segment|services|fmeg|division|vertical|software|for this business|c&w|wires|cables|"
                     r"exports?|international|subsidiar\w*)\b", re.I)
PAGE_JUNK = re.compile(r"[A-Z][\w&.,\- ]{2,60}?Limited\s+(?:\w+ \d{1,2}, \d{4}\s+)?(?:Page\s+)?\d+(?:\s+of\s+\d+)?\s*", re.S)
WORDS = {"double digit": (10, None), "double-digit": (10, None), "high single digit": (7, 9), "mid single digit": (4, 6),
         "low double digit": (10, 13), "low teens": (11, 13), "mid teens": (14, 16), "mid-teens": (14, 16), "high teens": (17, 19)}
NUMBER = r"(\d{1,3}(?:\.\d+)?)"
PCT = NUMBER + r"\s*(?:%|percent|per cent)"
CR = r"(?:INR|Rs\.?|₹)\s?(\d[\d,]*(?:\.\d+)?)\s*(?:crores?|cr\b)"
MORE = r"(more than|over|at least|minimum|above|in excess of|upwards of|north of)"


def _horizon(s: str, call: dict) -> str | None:
    fy = C.fiscal_year(call["date"])
    low = s.lower().replace("’", "'")
    m = re.search(r"\bfy\s?'?(?:20)?(\d{2})(?:\s?[-–/]\s?'?(\d{2}))?\b", low)
    if m:
        return f"FY{m.group(2) or m.group(1)}"
    m = re.search(r"financial year\s*'?(?:20)?(\d{2})\s*[-–,' ]+\s*'?(?:20)?(\d{2})", low)
    if m:
        return f"FY{m.group(2)}"
    m = re.search(r"\bby (?:march|mar) (?:20)?(\d{2})\b", low)
    if m:
        return f"FY{m.group(1)}"
    if re.search(r"\b(next|coming) (\d|two|three|four|five|few|couple of) years|medium[- ]term|long[- ]term|\bcagr\b", low):
        return "multi-year"
    if re.search(r"\bnext (financial |fiscal )?year\b", low):
        return f"FY{fy + 1:02d}"
    if re.search(r"\b(h2|second half)\b", low):
        return f"H2FY{fy:02d}"
    return f"FY{fy:02d}"   # Indian calls guide for the current fiscal year unless they say otherwise


def _target(text: str, unit: str) -> tuple[float | None, float | None] | None:
    low = text.lower()
    if unit == "USD bn":
        m = re.search(r"\$\s?(\d+(?:\.\d+)?)\s*(?:billion|bn)", low)
        return (float(m.group(1)), float(m.group(1))) if m else None
    if unit == "%":
        for w, (lo, hi) in WORDS.items():
            if w in low:
                return float(lo), (float(hi) if hi is not None else None)
        m = re.search(NUMBER + r"\s*(%?)\s*(?:to|-|–|and)\s*" + NUMBER + r"\s*(%|percent|per cent)?", low)
        if m and (m.group(2) or m.group(4)):
            lo, hi = sorted([float(m.group(1)), float(m.group(3))])
            return lo, hi
        m = re.search(MORE + r"?\s*(?:of|around|about|approximately|roughly|close to|~|nearly)?\s*" + PCT + r"(\s*plus|\+)?", low)
        if m:
            v = float(m.group(2))
            return (v, None) if (m.group(1) or m.group(3)) else (v, v)
        return None
    nums = [float(x.replace(",", "")) for x in re.findall(CR, text, re.I)]
    if not nums:
        return None
    if len(nums) >= 2 and re.search(r"\d\s*(?:crores?|cr)?\s*(to|-|–)\s*(?:INR|Rs|₹)", text, re.I):
        return min(nums[:2]), max(nums[:2])
    plus = re.search(MORE + r"\s*(?:INR|Rs|₹)", text, re.I) or re.search(r"crores?\s*plus|\d\+", low)
    return (nums[0], None) if plus else (nums[0], nums[0])


def _sane(metric: str, lo: float | None, hi: float | None) -> bool:
    if lo is None:
        return False
    if metric == "ebitda_margin":
        return 2 <= lo <= 70
    if metric.endswith("growth"):
        return -30 <= lo <= 80
    return lo > 0


def _segments(s: str) -> list[tuple[str, str, str, str, int]]:
    """Cut a sentence at metric keywords: [(metric, text from keyword to next keyword, basis, unit, start)]."""
    hits = []
    for metric, rx, basis, unit in KEYWORDS:
        for m in rx.finditer(s):
            hits.append((m.start(), m.end(), metric, basis, unit))
    hits.sort()
    kept = []
    for h in hits:                       # overlapping keywords: the earlier, more specific one wins
        if kept and h[0] < kept[-1][1]:
            continue
        word = s[h[0]:h[1]].lower()
        growth_ctx = "grow" in s[max(0, h[0] - 60):h[0]].lower() or re.search(r"\bmargin guidance\b", s[h[1]:], re.I)
        if word.startswith("guidance") and ((kept and h[0] - kept[-1][1] < 30) or not growth_ctx):
            continue                     # "margin guidance of 17%" belongs to the margin keyword before it
        if h[2] == "revenue_usd" and (not re.search(r"revenue|run[- ]rate|aspiration", s, re.I)
                                      or re.search(r"market cap|deal|tcv|acqui|agreement|valuation", s, re.I)):
            continue
        kept.append(h)
    out = []
    for i, (st, en, metric, basis, unit) in enumerate(kept):
        nxt = kept[i + 1][0] if i + 1 < len(kept) else len(s)
        body = s[st:nxt] if unit == "USD bn" else s[en:nxt]
        out.append((metric, body, basis, unit, st))
    return out


def clean(text: str) -> str:
    return " ".join(PAGE_JUNK.sub(" ", text).split())


def _name_like(speaker: str | None) -> bool:
    return bool(speaker) and len(speaker.split()) <= 4 and all(w[:1].isupper() for w in speaker.replace(".", " ").split())


def rule_guidance(call: dict) -> list[dict]:
    out: dict[tuple, dict] = {}
    text = " ".join(c["text"] for c in call["chunks"]).lower()
    ebit_house = len(re.findall(r"\bebit margin", text)) > len(re.findall(r"\bebitda margin", text))
    for ch in call["chunks"]:
        spk = ch.get("speaker")
        if spk not in call["management"] and _name_like(spk):   # headings like "Now on the guidance" aren't people
            continue
        for s in C.sentences({"text": clean(ch["text"])}):
            if not FORWARD.search(s) or ANALYST.search(s) or "?" in s:
                continue
            if PAST.search(s) and not re.search(r"\b(will|expect\w*|target\w*|guidance (for|is|of|to|remains))\b", s, re.I):
                continue
            horizon = _horizon(s, call)
            strong = bool(re.search(r"guid|target|aspir", s, re.I))
            for metric, body, basis, unit, st in _segments(s):
                if metric == "ebitda_margin" and ebit_house and not re.search(r"ebitda|operating", s[st:st + 25], re.I):
                    metric = "ebit_margin"         # a company that guides on EBIT means EBIT by "margin"
                if SEGMENT.search(s[max(0, st - 30):st] + body[:60]) or re.search(r"\b(fmeg|segment)\b", s, re.I):
                    continue                       # segment-level targets don't map to company tables
                if unit == "INR cr" and not strong and not re.search(r"expect", s, re.I):
                    continue                       # amounts already won/spent are often said in the future tense
                t = _target(body, unit)
                direction = None
                if not t and metric in ("ebitda_margin", "ebit_margin", "revenue_growth") and \
                        re.search(r"\b(will|should|expect\w*)\b", s, re.I):
                    m = re.search(r"\b(improv\w*|expan\w*|better|increas\w*|accelerat\w*|recover\w*|"
                                  r"declin\w*|compress\w*|lower|soft\w*|moderat\w*)\b", body, re.I)
                    if m:
                        direction = "down" if re.match(r"declin|compress|lower|soft|moderat", m.group(1), re.I) else "up"
                        t = (None, None)
                if not t or (direction is None and not _sane(metric, *t)):
                    continue
                key = (metric, horizon)
                if key in out and not (strong and not out[key]["_strong"]):
                    continue
                if direction and key in out:
                    continue                       # a figure beats a direction for the same thread
                out[key] = {"metric": metric, "metric_label": _label(metric), "basis": "directional" if direction else basis,
                            "target_lo": t[0], "target_hi": t[1], "unit": unit, "horizon": horizon,
                            "direction": direction, "confidence_words": FORWARD.search(s).group(0), "quote": C.quote(s),
                            "citation": ch["id"], "page": ch["page"], "_strong": strong}
    for g in out.values():
        g.pop("_strong")
    return list(out.values())


def _label(metric: str) -> str:
    return {"revenue_growth": "Revenue growth", "ebitda_margin": "EBITDA margin", "ebit_margin": "EBIT margin", "pat_growth": "PAT growth",
            "volume_growth": "Volume growth", "order_inflow": "Order inflow", "capex": "Capex",
            "revenue_usd": "Revenue (US$)"}.get(metric, metric)


def model_guidance(call: dict, company: str) -> list[dict] | None:
    turns = [c for c in call["chunks"] if c.get("speaker") in call["management"] or "?" in c["text"]]
    try:
        out = llm.complete_json("cheap", P7_SYSTEM, P7_USER.format(
            company=company, call_period=call["period"], call_date=call["date"].strftime("%b %Y"),
            turns=turns_block(turns)), max_tokens=6000)
    except Exception as e:
        log.warning("P7 %s %s: %s", company, call["period"], e)
        return None
    ids = {c["id"]: c["page"] for c in call["chunks"]}
    return [{**g, "page": ids[g["citation"]]} for g in out.get("guidance") or [] if g.get("citation") in ids]


def extract(call: dict, company: str) -> tuple[list[dict], str]:
    """(guidance items, method) for one call."""
    if llm.available("cheap"):
        g = model_guidance(call, company)
        if g is not None:
            return g, "model"
    return rule_guidance(call), "rules"
