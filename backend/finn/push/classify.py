"""Classify an exchange filing into the reference categories (Reference doc §1).

Rules first, model last:
  1. text rules (high precision, ordered; first match wins) over "<exchange category> | <text>"
  2. the exchange's own category, when the text says nothing more specific
  3. P1 LLM fallback (cheap tier), only when 1 and 2 found nothing and a key is configured
Every result says which step decided it (`method`), so a wrong label is easy to trace.
"""
from __future__ import annotations

import logging
import re

from .. import llm

log = logging.getLogger("finn.classify")

CATEGORIES = ["results", "M&A", "fund_raise", "management_change", "litigation", "insider_trading",
              "earnings_call", "investor_meetings", "credit_rating", "dividend", "bonus_split", "capex",
              "press_release", "postal_ballot", "agm_egm", "pledging", "unclassified"]

SENIOR = (r"\b(ceo|cfo|chief executive|chief financial|managing director|md|chairman|chairperson|"
          r"whole[- ]time director|(?<!non-)(?<!non- )(?<!non )executive director|coo|chief operating)\b")

# (category, subtype or None, pattern). Order matters: specific before general.
RULES: list[tuple[str, str | None, str]] = [
    # Call artefacts mention "financial results", so they go before results.
    ("earnings_call", "transcript", r"\btranscript\b"),
    ("earnings_call", "recording", r"\b(audio|video)? ?recording\b|link of (the )?recording"),
    # Not "Con. Call": that phrase is in NSE's category label for every investor-meeting filing.
    ("earnings_call", "notice", r"(earnings|conference) call\b.{0,80}\b(schedule|intimation|invite)"),
    # Results family.
    ("results", "board_notice", r"board.{0,60}\b(scheduled|will be held|to be held|is to meet)\b.{0,200}\bresults\b"),
    ("results", "newspaper_ad", r"newspaper.{0,80}\bresults\b"),
    ("results", "press_release", r"press release.{0,120}\bresults\b|results.{0,40}press release|"
                                 r"press release.{0,160}\b(q[1-4] ?fy\d\d|quarter)\b.{0,60}\b(revenue|profit|ebitda|pat)\b"),
    ("results", "deck", r"\b(investor|analyst|earnings) presentation\b"),
    ("results", "filing", r"\b(un)?audited\b.{0,40}financial results|financial results for the (quarter|period|half)|"
                          r"submitted to the exchange, the (consolidated and standalone )?(un-?audited )?financial results"),
    # Meetings with investors (after results: NSE files results-day notices under the con-call category).
    ("investor_meetings", None, r"schedule of (analyst|investor)?s? ?meet|analyst\(?s?\)?.{0,20}investor\(?s?\)? meet|"
                                r"investor conference|institutional investor meet|analysts?/institutional"),
    # Routine paperwork that would otherwise trip later rules.
    ("unclassified", "esop", r"\besop|\besos|\besps|grant of .{0,20}options|employee stock"),
    ("unclassified", "auditor", r"appointment of (the )?(statutory|secretarial|internal|cost) auditor"),
    ("unclassified", "compliance", r"regulation 74\(5\)|certificate under|trading window|monitoring agency|"
                                   r"loss of share certificate|duplicate share"),
    # Money in.
    ("fund_raise", "qip", r"qualified institution(al)? placement|\bqip\b"),
    ("fund_raise", "preferential", r"preferential (issue|allotment)"),
    ("fund_raise", "rights", r"rights issue"),
    ("fund_raise", "buyback", r"buy-?back"),
    ("fund_raise", "debt", r"non[- ]convertible|\bncds?\b|commercial paper|debentures|bonds?\b"),
    # Ratings, votes, meetings.
    ("credit_rating", None, r"credit rating|rating agency|\b(crisil|icra|care ratings|india ratings|fitch|moody)"),
    ("postal_ballot", None, r"postal ballot"),
    ("agm_egm", None, r"general meeting|\bagm\b|\begm\b"),
    # Disputes and regulators.
    ("litigation", "insolvency", r"insolvency|\bnclat?\b|\bibc\b|resolution process"),
    ("litigation", "regulatory_order", r"action\(?s?\)? taken or orders? passed|show cause|penalt|warning letter|"
                                       r"\busfda\b.{0,40}(observation|form 483|warning)|\bsebi order|tax demand"),
    ("litigation", None, r"litigation|dispute|lawsuit|arbitration"),
    # Clarifications (press_release per the reference) before management/M&A, whose words they quote.
    ("press_release", "clarification", r"rumou?r|news verification|clarification"),
    # People.
    ("management_change", None, r"appoint|resign|retire|cessation|change in (director|management|kmp)|"
                                r"re-?designat|key managerial|company secretary"),
    # Deals.
    ("M&A", "merger", r"amalgamation|merger|demerger|scheme of arrangement"),
    ("M&A", "stake_sale", r"sale of (entire |its )?stake|share purchase agreement|business transfer|divest"),
    ("M&A", "subsidiary_incorporation", r"incorporat\w+.{0,60}subsidiary|wholly[- ]owned subsidiary"),
    ("M&A", "acquisition", r"acqui|joint venture|strategic investment"),
    # Capital returns and share count.
    ("dividend", None, r"dividend"),
    ("bonus_split", None, r"\bbonus\b|stock split|sub-?division of (equity )?shares"),
    ("pledging", None, r"pledg|encumbrance"),
    ("insider_trading", None, r"regulation 7\(2\)|regulation 29|\bsast\b|insider trading|acquisition of shares by promoter"),
    ("capex", None, r"\bcapex\b|capacity expansion|new (plant|facility|unit)|greenfield|brownfield|"
                    r"commissioning of|commercial production"),
    # News.
    ("press_release", "order_win", r"order|contract|letter of (award|intent)|\bloa\b"),
    ("press_release", "business_update", r"\bsales\b.{0,20}(in|for) \w+ 20\d\d|production volume|business update|"
                                         r"monthly business"),
    ("press_release", "product", r"approv(al|ed) (in|by|from)|launch"),
    ("unclassified", "newspaper_ad", r"newspaper"),
    # Companies like Infosys file press releases under the generic "Updates" bucket with a quoted title.
    ("press_release", None, r"informed the exchange regarding '"),
    ("press_release", None, r"press release|media (statement|release)"),
]
COMPILED = [(c, s, re.compile(p, re.I | re.S)) for c, s, p in RULES]

# NSE's own categories that are specific enough to trust when no text rule fired.
EXCHANGE_HINTS: dict[str, tuple[str, str | None]] = {
    "Outcome of Board Meeting": ("results", "board_outcome"),
    "Financial Results": ("results", "filing"),
    "Integrated Filing- Financial": ("results", "filing"),
    "Investor Presentation": ("results", "deck"),
    "Analysts/Institutional Investor Meet/Con. Call Updates": ("investor_meetings", None),
    "Copy of Newspaper Publication": ("unclassified", "newspaper_ad"),
    "Acquisition": ("M&A", "acquisition"),
    "Amalgamation/Merger": ("M&A", "merger"),
    "Other Restructuring": ("M&A", "restructuring"),
    "Change in Management": ("management_change", None),
    "Change in Director(s)": ("management_change", "director"),
    "Appointment": ("management_change", None),
    "Resignation": ("management_change", None),
    "Resignation of Director/KMP/SMP": ("management_change", None),
    "Retirement": ("management_change", None),
    "Cessation": ("management_change", None),
    "Credit Rating": ("credit_rating", None),
    "Credit Rating- Revision": ("credit_rating", None),
    "Dividend": ("dividend", None),
    "Record Date": ("dividend", "record_date"),
    "Bonus": ("bonus_split", None),
    "Bagging/Receiving of orders/contracts": ("press_release", "order_win"),
    "Awarding of order(s)/contract(s)": ("press_release", "order_win"),
    "Press Release": ("press_release", None),
    "Shareholders meeting": ("agm_egm", None),
    "Allotment of Securities": ("fund_raise", None),
    "ESOP/ESOS/ESPS": ("unclassified", "esop"),
    "Corporate Insolvency Resolution Process": ("litigation", "insolvency"),
    "Pendency of Litigation(s)/dispute(s) or the outcome impacting the Company": ("litigation", None),
    "Action(s) taken or orders passed": ("litigation", "regulatory_order"),
    "Monthly Business Updates": ("press_release", "business_update"),
    "Trading Window": ("unclassified", "compliance"),
    "Monitoring Agency Report": ("unclassified", "compliance"),
}

P1_SYSTEM = "You classify Indian stock-exchange corporate announcements."
P1_USER = """Categories: {cats}.
Return {{"category": one of the categories, "subtype": short snake_case label}}.

Subject: {subject}
Text: {text}"""


def _mgmt_subtype(blob: str) -> str:
    b = blob.lower()
    if re.search(SENIOR, b):
        return "senior"
    if "independent director" in b:
        return "independent_director"
    if re.search(r"company secretary|compliance officer|key managerial|\bkmp\b|senior management|\bsmp\b", b):
        return "kmp"
    if "director" in b:
        return "director"
    return "other"


def _secondary(blob: str, primary: str) -> list[str]:
    out = []
    if primary != "dividend" and re.search(r"(interim|final|special) dividend|declared? .{0,20}dividend", blob, re.I):
        out.append("dividend")
    if primary != "bonus_split" and re.search(r"\bbonus issue|stock split|sub-?division", blob, re.I):
        out.append("bonus_split")
    if primary != "fund_raise" and re.search(r"fund ?rais|qualified institution|preferential issue", blob, re.I):
        out.append("fund_raise")
    return out


def classify(subject: str, text: str, exch_category: str | None = None, use_llm: bool = True) -> dict:
    """Return {category, subtype, secondary, method}."""
    exch_category = (exch_category or "").strip()
    blob = f"{exch_category} | {subject or ''} | {text or ''}"
    category = subtype = None
    method = None
    for cat, sub, rx in COMPILED:
        if rx.search(blob):
            category, subtype, method = cat, sub, "rule"
            break
    # Generic NSE buckets ("Updates", "General Updates") carry no signal, so only specific hints are trusted.
    if category is None and exch_category in EXCHANGE_HINTS:
        category, subtype = EXCHANGE_HINTS[exch_category]
        method = "exchange"
    if category is None and use_llm and llm.available("cheap"):
        try:
            out = llm.complete_json("cheap", P1_SYSTEM, P1_USER.format(
                cats=", ".join(CATEGORIES), subject=subject, text=(text or "")[:1500]), max_tokens=200)
            if out.get("category") in CATEGORIES:
                category, subtype, method = out["category"], out.get("subtype"), "llm"
        except Exception as e:
            log.warning("P1 fallback failed: %s", e)
    if category is None:
        category, subtype, method = "unclassified", "unmatched", "default"
    if category == "management_change":
        subtype = _mgmt_subtype(blob)
    return dict(category=category, subtype=subtype or "general", secondary=_secondary(blob, category),
                method=method)
