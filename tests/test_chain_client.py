# SPDX-License-Identifier: MIT
from __future__ import annotations

from typing import Any

import pytest

from app import create_app
from app.chain_client import ChainClientError, get_balance, transfer, void_transfer


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = "" if self.ok else "boom"

    def json(self) -> dict[str, Any]:
        return self._payload


def test_transfer_uses_expected_url_headers_and_body(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(self: Any, method: str, url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse({"tx_id": "abc123", "status": "submitted"})

    monkeypatch.setattr("requests.Session.request", fake_request)
    app = create_app(
        {
            "TESTING": True,
            "RC_NODE_URL": "https://node-1.local",
            "RC_ADMIN_KEY": "super-secret-admin-key",
            "DATABASE_PATH": "/tmp/rcp/test-chain-client.sqlite3",
            "COOKIE_SECRET": "x" * 32,
            "COOKIE_SECURE": False,
        }
    )

    with app.app_context():
        result = transfer("treasury", "github:alice", 12.5, memo="claim:alice")

    assert result["tx_id"] == "abc123"
    assert calls == [
        {
            "method": "POST",
            "url": "https://node-1.local/wallet/transfer",
            "headers": {"X-Admin-Key": "super-secret-admin-key"},
            "timeout": 30,
            "verify": False,
            "json": {
                "from_miner": "treasury",
                "to_miner": "github:alice",
                "amount_rtc": 12.5,
                "memo": "claim:alice",
            },
        }
    ]


def test_get_balance_and_void_transfer_use_expected_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(self: Any, method: str, url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse({"ok": True})

    monkeypatch.setattr("requests.Session.request", fake_request)
    app = create_app(
        {
            "TESTING": True,
            "RC_NODE_URL": "https://node-1.local",
            "RC_ADMIN_KEY": "super-secret-admin-key",
            "DATABASE_PATH": "/tmp/rcp/test-chain-client-2.sqlite3",
            "COOKIE_SECRET": "x" * 32,
            "COOKIE_SECURE": False,
        }
    )

    with app.app_context():
        get_balance("github:alice")
        void_transfer("tx-99")

    assert calls[0]["method"] == "GET"
    assert calls[0]["url"] == "https://node-1.local/wallet/balance"
    assert "headers" not in calls[0]
    assert calls[0]["params"] == {"miner_id": "github:alice"}
    assert calls[1]["method"] == "POST"
    assert calls[1]["url"] == "https://node-1.local/wallet/transfer/void/tx-99"
    assert calls[1]["headers"] == {"X-Admin-Key": "super-secret-admin-key"}


def test_get_balance_works_without_admin_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(self: Any, method: str, url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse({"amount_rtc": 3.5})

    monkeypatch.setattr("requests.Session.request", fake_request)
    app = create_app(
        {
            "TESTING": True,
            "RC_NODE_URL": "https://node-1.local",
            "RC_ADMIN_KEY": "",
            "DATABASE_PATH": "/tmp/rcp/test-chain-client-readonly.sqlite3",
            "COOKIE_SECRET": "x" * 32,
            "COOKIE_SECURE": False,
        }
    )

    with app.app_context():
        result = get_balance("github:alice")

    assert result == {"amount_rtc": 3.5}
    assert calls == [
        {
            "method": "GET",
            "url": "https://node-1.local/wallet/balance",
            "timeout": 30,
            "verify": False,
            "params": {"miner_id": "github:alice"},
        }
    ]


def test_write_methods_require_admin_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(self: Any, method: str, url: str, **kwargs: Any) -> FakeResponse:
        raise AssertionError("write request should fail before network call")

    monkeypatch.setattr("requests.Session.request", fake_request)
    app = create_app(
        {
            "TESTING": True,
            "RC_NODE_URL": "https://node-1.local",
            "RC_ADMIN_KEY": "",
            "DATABASE_PATH": "/tmp/rcp/test-chain-client-write-no-key.sqlite3",
            "COOKIE_SECRET": "x" * 32,
            "COOKIE_SECURE": False,
        }
    )

    with app.app_context():
        with pytest.raises(
            ChainClientError,
            match="RC_ADMIN_KEY required for write operations",
        ):
            transfer("treasury", "github:alice", 1)


def test_non_2xx_responses_raise_chain_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(self: Any, method: str, url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse({"error": "nope"}, status_code=503)

    monkeypatch.setattr("requests.Session.request", fake_request)
    app = create_app(
        {
            "TESTING": True,
            "RC_NODE_URL": "https://node-1.local",
            "RC_ADMIN_KEY": "super-secret-admin-key",
            "DATABASE_PATH": "/tmp/rcp/test-chain-client-3.sqlite3",
            "COOKIE_SECRET": "x" * 32,
            "COOKIE_SECURE": False,
        }
    )

    with app.app_context():
        with pytest.raises(ChainClientError):
            get_balance("github:alice")
