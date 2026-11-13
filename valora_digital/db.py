"""Tiny SQLite layer (standard library only) for storing contact enquiries."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import click
from flask import Flask, current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS enquiries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    contact     TEXT    NOT NULL,
    budget      TEXT    NOT NULL,
    message     TEXT    NOT NULL,
    ip_hash     TEXT,
    user_agent  TEXT,
    notified    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_enquiries_created_at ON enquiries (created_at);
"""


def get_db() -> sqlite3.Connection:
    """Return the SQLite connection for the current request."""
    if "db" not in g:
        path = current_app.config["DATABASE"]
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        g.db = conn
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db() -> None:
    get_db().executescript(SCHEMA)


def save_enquiry(*, name: str, contact: str, budget: str, message: str,
                 ip_hash: str, user_agent: str) -> int:
    """Insert an enquiry and return its id."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO enquiries (created_at, name, contact, budget, message, ip_hash, user_agent) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            name, contact, budget, message, ip_hash, user_agent[:200],
        ),
    )
    db.commit()
    return int(cur.lastrowid)


def mark_notified(enquiry_id: int) -> None:
    db = get_db()
    db.execute("UPDATE enquiries SET notified = 1 WHERE id = ?", (enquiry_id,))
    db.commit()


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create the database tables (safe to run repeatedly)."""
        init_db()
        click.echo(f"Database ready: {current_app.config['DATABASE']}")

    @app.cli.command("list-enquiries")
    @click.option("--limit", default=20, show_default=True, help="How many to show.")
    def list_enquiries_command(limit: int) -> None:
        """Print the most recent contact-form enquiries."""
        init_db()
        rows = get_db().execute(
            "SELECT id, created_at, name, contact, budget, message "
            "FROM enquiries ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        if not rows:
            click.echo("No enquiries yet.")
            return
        for row in rows:
            click.echo(f"#{row['id']}  {row['created_at']}  {row['name']}  <{row['contact']}>")
            click.echo(f"    budget : {row['budget']}")
            click.echo(f"    message: {row['message']}\n")
