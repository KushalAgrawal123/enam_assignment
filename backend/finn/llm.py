"""LLM router: every call goes through complete_json(tier, system, prompt).

- tier "cheap" (bulk extraction) or "strong" (reasoning); the model behind each tier is env-configurable.
- Responses are cached by content hash in Postgres (llm_cache) so every runtime shares one cache and one
  cost log, with a local file cache in front.
- Providers are chosen by model name: "gemini-*" -> google-genai, "claude-*" -> anthropic.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any

from . import config, db

log = logging.getLogger("finn.llm")
JSON_SUFFIX = " Respond with a single JSON object and nothing else."


class LLMUnavailable(RuntimeError):
    """No API key for the tier's provider. Callers degrade (e.g. rules-only classification)."""


def model_for(tier: str) -> str:
    return config.STRONG_MODEL if tier == "strong" else config.CHEAP_MODEL


def available(tier: str = "cheap") -> bool:
    m = model_for(tier)
    return bool(os.getenv("GEMINI_API_KEY") if m.startswith("gemini") else os.getenv("ANTHROPIC_API_KEY"))


def _key(model: str, system: str, prompt: str) -> str:
    raw = "\x1f".join([model, config.PROMPT_VERSION, system, prompt])
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


def _call_gemini(model: str, system: str, prompt: str, max_tokens: int) -> tuple[str, int, int]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    r = client.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                           max_output_tokens=max_tokens, temperature=0))
    u = r.usage_metadata
    return r.text or "", (u.prompt_token_count or 0) if u else 0, (u.candidates_token_count or 0) if u else 0


def _call_anthropic(model: str, system: str, prompt: str, max_tokens: int) -> tuple[str, int, int]:
    import anthropic

    client = anthropic.Anthropic()
    r = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                               messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in r.content if b.type == "text")
    return text, r.usage.input_tokens, r.usage.output_tokens


def complete_json(tier: str, system: str, prompt: str, max_tokens: int = 4000) -> dict:
    """Return the model's JSON object. Cached by (model, prompt version, system, prompt)."""
    model = model_for(tier)
    system = system + JSON_SUFFIX
    key = _key(model, system, prompt)

    local = config.CACHE_DIR / "llm" / f"{key}.json"
    if local.exists():
        return json.loads(local.read_text())
    try:
        rows = db.select("update llm_cache set hits = hits + 1 where key = %s returning response", (key,))
    except Exception as e:  # cache is an optimisation; never fail the call on it
        log.warning("llm_cache read failed: %s", e)
        rows = []
    if rows:
        out = rows[0]["response"]
    else:
        if not available(tier):
            raise LLMUnavailable(f"no API key for {model}")
        call = _call_gemini if model.startswith("gemini") else _call_anthropic
        text, tin, tout = call(model, system, prompt, max_tokens)
        out = _parse_json(text)
        pin, pout = config.PRICE_INR[tier]
        cost = round((tin * pin + tout * pout) / 1e6, 4)
        log.info("llm %s %s in=%d out=%d cost=₹%s", tier, model, tin, tout, cost)
        try:
            db.upsert("llm_cache", [dict(key=key, tier=tier, model=model, prompt_version=config.PROMPT_VERSION,
                                         response=out, tokens_in=tin, tokens_out=tout, cost_inr=cost)], key=["key"])
        except Exception as e:
            log.warning("llm_cache write failed: %s", e)
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(json.dumps(out))
    return out


def usage_summary() -> dict[str, Any]:
    """Total calls, tokens and ₹ across every runtime, by tier and model."""
    rows = db.select("""select tier, model, count(*) calls, sum(hits) cache_hits, sum(tokens_in) tokens_in,
                               sum(tokens_out) tokens_out, sum(cost_inr) cost_inr
                        from llm_cache group by tier, model order by tier, model""")
    total = sum(float(r["cost_inr"] or 0) for r in rows)
    return {"by_model": rows, "total_cost_inr": round(total, 2)}
