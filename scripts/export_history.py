"""Copy this project's Claude Code session logs into docs/build-history/claude-code/, with secrets scrubbed.

Scrubs (1) every value in finn/.env that is 8+ characters, (2) known key shapes (Anthropic, Google, Supabase,
GitHub, Vercel, Telegram, Postgres URLs with passwords, JWTs), and (3) long tokens pasted next to the word "token".
Never prints a secret: it reports only counts. Fails if anything from .env survives.
Usage: python scripts/export_history.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = pathlib.Path.home() / ".claude" / "projects" / "-Users-kushalagrawal-Desktop-enam-assignment"
DST = ROOT / "docs" / "build-history" / "claude-code"

PATTERNS = [
    r"sk-ant-[A-Za-z0-9_\-]{20,}", r"AIza[0-9A-Za-z_\-]{30,}", r"sb_(?:secret|publishable)_[A-Za-z0-9_\-]{10,}",
    r"gh[pousr]_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{30,}", r"vcp_[A-Za-z0-9]{20,}", r"tvly-[A-Za-z0-9\-]{20,}",
    r"\b\d{8,10}:[A-Za-z0-9_\-]{30,}\b",                               # Telegram bot token
    r"(postgres(?:ql)?://[^:\s\"'\\]+:)[^@\s\"'\\]+(@)",               # password inside a connection string
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}",  # JWT
    r"((?:token|key|secret|password)[^A-Za-z0-9]{1,40})[A-Za-z0-9]{24,}",  # a long value pasted after the word
]


def env_values() -> list[str]:
    vals = []
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                v = line.split("=", 1)[1].strip().strip("'\"")
                if len(v) >= 8 and not v.startswith("http"):
                    vals.append(v)
                elif v.startswith("postgres") and "@" in v:
                    vals.append(v)
    return sorted(set(vals), key=len, reverse=True)


def scrub(text: str, secrets: list[str]) -> tuple[str, int]:
    n = 0
    for s in secrets:
        if s in text:
            n += text.count(s)
            text = text.replace(s, "[REDACTED]")
    for p in PATTERNS:
        def sub(m: re.Match) -> str:
            groups = [g for g in m.groups() if g is not None] if m.re.groups else []
            if m.re.groups == 2:
                return f"{m.group(1)}[REDACTED]{m.group(2)}"
            if m.re.groups == 1:
                return f"{m.group(1)}[REDACTED]"
            return "[REDACTED]" if not groups else m.group(0)
        text, k = re.subn(p, sub, text, flags=re.I if "token|key" in p else 0)
        n += k
    return text, n


def main() -> None:
    secrets = env_values()
    DST.mkdir(parents=True, exist_ok=True)
    total = 0
    for f in sorted(SRC.glob("*.jsonl")):
        out, n = scrub(f.read_text(errors="replace"), secrets)
        leaked = [s for s in secrets if s in out]
        if leaked:
            sys.exit(f"{f.name}: {len(leaked)} .env values survived scrubbing; not written")
        (DST / f.name).write_text(out)
        total += n
        print(f"{f.name}: {f.stat().st_size // 1024} KB, {n} redactions")
    print(f"{total} redactions; checked against {len(secrets)} .env values")


if __name__ == "__main__":
    main()
