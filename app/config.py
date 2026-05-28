# Portions of this file are adapted from MergeWork (Copyright (c) 2026
# MergeWork contributors, MIT). See NOTICE and THIRD_PARTY_LICENSES/.
# Original source: github.com/ramimbo/mergework/app/config.py
# Adapted: 2026-05-28 — FastAPI -> Flask; ledger writes -> HTTP to RustChain
# Node 1 /wallet/transfer. No mint authority resides in this portal.
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _csv_env(name: str, default: str = "") -> tuple[str, ...]:
    raw_value = os.environ.get(name, default)
    if not raw_value.strip():
        return ()
    return tuple(item.strip().lower() for item in raw_value.split(",") if item.strip())


def _bool_env(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name, str(default)).strip()
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    port: int
    database_path: str
    rc_node_url: str
    rc_admin_key: str
    github_oauth_client_id: str
    github_oauth_client_secret: str
    cookie_secret: str
    admin_logins: tuple[str, ...]
    cookie_secure: bool
    testing: bool

    def to_mapping(self) -> dict[str, object]:
        return {
            "PORT": self.port,
            "DATABASE_PATH": self.database_path,
            "RC_NODE_URL": self.rc_node_url,
            "RC_ADMIN_KEY": self.rc_admin_key,
            "GITHUB_OAUTH_CLIENT_ID": self.github_oauth_client_id,
            "GITHUB_OAUTH_CLIENT_SECRET": self.github_oauth_client_secret,
            "COOKIE_SECRET": self.cookie_secret,
            "ADMIN_LOGINS": self.admin_logins,
            "COOKIE_SECURE": self.cookie_secure,
            "TESTING": self.testing,
        }


def get_settings(overrides: dict[str, object] | None = None) -> Settings:
    load_dotenv()

    repo_root = Path(__file__).resolve().parents[1]
    database_path = os.environ.get("RCP_DATABASE_PATH", str(repo_root / "claim_portal.sqlite3"))
    settings = Settings(
        port=_int_env("PORT", 5000),
        database_path=database_path,
        rc_node_url=os.environ.get("RC_NODE_URL", "").rstrip("/"),
        rc_admin_key=os.environ.get("RC_ADMIN_KEY", ""),
        github_oauth_client_id=os.environ.get("GITHUB_OAUTH_CLIENT_ID", ""),
        github_oauth_client_secret=os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", ""),
        cookie_secret=os.environ.get("COOKIE_SECRET", ""),
        admin_logins=_csv_env("ADMIN_LOGINS"),
        cookie_secure=_bool_env("COOKIE_SECURE", True),
        testing=False,
    )

    if not overrides:
        return settings

    merged = settings.to_mapping()
    merged.update(overrides)
    return Settings(
        port=int(merged["PORT"]),
        database_path=str(merged["DATABASE_PATH"]),
        rc_node_url=str(merged["RC_NODE_URL"]).rstrip("/"),
        rc_admin_key=str(merged["RC_ADMIN_KEY"]),
        github_oauth_client_id=str(merged["GITHUB_OAUTH_CLIENT_ID"]),
        github_oauth_client_secret=str(merged["GITHUB_OAUTH_CLIENT_SECRET"]),
        cookie_secret=str(merged["COOKIE_SECRET"]),
        admin_logins=tuple(str(login).lower() for login in merged.get("ADMIN_LOGINS", ())),
        cookie_secure=bool(merged["COOKIE_SECURE"]),
        testing=bool(merged.get("TESTING", False)),
    )
