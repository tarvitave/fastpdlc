"""fastpdlc.com lead capture — the seed the CRM grows from.

Deliberately tiny: one SQLite file, no ORM, no framework magic. It exists so the
landing page has somewhere to POST, and so that when a real CRM lands later the
leads already collected can be exported into it with one call.

    POST /api/subscribe   {"email": "...", "company": "", "source": "landing"}
    GET  /api/leads.csv   Authorization: Bearer $ADMIN_TOKEN
    GET  /api/health
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

DB_PATH = Path(os.getenv("LEADS_DB", "/data/leads.db"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
IP_SALT = os.getenv("IP_SALT", "change-me")

# Deliberately permissive: we are not the authority on what a valid address is,
# we just refuse the obviously-not-an-address before it reaches storage.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@asynccontextmanager
async def lifespan(app: FastAPI):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS leads (
                   id       INTEGER PRIMARY KEY,
                   email    TEXT NOT NULL UNIQUE,
                   source   TEXT NOT NULL DEFAULT '',
                   ip_hash  TEXT NOT NULL DEFAULT '',
                   created  INTEGER NOT NULL
               )"""
        )
    yield


app = FastAPI(title="fastpdlc.com leads", docs_url=None, redoc_url=None, lifespan=lifespan)


class Subscribe(BaseModel):
    email: str = Field(max_length=254)
    company: str = Field(default="", max_length=200)   # honeypot — must stay empty
    source: str = Field(default="landing", max_length=40)


# ── crude per-IP rate limit; enough to stop a bored script ──────────────────
_hits: dict[str, list[float]] = {}
_WINDOW, _LIMIT = 3600.0, 12


def _rate_limited(key: str) -> bool:
    now = time.time()
    seen = [t for t in _hits.get(key, []) if now - t < _WINDOW]
    seen.append(now)
    _hits[key] = seen
    if len(_hits) > 10_000:          # bound memory; oldest buckets go first
        for k in list(_hits)[:5_000]:
            _hits.pop(k, None)
    return len(seen) > _LIMIT


def _client_ip(request: Request) -> str:
    # Caddy sets X-Forwarded-For; trust it because nothing else can reach this port.
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/subscribe")
def subscribe(body: Subscribe, request: Request) -> JSONResponse:
    ip = _client_ip(request)

    # A bot filled the hidden field. Look successful, store nothing.
    if body.company.strip():
        return JSONResponse({"ok": True})

    if _rate_limited(ip):
        raise HTTPException(status_code=429, detail="too many requests")

    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="that address does not look right")

    ip_hash = hashlib.sha256((IP_SALT + ip).encode()).hexdigest()[:16]
    with _connect() as conn:
        # Re-subscribing is not an error, and must not leak whether we knew them.
        conn.execute(
            """INSERT INTO leads (email, source, ip_hash, created) VALUES (?, ?, ?, ?)
               ON CONFLICT(email) DO UPDATE SET source = excluded.source""",
            (email, body.source[:40], ip_hash, int(time.time())),
        )
    return JSONResponse({"ok": True})


@app.get("/api/leads.csv")
def export(authorization: str = Header(default="")) -> StreamingResponse:
    """Export for whatever CRM you land on later. Bearer token, not a login."""
    if not ADMIN_TOKEN or authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["email", "source", "created_utc"])
    with _connect() as conn:
        for email, source, created in conn.execute(
            "SELECT email, source, created FROM leads ORDER BY created"
        ):
            writer.writerow([email, source, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created))])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )
