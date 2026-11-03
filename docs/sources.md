# Data sources: what works from where

Spike run 3 Nov 2026 from a residential connection in India (PLAN Phase 1, step 1).

| Source | Endpoint | Result | Used for |
|---|---|---|---|
| NSE announcements | `nseindia.com/api/corporate-announcements` (session cookie from the home page) | ✅ JSON with ISIN, NSE category, text, PDF link, XBRL flag. Date ranges work; ~600 filings/day market-wide | **Primary filings feed** |
| NSE `EQUITY_L.csv` | `nsearchives.nseindia.com/content/equities/EQUITY_L.csv` | ✅ 2,623 listed equities with ISIN | Symbol validation, ISINs |
| NSE bhavcopy | `nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_<date>_F_0000.csv.zip` | ✅ | Price fallback |
| yfinance | `RELIANCE.NS`, `^NSEI` | ✅ | EOD prices, market cap, sector |
| screener.in | `/company/<SYMBOL>/consolidated/` | ✅ all sections incl. documents | Pull numbers (Phase 2) |
| BSE announcements | `api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w` | ❌ HTTP 403 to automated clients | Not used (`FINN_USE_BSE=0`) |
| BSE scrip list | `api.bseindia.com/.../ListofScripData/w` | ❌ empty body | Not used; `companies.bse_code` stays null |

BSE blocks scripted access; FINN does not try to get around that. NSE is the primary feed instead, which BUILD_PLAN
already allowed for (`FINN_USE_NSE`). Every portfolio company is NSE-listed, so no filings are lost.

From GitHub Actions: see the "Cloud runner check" section below (filled in when the first workflow run completes).
