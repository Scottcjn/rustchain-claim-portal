from __future__ import annotations

from typing import Any

import pytest

from app import create_app
from app.auth import signed_value
from app.db import create_claim_log, upsert_github_wallet_link
from app.mcp import create_blueprint as create_mcp_blueprint


@pytest.fixture
def app(tmp_path: Any):
    app = create_app(
        {
            "TESTING": True,
            "RC_NODE_URL": "https://node-1.local",
            "RC_ADMIN_KEY": "super-secret-admin-key",
            "DATABASE_PATH": str(tmp_path / "mcp.sqlite3"),
            "COOKIE_SECRET": "x" * 32,
            "COOKIE_SECURE": False,
            "PORTAL_VERSION": "phase2-test",
        }
    )
    app.register_blueprint(create_mcp_blueprint())

    with app.app_context():
        upsert_github_wallet_link(
            github_login="alice",
            rtc_address="RTC1111111111111111111111111111111111111111",
            public_key="11" * 32,
            signed_proof="{}",
        )
        create_claim_log("alice", 1.5, "submitted", tx_id="tx-1")
        create_claim_log("alice", 2.0, "failed")

    return app


def test_tools_list_exposes_only_read_only_phase_2_tools(app: Any) -> None:
    client = app.test_client()

    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    payload = response.get_json()

    assert response.status_code == 200
    assert [tool["name"] for tool in payload["result"]["tools"]] == [
        "portal.balance.get",
        "portal.wallet_link.lookup",
        "portal.claim_history",
        "portal.reserved.get",
        "portal.health",
    ]


def test_balance_and_reserved_tools_call_chain_client(
    app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fake_get_balance(identifier: str) -> dict[str, Any]:
        calls.append(identifier)
        amounts = {"miner-007": "12.5", "github:alice": "7.25"}
        return {"amount_rtc": amounts[identifier]}

    monkeypatch.setattr("app.mcp_tools.get_balance", fake_get_balance)
    client = app.test_client()

    balance_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "portal.balance.get",
                "arguments": {"identifier": "miner-007"},
            },
        },
    )
    reserved_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "portal.reserved.get",
                "arguments": {"github_login": "Alice"},
            },
        },
    )

    balance_payload = balance_response.get_json()
    reserved_payload = reserved_response.get_json()

    assert calls == ["miner-007", "github:alice"]
    assert balance_payload["result"]["structuredContent"] == {
        "amount_rtc": 12.5,
        "miner_id": "miner-007",
        "source": "chain",
    }
    assert reserved_payload["result"]["structuredContent"] == {
        "amount_rtc": 7.25,
        "github_account": "github:alice",
    }


def test_wallet_link_lookup_and_claim_history_support_db_reads(app: Any) -> None:
    client = app.test_client()

    lookup_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "portal.wallet_link.lookup",
                "arguments": {"github_login": "ALICE"},
            },
        },
    )

    cookie_value = signed_value("alice", "x" * 32)
    client.set_cookie("mrwk_user", cookie_value, domain="localhost")
    history_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "portal.claim_history",
                "arguments": {"limit": 1},
            },
        },
    )

    lookup_payload = lookup_response.get_json()
    history_payload = history_response.get_json()

    assert lookup_payload["result"]["structuredContent"] == {
        "linked": True,
        "rtc_address": "RTC1111111111111111111111111111111111111111",
        "linked_at": lookup_payload["result"]["structuredContent"]["linked_at"],
    }
    assert isinstance(lookup_payload["result"]["structuredContent"]["linked_at"], int)
    assert history_payload["result"]["structuredContent"]["total"] == 2
    assert history_payload["result"]["structuredContent"]["claims"] == [
        {
            "id": 2,
            "github_login": "alice",
            "amount_rtc": 2.0,
            "tx_id": None,
            "status": "failed",
            "created_at": history_payload["result"]["structuredContent"]["claims"][0][
                "created_at"
            ],
        }
    ]
    assert isinstance(
        history_payload["result"]["structuredContent"]["claims"][0]["created_at"], int
    )
