"""python -m jobs.eod [--days 90] — end-of-day prices for the portfolio, research set and NIFTY 50.
Alerts on these prices arrive in Phase 3."""
from __future__ import annotations

import argparse
import logging

from finn.push.pipeline import run_eod

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    print(run_eod(ap.parse_args().days))
