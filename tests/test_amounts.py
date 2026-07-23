# SPDX-License-Identifier: MIT
"""Amounts that reach /wallet/transfer must be finite decimals.

`Decimal` happily parses "NaN", "Infinity" and "1e400". The first crashed the
transfer route on the `amount <= 0` comparison; the other two rode through and
were handed to `requests(json=...)` as `float('inf')`, which serializes to a
bare `Infinity` literal — not valid JSON, and not an amount the ledger can mean.
"""

from __future__ import annotations

import json
import math
from decimal import Decimal
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import create_app
from app.accounts import balance_amount_from_response, format_rtc
from app.wallets import address_from_public_key_hex, canonical_wallet_json

PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
PUBLIC_KEY_HEX = PRIVATE_KEY.public_key().public_bytes_raw().hex()
ADDRESS = address_from_public_key_hex(PUBLIC_KEY_HEX)


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.status_code = 200
        self.ok = True
        self.text = ""

    def json(self) -> dict[str, Any]:
        return self._payload


@pytest.fixture()
def client_and_wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> tuple[Any, dict[str, Any]]:
    wire: dict[str, Any] = {}

    def fake_request(self: Any, method: str, url: str, **kwargs: Any) -> FakeResponse:
        if kwargs.get("json") is not None:
            wire["body"] = json.dumps(kwargs["json"])
        return FakeResponse({"tx_id": "tx-1", "status": "submitted"})

    monkeypatch.setattr("requests.Session.request", fake_request)
    app = create_app(
        {
            "TESTING": True,
            "RC_NODE_URL": "https://node-1.local",
            "RC_ADMIN_KEY": "admin-key",
            "DATABASE_PATH": str(tmp_path / "amounts.sqlite3"),
            "COOKIE_SECRET": "x" * 32,
            "COOKIE_SECURE": False,
        }
    )
    return app.test_client(), wire


def _signed_transfer_body(amount_text: str) -> dict[str, Any]:
    try:
        normalized = format_rtc(Decimal(amount_text))
    except (ValueError, ArithmeticError):
        # Amount validation happens before signature checks, so a body the
        # client could not even normalize still has to be rejected cleanly.
        normalized = None
    if normalized is None:
        signature = "ab" * 64
    else:
        payload = {
            "action": "transfer",
            "from_address": ADDRESS,
            "to_address": ADDRESS,
            "amount_rtc": normalized,
            "nonce": 1,
            "memo": "",
        }
        signature = PRIVATE_KEY.sign(canonical_wallet_json(payload).encode()).hex()
    return {
        "from_address": ADDRESS,
        "public_key_hex": PUBLIC_KEY_HEX,
        "to_address": ADDRESS,
        "amount_rtc": amount_text,
        "nonce": 1,
        "signature_hex": signature,
    }


@pytest.mark.parametrize("amount_text", ["Infinity", "inf", "1e400", "1" + "0" * 400])
def test_non_finite_transfer_amounts_are_rejected(
    client_and_wire: tuple[Any, dict[str, Any]], amount_text: str
) -> None:
    client, wire = client_and_wire
    response = client.post("/api/v1/transfers", json=_signed_transfer_body(amount_text))
    assert response.status_code == 400
    assert "body" not in wire, "a non-finite amount reached the node"


@pytest.mark.parametrize("amount_text", ["NaN", "-NaN", "sNaN"])
def test_nan_amount_returns_400_instead_of_crashing(
    client_and_wire: tuple[Any, dict[str, Any]], amount_text: str
) -> None:
    client, _ = client_and_wire
    response = client.post(
        "/api/v1/transfers",
        json={
            "from_address": ADDRESS,
            "public_key_hex": PUBLIC_KEY_HEX,
            "to_address": ADDRESS,
            "amount_rtc": amount_text,
            "nonce": 1,
            "signature_hex": "ab" * 64,
        },
    )
    assert response.status_code == 400
    assert "finite" in response.get_json()["error"]


def test_ordinary_amount_still_goes_through_as_valid_json(
    client_and_wire: tuple[Any, dict[str, Any]]
) -> None:
    client, wire = client_and_wire
    response = client.post("/api/v1/transfers", json=_signed_transfer_body("10.5"))
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["amount_rtc"] == "10.5"
    body = json.loads(wire["body"], parse_constant=_reject_constant)
    assert body["amount_rtc"] == 10.5


def _reject_constant(name: str) -> float:
    raise AssertionError(f"{name} is not valid JSON")


def test_format_rtc_rejects_non_finite() -> None:
    for value in ("Infinity", "-Infinity", "NaN"):
        with pytest.raises(ValueError, match="invalid RTC amount"):
            format_rtc(value)


def test_balance_response_must_be_finite() -> None:
    assert balance_amount_from_response({"balance_rtc": "12.25"}) == Decimal("12.25")
    for value in ("Infinity", "NaN", "1e400"):
        with pytest.raises(ValueError):
            balance_amount_from_response({"balance_rtc": value})


def test_float_of_a_huge_finite_decimal_is_infinite() -> None:
    """Why is_finite() alone is not enough: 1e400 is a finite Decimal whose
    float is not, and float is what goes on the wire."""
    huge = Decimal("1" + "0" * 400)
    assert huge.is_finite()
    assert not math.isfinite(float(huge))
