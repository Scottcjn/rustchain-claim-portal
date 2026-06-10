# SPDX-License-Identifier: MIT
from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.wallets import (
    address_from_public_key_hex,
    canonical_wallet_json,
    normalize_wallet_address,
    verify_wallet_signature,
)


def test_address_derivation_and_signature_verification_round_trip() -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_key_hex = public_key.hex()
    address = address_from_public_key_hex(public_key_hex)

    assert address.startswith("RTC")
    assert normalize_wallet_address(address.lower()) == address

    payload = {"action": "claim_github_balance", "address": address, "nonce": 7}
    signature_hex = private_key.sign(canonical_wallet_json(payload).encode()).hex()

    assert verify_wallet_signature(
        public_key_hex=public_key_hex,
        payload=payload,
        signature_hex=signature_hex,
    )
    assert not verify_wallet_signature(
        public_key_hex=public_key_hex,
        payload={**payload, "nonce": 8},
        signature_hex=signature_hex,
    )
