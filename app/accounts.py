# SPDX-License-Identifier: MIT
# Portions of this file are adapted from MergeWork (Copyright (c) 2026
# MergeWork contributors, MIT). See NOTICE and THIRD_PARTY_LICENSES/.
# Original source: github.com/ramimbo/mergework/app/accounts.py
# Adapted: 2026-05-28 — FastAPI -> Flask; ledger writes -> HTTP to RustChain
# Node 1 /wallet/transfer. No mint authority resides in this portal.
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import abort

from .chain_client import ChainClientError, get_balance
from .wallets import WalletError, normalize_wallet_address

GITHUB_LOGIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?$")


def normalized_wallet_address(address: str) -> str:
    try:
        return normalize_wallet_address(address)
    except WalletError as exc:
        abort(400, description=str(exc))


def normalized_account(account: str) -> str:
    if not account or not account.strip():
        abort(400, description="account must not be empty")
    if re.search(r"[\x00-\x1f\x7f]", account):
        abort(400, description="account must not contain control characters")

    clean = account.strip()
    lower = clean.lower()
    if lower.startswith("treasury:") or lower.startswith("reserve:"):
        abort(400, description="internal MergeWork ledger accounts are not supported")
    if lower.startswith("rtc"):
        return normalized_wallet_address(clean)
    if lower.startswith("github:"):
        login = clean.split(":", 1)[1].lower()
        if not GITHUB_LOGIN_RE.fullmatch(login):
            abort(400, description="github login must be valid")
        return f"github:{login}"
    abort(400, description="account must be an RTC wallet address or github:<login>")


def github_login_from_account(account: str) -> str | None:
    if not account.startswith("github:"):
        return None
    login = account.removeprefix("github:")
    if not GITHUB_LOGIN_RE.fullmatch(login):
        return None
    return login


def account_transfer_status(account: str) -> str:
    if account.startswith("github:"):
        return "Claim GitHub balances from /me after linking a registered RTC wallet."
    return "RTC wallet transfers are enabled for registered RTC addresses."


def format_rtc(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid RTC amount") from exc
    normalized = amount.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def balance_amount_from_response(payload: dict[str, Any]) -> Decimal:
    for key in ("balance_rtc", "balance", "amount_rtc"):
        if key in payload:
            return Decimal(str(payload[key]))
    raise ValueError("balance response missing balance field")


def account_api_context(account: str) -> dict[str, Any]:
    account = normalized_account(account)
    exists = True
    try:
        balance_payload = get_balance(account)
        balance_rtc = format_rtc(balance_amount_from_response(balance_payload))
    except ChainClientError as exc:
        if exc.status_code != 404:
            raise
        exists = False
        balance_rtc = "0"

    return {
        "account": account,
        "ledger_address": account,
        "github_login": github_login_from_account(account),
        "exists": exists,
        "balance_rtc": balance_rtc,
        "transfer_status": account_transfer_status(account),
    }
