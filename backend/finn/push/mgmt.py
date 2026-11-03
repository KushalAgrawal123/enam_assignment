"""Management-change card: who is leaving, who is arriving, and who the newcomer is.

Facts: P3 on the filing PDF when a cheap-tier key exists; otherwise the exchange's own one-line text, parsed by
rule ("Appointment of Mr X as Chief Financial Officer w.e.f. ..."). Background: Tavily search for incoming people,
a deterministic namesake filter, then P4 to write <=3 bullets, each citing exactly one surviving URL.
"""
from __future__ import annotations

import logging
import os
import re

import requests

from .. import llm

log = logging.getLogger("finn.mgmt")

ACTIONS = {"appoint": "appointment", "resign": "resignation", "retire": "retirement", "cessation": "cessation",
           "redesignat": "redesignation", "re-designat": "redesignation"}
ROLE_CLASS = [("ceo", r"\bceo\b|chief executive"), ("cfo", r"\bcfo\b|chief financial"),
              ("md", r"managing director|\bmd\b"), ("chair", r"chair(man|person)"),
              ("coo", r"\bcoo\b|chief operating"), ("independent_director", r"independent director"),
              ("director", r"director"), ("cs", r"company secretary|compliance officer"), ("kmp", r"key managerial|kmp|senior management")]
_PERSON = re.compile(r"(appoint\w*|resign\w*|retire\w*|cessation|re-?designat\w*)\s+(?:of\s+)?"
                     r"(?:(?:Mr|Mrs|Ms|Dr|Shri|Smt)\.?\s+)?([A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){0,4})"
                     r"(?:,?\s+as\s+(?:the\s+)?([^.;]+?))?(?=\s+(?:of the company|w\.?e\.?f|with effect)|[.;]|$)", re.I)
_DATE = re.compile(r"(?:w\.?e\.?f\.?|with effect from)\s*:?\s*([A-Z][a-z]+ \d{1,2},? \d{4}|\d{1,2}(?:st|nd|rd|th)? [A-Z][a-z]+,? \d{4})")


def role_class(role: str | None) -> str | None:
    r = (role or "").lower()
    for cls, rx in ROLE_CLASS:
        if re.search(rx, r) and not (cls == "director" and "non-executive" in r and "independent" in r):
            return cls
    return None


def facts_from_text(text: str) -> list[dict]:
    """Rule-based fallback on the exchange's one-liner."""
    out = []
    for m in _PERSON.finditer(text or ""):
        verb, name, role = m.group(1).lower(), m.group(2).strip(), (m.group(3) or "").strip() or None
        if name.lower() in {"the", "a", "an", "director", "directors", "management"}:
            continue
        action = next(v for k, v in ACTIONS.items() if verb.startswith(k))
        d = _DATE.search(text)
        out.append({"name": name, "role": role, "role_class": role_class(role), "action": action,
                    "effective_date": d.group(1) if d else None, "reason": None, "page": None, "bio": None})
    return out


P3_SYSTEM = ("You extract management-change facts from Indian stock-exchange filings. Use only the filing text. "
             "Copy profile text verbatim.")
P3_USER = """Return {{"changes": [{{"name": str, "role": str, "action": "appointment"|"resignation"|"cessation"|
"redesignation"|"retirement", "effective_date": "YYYY-MM-DD"|null, "reason": str|null,
"profile": str|null, "previous_employers": [str], "page": int|null}}]}}

{pages}"""


def facts_from_pdf(pages: list[str]) -> list[dict] | None:
    if not llm.available("cheap") or not pages:
        return None
    text = "\n".join(f"[page {i + 1}]\n{p[:5000]}" for i, p in enumerate(pages[:5]))
    try:
        out = llm.complete_json("cheap", P3_SYSTEM, P3_USER.format(pages=text), max_tokens=1500)
    except Exception as e:
        log.warning("P3 failed: %s", e)
        return None
    return [{**c, "role_class": role_class(c.get("role")), "bio": None} for c in out.get("changes") or []
            if c.get("name") and c.get("action") in ACTIONS.values()]


def plausible(snippet: dict, name: str, company: str, role: str | None, employers: list[str]) -> bool:
    """Namesake filter: the snippet must name the person AND tie them to this company, the role, or a past
    employer from the filing. Common names otherwise pull in strangers."""
    blob = f"{snippet.get('title', '')} {snippet.get('content', '')}".lower()
    parts = [p for p in re.split(r"\s+", name.lower()) if len(p) > 1 and not p.endswith(".")]
    if not parts or not all(p in blob for p in (parts[0], parts[-1])):
        return False
    company_words = [w for w in re.split(r"\W+", company.lower()) if len(w) > 3 and w not in {"limited", "india", "industries"}]
    anchors = company_words[:2] + [e.lower() for e in employers if e] + ([role.lower()] if role else [])
    return any(a and a in blob for a in anchors)


P4_SYSTEM = ("You write a terse professional background for an investor. Use only the snippets provided. Every bullet "
             "must cite exactly one URL from the list. If a snippet may refer to a different person with the same "
             "name, ignore it.")
P4_USER = """Person: {name}, incoming {role} at {company}.
Return {{"headline": "<= 12 words, e.g. ex-CFO of X, 20 yrs in auto",
"bullets": [{{"text": "<= 20 words", "url": "<one of the URLs>"}}]}} with at most 3 bullets covering
previous roles, tenure, and education.

Snippets:
{snippets}"""


def background(person: dict, company: str) -> dict | None:
    """Tavily search + namesake filter + P4. None when either key is missing."""
    key = os.getenv("TAVILY_API_KEY")
    if not key or not llm.available("cheap"):
        return None
    q = f"\"{person['name']}\" {person.get('role') or ''} {company} career".strip()
    try:
        r = requests.post("https://api.tavily.com/search", json={"query": q, "max_results": 6},
                          headers={"Authorization": f"Bearer {key}"}, timeout=20)
        r.raise_for_status()
        results = r.json().get("results", [])
    except Exception as e:
        log.warning("tavily: %s", e)
        return None
    kept = [s for s in results if plausible(s, person["name"], company, person.get("role"),
                                            person.get("previous_employers") or [])]
    if not kept:
        return {"headline": None, "bullets": [], "note": "No reliable public background found for this name."}
    snippets = "\n".join(f"[{i}] {s['url']}\n{s.get('title', '')}\n{s.get('content', '')[:700]}" for i, s in enumerate(kept))
    try:
        out = llm.complete_json("cheap", P4_SYSTEM, P4_USER.format(name=person["name"], role=person.get("role") or "",
                                                                  company=company, snippets=snippets), max_tokens=600)
    except Exception as e:
        log.warning("P4 failed: %s", e)
        return None
    urls = {s["url"] for s in kept}
    bullets = [b for b in out.get("bullets") or [] if b.get("url") in urls][:3]   # drop uncited/foreign URLs
    return {"headline": out.get("headline"), "bullets": bullets,
            "sources": [{"url": s["url"], "title": s.get("title", "")} for s in kept]}


def mgmt_card(text: str, company: str, url: str | None, pdf_pages: list[str] | None = None) -> dict | None:
    people = facts_from_pdf(pdf_pages or []) or facts_from_text(text)
    if not people:
        return None
    incoming = [p for p in people if p["action"] == "appointment"]
    outgoing = [p for p in people if p["action"] != "appointment"]
    for p in incoming:
        if p.get("role_class") in ("ceo", "cfo", "md", "chair", "coo", "director", "independent_director"):
            p["bio"] = background(p, company)
    flags = []
    if any(p.get("role_class") in ("ceo", "cfo", "md") for p in outgoing):
        flags.append("top-level departure")
    if any(p.get("reason") and re.search(r"personal|health|other opportunit", p["reason"], re.I) for p in outgoing):
        flags.append("departure reason given as personal/other")
    return {"type": "management_change", "outgoing": outgoing, "incoming": incoming, "flags": flags, "url": url}
