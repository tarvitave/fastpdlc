"""SQLite storage for the whole site: leads, analytics, newsletters, SEO reports.

One file, one connection per call, WAL mode. At this scale that is not a compromise
-- it is fewer moving parts than a database server, and it backs up by copying a file.
"""
from __future__ import annotations

import contextlib
import os
import pathlib
import sqlite3
import time

DB_PATH = pathlib.Path(os.getenv("LEADS_DB", "/data/leads.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id       INTEGER PRIMARY KEY,
    email    TEXT NOT NULL UNIQUE,
    source   TEXT NOT NULL DEFAULT '',
    ip_hash  TEXT NOT NULL DEFAULT '',
    created  INTEGER NOT NULL
);

-- Unsubscribes are kept rather than deleted so a re-import cannot resurrect them.
CREATE TABLE IF NOT EXISTS unsubscribes (
    email    TEXT PRIMARY KEY,
    created  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pageviews (
    id        INTEGER PRIMARY KEY,
    path      TEXT NOT NULL,
    referrer  TEXT NOT NULL DEFAULT '',
    visitor   TEXT NOT NULL DEFAULT '',   -- daily-rotating hash, not an identity
    created   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_pageviews_created ON pageviews(created);
CREATE INDEX IF NOT EXISTS ix_pageviews_path    ON pageviews(path);

CREATE TABLE IF NOT EXISTS newsletters (
    id         INTEGER PRIMARY KEY,
    slug       TEXT NOT NULL UNIQUE,
    subject    TEXT NOT NULL,
    body_md    TEXT NOT NULL,
    body_html  TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'draft',  -- draft | sent | failed
    recipients INTEGER NOT NULL DEFAULT 0,
    error      TEXT NOT NULL DEFAULT '',
    created    INTEGER NOT NULL,
    sent_at    INTEGER
);

CREATE TABLE IF NOT EXISTS seo_reports (
    id       INTEGER PRIMARY KEY,
    created  INTEGER NOT NULL,
    pages    INTEGER NOT NULL DEFAULT 0,
    issues   INTEGER NOT NULL DEFAULT 0,
    fixed    INTEGER NOT NULL DEFAULT 0,
    detail   TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS contact_messages (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    email    TEXT NOT NULL,
    subject  TEXT NOT NULL DEFAULT '',
    message  TEXT NOT NULL,
    created  INTEGER NOT NULL,
    handled  INTEGER NOT NULL DEFAULT 0
);

-- Failed admin logins, for lockout. Successful logins clear the row.
CREATE TABLE IF NOT EXISTS login_attempts (
    ip       TEXT PRIMARY KEY,
    fails    INTEGER NOT NULL DEFAULT 0,
    last     INTEGER NOT NULL DEFAULT 0
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


@contextlib.contextmanager
def cursor():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now() -> int:
    return int(time.time())


# ── subscribers ──────────────────────────────────────────────────────────────
def active_subscribers() -> list[str]:
    """Everyone who has opted in and not opted out."""
    with cursor() as conn:
        rows = conn.execute(
            "SELECT email FROM leads WHERE email NOT IN (SELECT email FROM unsubscribes)"
            " ORDER BY created"
        ).fetchall()
    return [r["email"] for r in rows]


def unsubscribe(email: str) -> None:
    with cursor() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unsubscribes (email, created) VALUES (?, ?)",
            (email.strip().lower(), now()),
        )
