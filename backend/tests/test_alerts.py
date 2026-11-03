"""EOD triggers on fixture prices, including a market-wide down day."""
import datetime as dt

from finn.push.alerts import category_alerts, eod_alerts

D0 = dt.date(2026, 10, 1)
BASE = {"vol_multiple": 2, "vol_lookback": 20, "min_avg_volume": 10_000, "price_move_pct": 5,
        "relative_to_index": False, "overrides": {}, "alert_categories": ["results"], "min_category_tier": "know"}


def series(closes, vols):
    return [{"date": D0 + dt.timedelta(days=i), "close": c, "volume": v} for i, (c, v) in enumerate(zip(closes, vols))]


def flat(n, last_close, last_vol=None, close=100.0, vol=100_000):
    return series([close] * (n - 1) + [last_close], [vol] * (n - 1) + [last_vol or vol])


def test_volume_spike_fires_and_merges_with_price():
    a = eod_alerts({"X": flat(25, 108, 300_000)}, BASE, None, [])
    assert len(a) == 1 and a[0]["kind"] == "price_volume"
    assert a[0]["payload"]["vol_x"] == 3.0 and len(a[0]["reasons"]) == 2      # one alert, two reasons


def test_thin_stock_volume_spike_ignored_below_liquidity_floor():
    assert eod_alerts({"X": flat(25, 100, 30_000, vol=5_000)}, BASE, None, []) == []


def test_market_wide_down_day_relative_to_index():
    index = flat(25, 94)                                 # NIFTY -6%
    stocks = {"A": flat(25, 93), "B": flat(25, 99.5)}    # A falls with the market; B holds up (+5.9% relative)
    absolute = {a["symbol"] for a in eod_alerts(stocks, BASE, index, [])}
    relative = {a["symbol"] for a in eod_alerts(stocks, {**BASE, "relative_to_index": True}, index, [])}
    assert absolute == {"A"}
    assert relative == {"B"}


def test_per_symbol_override_wins():
    s = {"A": flat(25, 106)}
    assert eod_alerts(s, BASE, None, [])
    assert not eod_alerts(s, {**BASE, "overrides": {"A": {"price_move_pct": 8}}}, None, [])


def test_likely_cause_is_top_scored_filing_before_close():
    s = {"A": flat(25, 110)}
    day = s["A"][-1]["date"]
    ts = dt.datetime.combine(day, dt.time(4, 0), dt.timezone.utc)      # 09:30 IST, same session
    filings = [{"symbol": "A", "ts": ts, "subject": "Order win", "url": "u1", "category": "press_release", "score": 0.5},
               {"symbol": "A", "ts": ts, "subject": "Results", "url": "u2", "category": "results", "score": 1.0}]
    a = eod_alerts(s, BASE, None, filings)[0]
    assert a["payload"]["likely_cause"]["subject"] == "Results"


def test_category_alerts_respect_list_and_tier():
    fs = [{"id": "1", "symbol": "A", "ts": 0, "subject": "Q2", "url": None, "category": "results", "tier": "act", "reasons": []},
          {"id": "2", "symbol": "A", "ts": 0, "subject": "Div", "url": None, "category": "dividend", "tier": "act", "reasons": []},
          {"id": "3", "symbol": "A", "ts": 0, "subject": "Ad", "url": None, "category": "results", "tier": "routine", "reasons": []}]
    assert [a["dedupe"] for a in category_alerts(fs, BASE)] == ["filing:1"]
