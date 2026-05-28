from __future__ import annotations

from typing import Any

import requests
from flask import current_app

try:
    from urllib3 import disable_warnings
    from urllib3.exceptions import InsecureRequestWarning
except ImportError:  # pragma: no cover
    disable_warnings = None
    InsecureRequestWarning = None


if disable_warnings is not None and InsecureRequestWarning is not None:
    disable_warnings(InsecureRequestWarning)


class ChainClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def _base_url() -> str:
    base_url = str(current_app.config.get("RC_NODE_URL", "")).rstrip("/")
    if not base_url:
        raise ChainClientError("RC_NODE_URL is not configured")
    return base_url


def _headers() -> dict[str, str]:
    admin_key = str(current_app.config.get("RC_ADMIN_KEY", ""))
    if not admin_key:
        raise ChainClientError("RC_ADMIN_KEY is not configured")
    return {"X-Admin-Key": admin_key}


def _handle_response(response: requests.Response) -> dict[str, Any]:
    if not response.ok:
        response_body = response.text.strip()
        message = f"RustChain node request failed with status {response.status_code}"
        if response_body:
            message = f"{message}: {response_body}"
        raise ChainClientError(
            message,
            status_code=response.status_code,
            response_body=response_body or None,
        )
    try:
        return response.json()
    except ValueError as exc:
        raise ChainClientError("RustChain node returned non-JSON response") from exc


def _request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    with requests.Session() as session:
        response = session.request(
            method,
            f"{_base_url()}{path}",
            headers=_headers(),
            timeout=30,
            verify=False,
            **kwargs,
        )
    return _handle_response(response)


def get_balance(miner_id: str) -> dict[str, Any]:
    return _request("GET", "/wallet/balance", params={"miner": miner_id})


def transfer(
    from_miner: str,
    to_miner: str,
    amount_rtc: float | str,
    memo: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "from_miner": from_miner,
        "to_miner": to_miner,
        "amount_rtc": amount_rtc,
    }
    if memo:
        payload["memo"] = memo
    return _request("POST", "/wallet/transfer", json=payload)


def void_transfer(tx_id: str) -> dict[str, Any]:
    return _request("POST", f"/wallet/transfer/void/{tx_id}")
