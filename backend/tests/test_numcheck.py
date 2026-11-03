from finn.pull import numcheck


def test_numbers_in_handles_rupees_percent_and_exempts_years():
    assert numcheck.numbers_in("Revenue ₹1,234.5 crore, up 12.5% in FY27 (2026)") == [1234.5, 12.5]
    assert numcheck.numbers_in("Q3FY27 margins at 150 bps") == [150.0]


def test_fabricated_numbers_are_removed():
    allowed = numcheck.harvest({"opm": 21.0, "rows": ["Sales 35620"], "quote": "guided 17% to 18%"})
    items = [{"note": "Guided 17–18%; came in at 21%.", "citations": ["T1"]},
             {"note": "Margin rose to 24% on pricing.", "citations": ["T1"]},          # 24 was never provided
             {"note": "Sales reached ₹35,620 cr.", "citations": ["T1"]}]
    kept, dropped = numcheck.filter_items(items, ("note",), allowed, {"T1"})
    assert [k["note"] for k in kept] == [items[0]["note"], items[2]["note"]] and dropped == 1


def test_unknown_citations_are_dropped_and_half_loss_fails_the_card():
    items = [{"note": "No numbers here", "citations": ["T-made-up"]}, {"note": "Fine", "citations": ["T1"]},
             {"note": "Also 99%", "citations": ["T1"]}]
    kept, dropped = numcheck.filter_items(items, ("note",), {1.0}, {"T1"})
    assert len(kept) == 1 and dropped == 2
    assert numcheck.failed(len(kept), dropped)
    assert not numcheck.failed(2, 1)


def test_tolerance_is_one_percent_or_half_a_unit():
    assert not numcheck.bad_numbers("about 100.9", {100.0})
    assert numcheck.bad_numbers("about 102", {100.0}) == [102.0]
    assert not numcheck.bad_numbers("fell 4%", {-4.0})
