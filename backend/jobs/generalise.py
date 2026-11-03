"""Generalisation check (PLAN Phase 5): run the full research job on tickers nobody tuned FINN on.

30 Nifty 500 names: 5 banks/NBFCs, 5 small caps, 2 recent listings, 18 others across sectors. Each stage is
caught separately, so the report says per card whether it passed, was a gap (with its reason) or failed, and
names any unhandled exception. Writes docs/generalise.md.
Usage: python -m jobs.generalise [--symbols A,B] [--budget 150]
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import time
import traceback

from finn import db
from finn.pull import bundle, run

GROUPS = {
    "bank/NBFC": ["SBIN", "KOTAKBANK", "BAJFINANCE", "CHOLAFIN", "PNB"],
    "small cap": ["CAMPUS", "RATEGAIN", "MAPMYINDIA", "ROUTE", "KAYNES"],
    "recent listing": ["SWIGGY", "HYUNDAI"],
    "other": ["MRF", "PAGEIND", "TITAN", "ITC", "DMART", "IRCTC", "ZYDUSLIFE", "TATAPOWER", "COALINDIA", "ONGC",
              "NESTLEIND", "TRENT", "DIVISLAB", "ABB", "CUMMINSIND", "DEEPAKNTR", "PIIND", "VOLTAS"],
}
CARDS = run.NUMBER_CARDS + run.ANALYSIS_CARDS
OUT = pathlib.Path(__file__).resolve().parents[2] / "docs" / "generalise.md"


def one(sym: str, budget: float) -> dict:
    res = {"symbol": sym, "errors": [], "secs": 0.0}
    t0 = time.time()
    for stage, fn in (("numbers", lambda: run.build_numbers(sym, refresh=True)),
                      ("documents", lambda: bundle.ingest(sym, budget_s=budget)),
                      ("analysis", lambda: run.build_analysis(sym, refresh=True))):
        try:
            fn()
        except Exception as e:     # recorded, never raised: the point is to find these
            res["errors"].append(f"{stage}: {type(e).__name__}: {e}"[:300])
            res["trace"] = traceback.format_exc()[-1500:]
            if stage == "numbers":
                break
    rows = {r["card"]: r for r in db.select("select card, status, gaps from analyses where symbol = %s", (sym,))}
    res["cards"] = {c: (rows[c]["status"], " ".join(rows[c]["gaps"] or [])) if c in rows else ("missing", "") for c in CARDS}
    res["docs"] = bundle.doc_status(sym) if not res["errors"] or "numbers" not in res["errors"][0] else None
    res["secs"] = round(time.time() - t0, 1)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols")
    ap.add_argument("--budget", type=float, default=150)
    a = ap.parse_args()
    group_of = {s: g for g, ss in GROUPS.items() for s in ss}
    syms = a.symbols.split(",") if a.symbols else list(group_of)
    results = []
    for s in syms:
        r = one(s, a.budget)
        results.append(r)
        print(s, r["secs"], {c: v[0] for c, v in r["cards"].items()}, r["errors"], flush=True)
    crashes = [r for r in results if r["errors"]]
    lines = [f"# Generalisation run — {dt.date.today().isoformat()}", "",
             f"{len(results)} tickers FINN was never tuned on. Per card: ✓ ready, ○ gap (reason below), ✗ failed, · missing. "
             f"Unhandled exceptions: **{len(crashes)}**.", "",
             "| Symbol | Group | " + " | ".join(CARDS) + " | Docs | Time |", "|" + "---|" * (len(CARDS) + 4)]
    mark = {"ready": "✓", "gap": "○", "failed": "✗", "missing": "·"}
    for r in results:
        d = r["docs"] or {}
        docs = f"{d.get('transcripts', 0)}T{' +AR' if d.get('annual_report') else ''}" if d else "—"
        lines.append(f"| {r['symbol']} | {group_of.get(r['symbol'], '')} | " +
                     " | ".join(mark[r["cards"][c][0]] for c in CARDS) + f" | {docs} | {r['secs']}s |")
    lines += ["", "## Gap reasons", ""]
    reasons: dict[str, list[str]] = {}
    for r in results:
        for c, (st, why) in r["cards"].items():
            if st in ("gap", "failed") and why:
                reasons.setdefault(f"{c}: {why}", []).append(r["symbol"])
    lines += [f"- **{k}** — {', '.join(v)}" for k, v in sorted(reasons.items())]
    if crashes:
        lines += ["", "## Exceptions", ""] + [f"- {r['symbol']}: {'; '.join(r['errors'])}" for r in crashes]
    OUT.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}; {len(crashes)} with exceptions")


if __name__ == "__main__":
    main()
