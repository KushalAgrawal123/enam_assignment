"""python -m jobs.warm --freeze [ISO] [--force]

Writes the demo snapshot the web app falls back to (web/public/demo/snapshot.json): the 7 days of filings
before the freeze time, prices for sparklines, companies and settings.

PLAN Delta 8: a snapshot is frozen at the end of every phase, and the one with the most Act items stays the
default. A poorer snapshot is written to demo/archive/ instead unless --force is given.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from finn import config, db

DEMO = config.ROOT / "web" / "public" / "demo"


def _iso(v):
    if isinstance(v, dt.datetime):
        return v.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(v, (dt.date,)):
        return v.isoformat()
    return float(v) if v.__class__.__name__ == "Decimal" else v


def _clean(rows: list[dict]) -> list[dict]:
    return [{k: _iso(v) for k, v in r.items()} for r in rows]


def snapshot(freeze: dt.datetime) -> dict:
    start = freeze - dt.timedelta(days=7)
    filings = db.select("""select id, symbol, ts, subject, url, category, subtype, secondary, score, tier, reasons,
                                  card, card_status from filings where ts between %s and %s order by ts desc""",
                        (start, freeze))
    prices = db.select("""select symbol, date, close, volume from prices
                          where date between %s and %s order by symbol, date""",
                       ((freeze - dt.timedelta(days=90)).date(), freeze.date()))
    companies = db.select("""select symbol, name, sector, mcap_cr, is_financial, in_portfolio, in_research_set
                             from companies order by symbol""")
    s = db.settings()
    return dict(freeze_time=_iso(freeze), companies=_clean(companies), filings=_clean(filings),
                prices=_clean(prices), alerts=[], settings={k: _iso(v) for k, v in s.items()})


def warm_research() -> None:
    """Number cards + documents for the research set; payloads frozen to web/public/demo/research/."""
    from finn.pull import bundle, run

    out = DEMO / "research"
    out.mkdir(parents=True, exist_ok=True)
    for sym in config.RESEARCH:
        run.build_numbers(sym, refresh=True)
        while not bundle.ingest(sym, budget_s=600)["done"]:
            pass
        p = run.payload(sym)
        (out / f"{sym}.json").write_text(json.dumps(p, default=str, separators=(",", ":")))
        print(f"{sym}: {p['documents']}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", nargs="?", const="now")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--research", action="store_true", help="build + ingest the research set, freeze its payloads")
    a = ap.parse_args()
    if a.research:
        warm_research()
    if not a.freeze:
        if a.research:
            return
        raise SystemExit("usage: python -m jobs.warm [--research] --freeze [ISO] [--force]")
    freeze = dt.datetime.now(dt.timezone.utc) if a.freeze == "now" else dt.datetime.fromisoformat(a.freeze)
    snap = snapshot(freeze)
    acts = sum(1 for f in snap["filings"] if f["tier"] == "act")
    DEMO.mkdir(parents=True, exist_ok=True)
    target = DEMO / "snapshot.json"
    if target.exists() and not a.force:
        old = json.loads(target.read_text())
        old_acts = sum(1 for f in old["filings"] if f["tier"] == "act")
        if old_acts > acts:
            target = DEMO / "archive" / f"{freeze:%Y%m%dT%H%M}.json"
            target.parent.mkdir(exist_ok=True)
            print(f"existing snapshot has more Act items ({old_acts} > {acts}); archiving the new one")
    target.write_text(json.dumps(snap, separators=(",", ":")))
    print(f"wrote {target.relative_to(config.ROOT)}: {len(snap['filings'])} filings ({acts} act), "
          f"{len(snap['prices'])} price rows, frozen at {snap['freeze_time']}")


if __name__ == "__main__":
    main()
