from __future__ import annotations

from app.auth import signed_value, verified_value


def test_signed_value_round_trip(monkeypatch) -> None:
    monkeypatch.setattr("app.auth.time.time", lambda: 1_700_000_000)
    token = signed_value("alice", "s" * 32)

    monkeypatch.setattr("app.auth.time.time", lambda: 1_700_000_010)
    assert verified_value(token, "s" * 32, 60) == "alice"


def test_verified_value_rejects_tampering_and_expiry(monkeypatch) -> None:
    monkeypatch.setattr("app.auth.time.time", lambda: 1_700_000_000)
    token = signed_value("alice", "s" * 32)
    tampered = token.replace("alice", "bob", 1)

    monkeypatch.setattr("app.auth.time.time", lambda: 1_700_000_010)
    assert verified_value(tampered, "s" * 32, 60) is None

    monkeypatch.setattr("app.auth.time.time", lambda: 1_700_000_100)
    assert verified_value(token, "s" * 32, 60) is None
