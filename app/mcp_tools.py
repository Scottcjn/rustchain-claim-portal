# Portions of this file are adapted from MergeWork (Copyright (c) 2026
# MergeWork contributors, MIT). See NOTICE and THIRD_PARTY_LICENSES/.
# Original source: github.com/ramimbo/mergework/app/mcp_tools.py
# Adapted: 2026-05-29 — FastAPI -> Flask, EXECUTE tools dropped per
# upstream guidance (ramimbo/mergework#571: "read-only MCP/status/
# reconciliation surfaces are a safer first step"). Only read tools
# included in this Phase 2 port. No mint, no transfer, no link via MCP.
from __future__ import annotations

from decimal import Decimal
from typing import Any

from flask import current_app

from .accounts import GITHUB_LOGIN_RE, balance_amount_from_response
from .chain_client import (
    get_balance,
    get_bridge_reconciliation_by_epoch,
    get_bridge_reconciliation_latest,
    get_bridge_state,
    list_bridge_events,
    list_bridge_reconciliation_recent,
    list_bridge_transfers_recent,
)
from .db import get_db, get_github_wallet_link
from .wallets import WalletError, normalize_wallet_address


class MCPInvalidArguments(ValueError):
    pass


MCP_TOOLS: list[dict[str, Any]] = [
    {
        "name": "portal.balance.get",
        "description": "Look up RTC balance for a wallet, github:login, or plain miner id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "RTC address, github:login, or plain miner id.",
                }
            },
            "required": ["identifier"],
            "additionalProperties": False,
        },
    },
    {
        "name": "portal.wallet_link.lookup",
        "description": "Look up the RTC wallet currently linked to a GitHub login.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "github_login": {
                    "type": "string",
                    "description": "GitHub login to inspect.",
                }
            },
            "required": ["github_login"],
            "additionalProperties": False,
        },
    },
    {
        "name": "portal.claim_history",
        "description": (
            "List recent claim attempts for a GitHub login, or for the current "
            "authenticated user when github_login is omitted."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "github_login": {
                    "type": ["string", "null"],
                    "description": "Optional GitHub login override.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": "Maximum number of claims to return.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "portal.reserved.get",
        "description": "Look up the RTC balance reserved in a github:<login> placeholder account.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "github_login": {
                    "type": "string",
                    "description": "GitHub login whose reserved balance should be queried.",
                }
            },
            "required": ["github_login"],
            "additionalProperties": False,
        },
    },
    {
        "name": "portal.health",
        "description": "Return basic portal status and configured node information.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "bridge.state.get",
        "description": (
            "Aggregate bridge state on the RustChain side: locked_in / "
            "completed_in / voided_in totals + by_status + by_direction "
            "breakdowns + last_event_at. Matches FEDERATION_DESIGN_NOTE "
            "section 3.2 invariant shape. Public read, no auth."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "bridge.events.list",
        "description": (
            "Recent bridge state-change events with public-safe fields only. "
            "Sensitive fields (addresses, external_tx_hash, internal ids) are "
            "intentionally omitted. Window default 24h, max 30d. Limit 1-200."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max events to return (1-200, default 50).",
                    "minimum": 1,
                    "maximum": 200,
                },
                "window_seconds": {
                    "type": "integer",
                    "description": "Look-back window in seconds (default 86400).",
                    "minimum": 0,
                    "maximum": 30 * 86400,
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "bridge.transfers.recent",
        "description": (
            "Paginated public list of bridge transfers. Same public-safe "
            "field set as bridge.events.list, plus optional status and "
            "direction filters and explicit offset for pagination."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max transfers per page (1-200, default 50).",
                    "minimum": 1,
                    "maximum": 200,
                },
                "offset": {
                    "type": "integer",
                    "description": "Page offset (>= 0, default 0).",
                    "minimum": 0,
                },
                "status": {
                    "type": "string",
                    "description": "Optional status filter.",
                    "enum": [
                        "pending",
                        "locked",
                        "confirming",
                        "completed",
                        "voided",
                        "failed",
                    ],
                },
                "direction": {
                    "type": "string",
                    "description": "Optional direction filter.",
                    "enum": ["deposit", "withdraw"],
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "bridge.reconciliation.latest",
        "description": (
            "Most recent bridge reconciliation snapshot (federation Layer "
            "2). Each snapshot is an epoch-pinned attestation containing "
            "bridged_supply_committed, state_hash, and per-status totals."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "bridge.reconciliation.by_epoch",
        "description": (
            "Reconciliation snapshot for a specific epoch, if one exists. "
            "Returns snapshot=null if no snapshot has been recorded for "
            "that epoch."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "epoch": {
                    "type": "integer",
                    "description": "Non-negative epoch number.",
                    "minimum": 0,
                }
            },
            "required": ["epoch"],
            "additionalProperties": False,
        },
    },
    {
        "name": "bridge.reconciliation.recent",
        "description": (
            "Recent N reconciliation snapshots, ordered by epoch descending. "
            "Default 20, max 200."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max snapshots to return (1-200, default 20).",
                    "minimum": 1,
                    "maximum": 200,
                }
            },
            "additionalProperties": False,
        },
    },
]


def _require_allowed_fields(args: dict[str, Any], allowed: set[str]) -> None:
    unknown_fields = sorted(set(args) - allowed)
    if unknown_fields:
        raise MCPInvalidArguments(
            f"unexpected argument(s): {', '.join(unknown_fields)}"
        )


def _require_string(args: dict[str, Any], field: str) -> str:
    value = args.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MCPInvalidArguments(f"{field} must be a non-empty string")
    return value.strip()


def _optional_string(args: dict[str, Any], field: str) -> str | None:
    value = args.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise MCPInvalidArguments(f"{field} must be a string")
    stripped = value.strip()
    return stripped or None


def _positive_int(args: dict[str, Any], field: str, *, default: int) -> int:
    raw_value = args.get(field, default)
    if isinstance(raw_value, bool):
        raise MCPInvalidArguments(f"{field} must be an integer")
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise MCPInvalidArguments(f"{field} must be an integer") from exc
    if value <= 0:
        raise MCPInvalidArguments(f"{field} must be greater than zero")
    if value > 100:
        raise MCPInvalidArguments(f"{field} must be at most 100")
    return value


def _normalize_github_login(github_login: str) -> str:
    normalized = github_login.strip().lower()
    if not GITHUB_LOGIN_RE.fullmatch(normalized):
        raise MCPInvalidArguments("github_login must be a valid GitHub login")
    return normalized


def _normalize_balance_identifier(identifier: str) -> str:
    clean = identifier.strip()
    if not clean:
        raise MCPInvalidArguments("identifier must not be empty")
    if any(ord(char) < 32 or 127 <= ord(char) < 160 for char in clean):
        raise MCPInvalidArguments("identifier must not contain control characters")

    lower = clean.lower()
    if lower.startswith("github:"):
        github_login = _normalize_github_login(clean.split(":", 1)[1])
        return f"github:{github_login}"
    if lower.startswith("rtc"):
        try:
            return normalize_wallet_address(clean)
        except WalletError as exc:
            raise MCPInvalidArguments(str(exc)) from exc
    return clean


def _amount_rtc(payload: dict[str, Any]) -> float:
    amount = balance_amount_from_response(payload)
    return float(Decimal(str(amount)))


def _tool_balance_get(args: dict[str, Any]) -> dict[str, Any]:
    _require_allowed_fields(args, {"identifier"})
    identifier = _normalize_balance_identifier(_require_string(args, "identifier"))
    return {
        "amount_rtc": _amount_rtc(get_balance(identifier)),
        "miner_id": identifier,
        "source": "chain",
    }


def _tool_wallet_link_lookup(args: dict[str, Any]) -> dict[str, Any]:
    _require_allowed_fields(args, {"github_login"})
    github_login = _normalize_github_login(_require_string(args, "github_login"))
    row = get_github_wallet_link(github_login)
    if row is None:
        return {"linked": False, "rtc_address": None, "linked_at": None}
    return {
        "linked": True,
        "rtc_address": str(row["rtc_address"]),
        "linked_at": int(row["linked_at"]),
    }


def _tool_claim_history(
    args: dict[str, Any], *, session_github_login: str | None
) -> dict[str, Any]:
    _require_allowed_fields(args, {"github_login", "limit"})
    github_login = _optional_string(args, "github_login")
    if github_login is None:
        github_login = session_github_login
    if github_login is None:
        raise MCPInvalidArguments(
            "github_login is required when no authenticated session is present"
        )
    github_login = _normalize_github_login(github_login)
    limit = _positive_int(args, "limit", default=20)

    database = get_db()
    total_row = database.execute(
        "SELECT COUNT(*) AS total FROM claim_log WHERE github_login = ?",
        (github_login,),
    ).fetchone()
    claim_rows = database.execute(
        """
        SELECT id, github_login, amount_rtc, tx_id, status, created_at
        FROM claim_log
        WHERE github_login = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (github_login, limit),
    ).fetchall()

    claims = [
        {
            "id": int(row["id"]),
            "github_login": str(row["github_login"]),
            "amount_rtc": float(row["amount_rtc"]),
            "tx_id": None if row["tx_id"] is None else str(row["tx_id"]),
            "status": str(row["status"]),
            "created_at": int(row["created_at"]),
        }
        for row in claim_rows
    ]
    return {"claims": claims, "total": int(total_row["total"] if total_row else 0)}


def _tool_reserved_get(args: dict[str, Any]) -> dict[str, Any]:
    _require_allowed_fields(args, {"github_login"})
    github_login = _normalize_github_login(_require_string(args, "github_login"))
    github_account = f"github:{github_login}"
    return {
        "amount_rtc": _amount_rtc(get_balance(github_account)),
        "github_account": github_account,
    }


def _tool_health(args: dict[str, Any]) -> dict[str, Any]:
    _require_allowed_fields(args, set())
    return {
        "ok": True,
        "node_url": str(current_app.config.get("RC_NODE_URL", "")),
        "version": str(current_app.config.get("PORTAL_VERSION", "unknown")),
    }


def _tool_bridge_state_get(args: dict[str, Any]) -> dict[str, Any]:
    _require_allowed_fields(args, set())
    return get_bridge_state()


def _bridge_int_arg(
    args: dict[str, Any],
    field: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = args.get(field, default)
    if isinstance(raw_value, bool):
        raise MCPInvalidArguments(f"{field} must be an integer")
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise MCPInvalidArguments(f"{field} must be an integer") from exc
    if value < minimum:
        raise MCPInvalidArguments(f"{field} must be >= {minimum}")
    if value > maximum:
        raise MCPInvalidArguments(f"{field} must be <= {maximum}")
    return value


def _tool_bridge_events_list(args: dict[str, Any]) -> dict[str, Any]:
    _require_allowed_fields(args, {"limit", "window_seconds"})
    limit = _bridge_int_arg(args, "limit", default=50, minimum=1, maximum=200)
    window_seconds = _bridge_int_arg(
        args, "window_seconds", default=86400, minimum=0, maximum=30 * 86400
    )
    return list_bridge_events(limit=limit, window_seconds=window_seconds)


_BRIDGE_STATUS_VALUES = {
    "pending",
    "locked",
    "confirming",
    "completed",
    "voided",
    "failed",
}
_BRIDGE_DIRECTION_VALUES = {"deposit", "withdraw"}


def _tool_bridge_transfers_recent(args: dict[str, Any]) -> dict[str, Any]:
    _require_allowed_fields(args, {"limit", "offset", "status", "direction"})
    limit = _bridge_int_arg(args, "limit", default=50, minimum=1, maximum=200)
    offset = _bridge_int_arg(args, "offset", default=0, minimum=0, maximum=10**9)

    status = _optional_string(args, "status")
    if status is not None and status not in _BRIDGE_STATUS_VALUES:
        raise MCPInvalidArguments(
            f"status must be one of: {sorted(_BRIDGE_STATUS_VALUES)}"
        )
    direction = _optional_string(args, "direction")
    if direction is not None and direction not in _BRIDGE_DIRECTION_VALUES:
        raise MCPInvalidArguments(
            f"direction must be one of: {sorted(_BRIDGE_DIRECTION_VALUES)}"
        )
    return list_bridge_transfers_recent(
        limit=limit, offset=offset, status=status, direction=direction
    )


def _tool_bridge_reconciliation_latest(args: dict[str, Any]) -> dict[str, Any]:
    _require_allowed_fields(args, set())
    return get_bridge_reconciliation_latest()


def _tool_bridge_reconciliation_by_epoch(args: dict[str, Any]) -> dict[str, Any]:
    _require_allowed_fields(args, {"epoch"})
    if "epoch" not in args:
        raise MCPInvalidArguments("epoch is required")
    epoch = _bridge_int_arg(args, "epoch", default=0, minimum=0, maximum=10**12)
    return get_bridge_reconciliation_by_epoch(epoch)


def _tool_bridge_reconciliation_recent(args: dict[str, Any]) -> dict[str, Any]:
    _require_allowed_fields(args, {"limit"})
    limit = _bridge_int_arg(args, "limit", default=20, minimum=1, maximum=200)
    return list_bridge_reconciliation_recent(limit=limit)


def call_mcp_tool(
    name: str,
    args: dict[str, Any],
    *,
    session_github_login: str | None = None,
) -> dict[str, Any]:
    if name == "portal.balance.get":
        return _tool_balance_get(args)
    if name == "portal.wallet_link.lookup":
        return _tool_wallet_link_lookup(args)
    if name == "portal.claim_history":
        return _tool_claim_history(args, session_github_login=session_github_login)
    if name == "portal.reserved.get":
        return _tool_reserved_get(args)
    if name == "portal.health":
        return _tool_health(args)
    if name == "bridge.state.get":
        return _tool_bridge_state_get(args)
    if name == "bridge.events.list":
        return _tool_bridge_events_list(args)
    if name == "bridge.transfers.recent":
        return _tool_bridge_transfers_recent(args)
    if name == "bridge.reconciliation.latest":
        return _tool_bridge_reconciliation_latest(args)
    if name == "bridge.reconciliation.by_epoch":
        return _tool_bridge_reconciliation_by_epoch(args)
    if name == "bridge.reconciliation.recent":
        return _tool_bridge_reconciliation_recent(args)
    raise MCPInvalidArguments(f"unknown tool: {name}")


__all__ = ["MCPInvalidArguments", "MCP_TOOLS", "call_mcp_tool"]
