# Portions of this file are adapted from MergeWork (Copyright (c) 2026
# MergeWork contributors, MIT). See NOTICE and THIRD_PARTY_LICENSES/.
# Original source: github.com/ramimbo/mergework/app/wallets.py
# Adapted: 2026-05-28 — FastAPI -> Flask; ledger writes -> HTTP to RustChain
# Node 1 /wallet/transfer. No mint authority resides in this portal.
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ADDRESS_RE = re.compile(r"^RTC[0-9a-f]{40}$")
PUBLIC_KEY_RE = re.compile(r"^[0-9a-f]{64}$")
SIGNATURE_RE = re.compile(r"^[0-9a-f]{128}$")


class WalletError(ValueError):
    pass


def canonical_wallet_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def normalize_public_key_hex(public_key_hex: str) -> str:
    normalized = public_key_hex.strip().lower()
    if not PUBLIC_KEY_RE.fullmatch(normalized):
        raise WalletError("public key must be 32 bytes encoded as lowercase hex")
    return normalized


def normalize_signature_hex(signature_hex: str) -> str:
    normalized = signature_hex.strip().lower()
    if not SIGNATURE_RE.fullmatch(normalized):
        raise WalletError("signature must be 64 bytes encoded as lowercase hex")
    return normalized


def normalize_wallet_address(address: str) -> str:
    normalized = address.strip()
    if len(normalized) >= 3 and normalized[:3].lower() == "rtc":
        normalized = "RTC" + normalized[3:].lower()
    if not ADDRESS_RE.fullmatch(normalized):
        raise WalletError("invalid RTC wallet address")
    return normalized


def address_from_public_key_hex(public_key_hex: str) -> str:
    public_key = normalize_public_key_hex(public_key_hex)
    digest = hashlib.sha256(bytes.fromhex(public_key)).hexdigest()
    return f"RTC{digest[:40]}"


def verify_wallet_signature(
    *, public_key_hex: str, payload: dict[str, Any], signature_hex: str
) -> bool:
    public_key = Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(normalize_public_key_hex(public_key_hex))
    )
    signature = bytes.fromhex(normalize_signature_hex(signature_hex))
    try:
        public_key.verify(signature, canonical_wallet_json(payload).encode())
    except InvalidSignature:
        return False
    return True
