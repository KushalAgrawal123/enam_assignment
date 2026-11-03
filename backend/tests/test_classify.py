"""Classifier accuracy on real NSE filings, labelled by hand against the reference categories.

classify_labelled.json: 96 portfolio filings (27 Oct – 3 Nov 2026). The rules were tuned on these.
classify_holdout.json: 34 filings from 12 other companies, labelled before the classifier ever saw them and
never tuned on. The holdout number is the honest one.
"""
import json
from pathlib import Path

import pytest

from finn.push.classify import classify

FIX = Path(__file__).parent / "fixtures"


def accuracy(name: str) -> tuple[float, list]:
    cases = json.loads((FIX / name).read_text())
    misses = []
    for c in cases:
        got = classify(c["subject"], c["text"], c["exch_category"], use_llm=False)["category"]
        if got != c["label"]:
            misses.append((c["id"], c["label"], got, c["text"][:90]))
    return 1 - len(misses) / len(cases), misses


@pytest.mark.parametrize("name", ["classify_labelled.json", "classify_holdout.json"])
def test_accuracy_at_least_90pct(name):
    acc, misses = accuracy(name)
    print(f"\n{name}: {acc:.1%}", *misses, sep="\n  ")
    assert acc >= 0.90


@pytest.mark.parametrize("text,exch,category,subtype", [
    ("Appointment of Mr Rajiv Dube as Non- Executive Director", "Appointment", "management_change", "director"),
    ("Resignation of Chief Financial Officer", "Resignation", "management_change", "senior"),
    ("Appointment of Mrs X as Non-Executive Independent Director", "Appointment", "management_change",
     "independent_director"),
    ("Transcript of the discussion on the Unaudited Financial Results for the quarter ended September 30, 2026",
     "Analysts/Institutional Investor Meet/Con. Call Updates", "earnings_call", "transcript"),
    ("Bharti Airtel Limited has informed the Exchange about Schedule of meet.",
     "Analysts/Institutional Investor Meet/Con. Call Updates", "investor_meetings", "general"),
    ("Appointment of Statutory Auditors Pursuant to Mandatory Auditor Rotation", "General Updates",
     "unclassified", "auditor"),
    ("Allotment of 7683981 securities pursuant to Qualified Institution Placement", "Allotment of Securities",
     "fund_raise", "qip"),
])
def test_specific_cases(text, exch, category, subtype):
    out = classify(text, text, exch, use_llm=False)
    assert (out["category"], out["subtype"]) == (category, subtype)


def test_secondary_dividend_on_results_day():
    text = "The Board approved the unaudited financial results for the quarter ended September 30, 2026 and declared an interim dividend of Rs 5 per share."
    out = classify(text, text, "Outcome of Board Meeting", use_llm=False)
    assert out["category"] == "results" and "dividend" in out["secondary"]


def test_no_signal_falls_back_to_unclassified_without_llm():
    out = classify("Disclosure under Regulation 30", "Disclosure under Regulation 30", "General Updates", use_llm=False)
    assert out == {"category": "unclassified", "subtype": "unmatched", "secondary": [], "method": "default"}
