# What FINN costs to run

Measured on 3 Nov 2026 from `llm.usage_summary()` (the `llm_cache` table logs every model call, its tokens and ₹ cost)
and the platforms' dashboards.

## As deployed today: ₹0

| Item | Usage | Cost |
|---|---|---|
| Model calls (all tiers) | **0 calls**: no model keys are configured, so every card runs its rule path | ₹0 |
| Vercel (web + API) | Hobby plan; API functions run a few seconds per research request | ₹0 |
| Supabase Postgres | 14 MB of 500 MB; 85 filings, 61 transcripts, 10 annual-report sections | ₹0 |
| GitHub Actions | push poll every 15 min + EOD; public repo, so minutes are free | ₹0 |
| **Total** | warming 5 research companies + 30 generalisation tickers + one day of Push | **₹0** |

`usage_summary()` output at the time of writing:

```
{'by_model': [], 'total_cost_inr': 0}
```

## With model keys: estimate, to be replaced by measurement

Prices at ₹88/US$ (set in `backend/finn/config.py`, overridable by env): Gemini 2.5 Flash ₹26.4 / ₹220 per million
input / output tokens; Claude Sonnet 5 ₹176 / ₹880.

| Run | Calls | Tokens (approx.) | ₹ (approx.) |
|---|---|---|---|
| First research run on a new ticker | P7 + P8 on 4 transcripts (8 cheap), P6 (1 cheap), P9–P11 (3 strong), P12 (1 cheap) | cheap 220k in / 18k out; strong 30k in / 4.5k out | ≈ ₹6 cheap + ₹9 strong ≈ **₹15** |
| Second view of the same ticker (24 h) | 0 (stored cards; `llm_calls: 0` in the analyse response) | 0 | **₹0** |
| One day of Push | P1 for ~5 rule misses, P2 for ~10 results PDFs, P3/P5 for ~20 filings | cheap ≈ 150k in / 15k out | ≈ **₹7** |

Every response is cached by content hash (`llm_cache` + a local file cache), so re-running a job never pays twice.
After adding keys, run `python -c "from finn import llm; print(llm.usage_summary())"` in `backend/` and replace this
table with the measured numbers.
