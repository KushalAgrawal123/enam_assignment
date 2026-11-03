"""Results card from screener's quarterly table: QoQ/YoY, arithmetic verification, banks, period parsing."""
import copy
from pathlib import Path

import pytest

from finn.push.results import TO_CRORE, period_end_from_text, results_card
from finn.sources.fetchers import parse_screener

FIX = Path(__file__).parent / "fixtures"


def quarters(sym):
    return parse_screener((FIX / f"screener_{sym}.html").read_text())["tables"]["quarters"]


def test_industrial_card_values_and_changes():
    q = quarters("ASIANPAINT")
    c = results_card(q, "2026-09-30", False, "consolidated", "u")
    rows = {r["metric"]: r for r in c["rows"]}
    assert [r["metric"] for r in c["rows"]] == ["Revenue", "EBITDA*", "PBT", "PAT"]
    i = q["periods"].index("2026-09-30")
    assert rows["Revenue"]["value_cr"] == q["rows"]["Sales"][i]
    assert rows["Revenue"]["qoq_pct"] == round((q["rows"]["Sales"][i] / q["rows"]["Sales"][i - 1] - 1) * 100, 1)
    assert rows["PAT"]["yoy_pct"] == round((q["rows"]["Net Profit"][i] / q["rows"]["Net Profit"][i - 4] - 1) * 100, 1)
    assert c["verified"] and c["source"] == "screener" and c["ebitda_note"]


def test_corrupted_history_makes_the_card_unverified():
    q = copy.deepcopy(quarters("ASIANPAINT"))
    i = q["periods"].index("2026-06-30")          # last quarter's PBT, off by a factor of ten
    q["rows"]["Profit before tax"][i] *= 10
    c = results_card(q, "2026-09-30", False, "consolidated", "u")
    assert not c["verified"]
    assert any("last quarter" in x for x in c["issues"])


def test_filing_numbers_must_agree_with_the_table():
    q = quarters("ASIANPAINT")
    i = q["periods"].index("2026-09-30")
    ok = results_card(q, "2026-09-30", False, None, "u", pdf_values={"revenue": q["rows"]["Sales"][i]})
    bad = results_card(q, "2026-09-30", False, None, "u", pdf_values={"revenue": q["rows"]["Sales"][i] * 1.2})
    assert ok["verified"] and ok["source"] == "pdf"
    assert not bad["verified"]


def test_bank_schema_drops_ebitda():
    c = results_card(quarters("HDFCBANK"), "2026-09-30", True, "consolidated", "u")
    assert [r["metric"] for r in c["rows"]] == ["Revenue", "PBT", "PAT"]
    assert c["margin"] == {} and "Bank" in c["ebitda_note"]
    assert c["verified"]


def test_quarter_not_in_table_yet_returns_none():
    assert results_card(quarters("ASIANPAINT"), "2026-12-31", False, None, "u") is None


@pytest.mark.parametrize("text,expected", [
    ("financial results for the quarter and half year ended September 30, 2026", "2026-09-30"),
    ("Unaudited Financial Results for the quarter ended 30th June 2026", "2026-06-30"),
    ("results for the period ended 31 March, 2026", "2026-03-31"),
    ("no date here", None),
])
def test_period_end_from_text(text, expected):
    assert period_end_from_text(text) == expected


def test_unit_normalisation_to_crore():
    assert 7_32_772 * TO_CRORE["lakh"] == pytest.approx(7327.72)     # BEL files in ₹ lakh
    assert 21793.64 * TO_CRORE["crore"] == 21793.64
    assert 1_000 * TO_CRORE["million"] == 100
