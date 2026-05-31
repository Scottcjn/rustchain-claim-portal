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
        raise ChainClientError("RC_ADMIN_KEY required for write operations")
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


def _request_public(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    """Read-only request that does NOT send the admin key.

    Used for Node 1 endpoints that are explicitly public, including
    wallet balance reads and federation bridge read endpoints.
    """
    with requests.Session() as session:
        response = session.request(
            method,
            f"{_base_url()}{path}",
            timeout=30,
            verify=False,
            **kwargs,
        )
    return _handle_response(response)


def get_balance(miner_id: str) -> dict[str, Any]:
    return _request_public("GET", "/wallet/balance", params={"miner_id": miner_id})


def get_bridge_state() -> dict[str, Any]:
    """Aggregate bridge state. Public read, no admin key."""
    return _request_public("GET", "/bridge/state")


def list_bridge_events(limit: int = 50, window_seconds: int = 86400) -> dict[str, Any]:
    """Recent bridge state-change events. Public read."""
    params = {"limit": limit, "window_seconds": window_seconds}
    return _request_public("GET", "/bridge/events", params=params)


def list_bridge_transfers_recent(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    direction: str | None = None,
) -> dict[str, Any]:
    """Paginated public list of bridge transfers."""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    if direction:
        params["direction"] = direction
    return _request_public("GET", "/bridge/transfers/recent", params=params)


def get_bridge_reconciliation_latest() -> dict[str, Any]:
    """Most recent bridge reconciliation snapshot (Layer 2)."""
    return _request_public("GET", "/bridge/reconciliation/latest")


def get_bridge_reconciliation_by_epoch(epoch: int) -> dict[str, Any]:
    """Bridge reconciliation snapshot for a specific epoch (Layer 2)."""
    return _request_public("GET", f"/bridge/reconciliation/by_epoch/{int(epoch)}")


def list_bridge_reconciliation_recent(limit: int = 20) -> dict[str, Any]:
    """Most recent N reconciliation snapshots (Layer 2)."""
    return _request_public(
        "GET", "/bridge/reconciliation/recent", params={"limit": limit}
    )


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
