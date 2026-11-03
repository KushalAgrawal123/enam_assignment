"""Telegram delivery. Without a bot token alerts are still stored and shown in the app; they just aren't pushed."""
from __future__ import annotations

import html
import logging
import os

import requests

from .. import db

log = logging.getLogger("finn.notify")
APP_URL = os.getenv("FINN_APP_URL", "https://finn-beryl-delta.vercel.app")


def _chat_id(token: str) -> str | None:
    """TELEGRAM_CHAT_ID, else the chat of the last message sent to the bot (remembered in meta)."""
    cid = os.getenv("TELEGRAM_CHAT_ID") or (db.get_meta("telegram_chat") or {}).get("id")
    if cid:
        return str(cid)
    try:
        upd = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15).json().get("result", [])
    except requests.RequestException:
        return None
    chats = [u["message"]["chat"]["id"] for u in upd if "message" in u]
    if chats:
        db.set_meta("telegram_chat", {"id": chats[-1]})
        return str(chats[-1])
    return None


def format_alert(a: dict) -> str:
    p = a.get("payload") or {}
    lines = [f"<b>{html.escape(a['title'])}</b>"] + [f"• {html.escape(r)}" for r in a.get("reasons") or []][:3]
    cause = p.get("likely_cause")
    if cause:
        lines.append(f"Likely cause: {html.escape(cause['subject'][:140])}")
    url = p.get("url") or (cause or {}).get("url")
    if url:
        lines.append(f'<a href="{html.escape(url)}">Filing</a> · <a href="{APP_URL}/?symbol={a["symbol"]}">Open in FINN</a>')
    else:
        lines.append(f'<a href="{APP_URL}/?symbol={a["symbol"]}">Open in FINN</a>')
    return "\n".join(lines)


def send_pending(limit: int = 20) -> dict:
    """Push unsent alerts to Telegram, oldest first. Returns counts; never raises."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    pending = db.select("select * from alerts where not sent order by ts limit %s", (limit,))
    if not token:
        return {"sent": 0, "pending": len(pending), "reason": "TELEGRAM_BOT_TOKEN not set"}
    cid = _chat_id(token)
    if not cid:
        return {"sent": 0, "pending": len(pending), "reason": "send the bot a message first so it knows where to post"}
    sent = 0
    for a in pending:
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=15,
                              json={"chat_id": cid, "text": format_alert(a), "parse_mode": "HTML",
                                    "disable_web_page_preview": True})
            if r.ok:
                db.execute("update alerts set sent = true where id = %s", (a["id"],))
                sent += 1
            else:
                log.warning("telegram %s: %s", r.status_code, r.text[:200])
        except requests.RequestException as e:
            log.warning("telegram: %s", e)
    return {"sent": sent, "pending": len(pending) - sent}
