"""Management's characterisations of recent performance, once per transcript (P8; a rule extractor without a key).

The rule path keeps management sentences about the present or recent past that name a topic it can test
against tables (margins, growth, working capital, cash flow, debt) and carry a clear direction word.
"""
from __future__ import annotations

import logging
import re

from .. import llm
from . import calls as C
from .guidance import FORWARD, SEGMENT, _name_like, clean
from .prompts import P8_SYSTEM, P8_USER, turns_block

log = logging.getLogger("finn.claims")

TOPICS = [  # (topic, pattern, testable screener metric)
    ("margins", r"\b(ebitda|operating|ebit)? ?margins?\b", "OPM %"),
    ("working_capital", r"\b(working capital|receivables?|debtor days|DSO|collections?)\b", "Debtor Days"),
    ("cash_flow", r"\b(cash flows?|cash generation|operating cash|free cash)\b", "Cash from Operating Activity"),
    ("debt", r"\b(debt|borrowings?)\b(?! ?free)", "Borrowings"),
    ("growth", r"\b(revenue|top ?line|sales)\b", "Sales growth"),
    ("demand", r"\bdemand\b", None),
]
UP = r"(improv\w*|strong\w*|healthy|robust|record|expan\w*|better|increas\w*|grew|grow\w*|higher|up|rose|accelerat\w*)"
DOWN = r"(declin\w*|pressure\w*|weak\w*|soft\w*|lower|subdued|contract\w*|challeng\w*|slow\w*|fell|dip\w*|muted|down)"
# For these topics "lower"/"reduced" is good news.
INVERTED = {"working_capital", "debt"}


def _polarity(topic: str, s: str) -> str | None:
    """Direction words within 60 characters of the topic word; none or both -> no claim."""
    up, down = re.search(rf"\b{UP}\b", s, re.I), re.search(rf"\b{DOWN}\b|\breduc\w*", s, re.I)
    if bool(up) == bool(down):
        return None
    pos = bool(up)
    if topic in INVERTED and re.search(r"\b(lower|reduc\w*|declin\w*|fell|down)\b", s, re.I):
        pos = True
    return "positive" if pos else "negative"


def rule_claims(call: dict) -> list[dict]:
    out, seen = [], set()
    for ch in call["chunks"]:
        spk = ch.get("speaker")
        if spk not in call["management"] and _name_like(spk):
            continue
        for s in C.sentences({"text": clean(ch["text"])}):
            if "?" in s or (FORWARD.search(s) and re.search(r"\b(will|expect\w*|guid\w*|target\w*)\b", s, re.I)):
                continue
            if not re.search(r"\b(we|our|us)\b", s, re.I) or SEGMENT.search(s) or \
                    re.search(r"\b(would|could|might|longer term|going forward)\b", s, re.I):
                continue
            for topic, pat, metric in TOPICS:
                m = re.search(pat, s, re.I)
                if topic in seen or not m:
                    continue
                pol = _polarity(topic, s[max(0, m.start() - 60):m.end() + 60])
                if not pol:
                    continue
                seen.add(topic)
                out.append({"topic": topic, "claim": C.quote(s, 20), "polarity": pol, "testable_metric": metric,
                            "quote": C.quote(s), "citation": ch["id"], "page": ch["page"]})
                break
    return out[:10]


def model_claims(call: dict, company: str) -> list[dict] | None:
    turns = [c for c in call["chunks"] if c.get("speaker") in call["management"]]
    try:
        out = llm.complete_json("cheap", P8_SYSTEM, P8_USER.format(company=company, call_period=call["period"],
                                                                  turns=turns_block(turns)), max_tokens=4000)
    except Exception as e:
        log.warning("P8 %s %s: %s", company, call["period"], e)
        return None
    ids = {c["id"]: c["page"] for c in call["chunks"]}
    return [{**c, "page": ids[c["citation"]]} for c in out.get("claims") or [] if c.get("citation") in ids]


def extract(call: dict, company: str) -> tuple[list[dict], str]:
    if llm.available("cheap"):
        c = model_claims(call, company)
        if c is not None:
            return c, "model"
    return rule_claims(call), "rules"
