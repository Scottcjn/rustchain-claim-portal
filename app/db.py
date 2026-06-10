# SPDX-License-Identifier: MIT
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from flask import Flask, current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS oauth_sessions (
  state TEXT PRIMARY KEY,
  cookie_token TEXT NOT NULL,
  next_path TEXT,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS github_wallet_links (
  github_login TEXT PRIMARY KEY,
  rtc_address TEXT NOT NULL,
  public_key TEXT NOT NULL,
  linked_at INTEGER NOT NULL,
  signed_proof TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claim_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  github_login TEXT NOT NULL,
  amount_rtc REAL NOT NULL,
  tx_id TEXT,
  status TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
"""


def _connect(database_path: str) -> sqlite3.Connection:
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE_PATH"])
    return g.db


def close_db(_: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    connection = _connect(current_app.config["DATABASE_PATH"])
    try:
        connection.executescript(SCHEMA)
        connection.commit()
    finally:
        connection.close()


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()


def create_oauth_session(state: str, cookie_token: str, next_path: str | None) -> None:
    now = int(time.time())
    database = get_db()
    database.execute(
        """
        INSERT OR REPLACE INTO oauth_sessions (state, cookie_token, next_path, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (state, cookie_token, next_path, now),
    )
    database.commit()


def get_oauth_session(state: str) -> sqlite3.Row | None:
    cursor = get_db().execute(
        """
        SELECT state, cookie_token, next_path, created_at
        FROM oauth_sessions
        WHERE state = ?
        """,
        (state,),
    )
    return cursor.fetchone()


def delete_oauth_session(state: str) -> None:
    database = get_db()
    database.execute("DELETE FROM oauth_sessions WHERE state = ?", (state,))
    database.commit()


def upsert_github_wallet_link(
    github_login: str,
    rtc_address: str,
    public_key: str,
    signed_proof: str,
) -> sqlite3.Row:
    now = int(time.time())
    database = get_db()
    database.execute(
        """
        INSERT INTO github_wallet_links (github_login, rtc_address, public_key, linked_at, signed_proof)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(github_login)
        DO UPDATE SET
          rtc_address = excluded.rtc_address,
          public_key = excluded.public_key,
          linked_at = excluded.linked_at,
          signed_proof = excluded.signed_proof
        """,
        (github_login, rtc_address, public_key, now, signed_proof),
    )
    database.commit()
    return get_github_wallet_link(github_login)


def get_github_wallet_link(github_login: str) -> sqlite3.Row | None:
    cursor = get_db().execute(
        """
        SELECT github_login, rtc_address, public_key, linked_at, signed_proof
        FROM github_wallet_links
        WHERE github_login = ?
        """,
        (github_login.lower(),),
    )
    return cursor.fetchone()


def get_github_wallet_link_by_address(rtc_address: str) -> sqlite3.Row | None:
    cursor = get_db().execute(
        """
        SELECT github_login, rtc_address, public_key, linked_at, signed_proof
        FROM github_wallet_links
        WHERE rtc_address = ?
        """,
        (rtc_address,),
    )
    return cursor.fetchone()


def create_claim_log(
    github_login: str,
    amount_rtc: float,
    status: str,
    tx_id: str | None = None,
) -> int:
    now = int(time.time())
    database = get_db()
    cursor = database.execute(
        """
        INSERT INTO claim_log (github_login, amount_rtc, tx_id, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (github_login.lower(), amount_rtc, tx_id, status, now),
    )
    database.commit()
    return int(cursor.lastrowid)


def update_claim_log(claim_id: int, status: str, tx_id: str | None = None) -> None:
    database = get_db()
    database.execute(
        """
        UPDATE claim_log
        SET status = ?, tx_id = COALESCE(?, tx_id)
        WHERE id = ?
        """,
        (status, tx_id, claim_id),
    )
    database.commit()
