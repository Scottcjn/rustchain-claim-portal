from __future__ import annotations

from typing import Any

import pytest

from app import create_app
from app.auth import signed_value
from app.db import create_claim_log, upsert_github_wallet_link


@pytest.fixture
def app(tmp_path: Any):
    # MCP blueprint is now registered automatically by create_app(); no
    # manual registration needed here.
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
        "bridge.state.get",
        "bridge.events.list",
        "bridge.transfers.recent",
        "bridge.reconciliation.latest",
        "bridge.reconciliation.by_epoch",
        "bridge.reconciliation.recent",
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


def test_bridge_state_tool_calls_chain_client(monkeypatch, app: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_get_bridge_state() -> dict[str, Any]:
        captured["called"] = True
        return {"ok": True, "state": {"locked_in_rtc": 42.0}}

    import app.chain_client as cc
    import app.mcp_tools as mt

    monkeypatch.setattr(cc, "get_bridge_state", fake_get_bridge_state)
    monkeypatch.setattr(mt, "get_bridge_state", fake_get_bridge_state)

    client = app.test_client()
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {"name": "bridge.state.get", "arguments": {}},
        },
    )
    assert resp.status_code == 200
    assert captured.get("called") is True


def test_bridge_transfers_recent_rejects_bad_status(app: Any) -> None:
    client = app.test_client()
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "bridge.transfers.recent",
                "arguments": {"status": "__not_a_status__"},
            },
        },
    )
    # tools/call returns 200 with an error payload in the result content
    assert resp.status_code == 200
    body = resp.get_json()
    # Either error key OR content array describing the validation failure
    has_error = "error" in body or any(
        "must be one of" in str(c)
        for c in body.get("result", {}).get("content", [])
    )
    assert has_error


def test_bridge_reconciliation_latest_calls_chain_client(monkeypatch, app: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_latest() -> dict[str, Any]:
        captured["called"] = True
        return {"ok": True, "snapshot": {"epoch": 42, "state_hash": "a" * 64}}

    import app.chain_client as cc
    import app.mcp_tools as mt

    monkeypatch.setattr(cc, "get_bridge_reconciliation_latest", fake_latest)
    monkeypatch.setattr(mt, "get_bridge_reconciliation_latest", fake_latest)

    client = app.test_client()
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 200,
            "method": "tools/call",
            "params": {"name": "bridge.reconciliation.latest", "arguments": {}},
        },
    )
    assert resp.status_code == 200
    assert captured.get("called") is True


def test_bridge_reconciliation_by_epoch_requires_epoch(app: Any) -> None:
    client = app.test_client()
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 201,
            "method": "tools/call",
            "params": {"name": "bridge.reconciliation.by_epoch", "arguments": {}},
        },
    )
    body = resp.get_json()
    has_error = "error" in body or any(
        "epoch is required" in str(c) or "epoch" in str(c)
        for c in body.get("result", {}).get("content", [])
    )
    assert has_error


def test_bridge_reconciliation_by_epoch_rejects_negative(monkeypatch, app: Any) -> None:
    def fake_by_epoch(epoch: int) -> dict[str, Any]:
        return {"ok": True, "snapshot": {"epoch": epoch}}

    import app.chain_client as cc
    import app.mcp_tools as mt

    monkeypatch.setattr(cc, "get_bridge_reconciliation_by_epoch", fake_by_epoch)
    monkeypatch.setattr(mt, "get_bridge_reconciliation_by_epoch", fake_by_epoch)

    client = app.test_client()
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 202,
            "method": "tools/call",
            "params": {
                "name": "bridge.reconciliation.by_epoch",
                "arguments": {"epoch": -5},
            },
        },
    )
    body = resp.get_json()
    has_error = "error" in body or any(
        ">= 0" in str(c) or "must be" in str(c)
        for c in body.get("result", {}).get("content", [])
    )
    assert has_error


def test_bridge_reconciliation_recent_default_limit(monkeypatch, app: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_recent(limit: int) -> dict[str, Any]:
        captured["limit"] = limit
        return {"ok": True, "count": 0, "limit": limit, "snapshots": []}

    import app.chain_client as cc
    import app.mcp_tools as mt

    monkeypatch.setattr(cc, "list_bridge_reconciliation_recent", fake_recent)
    monkeypatch.setattr(mt, "list_bridge_reconciliation_recent", fake_recent)

    client = app.test_client()
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 203,
            "method": "tools/call",
            "params": {"name": "bridge.reconciliation.recent", "arguments": {}},
        },
    )
    assert resp.status_code == 200
    assert captured.get("limit") == 20  # default


def test_bridge_reconciliation_recent_limit_clamp(monkeypatch, app: Any) -> None:
    """limit > 200 should be rejected by validation BEFORE hitting the client."""
    import app.chain_client as cc
    import app.mcp_tools as mt

    called: dict[str, Any] = {}

    def fake_recent(limit: int) -> dict[str, Any]:
        called["limit"] = limit
        return {"ok": True}

    monkeypatch.setattr(cc, "list_bridge_reconciliation_recent", fake_recent)
    monkeypatch.setattr(mt, "list_bridge_reconciliation_recent", fake_recent)

    client = app.test_client()
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 204,
            "method": "tools/call",
            "params": {
                "name": "bridge.reconciliation.recent",
                "arguments": {"limit": 5000},
            },
        },
    )
    body = resp.get_json()
    # Validation rejects at MCP layer; chain_client never called.
    has_error = "error" in body or any(
        "<= 200" in str(c) for c in body.get("result", {}).get("content", [])
    )
    assert has_error
    assert "limit" not in called  # client was NOT called with bad value
