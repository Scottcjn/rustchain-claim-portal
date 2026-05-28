# Portions of this file are adapted from MergeWork (Copyright (c) 2026
# MergeWork contributors, MIT). See NOTICE and THIRD_PARTY_LICENSES/.
# Original source: github.com/ramimbo/mergework/app/wallet_api.py
# Adapted: 2026-05-28 — FastAPI -> Flask; ledger writes -> HTTP to RustChain
# Node 1 /wallet/transfer. No mint authority resides in this portal.
from __future__ import annotations

import hmac
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import Blueprint, Response, abort, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

from .accounts import (
    account_api_context,
    balance_amount_from_response,
    format_rtc,
    normalized_account,
)
from .auth import AuthService, register_auth_routes
from .chain_client import ChainClientError, get_balance, transfer
from .db import (
    create_claim_log,
    get_github_wallet_link,
    get_github_wallet_link_by_address,
    update_claim_log,
    upsert_github_wallet_link,
)
from .me import me_page_context, render_me_page
from .wallets import (
    WalletError,
    address_from_public_key_hex,
    canonical_wallet_json,
    normalize_public_key_hex,
    normalize_signature_hex,
    normalize_wallet_address,
    verify_wallet_signature,
)


def _json_object() -> dict[str, Any]:
    data = request.get_json(silent=False)
    if not isinstance(data, dict):
        abort(400, description="request body must be a JSON object")
    return data


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        abort(400, description=f"{key} must be a non-empty string")
    return value.strip()


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool):
        abort(400, description=f"{key} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError):
        abort(400, description=f"{key} must be an integer")


def _optional_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        abort(400, description=f"{key} must be a string")
    stripped = value.strip()
    return stripped or None


def _parse_amount_rtc(amount_text: str) -> Decimal:
    try:
        amount = Decimal(amount_text)
    except InvalidOperation:
        abort(400, description="amount_rtc must be a valid decimal string")
    if amount <= 0:
        abort(400, description="amount_rtc must be greater than zero")
    return amount


def _normalize_wallet_identity(address: str, public_key_hex: str) -> tuple[str, str]:
    try:
        normalized_address = normalize_wallet_address(address)
        normalized_public_key = normalize_public_key_hex(public_key_hex)
    except WalletError as exc:
        abort(400, description=str(exc))

    derived_address = address_from_public_key_hex(normalized_public_key)
    if not hmac.compare_digest(derived_address, normalized_address):
        abort(400, description="public key does not match RTC wallet address")
    return normalized_address, normalized_public_key


def _signature_payload_for_link(address: str, github_login: str, nonce: int) -> dict[str, Any]:
    return {
        "action": "link_github",
        "address": address,
        "github_login": github_login.lower(),
        "nonce": nonce,
    }


def _signature_payload_for_claim(address: str, github_login: str, nonce: int) -> dict[str, Any]:
    return {
        "action": "claim_github_balance",
        "address": address,
        "github_login": github_login.lower(),
        "nonce": nonce,
    }


def _signature_payload_for_transfer(
    from_address: str,
    to_address: str,
    amount_rtc: str,
    nonce: int,
    memo: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "action": "transfer",
        "from_address": from_address,
        "to_address": to_address,
        "amount_rtc": amount_rtc,
        "nonce": nonce,
        "memo": memo or "",
    }
    return payload


def _extract_tx_id(payload: dict[str, Any]) -> str | None:
    for key in ("tx_id", "transaction_id", "id"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _chain_error_response(exc: ChainClientError) -> tuple[Response, int]:
    return jsonify({"error": str(exc)}), 502


def create_blueprint() -> Blueprint:
    bp = Blueprint("portal", __name__)
    register_auth_routes(bp)

    @bp.route("/me", methods=["GET"])
    def me_page() -> str:
        auth = AuthService(current_app.config)
        login = auth.github_login_from_request(request)
        return render_me_page(me_page_context(login))

    @bp.route("/api/v1/accounts/<account>", methods=["GET"])
    def api_account(account: str) -> Response:
        try:
            return jsonify(account_api_context(account))
        except ChainClientError as exc:
            return _chain_error_response(exc)

    @bp.route("/api/v1/wallets/register", methods=["GET"])
    def api_register_wallet_get() -> None:
        abort(405, description="use POST for this route")

    @bp.route("/api/v1/wallets/register", methods=["POST"])
    def api_register_wallet() -> Response:
        data = _json_object()
        address, public_key_hex = _normalize_wallet_identity(
            address_from_public_key_hex(_required_str(data, "public_key_hex")),
            _required_str(data, "public_key_hex"),
        )
        label = _optional_str(data, "label")
        return jsonify(
            {
                "address": address,
                "public_key_hex": public_key_hex,
                "label": label,
            }
        )

    @bp.route("/api/v1/wallets/link-github", methods=["GET"])
    def api_link_wallet_github_get() -> None:
        abort(405, description="use POST for this route")

    @bp.route("/api/v1/wallets/<address>", methods=["GET"])
    def api_wallet(address: str) -> Response:
        try:
            address = normalize_wallet_address(address)
        except WalletError as exc:
            abort(400, description=str(exc))

        wallet_link = get_github_wallet_link_by_address(address)
        if wallet_link is None:
            abort(404, description="wallet not found")
        return jsonify(
            {
                "address": str(wallet_link["rtc_address"]),
                "public_key_hex": str(wallet_link["public_key"]),
                "github_login": str(wallet_link["github_login"]),
                "linked_at": int(wallet_link["linked_at"]),
                "signed_proof": str(wallet_link["signed_proof"]),
            }
        )

    @bp.route("/api/v1/wallets/link-github", methods=["POST"])
    def api_link_wallet_github() -> Response:
        auth = AuthService(current_app.config)
        github_login = auth.require_github_login(request)
        data = _json_object()
        address, public_key_hex = _normalize_wallet_identity(
            _required_str(data, "address"),
            _required_str(data, "public_key_hex"),
        )
        nonce = _required_int(data, "nonce")
        try:
            signature_hex = normalize_signature_hex(_required_str(data, "signature_hex"))
        except WalletError as exc:
            abort(400, description=str(exc))

        payload = _signature_payload_for_link(address, github_login, nonce)
        if not verify_wallet_signature(
            public_key_hex=public_key_hex,
            payload=payload,
            signature_hex=signature_hex,
        ):
            abort(400, description="wallet signature verification failed")

        signed_proof = canonical_wallet_json(
            {
                **payload,
                "public_key_hex": public_key_hex,
                "signature_hex": signature_hex,
            }
        )
        row = upsert_github_wallet_link(
            github_login=github_login,
            rtc_address=address,
            public_key=public_key_hex,
            signed_proof=signed_proof,
        )
        return jsonify(
            {
                "github_login": str(row["github_login"]),
                "rtc_address": str(row["rtc_address"]),
                "public_key_hex": str(row["public_key"]),
                "linked_at": int(row["linked_at"]),
                "signed_proof": str(row["signed_proof"]),
            }
        )

    @bp.route("/api/v1/github/claim", methods=["POST"])
    def api_github_claim() -> Response:
        auth = AuthService(current_app.config)
        github_login = auth.require_github_login(request)
        data = _json_object()
        try:
            address = normalize_wallet_address(_required_str(data, "address"))
        except WalletError as exc:
            abort(400, description=str(exc))
        nonce = _required_int(data, "nonce")
        try:
            signature_hex = normalize_signature_hex(_required_str(data, "signature_hex"))
        except WalletError as exc:
            abort(400, description=str(exc))

        wallet_link = get_github_wallet_link(github_login)
        if wallet_link is None:
            abort(404, description="no RTC wallet is linked to this GitHub login")
        if not hmac.compare_digest(address, str(wallet_link["rtc_address"])):
            abort(400, description="claim address does not match linked RTC wallet")

        payload = _signature_payload_for_claim(address, github_login, nonce)
        if not verify_wallet_signature(
            public_key_hex=str(wallet_link["public_key"]),
            payload=payload,
            signature_hex=signature_hex,
        ):
            abort(400, description="wallet signature verification failed")

        try:
            balance_payload = get_balance(f"github:{github_login}")
            amount = balance_amount_from_response(balance_payload)
        except (ChainClientError, ValueError) as exc:
            if isinstance(exc, ChainClientError):
                return _chain_error_response(exc)
            abort(502, description=str(exc))

        if amount <= 0:
            abort(400, description="no GitHub balance is available to claim")

        claim_id = create_claim_log(github_login, float(amount), "pending")
        try:
            chain_result = transfer(
                from_miner=f"github:{github_login}",
                to_miner=address,
                amount_rtc=float(amount),
                memo=f"claim:{github_login}",
            )
        except ChainClientError as exc:
            update_claim_log(claim_id, "failed")
            return _chain_error_response(exc)

        tx_id = _extract_tx_id(chain_result)
        update_claim_log(claim_id, "submitted", tx_id=tx_id)
        return jsonify(
            {
                "id": claim_id,
                "github_login": github_login,
                "amount_rtc": format_rtc(amount),
                "status": "submitted",
                "to_address": address,
                "tx_id": tx_id,
                "chain_result": chain_result,
            }
        )

    @bp.route("/api/v1/transfers", methods=["POST"])
    def api_submit_transfer() -> Response:
        data = _json_object()
        from_address, public_key_hex = _normalize_wallet_identity(
            _required_str(data, "from_address"),
            _required_str(data, "public_key_hex"),
        )
        to_address = normalized_account(_required_str(data, "to_address"))
        amount = _parse_amount_rtc(_required_str(data, "amount_rtc"))
        amount_text = format_rtc(amount)
        nonce = _required_int(data, "nonce")
        memo = _optional_str(data, "memo")
        try:
            signature_hex = normalize_signature_hex(_required_str(data, "signature_hex"))
        except WalletError as exc:
            abort(400, description=str(exc))

        payload = _signature_payload_for_transfer(
            from_address=from_address,
            to_address=to_address,
            amount_rtc=amount_text,
            nonce=nonce,
            memo=memo,
        )
        if not verify_wallet_signature(
            public_key_hex=public_key_hex,
            payload=payload,
            signature_hex=signature_hex,
        ):
            abort(400, description="wallet signature verification failed")

        try:
            chain_result = transfer(
                from_miner=from_address,
                to_miner=to_address,
                amount_rtc=float(amount),
                memo=memo,
            )
        except ChainClientError as exc:
            return _chain_error_response(exc)

        return jsonify(
            {
                "from_address": from_address,
                "to_address": to_address,
                "amount_rtc": amount_text,
                "memo": memo,
                "tx_id": _extract_tx_id(chain_result),
                "chain_result": chain_result,
            }
        )

    @bp.errorhandler(ChainClientError)
    def handle_chain_client_error(exc: ChainClientError) -> tuple[Response, int]:
        return _chain_error_response(exc)

    @bp.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException) -> tuple[Response, int]:
        if request.path.startswith("/api/"):
            return jsonify({"error": exc.description}), exc.code or 500
        return exc

    return bp
