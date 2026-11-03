"""python -m jobs.source_check — can this machine reach the data sources? Exit 1 if the filings feed is down.

Run on every workflow run so docs/sources.md can say what works from GitHub's runners, not just from home.
"""
from __future__ import annotations

import datetime as dt
import sys

from finn.sources import fetchers


def main() -> int:
    end = dt.datetime.now(dt.timezone.utc)
    ok = True
    checks = {
        "nse_announcements": lambda: len(fetchers.nse_announcements(end - dt.timedelta(days=7), end, ["RELIANCE"])),
        "nse_equity_list": lambda: len(fetchers.nse_equity_list()),
        "yfinance": lambda: len(fetchers.eod_prices(["RELIANCE"], days=5, index=None)),
    }
    for name, fn in checks.items():
        try:
            n = fn()
            print(f"{name}: OK ({n} rows)")
            if n == 0 and name == "nse_announcements":
                ok = False
        except Exception as e:  # report every source, don't stop at the first failure
            print(f"{name}: FAIL {type(e).__name__}: {e}")
            ok = ok and name != "nse_announcements"
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
