# FINN — Financial Investment Agent

An editor, not a terminal: FINN sends a finite brief of what changed in your portfolio, ranks every filing into
**Act**, **Know** or **Routine**, says why each item is there, and ends.

**Try it on a phone:** https://finn-beryl-delta.vercel.app (installable; add it to your home screen).

**Look up any NSE company:** https://finn-beryl-delta.vercel.app/lookup — every number taps through to the table row it came from.

Status: Phases 1–2 of 5 done (see `PLAN.md`). Live data from NSE, refreshed every 15 minutes by GitHub Actions. If live
data is unavailable the app falls back to a frozen snapshot and says so in the top-right chip.
