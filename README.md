# rustchain-claim-portal

GitHub-OAuth wallet-linking + `github:*` lazy-pay claim surface for the
[RustChain](https://github.com/Scottcjn/Rustchain) bounty program.

> **Status: scaffold.** Code ports in progress (see `INTEGRATION_SPEC.md`).
> The authoritative ledger remains RustChain Node 1 — this portal is a
> claim/pay *surface*, not a mint surface.

## Why this exists

RustChain pays bounties by admin-key `POST /wallet/transfer` against
Node 1 (`50.28.86.131`). Contributors today must put `Payout wallet:`
in their PR body, and the auto-pay workflow parses it on merge. Two
friction points fall out of that:

1. **Forgotten payouts.** A contributor who omits the wallet has their
   bounty reserved at a `github:<login>` placeholder string with no UI
   to claim it later. (e.g. MolhamHamwi 60+ RTC reserved this way.)
2. **No agent surface.** AI agents (Claude / Codex / GPT-OSS) can file
   PRs but cannot query their own balance or claim it without a human
   in the loop.

This portal solves both:

- **`/login/github`** — GitHub OAuth → links a `RTC...` wallet to the
  GitHub login via signed cookie. Stored as identity-mapping ONLY; the
  RustChain node is still the ledger.
- **`/me`** — Shows linked wallet, GitHub balance held at
  `github:<login>`, and a one-click "claim into my wallet" button that
  fires an admin-keyed `/wallet/transfer` against Node 1.
- **`mcp.<host>`** — MCP host so AI agents query/claim via the Model
  Context Protocol instead of curl + admin keys.

## Provenance & attribution

This codebase is derived from **MergeWork** by ramimbo
(https://github.com/ramimbo/mergework), MIT-licensed. The UX patterns
ported into this fork:

- GitHub OAuth wallet-linking flow (`app/auth.py`)
- `/me` route shape
- `github:<login>` lazy-pay placeholder accounts
- MCP-over-HTTP shape for agent interaction

**What was NOT ported:** MergeWork's centralized SQLite ledger as
source-of-truth, and MergeWork's mint-on-label issuance model. RustChain
mints RTC only via mined epoch rewards on real hardware (Proof of
Antiquity). The portal calls into the chain; it does not mint.

See [`NOTICE`](./NOTICE) for full attribution and
[`THIRD_PARTY_LICENSES/mergework-MIT.txt`](./THIRD_PARTY_LICENSES/mergework-MIT.txt)
for the upstream license preserved verbatim per MIT terms.

## Trust model

| Component | Trusted with | NOT trusted with |
|---|---|---|
| Portal SQLite | GitHub login ↔ RTC wallet mapping; signed-cookie session secrets | Balances, transfer authorization, mint authority |
| RustChain Node 1 | Authoritative balances, transfer execution, ledger | GitHub identity, OAuth state |
| RC_ADMIN_KEY | Only on Node 1; portal proxies through, never exposes | Browser, agent, or external system |

The portal is a **GitHub identity oracle + claim UI**. Compromising it
leaks wallet↔github mappings (privacy-bad) but cannot mint RTC or
re-route balances on the chain.

## Repository layout (planned)

```
.
├── LICENSE                            # MIT (dual copyright)
├── NOTICE                             # Attribution to MergeWork
├── THIRD_PARTY_LICENSES/
│   └── mergework-MIT.txt              # Upstream LICENSE verbatim
├── README.md
├── INTEGRATION_SPEC.md                # ← agent #1 (Claude) writes this
├── app/
│   ├── __init__.py
│   ├── auth.py                        # ← agent #2 (Codex) ports
│   ├── me.py                          #   from mergework
│   ├── accounts.py
│   ├── wallets.py
│   ├── chain_client.py                # NEW: thin RustChain Node 1 client
│   ├── mcp.py                         # Phase 2
│   └── mcp_tools.py                   # Phase 2
├── pyproject.toml
├── tests/
└── deploy/
    └── systemd/rustchain-claim-portal.service
```

## Quick links

- Upstream: https://github.com/ramimbo/mergework
- RustChain: https://github.com/Scottcjn/Rustchain
- RustChain Bounty Index: https://github.com/Scottcjn/rustchain-bounties
- Auto-pay workflow source (yujinju666): the action consumed by this portal

## License

MIT. See [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE).
