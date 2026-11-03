"""Exit check for Phase 4: sample citations from the research set's cards and open each receipt.

A table citation must resolve to its row; a document citation must resolve to its page with the quote found.
Usage: python -m jobs.receipt_check [--n 20]
"""
from __future__ import annotations

import argparse
import random

from finn import config, db
from finn.pull import run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    pool = []
    for sym in config.RESEARCH:
        for r in db.select("select card, citations from analyses where symbol = %s", (sym,)):
            pool += [(sym, r["card"], c) for c in r["citations"] or []]
    random.seed(7)
    docs = [p for p in pool if not p[2]["id"].startswith("TBL-")]
    tables = [p for p in pool if p[2]["id"].startswith("TBL-")]
    sample = random.sample(docs, min(len(docs), a.n // 2)) + random.sample(tables, min(len(tables), a.n - a.n // 2))
    misses = 0
    for sym, card, c in sample:
        r = run.receipt(sym, c["id"], c.get("quote"))
        ok = bool(r) and (r["kind"] == "table" or r.get("highlight") is not None)
        misses += not ok
        print(f"{'ok  ' if ok else 'MISS'} {sym:10} {card:13} {c['id']}")
    print(f"\n{len(sample) - misses}/{len(sample)} receipts opened with the source highlighted; {misses} misses")


if __name__ == "__main__":
    main()
