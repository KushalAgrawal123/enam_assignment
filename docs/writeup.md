# FINN — covering note

**Prototype:** https://finn-beryl-delta.vercel.app · **Repo:** https://github.com/KushalAgrawal123/enam_assignment ·
**Build history:** [docs/build-history/](build-history/) · **Video:** _link to be added_

## What I built
FINN is an editor, not a terminal. It ranks every filing from your portfolio into **Act**, **Know** or **Routine**,
says why each item is there, and ends. Triggers are written as editable sentences, such as "tell me when a stock
trades more than **2×** its **20**-day volume…". Results cards show QoQ and YoY numbers that are checked by
arithmetic. Pull works on any NSE ticker. Its centrepiece is a **Promise ledger**: what management guided on each of
its last four calls, against what the reported tables show. Every number and quote opens its source (**Receipts**).

## Key decisions and tradeoffs
- **Models never write numbers.** Numbers come from tables. Model text passes a post-check that strips any figure
  not present in its inputs, and any citation it wasn't given. This trades coverage for trust.
- **Every card has a rule path.** FINN runs end to end with no model keys, at ₹0 ([cost.md](cost.md)). The rule
  path decides ledger verdicts in code (inside the range is delivered, above is beat, within 10% below is partial,
  otherwise missed), and every line it shows is a verbatim quote. Keys add written analysis on top; they never
  replace the arithmetic.
  - Example: HCLTECH guided an EBIT margin of 17–18% for FY26, and its tables show 17.2%, so the verdict is delivered.
  - Example: KPIT said FY26 margins would rise; they fell from 21% to 19%, so the verdict is missed.
- **Rules-first classification** (91% on a held-out set), with a model only for leftovers. This is cheap,
  deterministic and explainable.
- **Materiality is a visible weight table**, not a model's "importance" score. The user can tune it, and FINN learns
  from triage: after three "Noted" swipes on a category, it offers to make that category routine.
- **Model routing for when keys are added:** a cheap model for extraction (once per transcript, cached by content
  hash) and a strong model for three synthesis calls per company. A first research run is estimated at about ₹15;
  a second view costs ₹0 (measured as 0 calls).
- **NSE is the only filings feed.** BSE's API refuses automated clients, and I didn't work around that. NSE's XBRL
  index stops in January 2025, so results are read from screener's table and checked by its arithmetic identities
  (all 9 cards in results week verified, and hand-checked against the filed PDFs).
- **A PWA, not a native app**, so a reviewer needs only a link. Telegram covers push.
- **Free infrastructure:** Vercel (web and API), Supabase and GitHub Actions. A frozen demo snapshot means the demo
  never depends on scraping that day.
- **Single-user auth:** a shared token held by the web app's server routes. It never reaches the browser.

## Evidence
- **Tests:** 70 backend tests (classifier, scoring, digest parity, results arithmetic, alerts, ledger boundaries,
  number check, and a check that Pull has no web or search imports) plus the web tests, all run in CI.
- **Lighthouse mobile Performance:** Brief 98, Watch 96, research page 94.
- **Receipts:** 20 of 20 sampled receipts opened with the cited cell or sentence highlighted (`jobs.receipt_check`).
- **Generalisation:** 30 tickers FINN was never tuned on (banks, small caps, recent listings): 0 unhandled
  exceptions, all number cards built. Every gap carries its reason ([generalise.md](generalise.md)).

## What I deliberately left out
Native app and native push, voice, intraday data, a vector database (transcripts fit in context, and annual reports
are cut into sections by heading), multi-user accounts, LinkedIn scraping, full annual-report parsing, and valuation
or price targets.

## Where I'd take it next
- Segment-level promise tracking, such as FMEG margins at Polycab.
- Constant-currency guidance checked against reported USD revenue.
- Learning materiality weights from triage instead of offering one category at a time.
- Peer comparisons built from primary sources only.
- Alerts at announcement time.
- Native push.
- Red-flag scans of the auditor's report and related-party notes.
- A shared team brief with annotations.
