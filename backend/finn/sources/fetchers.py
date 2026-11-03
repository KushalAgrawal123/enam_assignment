"""Data sources. Plumbing only: fetch, normalise, return plain dicts.

Filings: NSE corporate announcements (primary). BSE's API refuses automated requests (docs/sources.md), so
bse_announcements is disabled unless FINN_USE_BSE=1.
Prices: yfinance, with NSE bhavcopy as the fallback.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import logging
import re
import time
import zipfile
from functools import lru_cache
from zoneinfo import ZoneInfo

import warnings

import requests

warnings.filterwarnings("ignore", message=".*inplace keyword.*")

log = logging.getLogger("finn.fetch")
IST = ZoneInfo("Asia/Kolkata")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
NSE = "https://www.nseindia.com"


class SourceError(RuntimeError):
    pass


# ---------------------------------------------------------------- NSE ---

_nse: requests.Session | None = None


def _nse_session(fresh: bool = False) -> requests.Session:
    global _nse
    if _nse is None or fresh:
        s = requests.Session()
        s.headers.update({**UA, "Referer": NSE + "/", "Accept": "application/json, text/plain, */*"})
        s.get(NSE, timeout=20)               # NSE issues its session cookies on the home page
        _nse = s
    return _nse


def _nse_get(path: str, params: dict) -> list | dict:
    last: Exception | None = None
    for attempt in range(3):
        try:
            r = _nse_session(fresh=attempt > 0).get(NSE + path, params=params, timeout=30)
            if r.status_code == 200 and r.text.strip():
                return r.json()
            last = SourceError(f"NSE {path} -> HTTP {r.status_code}")
        except (requests.RequestException, ValueError) as e:
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise SourceError(f"NSE {path} failed: {last}")


def _parse_nse_ts(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%d-%b-%Y %H:%M:%S").replace(tzinfo=IST).astimezone(dt.timezone.utc)


def nse_announcements(start: dt.datetime, end: dt.datetime, symbols: list[str]) -> list[dict]:
    """Announcements for `symbols` between start and end (any tz). One request per symbol."""
    out: list[dict] = []
    params = dict(index="equities", from_date=start.astimezone(IST).strftime("%d-%m-%Y"),
                  to_date=end.astimezone(IST).strftime("%d-%m-%Y"))
    for sym in symbols:
        try:
            rows = _nse_get("/api/corporate-announcements", {**params, "symbol": sym})
        except SourceError as e:
            log.warning("announcements %s: %s", sym, e)
            continue
        for r in rows if isinstance(rows, list) else []:
            ts = _parse_nse_ts(r["an_dt"])
            if not (start <= ts <= end):
                continue
            text = (r.get("attchmntText") or "").strip()
            out.append(dict(
                id=f"NSE-{r['seq_id']}", symbol=r.get("symbol") or sym, isin=r.get("sm_isin"), ts=ts,
                exch_category=(r.get("desc") or "").strip(), subject=_subject(r.get("desc"), text),
                text=text, url=r.get("attchmntFile"), src="NSE", has_xbrl=bool(r.get("hasXbrl"))))
        time.sleep(0.4)
    return out


_BOILER = re.compile(r"^.{0,120}?\b(has|have)?\s*(informed|submitted to|informs|filed with) (the )?exchange,?\s*"
                     r"(about|regarding|that|on|the)?\s*", re.I)


def _subject(desc: str | None, text: str) -> str:
    """NSE has no subject line: the first sentence of the text minus "X Ltd has informed the Exchange about"."""
    t = re.sub(r"\b(Mr|Mrs|Ms|Dr|Shri|Smt|No|Rs|i\.e|viz|Ltd|Co)\.\s", lambda m: m.group(1) + " ", text or "")
    first = t.split(". ")[0].strip()
    first = _BOILER.sub("", first).strip(" '\"").rstrip(".").strip(" '\"")
    first = first[:1].upper() + first[1:] if first else ""
    if len(first) < 4:
        first = (desc or "Announcement").strip()
    return (first[:200] + "…") if len(first) > 200 else first


@lru_cache(maxsize=1)
def nse_equity_list() -> dict[str, dict]:
    """{SYMBOL: {name, isin, series, listed}} from NSE's EQUITY_L.csv (every listed equity)."""
    r = requests.get("https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv", headers=UA, timeout=30)
    r.raise_for_status()
    out = {}
    for row in csv.DictReader(io.StringIO(r.text)):
        row = {k.strip(): (v or "").strip() for k, v in row.items()}
        out[row["SYMBOL"]] = dict(name=row["NAME OF COMPANY"], isin=row["ISIN NUMBER"], series=row["SERIES"],
                                  listed=row["DATE OF LISTING"])
    return out


# ---------------------------------------------------------------- BSE ---

def bse_announcements(start: dt.datetime, end: dt.datetime, scrip_codes: list[str]) -> list[dict]:
    """Disabled: BSE's API returns 403 to automated clients (spike, 3 Nov 2026). Kept for the contract."""
    raise SourceError("BSE announcements are disabled (FINN_USE_BSE=0); see docs/sources.md")


# ------------------------------------------------------------- prices ---

def eod_prices(symbols: list[str], days: int = 90, index: str | None = "^NSEI") -> list[dict]:
    """Daily OHLCV for NSE symbols (and the index under its own ticker) from yfinance."""
    import yfinance as yf

    tickers = [f"{s}.NS" for s in symbols] + ([index] if index else [])
    df = yf.download(tickers, period=f"{days}d", interval="1d", progress=False, auto_adjust=False,
                     group_by="ticker", threads=True)
    out = []
    for t in tickers:
        if t not in df.columns.get_level_values(0):
            log.warning("yfinance returned nothing for %s", t)
            continue
        sub = df[t].dropna(subset=["Close"])
        sym = t[:-3] if t.endswith(".NS") else t
        for idx, r in sub.iterrows():
            out.append(dict(symbol=sym, date=idx.date(), open=_f(r["Open"]), high=_f(r["High"]), low=_f(r["Low"]),
                            close=_f(r["Close"]), volume=int(r["Volume"]) if r["Volume"] == r["Volume"] else None))
    return out


def bhavcopy_history(day: dt.date, symbols: list[str]) -> list[dict]:
    """One day's EQ-series OHLCV from the NSE bhavcopy (fallback when yfinance fails)."""
    url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{day:%Y%m%d}_F_0000.csv.zip"
    r = requests.get(url, headers=UA, timeout=30)
    if r.status_code != 200:
        return []
    z = zipfile.ZipFile(io.BytesIO(r.content))
    want = set(symbols)
    out = []
    for row in csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode())):
        if row["TckrSymb"] in want and row["SctySrs"] == "EQ":
            out.append(dict(symbol=row["TckrSymb"], date=day, open=_f(row["OpnPric"]), high=_f(row["HghPric"]),
                            low=_f(row["LwPric"]), close=_f(row["ClsPric"]), volume=int(float(row["TtlTradgVol"]))))
    return out


def company_profile(symbol: str) -> dict:
    """Sector, industry and market cap (₹ crore) from yfinance. Best effort."""
    import yfinance as yf

    t = yf.Ticker(f"{symbol}.NS")
    out: dict = {}
    try:
        out["mcap_cr"] = round(float(t.fast_info["marketCap"]) / 1e7, 1)
    except Exception:
        out["mcap_cr"] = None
    try:
        info = t.info
        out["sector"] = info.get("sector")
        out["industry"] = info.get("industry")
    except Exception:
        out["sector"] = out["industry"] = None
    return out


def _f(v) -> float | None:
    try:
        v = float(v)
        return None if v != v else round(v, 4)
    except (TypeError, ValueError):
        return None
