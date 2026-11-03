"""Chunk ids (BUILD_PLAN §6.1) — the unit every Pull citation points at.

Transcript: T{call}-p{page}-{turn}, one chunk per speaker turn, split at 1,500 characters.
            {call} is the call's month, e.g. T2026-08 for the August 2026 call.
Annual report: AR{year}-p{page}, only for pages inside the stored sections.
"""
from __future__ import annotations

import re

MAX_CHARS = 1500
# "Moderator:", "Amit Syngle:", "Mr. R. J. Jeyamurugan:" at the start of a line.
SPEAKER = re.compile(r"^\s*((?:Mr\.|Ms\.|Mrs\.|Dr\.)?\s*[A-Z][A-Za-z.'\- ]{1,48}?)\s*:\s+", re.M)


def call_key(period: str) -> str:
    """'Aug 2026' -> '2026-08'."""
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    m = re.match(r"([A-Z][a-z]{2})\w* (\d{4})", period or "")
    return f"{m.group(2)}-{months.index(m.group(1)) + 1:02d}" if m and m.group(1) in months else re.sub(r"\W+", "", period or "x")


def transcript_chunks(pages: list[str], period: str) -> list[dict]:
    key = call_key(period)
    out: list[dict] = []
    speaker = None
    for pno, text in enumerate(pages, 1):
        turn = 0
        marks = list(SPEAKER.finditer(text))
        spans = []
        if not marks or marks[0].start() > 0:          # continuation of the previous page's speaker
            spans.append((speaker, text[: marks[0].start()] if marks else text))
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            spans.append((m.group(1).strip(), text[m.end():end]))
        for spk, body in spans:
            body = " ".join(body.split())
            if not body:
                continue
            speaker = spk or speaker
            for start in range(0, len(body), MAX_CHARS):
                out.append({"id": f"T{key}-p{pno}-{turn}", "page": pno, "speaker": speaker,
                            "text": body[start:start + MAX_CHARS]})
                turn += 1
    return out


def ar_chunks(pages: list[str], year: str, section_pages: list[int]) -> list[dict]:
    return [{"id": f"AR{year}-p{p}", "page": p, "text": " ".join(pages[p - 1].split())}
            for p in sorted(set(section_pages)) if 0 < p <= len(pages) and pages[p - 1].strip()]
