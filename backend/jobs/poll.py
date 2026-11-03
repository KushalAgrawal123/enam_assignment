"""python -m jobs.poll [--since 7d|36h] [--rescore]

Without --since, polls from one hour before the last successful poll (overlap absorbs late filings),
or the last 24 hours on a first run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import re

from finn import db
from finn.push.pipeline import run_poll


def parse_span(s: str) -> dt.timedelta:
    m = re.fullmatch(r"(\d+)([dh])", s)
    if not m:
        raise SystemExit(f"--since must look like 7d or 36h, got {s!r}")
    n = int(m.group(1))
    return dt.timedelta(days=n) if m.group(2) == "d" else dt.timedelta(hours=n)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--rescore", action="store_true", help="re-classify and re-score filings already stored")
    a = ap.parse_args()
    end = dt.datetime.now(dt.timezone.utc)
    if a.since:
        start = end - parse_span(a.since)
    else:
        last = db.get_meta("last_poll")
        start = (dt.datetime.fromisoformat(last["end"]) - dt.timedelta(hours=1)) if last else end - dt.timedelta(days=1)
    print(run_poll(start, end, rescore=a.rescore))


if __name__ == "__main__":
    main()
