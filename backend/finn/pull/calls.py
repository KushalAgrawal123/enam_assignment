"""Earnings calls as Pull reads them: stored transcripts -> chunks, the management side, sentences, fiscal years."""
from __future__ import annotations

import datetime as dt
import re

from .. import db
from .chunks import call_key, transcript_chunks

MODERATOR = re.compile(r"moderator|operator|coordinator", re.I)


def call_date(period: str) -> dt.date:
    y, m = map(int, call_key(period).split("-")) if re.match(r"\d{4}-\d{2}$", call_key(period)) else (1900, 1)
    return dt.date(y, m, 1)


def fiscal_year(d: dt.date) -> int:
    """Indian FY number (FY27 ends 31 Mar 2027)."""
    return (d.year + 1 if d.month >= 4 else d.year) % 100


def fy_end(fy: int) -> dt.date:
    return dt.date(2000 + fy, 3, 31)


def load_calls(symbol: str, limit: int = 4) -> list[dict]:
    """The newest `limit` readable transcripts, oldest first: {period, key, date, url, chunks}."""
    rows = db.select("""select url, period, pages from docs where symbol = %s and kind = 'transcript'
                        and jsonb_array_length(pages) > 0 and not coalesce(ocr_needed, false)""", (symbol,))
    calls = {}
    for r in rows:
        k = call_key(r["period"])
        if k not in calls:   # one transcript per call month
            calls[k] = {"period": r["period"], "key": k, "date": call_date(r["period"]), "url": r["url"],
                        "chunks": transcript_chunks(r["pages"], r["period"])}
    out = sorted(calls.values(), key=lambda c: c["date"])[-limit:]
    for c in out:
        c["management"] = management(c["chunks"])
    return out


def management(chunks: list[dict]) -> set[str]:
    """Speakers who answer rather than ask: few of their turns are questions, and they speak at length."""
    stats: dict[str, list[int]] = {}
    for c in chunks:
        s = c.get("speaker")
        if not s or MODERATOR.search(s):
            continue
        st = stats.setdefault(s, [0, 0, 0])
        st[0] += 1
        st[1] += "?" in c["text"]
        st[2] += len(c["text"])
    if not stats:
        return set()
    biggest = max(v[2] for v in stats.values())
    return {s for s, (n, q, chars) in stats.items() if q / n < 0.34 and (chars >= 0.15 * biggest or n >= 4)}


def sentences(chunk: dict) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+(?=[A-Z\"'])", chunk["text"]) if len(s.strip()) > 20]


def quote(s: str, words: int = 30) -> str:
    w = s.split()
    return " ".join(w[:words]) + (" …" if len(w) > words else "")
