import pytest

from finn.push.score import ACT, KNOW, base_weight, score_filing


def cats(category, subtype=None, secondary=()):
    return {"category": category, "subtype": subtype, "secondary": list(secondary)}


@pytest.mark.parametrize("c,expected", [
    (cats("results", "filing"), "act"),
    (cats("management_change", "senior"), "act"),
    (cats("fund_raise", "qip"), "act"),
    (cats("press_release", "order_win"), "know"),
    (cats("earnings_call", "transcript"), "know"),
    (cats("results", "newspaper_ad"), "routine"),
    (cats("unclassified", "esop"), "routine"),
    (cats("investor_meetings"), "routine"),
])
def test_default_tiers(c, expected):
    assert score_filing(c, "", "")["tier"] == expected


def test_tier_boundaries_are_inclusive():
    assert score_filing(cats("x"), "", "", weights={"x": ACT})["tier"] == "act"
    assert score_filing(cats("x"), "", "", weights={"x": ACT - 0.001})["tier"] == "know"
    assert score_filing(cats("x"), "", "", weights={"x": KNOW})["tier"] == "know"
    assert score_filing(cats("x"), "", "", weights={"x": KNOW - 0.001})["tier"] == "routine"


def test_user_weights_override_base():
    assert base_weight("dividend", None) == 0.30
    out = score_filing(cats("dividend"), "Interim dividend", "", weights={"dividend": 0.05})
    assert out["tier"] == "routine"


def test_subtype_weight_beats_category_weight():
    assert base_weight("results", "filing") > base_weight("results", "deck") > base_weight("results", "newspaper_ad")


def test_price_move_lifts_and_explains():
    calm = score_filing(cats("press_release", "order_win"), "Order win", "")
    moved = score_filing(cats("press_release", "order_win"), "Order win", "", same_day_move_pct=-6.5)
    assert moved["score"] == pytest.approx(calm["score"] + 0.20)
    assert "stock moved -6.5% that day" in moved["reasons"]
    small = score_filing(cats("press_release", "order_win"), "Order win", "", same_day_move_pct=2.9)
    assert small["score"] == calm["score"]


def test_small_company_news_counts_for_more():
    big = score_filing(cats("press_release", "order_win"), "", "", mcap_cr=500_000)
    small = score_filing(cats("press_release", "order_win"), "", "", mcap_cr=9_000)
    assert small["score"] > big["score"]
    assert any("small company" in r for r in small["reasons"])


def test_rating_direction_read_from_text():
    down = score_filing(cats("credit_rating"), "Credit Rating", "ICRA has downgraded the long-term rating to A+")
    reaffirm = score_filing(cats("credit_rating"), "Credit Rating", "CRISIL has reaffirmed AA+ (Stable)")
    assert down["tier"] == "act" and reaffirm["tier"] == "know"


def test_senior_departure_scores_above_appointment():
    gone = score_filing(cats("management_change", "senior"), "Resignation of CFO", "")
    new = score_filing(cats("management_change", "senior"), "Appointment of CFO", "")
    assert gone["score"] > new["score"]


def test_score_is_clipped_and_every_bump_has_a_reason():
    out = score_filing(cats("results", "filing", ["dividend"]), "", "", alert_categories=["results"],
                       same_day_move_pct=12.0)
    assert out["score"] == 1.0
    assert len(out["reasons"]) == 4   # label, secondary, alert list, price move
