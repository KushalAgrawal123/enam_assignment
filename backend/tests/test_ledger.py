import datetime as dt

from finn.pull import ledger
from finn.pull.guidance import rule_guidance
from finn.pull.numbers import Tables


def test_verdict_boundaries():
    assert ledger.decide(15.0, 12, 15) == "delivered"        # top of the range
    assert ledger.decide(12.0, 12, 15) == "delivered"        # bottom of the range
    assert ledger.decide(15.1, 12, 15) == "beat"
    assert ledger.decide(10.8, 12, 15) == "partial"          # 10% below the low end, exactly
    assert ledger.decide(10.7, 12, 15) == "missed"
    assert ledger.decide(40.0, 15, None) == "delivered"      # "15%+" has no ceiling
    assert ledger.decide(27.4, 27, 27) == "delivered"        # point target: ±0.5 for whole-number OPM
    assert ledger.decide(28.0, 27, 27) == "beat"


BUNDLE = {"tables": {"profit-loss": {"periods": ["2025-03-31", "2026-03-31", "TTM"], "rows": {
    "Sales": [100.0, 116.0, 120.0], "OPM %": [20.0, 22.0, 22.0], "Net Profit": [10.0, 9.0, 9.5],
    "Operating Profit": [20.0, 25.5, 26.0], "Depreciation": [3.0, 5.0, 5.0]}}}}


def call(period, key, items):
    return ({"period": period, "key": key, "url": f"https://x/{key}.pdf"}, items)


def g(metric, horizon, lo, hi, cid, direction=None):
    return {"metric": metric, "metric_label": metric, "horizon": horizon, "unit": "%", "target_lo": lo,
            "target_hi": hi, "direction": direction, "quote": "q", "citation": cid, "page": 1}


def test_threads_actuals_and_revisions():
    t = Tables(BUNDLE)
    out = ledger.build([
        call("May 2025", "2025-05", [g("revenue_growth", "FY26", 12, 14, "T2025-05-p1-0"), g("ebitda_margin", "FY26", 21, 21, "T2025-05-p2-0")]),
        call("Aug 2025", "2025-08", [g("revenue_growth", "FY26", 14, 16, "T2025-08-p1-0"), g("pat_growth", "FY26", 15, None, "T2025-08-p3-0")]),
        call("May 2026", "2026-05", [g("ebit_margin", "FY26", 17, 18, "T2026-05-p1-0"), g("revenue_growth", f"FY{(dt.date.today().year + 2) % 100}", 10, 12, "T2026-05-p2-0"),
                                     g("order_inflow", "FY27", 500, None, "T2026-05-p3-0")]),
    ], t, False, "Test Co")
    by = {i["id"]: i for i in out["items"]}
    rev = by["revenue_growth:FY26"]
    assert rev["verdict"] == "delivered" and rev["quarters"][-1]["actual"] == 16.0          # 116/100 − 1, latest target 14–16
    assert rev["revisions"] == [{"from_period": "May 2025", "to_period": "Aug 2025", "change": "12–14% → 14–16%"}]
    assert by["ebitda_margin:FY26"]["verdict"] == "beat"                                       # 22 vs 21 ± 0.5
    assert by["pat_growth:FY26"]["verdict"] == "missed"                                       # −10% vs 15%+
    assert by["ebit_margin:FY26"]["quarters"][0]["actual"] == 17.7                            # (25.5 − 5) / 116
    assert by["ebit_margin:FY26"]["verdict"] == "delivered"
    assert by["order_inflow:FY27"]["verdict"] == "not_verifiable"
    assert [i for i in out["items"] if i["verdict"] == "pending"]
    ids = {c["id"] for c in out["citations"]}
    assert "TBL-profit-loss-Sales-2026-03-31" in ids and "T2025-08-p1-0" in ids


def test_rule_guidance_reads_management_figures_only():
    def ch(i, spk, text):
        return {"id": f"T2026-05-p1-{i}", "page": 1, "speaker": spk, "text": text}
    c = {"period": "May 2026", "key": "2026-05", "date": dt.date(2026, 5, 1), "management": {"Ana CFO"}, "chunks": [
        ch(0, "Raj Analyst", "What is the guidance for FY27? Will margins improve?"),
        ch(1, "Ana CFO", "So our guidance for FY27 is revenue growth of 12% to 14%, EBITDA margin around 21% and capex of INR 500 crores."),
        ch(2, "Ana CFO", "Last year revenue grew 16% and margins were 20%."),
        ch(3, "Ana CFO", "In the FMEG segment we expect margins of 8% to 10% by FY30."),
        ch(4, "Ana CFO", "We have been reasonably clear on this topic so far."),
    ]}
    got = {(x["metric"], x["horizon"]): (x["target_lo"], x["target_hi"]) for x in rule_guidance(c)}
    assert got == {("revenue_growth", "FY27"): (12.0, 14.0), ("ebitda_margin", "FY27"): (21.0, 21.0),
                   ("capex", "FY27"): (500.0, 500.0)}
