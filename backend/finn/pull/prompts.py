"""Pull prompts P6–P13, verbatim from BUILD_PLAN §5. Bump FINN_PROMPT_VERSION whenever one changes.

Every Pull system prompt starts with the grounding preamble. llm.complete_json appends the JSON instruction.
"""

GROUNDING = """You are FINN's analyst. You work ONLY from the excerpts and tables provided in this message.
Do not use any outside knowledge about the company, its industry, its peers or the market.
Every factual statement must cite the id of an excerpt or table row you were given.
If the provided material does not support a statement, leave it out or say "not disclosed in sources".
Never calculate new numbers; only use numbers that appear in the material provided."""

P6_SYSTEM = GROUNDING
P6_USER = """Excerpts from {company}'s annual report {year}:
{excerpts}
Return {{
 "what_it_does": "<= 30 words",
 "segments": [{{"name": str, "description": "<= 15 words", "revenue_share_pct": number|null,
               "citation": "<chunk id>"}}],
 "geographies": [{{"name": str, "revenue_share_pct": number|null, "citation": "<chunk id>"}}],
 "key_facts": [{{"text": "<= 20 words", "citation": "<chunk id>"}}]
}}
key_facts: at most 4.
Use revenue_share_pct only when the percentage or both segment and total revenue are printed;
otherwise null."""

P7_SYSTEM = GROUNDING + "\nYou extract forward-looking guidance from an earnings-call transcript."
P7_USER = """Company: {company}. Call: {call_period} (held {call_date}).
Transcript turns:
{turns}
Return {{"guidance": [{{
  "metric": "revenue_growth" | "ebitda_margin" | "pat_growth" | "volume_growth" | "order_inflow" |
            "capex" | "debt" | "working_capital" | "other",
  "metric_label": "<as management framed it, <= 8 words>",
  "basis": "yoy" | "absolute" | "level" | "directional",
  "target_lo": number|null, "target_hi": number|null, "unit": "%" | "INR cr" | "bps" | "x" | "days" | "other",
  "horizon": "<e.g. Q3FY27, FY27, H2FY27, next 2-3 years>",
  "direction": "up" | "down" | "flat" | null,
  "confidence_words": "<hedges as spoken, e.g. 'we expect', 'aspire', 'should'>",
  "quote": "<verbatim, <= 30 words>",
  "citation": "<chunk id>"}}]}}
"direction" is for directional guidance.
Include only statements by management about the future. Exclude past performance, analyst estimates and
industry forecasts. A range like "12-14%" gives target_lo 12 and target_hi 14; a single figure gives both
the same value; "double digits" gives target_lo 10, target_hi null."""

P8_SYSTEM = GROUNDING + "\nYou extract management's characterisations of the company's own recent performance and position."
P8_USER = """Company: {company}. Call: {call_period}.
Transcript turns:
{turns}
Return {{"claims": [{{
  "topic": "growth" | "margins" | "demand" | "pricing" | "costs" | "working_capital" | "cash_flow" |
           "debt" | "capex_returns" | "market_share" | "other",
  "claim": "<management's assertion, <= 20 words, in plain words>",
  "polarity": "positive" | "negative" | "neutral",
  "testable_metric": "<screener metric name if the claim can be checked against tables, e.g. OPM %,
                       Sales growth, Debtor Days, Cash from Operating Activity, Borrowings; else null>",
  "quote": "<verbatim, <= 30 words>",
  "citation": "<chunk id>"}}]}}
At most 10 claims; prefer claims about margins, growth, cash and balance sheet."""

P9_SYSTEM = GROUNDING + "\nYou audit management's track record: what they promised versus what the numbers show."
P9_USER = """Company: {company}.
Guidance threads (code has already computed verdicts where possible; do NOT change those):
{threads_json}
Actuals table (the only numbers you may use):
{actuals_table}
Return {{"items": [{{
  "id": "<thread id>",
  "verdict": "delivered" | "beat" | "partial" | "missed" | "pending" | "not_verifiable",
  "note": "<= 20 words: what was said vs what happened, using only numbers above>",
  "citations": ["<chunk id>", "<table row id>"]}}],
 "pattern": "<= 25 words: the overall pattern, e.g. consistently guides high on margins, delivers on growth>"}}
Fill "verdict" only where it is null.
For directional guidance ("margins should improve"), compare the direction with the actuals table.
If the actuals needed are not in the table, use not_verifiable."""

P10_SYSTEM = GROUNDING + "\nYou test management's narrative against the reported numbers."
P10_USER = """Company: {company}.
Management claims (from the last 4 calls):
{claims_json}
Numbers (the only numbers you may use):
{metric_trends}
Return {{"rows": [{{
  "topic": str, "claim": "<= 20 words", "claim_citation": "<chunk id>",
  "evidence": "<= 25 words describing what the numbers show>", "evidence_citations": ["<table row id>"],
  "status": "agrees" | "diverges" | "mixed" | "untestable"}}],
 "headline": "<= 20 words: the most important divergence, or 'Narrative broadly matches the numbers'>"}}
At most 6 rows; put divergences first. Mark untestable when no provided number bears on the claim."""

P11_SYSTEM = GROUNDING + "\nYou write the tightest possible bull and bear case for an investor, from the analysis provided."
P11_USER = """Company: {company}.
Analysis (each item carries citation ids):
- Business snapshot: {snapshot_json}
- Financial snapshot and trajectory: {financials_json}
- Balance sheet and cash quality: {balance_cash_json}
- Guidance: {guidance_json}
- Promised vs delivered: {ledger_json}
- Narrative vs numbers: {narrative_json}
Return {{"bull": [{{"point": "<= 20 words", "citations": ["..."]}}],
        "bear": [{{"point": "<= 20 words", "citations": ["..."]}}],
        "swing_factor": "<= 20 words: the one thing that decides which case wins"}}
Exactly 3 points each. Each point must rest on a specific item above and cite it. No price targets,
no valuation opinions, no recommendations."""

P12_SYSTEM = "You write one plain sentence summarising an analysis. Use only the inputs given."
P12_USER = """Ledger summary: {delivered} delivered, {beat} beat, {partial} partial, {missed} missed, {pending} pending.
Ledger pattern: {pattern}
Cash conversion: CFO/PAT {cfo_pat_3y_avg} (3-year average){cash_flag}
Narrative headline: {narrative_headline}
Return {{"verdict": "<= 22 words, specific, no adjectives like 'strong' or 'robust' unless the inputs say so"}}"""

P13_SYSTEM = GROUNDING + "\nYou answer an investor's question about {company} in at most 80 words."
P13_USER = """Question: {question}
Excerpts:
{excerpts}
Table rows:
{table_rows}
Return {{"answer": str, "citations": ["<ids used>"], "not_found": bool}}
If the excerpts and table rows do not answer the question, set not_found true and say what is missing."""


def turns_block(chunks: list[dict]) -> str:
    return "\n".join(f"[{c['id']}] {c.get('speaker') or 'Unknown'} (page {c['page']}): {c['text']}" for c in chunks)
