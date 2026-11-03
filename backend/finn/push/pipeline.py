"""Push pipeline (BUILD_PLAN §4.4): fetch -> dedupe -> classify -> score -> upsert.

Phase 1 stops at scored filings; cards and alerts are added in Phase 3.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from zoneinfo import ZoneInfo

from .. import config, db
from ..sources import fetchers
from .classify import classify
from . import notify
from .alerts import category_alerts, eod_alerts
from .score import base_weight, score_filing

log = logging.getLogger("finn.pipeline")
IST = ZoneInfo("Asia/Kolkata")
INDEX = config.INDEX_TICKER


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def dedupe(rows: list[dict]) -> list[dict]:
    """Drop repeats: same id, or same ISIN + normalised subject within ±10 minutes (cross-exchange copies)."""
    out: list[dict] = []
    for r in sorted(rows, key=lambda r: r["ts"]):
        if any(o["id"] == r["id"] or (o["isin"] == r["isin"] and _norm(o["subject"]) == _norm(r["subject"])
                                      and abs((o["ts"] - r["ts"]).total_seconds()) <= 600) for o in out[-50:]):
            continue
        out.append(r)
    return out


def _session(ts: dt.datetime) -> dt.date:
    """The first session a filing can move: the same day if filed before the 15:30 IST close, else the next."""
    local = ts.astimezone(IST)
    return local.date() if local.time() < dt.time(15, 30) else local.date() + dt.timedelta(days=1)


_PERIOD = re.compile(r"(quarter|period|half[- ]year|year)( and half[- ]year)? ended,? (on )?(\w+ \d{1,2},? \d{4}|\d{1,2}(st|nd|rd|th)? \w+,? \d{4})", re.I)


def headline(cats: dict, subject: str, text: str) -> str:
    """Readable titles for the cards that lead a results family ("In continuation of our letter…" is not one)."""
    if cats["category"] == "results" and cats.get("subtype") in ("filing", "board_outcome"):
        m = _PERIOD.search(f"{subject} {text}")
        when = f" for the {m.group(1).lower()} ended {m.group(4)}" if m else ""
        return f"Results{when}"
    return subject


def _move_on(symbol: str, ts: dt.datetime, prices: dict[str, list[dict]]) -> float | None:
    """Close-to-close % move on the session the filing could affect (see _session)."""
    series = prices.get(symbol) or []
    day = _session(ts)
    for i, p in enumerate(series):
        if p["date"] >= day and i > 0 and series[i - 1]["close"]:
            return round((float(p["close"]) / float(series[i - 1]["close"]) - 1) * 100, 2)
    return None


def run_poll(start: dt.datetime, end: dt.datetime, rescore: bool = False) -> dict:
    companies = db.select("select symbol, isin, mcap_cr from companies where in_portfolio")
    symbols = [c["symbol"] for c in companies]
    meta = {c["symbol"]: c for c in companies}
    settings = db.settings()

    rows: list[dict] = []
    if config.USE_NSE:
        rows += fetchers.nse_announcements(start, end, symbols)
    if config.USE_BSE:
        rows += fetchers.bse_announcements(start, end, [])
    rows = [r for r in dedupe(rows) if r["symbol"] in meta]

    existing = {r["id"] for r in db.select("select id from filings where id = any(%s)", ([r["id"] for r in rows],))}
    todo = rows if rescore else [r for r in rows if r["id"] not in existing]

    prices: dict[str, list[dict]] = {}
    for p in db.select("select symbol, date, close from prices where date >= %s order by symbol, date",
                       ((start - dt.timedelta(days=10)).date(),)):
        prices.setdefault(p["symbol"], []).append(p)

    # A day's price move is attributed to one filing only: the most material one that session (its likely
    # cause). Otherwise a results-day jump would lift every routine filing the company made that day.
    cats_by_id = {r["id"]: classify(r["subject"], r["text"], r["exch_category"]) for r in todo}
    cause: dict[tuple, tuple[float, str]] = {}
    for r in todo:
        c = cats_by_id[r["id"]]
        key = (r["symbol"], _session(r["ts"]))
        b = base_weight(c["category"], c["subtype"], settings.get("weights"))
        if key not in cause or b > cause[key][0]:
            cause[key] = (b, r["id"])

    out = []
    for r in todo:
        cats = cats_by_id[r["id"]]
        move = _move_on(r["symbol"], r["ts"], prices) if cause[(r["symbol"], _session(r["ts"]))][1] == r["id"] else None
        s = score_filing(cats, r["subject"], r["text"], mcap_cr=float(meta[r["symbol"]]["mcap_cr"] or 0) or None,
                         alert_categories=settings.get("alert_categories"),
                         same_day_move_pct=move, weights=settings.get("weights"))
        subject = headline(cats, r["subject"], r["text"])
        out.append(dict(id=r["id"], symbol=r["symbol"], isin=r["isin"], ts=r["ts"], subject=subject,
                        text=r["text"], url=r["url"], src=r["src"], exch_category=r["exch_category"],
                        has_xbrl=r.get("has_xbrl", False), category=cats["category"], subtype=s["subtype"],
                        secondary=cats["secondary"], method=cats["method"], score=s["score"], tier=s["tier"],
                        reasons=s["reasons"]))
    db.upsert("filings", out, key=["id"], update=[k for k in (out[0] if out else {}) if k not in ("card", "card_status")])
    for o in out:
        if o["tier"] in ("act", "know") and o["category"] in CARD_CATEGORIES:
            db.execute("update filings set card_status = 'pending' where id = %s and card_status in ('none', 'failed')",
                       (o["id"],))
    cards = build_cards()
    new_alerts = category_alerts(out, settings) if not rescore else []
    stored = store_alerts(new_alerts)
    pushed = notify.send_pending()
    db.set_meta("last_poll", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "start": start.isoformat(),
                              "end": end.isoformat(), "fetched": len(rows), "new": len(out)})
    tiers = {t: sum(1 for o in out if o["tier"] == t) for t in ("act", "know", "routine")}
    log.info("poll %s..%s fetched=%d new=%d %s cards=%s alerts=%d telegram=%s", start, end, len(rows), len(out),
             tiers, cards, stored, pushed)
    return dict(fetched=len(rows), new=len(out), **tiers, cards=cards, alerts=stored, telegram=pushed)


CARD_CATEGORIES = {"results", "management_change", "M&A", "fund_raise", "capex", "litigation", "credit_rating",
                   "insider_trading", "pledging", "dividend", "bonus_split", "press_release"}


def build_cards(limit: int = 40) -> dict:
    """Build cards for pending Act/Know filings. A results card waits (stays pending) until screener's table has
    the quarter; it gives up after 3 days. Failures mark the card failed, never the poll."""
    from .mgmt import mgmt_card
    from .oneliner import oneliner
    from .results import pdf_values, period_end_from_text, results_card
    from .. import llm

    pending = db.select("""select f.id, f.symbol, f.ts, f.subject, f.text, f.url, f.category, f.subtype,
                                  c.name, c.is_financial
                           from filings f join companies c using (symbol)
                           where f.card_status = 'pending' order by f.ts desc limit %s""", (limit,))
    screener: dict[str, dict] = {}
    done = waiting = failed = 0
    for f in pending:
        try:
            card = None
            if f["category"] == "results" and f["subtype"] in ("filing", "board_outcome"):
                period = period_end_from_text(f"{f['subject']} {f['text']}") or _last_quarter_end(f["ts"])
                if f["symbol"] not in screener:
                    screener[f["symbol"]] = fetchers.screener_company(f["symbol"])
                b = screener[f["symbol"]]
                pdfv = None
                if llm.available("cheap") and f["url"]:
                    pdfv = pdf_values(fetchers.pdf_pages(f["url"], max_pages=8), period)
                card = results_card(b["tables"].get("quarters"), period, bool(f["is_financial"]), b.get("basis"),
                                    f["url"], pdf_values=pdfv)
                if card is None and dt.datetime.now(dt.timezone.utc) - f["ts"] < dt.timedelta(days=3):
                    waiting += 1
                    continue
            elif f["category"] == "management_change":
                pages = fetchers.pdf_pages(f["url"], max_pages=5) if llm.available("cheap") and f["url"] else None
                card = mgmt_card(f["text"] or f["subject"], f["name"] or f["symbol"], f["url"], pages)
            elif f["category"] != "results":
                pages = fetchers.pdf_pages(f["url"], max_pages=4) if llm.available("cheap") and f["url"] else None
                card = oneliner(f["category"], f["subject"], f["text"] or "", f["url"], pages)
            status = "ready" if card else "none"
            db.execute("update filings set card = %s, card_status = %s where id = %s",
                       (db.Jsonb(card) if card else None, status, f["id"]))
            done += bool(card)
        except Exception as e:  # degrade per card
            log.warning("card %s %s: %s", f["symbol"], f["id"], e)
            db.execute("update filings set card_status = 'failed' where id = %s", (f["id"],))
            failed += 1
    return {"built": done, "waiting": waiting, "failed": failed}


def _last_quarter_end(ts: dt.datetime) -> str:
    d = ts.astimezone(IST).date()
    q_end_month = ((d.month - 1) // 3) * 3          # quarter that ended before this one
    y = d.year if q_end_month else d.year - 1
    m = q_end_month or 12
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - dt.timedelta(days=1)).isoformat()


def store_alerts(alerts: list[dict]) -> int:
    if not alerts:
        return 0
    before = db.select("select count(*) n from alerts")[0]["n"]
    db.upsert("alerts", alerts, key=["dedupe"], update=[])      # first write wins; re-runs don't re-alert
    return db.select("select count(*) n from alerts")[0]["n"] - before


def run_eod(days: int = 90) -> dict:
    companies = db.select("select symbol from companies where in_portfolio or in_research_set")
    symbols = [c["symbol"] for c in companies]
    db.upsert("companies", [dict(symbol=INDEX, name="NIFTY 50", sector="Index")], key=["symbol"], update=["name"])
    rows = fetchers.eod_prices(symbols, days=days, index=INDEX)
    got = {r["symbol"] for r in rows}
    missing = [s for s in symbols if s not in got]
    if missing:  # yfinance gap: rebuild the last two weeks from NSE bhavcopy
        log.warning("yfinance missing %s; falling back to bhavcopy", missing)
        today = dt.datetime.now(IST).date()
        for back in range(0, 15):
            rows += fetchers.bhavcopy_history(today - dt.timedelta(days=back), missing)
    db.upsert("prices", rows, key=["symbol", "date"])
    stored = eod_check()
    pushed = notify.send_pending()
    db.set_meta("last_eod", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "rows": len(rows),
                             "missing_from_yfinance": missing, "alerts": stored})
    log.info("eod rows=%d missing=%s alerts=%d telegram=%s", len(rows), missing, stored, pushed)
    return dict(rows=len(rows), symbols=len(got), missing=missing, alerts=stored, telegram=pushed)


def eod_check() -> int:
    """Run the price/volume triggers on the latest stored session for the portfolio."""
    settings = db.settings()
    series: dict[str, list[dict]] = {}
    for p in db.select("""select symbol, date, close, volume from prices
                          where date >= current_date - 60 order by symbol, date"""):
        series.setdefault(p["symbol"], []).append(p)
    portfolio = {r["symbol"] for r in db.select("select symbol from companies where in_portfolio")}
    filings = db.select("""select id, symbol, ts, subject, url, category, score from filings
                           where ts >= now() - interval '5 days'""")
    alerts = eod_alerts({s: v for s, v in series.items() if s in portfolio}, settings, series.get(INDEX), filings)
    return store_alerts(alerts)
