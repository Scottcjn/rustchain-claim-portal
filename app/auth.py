# Portions of this file are adapted from MergeWork (Copyright (c) 2026
# MergeWork contributors, MIT). See NOTICE and THIRD_PARTY_LICENSES/.
# Original source: github.com/ramimbo/mergework/app/auth.py
# Adapted: 2026-05-28 — FastAPI -> Flask; ledger writes -> HTTP to RustChain
# Node 1 /wallet/transfer. No mint authority resides in this portal.
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any, Mapping
from urllib.parse import unquote, urlencode

import requests
from flask import Blueprint, abort, current_app, redirect, request, url_for

from .db import create_oauth_session, delete_oauth_session, get_oauth_session


def oauth_configured(settings: Mapping[str, Any]) -> bool:
    return bool(
        settings.get("GITHUB_OAUTH_CLIENT_ID")
        and settings.get("GITHUB_OAUTH_CLIENT_SECRET")
        and settings.get("COOKIE_SECRET")
    )


def safe_next_path(next_path: str | None) -> str:
    decoded_next_path = unquote(next_path) if next_path else ""
    if (
        not next_path
        or not next_path.startswith("/")
        or next_path.startswith("//")
        or len(next_path) > 2048
        or "\\" in next_path
        or decoded_next_path.startswith("//")
        or len(decoded_next_path) > 2048
        or "\\" in decoded_next_path
        or any(ord(char) < 32 or 127 <= ord(char) < 160 for char in next_path)
        or any(ord(char) < 32 or 127 <= ord(char) < 160 for char in decoded_next_path)
    ):
        return "/me"
    return next_path


def signed_value(value: str, secret: str) -> str:
    timestamp = str(int(time.time()))
    body = f"{value}|{timestamp}"
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}|{signature}"


def verified_value(token: str | None, secret: str, max_age_seconds: int) -> str | None:
    if not token or not secret:
        return None
    try:
        value, timestamp, signature = token.rsplit("|", 2)
        age = int(time.time()) - int(timestamp)
    except ValueError:
        return None
    if age < 0 or age > max_age_seconds:
        return None
    expected = hmac.new(
        secret.encode(), f"{value}|{timestamp}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    return value


class AuthService:
    def __init__(self, settings: Mapping[str, Any]) -> None:
        self._settings = settings

    def github_login_from_request(self, incoming_request: Any) -> str | None:
        login = verified_value(
            incoming_request.cookies.get("mrwk_user"),
            str(self._settings.get("COOKIE_SECRET", "")),
            604_800,
        )
        return login.lower() if login else None

    def require_github_login(self, incoming_request: Any) -> str:
        login = self.github_login_from_request(incoming_request)
        if login is None:
            abort(401, description="github login required")
        return login


def register_auth_routes(bp: Blueprint) -> None:
    @bp.route("/auth/github/login", methods=["GET"])
    def auth_github_login() -> Any:
        if not oauth_configured(current_app.config):
            abort(503, description="GitHub OAuth is not configured")

        safe_next = safe_next_path(request.args.get("next"))
        state = secrets.token_urlsafe(24)
        cookie_token = signed_value(state, str(current_app.config["COOKIE_SECRET"]))
        create_oauth_session(state, cookie_token, safe_next)

        query = urlencode(
            {
                "client_id": current_app.config["GITHUB_OAUTH_CLIENT_ID"],
                "redirect_uri": url_for("portal.auth_github_callback", _external=True),
                "scope": "read:user",
                "state": state,
            }
        )
        response = redirect(f"https://github.com/login/oauth/authorize?{query}", code=302)
        response.set_cookie(
            "mrwk_oauth_state",
            cookie_token,
            httponly=True,
            secure=bool(current_app.config.get("COOKIE_SECURE", True)),
            samesite="Lax",
            max_age=600,
        )
        return response

    @bp.route("/auth/github/callback", methods=["GET"])
    def auth_github_callback() -> Any:
        if not oauth_configured(current_app.config):
            abort(503, description="GitHub OAuth is not configured")

        code = request.args.get("code", "")
        state = request.args.get("state", "")
        if not code or not state:
            abort(400, description="code and state are required")

        cookie_state = request.cookies.get("mrwk_oauth_state")
        oauth_session = get_oauth_session(state)
        if oauth_session is None or not cookie_state:
            abort(401, description="invalid OAuth state")
        if not hmac.compare_digest(cookie_state, str(oauth_session["cookie_token"])):
            abort(401, description="invalid OAuth state")

        state_value = verified_value(cookie_state, str(current_app.config["COOKIE_SECRET"]), 600)
        if state_value is None or not hmac.compare_digest(state_value, state):
            abort(401, description="expired OAuth state")

        try:
            token_response = requests.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": current_app.config["GITHUB_OAUTH_CLIENT_ID"],
                    "client_secret": current_app.config["GITHUB_OAUTH_CLIENT_SECRET"],
                    "code": code,
                    "redirect_uri": url_for("portal.auth_github_callback", _external=True),
                },
                timeout=30,
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            if not access_token:
                abort(401, description="GitHub OAuth token exchange failed")

            user_response = requests.get(
                "https://api.github.com/user",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=30,
            )
            user_response.raise_for_status()
            login = str(user_response.json().get("login", "")).lower()
        except requests.RequestException as exc:
            abort(502, description=f"GitHub OAuth request failed: {exc}")

        if not login:
            abort(401, description="GitHub OAuth user lookup failed")

        next_path = safe_next_path(str(oauth_session["next_path"] or "/me"))
        response = redirect(next_path, code=302)
        response.set_cookie(
            "mrwk_user",
            signed_value(login, str(current_app.config["COOKIE_SECRET"])),
            httponly=True,
            secure=bool(current_app.config.get("COOKIE_SECURE", True)),
            samesite="Lax",
            max_age=604_800,
        )
        if login in current_app.config.get("ADMIN_LOGINS", ()):
            response.set_cookie(
                "mrwk_admin",
                signed_value(login, str(current_app.config["COOKIE_SECRET"])),
                httponly=True,
                secure=bool(current_app.config.get("COOKIE_SECURE", True)),
                samesite="Lax",
                max_age=86_400,
            )
        response.delete_cookie("mrwk_oauth_state")
        delete_oauth_session(state)
        return response

    @bp.route("/auth/logout", methods=["POST"])
    def auth_logout() -> Any:
        response = redirect("/", code=303)
        response.delete_cookie("mrwk_user")
        response.delete_cookie("mrwk_admin")
        response.delete_cookie("mrwk_oauth_state")
        return response
