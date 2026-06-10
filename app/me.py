# SPDX-License-Identifier: MIT
# Portions of this file are adapted from MergeWork (Copyright (c) 2026
# MergeWork contributors, MIT). See NOTICE and THIRD_PARTY_LICENSES/.
# Original source: github.com/ramimbo/mergework/app/me.py
# Adapted: 2026-05-28 — FastAPI -> Flask; ledger writes -> HTTP to RustChain
# Node 1 /wallet/transfer. No mint authority resides in this portal.
from __future__ import annotations

from html import escape
from typing import Any

from flask import current_app

from .accounts import balance_amount_from_response, format_rtc
from .chain_client import ChainClientError, get_balance
from .db import get_github_wallet_link


def me_page_context(login: str | None) -> dict[str, Any]:
    github_balance_rtc = "0"
    linked_wallet_address = ""
    if login:
        try:
            github_balance_rtc = format_rtc(
                balance_amount_from_response(get_balance(f"github:{login}"))
            )
        except (ChainClientError, ValueError) as exc:
            current_app.logger.warning("GitHub balance lookup failed for %s: %s", login, exc)
            github_balance_rtc = "unavailable"

        linked_wallet = get_github_wallet_link(login)
        if linked_wallet:
            linked_wallet_address = str(linked_wallet["rtc_address"])

    return {
        "github_login": login,
        "github_balance_rtc": github_balance_rtc,
        "linked_wallet_address": linked_wallet_address,
    }


def render_me_page(context: dict[str, Any]) -> str:
    github_login = context.get("github_login")
    linked_wallet = escape(str(context.get("linked_wallet_address", "")))
    balance = escape(str(context.get("github_balance_rtc", "0")))
    if not github_login:
        return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>rustchain-claim-portal</title>
  </head>
  <body>
    <h1>rustchain-claim-portal</h1>
    <p>Sign in with GitHub to view your linked RTC wallet and claimable balance.</p>
    <p><a href="/auth/github/login?next=/me">Sign in with GitHub</a></p>
  </body>
</html>
""".strip()

    login = escape(str(github_login))
    logout_form = """
    <form action="/auth/logout" method="post">
      <button type="submit">Log out</button>
    </form>
    """.strip()
    return f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>{login} · rustchain-claim-portal</title>
  </head>
  <body>
    <h1>Signed in as {login}</h1>
    <p>GitHub balance: {balance} RTC</p>
    <p>Linked wallet: {linked_wallet or "not linked"}</p>
    <p>Use the JSON APIs to link your wallet or claim your balance.</p>
    {logout_form}
  </body>
</html>
""".strip()
