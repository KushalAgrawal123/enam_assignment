"""Triggered alerts: end-of-day price/volume moves and material filings, against thresholds the user sets.

EOD: one merged alert per symbol per session when volume >= k x its N-session average (and that average clears a
liquidity floor) and/or |move| >= X% (optionally measured against NIFTY 50, so a market-wide fall doesn't fire
for every stock). Per-symbol overrides win over the global settings. Each alert names its likely cause: the
top-scored filing from that company in the 24 hours before the close.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
TIER_RANK = {"routine": 0, "know": 1, "act": 2}


def _setting(settings: dict, symbol: str, key: str):
    return (settings.get("overrides") or {}).get(symbol, {}).get(key, settings.get(key))


def _ret(series: list[dict], i: int) -> float | None:
    if i < 1 or not series[i - 1]["close"]:
        return None
    return (float(series[i]["close"]) / float(series[i - 1]["close"]) - 1) * 100


def eod_alerts(prices: dict[str, list[dict]], settings: dict, index_series: list[dict] | None,
               filings: list[dict], day: dt.date | None = None) -> list[dict]:
    """prices: {symbol: [{date, close, volume}] ascending}. filings: [{symbol, ts, subject, url, category, score}]."""
    idx = {p["date"]: i for i, p in enumerate(index_series or [])}
    out = []
    for sym, series in prices.items():
        if len(series) < 3:
            continue
        i = len(series) - 1 if day is None else next((k for k, p in enumerate(series) if p["date"] == day), None)
        if i is None or i < 1:
            continue
        today = series[i]
        lookback = int(_setting(settings, sym, "vol_lookback") or 20)
        hist = [float(p["volume"]) for p in series[max(0, i - lookback):i] if p.get("volume")]
        avg = sum(hist) / len(hist) if hist else None
        vol_x = round(float(today["volume"]) / avg, 2) if avg and today.get("volume") else None
        ret = _ret(series, i)
        index_ret = None
        if index_series and today["date"] in idx:
            index_ret = _ret(index_series, idx[today["date"]])
        rel = _setting(settings, sym, "relative_to_index")
        move = (ret - index_ret) if (rel and ret is not None and index_ret is not None) else ret

        reasons = []
        k = float(_setting(settings, sym, "vol_multiple") or 2)
        floor = float(_setting(settings, sym, "min_avg_volume") or 0)
        if vol_x is not None and vol_x >= k and avg >= floor:
            reasons.append(f"volume {vol_x:.1f}× its {len(hist)}-session average (your threshold {k:g}×)")
        x = float(_setting(settings, sym, "price_move_pct") or 5)
        if move is not None and abs(move) >= x:
            what = "relative to NIFTY 50" if rel and index_ret is not None else "on the day"
            reasons.append(f"moved {move:+.1f}% {what} (your threshold ±{x:g}%)")
        if not reasons:
            continue

        close = dt.datetime.combine(today["date"], dt.time(15, 30), IST)
        window = [f for f in filings if f["symbol"] == sym and close - dt.timedelta(hours=24) <= f["ts"] <= close]
        cause = max(window, key=lambda f: float(f["score"]), default=None)
        glyph = "▲" if (ret or 0) >= 0 else "▼"
        title = f"{sym} {glyph} {ret:+.1f}%" + (f" on {vol_x:.1f}× volume" if vol_x and vol_x >= k else "")
        out.append({
            "dedupe": f"eod:{sym}:{today['date'].isoformat()}", "symbol": sym, "kind": "price_volume",
            "ts": close.astimezone(dt.timezone.utc), "title": title, "reasons": reasons,
            "payload": {"date": today["date"].isoformat(), "close": float(today["close"]),
                        "ret_pct": round(ret, 2) if ret is not None else None,
                        "index_ret_pct": round(index_ret, 2) if index_ret is not None else None, "vol_x": vol_x,
                        "likely_cause": {"subject": cause["subject"], "url": cause.get("url"),
                                         "category": cause["category"]} if cause else None}})
    return out


def category_alerts(filings: list[dict], settings: dict) -> list[dict]:
    """New filings in a category the user asked to be alerted on, at or above their minimum tier."""
    cats = set(settings.get("alert_categories") or [])
    floor = TIER_RANK.get(settings.get("min_category_tier") or "know", 1)
    return [{"dedupe": f"filing:{f['id']}", "symbol": f["symbol"], "kind": "filing", "ts": f["ts"],
             "title": f"{f['symbol']}: {f['subject']}", "reasons": f.get("reasons") or [],
             "payload": {"filing_id": f["id"], "url": f.get("url"), "category": f["category"], "tier": f["tier"]}}
            for f in filings if f["category"] in cats and TIER_RANK.get(f["tier"], 0) >= floor]
