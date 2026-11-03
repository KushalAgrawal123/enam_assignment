"""Postgres helpers. Jobs and the API talk to Supabase over the session pooler (PLAN Delta 9)."""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterable, Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from . import config


_conn: psycopg.Connection | None = None


@contextmanager
def conn():
    """One reused autocommit connection per process: a new TLS handshake to the pooler costs ~1 s."""
    global _conn
    if _conn is None or _conn.closed or _conn.broken:
        _conn = psycopg.connect(config.DB_URL, row_factory=dict_row, prepare_threshold=None, autocommit=True)
    try:
        yield _conn
    except psycopg.OperationalError:
        _conn.close()
        _conn = None
        raise


def select(sql: str, params: Sequence[Any] | dict | None = None) -> list[dict]:
    with conn() as c:
        return list(c.execute(sql, params or ()).fetchall())


def execute(sql: str, params: Sequence[Any] | dict | None = None) -> None:
    with conn() as c:
        c.execute(sql, params or ())


def _adapt(v: Any) -> Any:
    return Jsonb(v) if isinstance(v, dict) or (isinstance(v, list) and v and isinstance(v[0], dict)) else v


def upsert(table: str, rows: Iterable[dict], key: Sequence[str], update: Sequence[str] | None = None) -> int:
    """Insert rows; on key conflict update `update` columns (default: every non-key column)."""
    rows = list(rows)
    if not rows:
        return 0
    cols = list(rows[0].keys())
    update = [c for c in (update if update is not None else cols) if c not in key]
    sql = (f"insert into {table} ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))}) "
           f"on conflict ({', '.join(key)}) do "
           + (f"update set {', '.join(f'{c} = excluded.{c}' for c in update)}" if update else "nothing"))
    with conn() as c:
        with c.transaction(), c.cursor() as cur:
            cur.executemany(sql, [[_adapt(r.get(k)) for k in cols] for r in rows])
    return len(rows)


def get_meta(key: str, default: Any = None) -> Any:
    rows = select("select value from meta where key = %s", (key,))
    return rows[0]["value"] if rows else default


def set_meta(key: str, value: Any) -> None:
    execute("insert into meta (key, value, updated_at) values (%s, %s, now()) "
            "on conflict (key) do update set value = excluded.value, updated_at = now()", (key, Jsonb(value)))


def settings() -> dict:
    rows = select("select * from settings where id = 1")
    return rows[0] if rows else {}


def to_json(v: Any) -> str:
    return json.dumps(v, default=str)
