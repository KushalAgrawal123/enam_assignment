"""Deterministic cards on saved screener pages: one industrial (ASIANPAINT), one bank (HDFCBANK)."""
from pathlib import Path

import pytest

from finn.pull.numbers import _collect_ids, looks_financial, number_cards
from finn.sources.fetchers import parse_screener

FIX = Path(__file__).parent / "fixtures"


def cards(symbol):
    b = parse_screener((FIX / f"screener_{symbol}.html").read_text())
    return b, number_cards(b, looks_financial(b))


def numbers_in(x, path=""):
    """Every numeric 'value' in the card data, with the dict that holds it."""
    if isinstance(x, dict):
        if isinstance(x.get("value"), (int, float)):
            yield path, x
        for k, v in x.items():
            yield from numbers_in(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from numbers_in(v, f"{path}[{i}]")


@pytest.mark.parametrize("symbol", ["ASIANPAINT", "HDFCBANK"])
def test_every_number_carries_a_table_citation(symbol):
    _, cs = cards(symbol)
    for card in cs.values():
        ids = {c["id"] for c in card["citations"]}
        for path, holder in numbers_in(card["data"]):
            if "quarterly_revenue" in path:      # sparkline points: drawn, not quoted
                continue
            refs = [holder["citation"]] if "citation" in holder else holder.get("citations", [])
            assert refs, f"{card['id']}{path} has no citation"
            assert all(r.startswith("TBL-") and r in ids for r in refs), (card["id"], path, refs)


def test_cited_values_match_the_table():
    b, cs = cards("ASIANPAINT")
    for card in cs.values():
        for c in card["citations"]:
            ref = c["table_ref"]
            if ref["section"] == "top":
                assert b["top"][ref["metric"]] == ref["value"]
                continue
            tab = b["tables"][ref["section"]]
            assert tab["rows"][ref["metric"]][tab["periods"].index(ref["period"])] == ref["value"]


def test_industrial_shows_margin_and_leverage():
    _, cs = cards("ASIANPAINT")
    labels = {i["label"] for i in cs["financials"]["data"]["items"]}
    assert {"EBITDA margin (OPM)", "ROCE", "Debt / equity"} <= labels
    assert cs["balance_sheet"]["data"]["working_capital"]["cash_conversion_cycle"]


def test_bank_hides_ebitda_style_metrics():
    b, cs = cards("HDFCBANK")
    assert looks_financial(b)
    labels = {i["label"] for i in cs["financials"]["data"]["items"]}
    assert not labels & {"EBITDA margin (OPM)", "ROCE", "Debt / equity"}
    assert "Financing margin" in labels
    assert cs["cash_quality"]["data"]["flag"] is None and cs["cash_quality"]["gaps"]
    assert all(c["status"] == "ready" for c in cs.values())


def test_de_is_derived_from_cited_cells():
    _, cs = cards("ASIANPAINT")
    de = next(i for i in cs["financials"]["data"]["items"] if i["label"] == "Debt / equity")
    assert len(de["citations"]) == 3 and de["derived"]
