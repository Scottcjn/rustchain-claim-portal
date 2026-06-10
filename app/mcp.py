# SPDX-License-Identifier: MIT
# Portions of this file are adapted from MergeWork (Copyright (c) 2026
# MergeWork contributors, MIT). See NOTICE and THIRD_PARTY_LICENSES/.
# Original source: github.com/ramimbo/mergework/app/mcp.py
# Adapted: 2026-05-29 — FastAPI -> Flask, EXECUTE tools dropped per
# upstream guidance (ramimbo/mergework#571: "read-only MCP/status/
# reconciliation surfaces are a safer first step"). Only read tools
# included in this Phase 2 port. No mint, no transfer, no link via MCP.
from __future__ import annotations

import json
from typing import Any

from flask import Blueprint, Response, abort, current_app, jsonify, request
from werkzeug.exceptions import BadRequest

from .auth import AuthService
from .chain_client import ChainClientError
from .mcp_tools import MCPInvalidArguments, MCP_TOOLS, call_mcp_tool


def _jsonrpc_error(response_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": response_id, "error": {"code": code, "message": message}}


def _tool_result_response(response_id: Any, tool_result: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(tool_result, dict):
        return {
            "jsonrpc": "2.0",
            "id": response_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(tool_result)}],
                "structuredContent": tool_result,
            },
        }
    return {
        "jsonrpc": "2.0",
        "id": response_id,
        "result": {"content": [{"type": "text", "text": tool_result}]},
    }


def _session_github_login() -> str | None:
    return AuthService(current_app.config).github_login_from_request(request)


def _require_session() -> str:
    # Phase 2 is intentionally read-only and does not enforce session auth.
    # Future execute-tier tools should call this helper before mutating state.
    login = _session_github_login()
    if login is None:
        abort(401, description="github login required")
    return login


def create_blueprint() -> Blueprint:
    bp = Blueprint("portal_mcp", __name__)

    @bp.route("/mcp", methods=["POST"])
    def mcp_endpoint() -> Response:
        try:
            payload = request.get_json(silent=False)
        except BadRequest:
            return jsonify(_jsonrpc_error(None, -32700, "parse error")), 400

        if not isinstance(payload, dict):
            return jsonify(_jsonrpc_error(None, -32600, "invalid request")), 400

        response_id = payload.get("id")
        method = payload.get("method")

        if method == "tools/list":
            return jsonify(
                {"jsonrpc": "2.0", "id": response_id, "result": {"tools": MCP_TOOLS}}
            )

        if method != "tools/call":
            return jsonify(_jsonrpc_error(response_id, -32601, "unknown method"))

        params = payload.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return jsonify(_jsonrpc_error(response_id, -32602, "invalid params"))

        name = params.get("name")
        if not isinstance(name, str) or not name.strip():
            return jsonify(_jsonrpc_error(response_id, -32602, "tool name is required"))

        arguments = params.get("arguments", {})
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return jsonify(_jsonrpc_error(response_id, -32602, "invalid params"))

        try:
            tool_result = call_mcp_tool(
                name.strip(),
                arguments,
                session_github_login=_session_github_login(),
            )
        except MCPInvalidArguments as exc:
            return jsonify(_jsonrpc_error(response_id, -32602, str(exc)))
        except ChainClientError as exc:
            current_app.logger.warning("MCP tool %s failed against chain: %s", name, exc)
            return jsonify(_jsonrpc_error(response_id, -32000, str(exc))), 502
        except Exception:
            current_app.logger.exception("MCP tool %s failed unexpectedly", name)
            return jsonify(_jsonrpc_error(response_id, -32603, "internal error")), 500

        return jsonify(_tool_result_response(response_id, tool_result))

    return bp


__all__ = ["create_blueprint"]
