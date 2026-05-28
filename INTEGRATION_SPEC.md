# rustchain-claim-portal — Integration Spec

*Authoritative design doc. Read before coding. Updated 2026-05-28.*

---

## 1. Mission

`rustchain-claim-portal` is a claim/pay **surface** in front of the RustChain
bounty system. It is NOT a ledger. The chain is the ledger. The portal exists
solely to (a) let a GitHub contributor link an `RTC...` wallet to their GitHub
login so the auto-pay workflow can pay them directly on merge, (b) let a
contributor who was paid before linking (a `github:<login>` lazy-pay placeholder
account on Node 1) reclaim those reserved funds into a real wallet, and (c)
expose a thin MCP surface so AI agents can do the same without admin keys.
Source-of-truth for balances, transfers, and issuance remains
`https://50.28.86.131` (Node 1).

---

## 2. Primitives — MergeWork → RustChain Mapping

| MergeWork primitive | What it does there | RustChain equivalent | Adapt / Preserve / Drop |
|---|---|---|---|
| `Account` SQLAlchemy model (mergework `app/accounts.py:114`) | First-class ledger row: balance, type prefix, history | RustChain `balances` table on Node 1, keyed by `miner_id` text | **DROP.** Portal does not own balances. Portal stores ONLY the `github_login ↔ rtc_address` mapping; balance is fetched live from `https://50.28.86.131/wallet/balance?miner=...` |
| `TREASURY_ACCOUNT` constant `"treasury:mrwk"` | Source of all mint operations | `founder_community` miner_id on Node 1 (also `founder_dev_fund`, `founder_team_bounty`, `founder_founders` per `RUSTCHAIN_BOUNTY_OPERATOR.md` §3) | **DROP.** Portal never authors a transfer FROM treasury; treasury transfers are auto-pay-workflow's job. Portal only sources transfers from the `github:<login>` placeholder. |
| `reserve:bounty:<id>` accounts | Pre-allocated bounty reservation pre-merge | No equivalent. RustChain pays on merge, not on label. | **DROP.** Reservation semantics not used. |
| `mrwk1` + 40-hex-char wallet address (mergework `app/wallets.py:11`, `ADDRESS_RE`) | Wallet address derived from Ed25519 pubkey: `mrwk1` + first 40 hex of `sha256(pubkey)` | `RTC` + 40 lowercase hex (sha256 of pubkey, first 160 bits). Same construction, different prefix. | **ADAPT.** Replace regex `^mrwk1[0-9a-f]{40}$` with `^RTC[0-9a-f]{40}$`. Keep the rest of `wallets.py` (Ed25519 verify, canonical JSON, public-key normalization) verbatim — it's load-bearing for the link-wallet signed-proof step. |
| Signed transfer `submit_wallet_transfer` (mergework `app/wallet_api.py:107`) | Contributor signs a canonical-JSON transfer with their Ed25519 priv key; server verifies and writes a ledger entry | Node 1 already exposes `POST /wallet/transfer/signed` and admin-keyed `POST /wallet/transfer`. Portal does NOT replicate signing semantics for arbitrary transfers. | **DROP for arbitrary transfers. ADAPT for one narrow case:** the link-wallet step asks the contributor to sign a `{"github_login": ..., "address": ..., "nonce": ...}` payload, which the portal verifies (Ed25519) and stores as `signed_proof` in `github_wallet_links`. That's the entire on-portal use of signatures. |
| `github:<login>` lazy-pay placeholder account (mergework `app/accounts.py:63-67`) | Account opened on first label-application when no wallet was provided; contributor later claims by linking a wallet | Already exists on RustChain Node 1. Auto-pay workflow falls back to `to_miner: "github:alice"` when PR body has no `Payout wallet:` line. The `balances` table happily stores `github:alice → 60 RTC`. | **PRESERVE the concept; PORT the claim UX.** Portal's `/me` reads `/wallet/balance?miner=github:<login>`, shows the balance, and offers a "claim to my linked wallet" button that triggers a portal-side `/wallet/transfer` call (see §5 trust-boundary discussion). |
| `/me` route (mergework `app/me.py`) | Shows `github_balance_mrwk` + `linked_wallet_address` | Same shape, swap MRWK → RTC, swap SQLAlchemy call → HTTP GET to Node 1 | **ADAPT.** Roughly 22 LOC stays 22 LOC. |
| GitHub OAuth flow + `safe_next_path` + `signed_value`/`verified_value` (mergework `app/auth.py:24-64`, `:107-202`) | Cookie-based session, HMAC-signed cookie, OAuth state CSRF, login redirect | No equivalent in RustChain stack. RustChain has admin keys, not user logins. | **PORT verbatim** (FastAPI→Flask only). The `safe_next_path` open-redirect guard at `app/auth.py:24-39` is non-obvious and correct; copy it, don't re-derive it. |
| MCP-over-HTTP host (mergework `app/mcp.py`, `mcp_tools.py`) | JSON-RPC 2.0 `tools/list` and `tools/call` over HTTP; agents authenticate via API token | No equivalent. RustChain has no agent surface today. | **PORT in Phase 2.** Reduced tool set: `get_balance`, `get_linked_wallet`, `claim_github_balance`. Agent auth via static bearer token issued per-agent (not OAuth). |
| SQLAlchemy + Alembic + Jinja2 (mergework `pyproject.toml:13-21`) | ORM + migrations + templates | RustChain's entire stack is Flask + `import sqlite3` stdlib + jinja-via-Flask | **DROP all three.** See §7. |

---

## 3. Data Flows

### 3.1 First-time contributor (no wallet on file)

```
  ┌──────────┐  PR merged   ┌───────────────────┐
  │ alice    │ ──────────▶  │ award-rtc.yml     │
  │ (no      │              │ (GitHub Action)   │
  │  wallet  │              │ on Rustchain repo │
  │  in PR   │              └────────┬──────────┘
  │  body)   │                       │ no `Payout wallet:` line found
  └──────────┘                       │ falls back to `github:alice`
                                     ▼
                          ┌─────────────────────────┐
                          │ Node 1 /wallet/transfer │
                          │ X-Admin-Key: $RC_AK     │
                          │ from: founder_community │
                          │ to:   github:alice      │
                          │ amount: 5 RTC           │
                          └────────────┬────────────┘
                                       │ balance row: github:alice = 5 RTC
                                       │ (chain ledger)
                                       ▼
                          ┌────────────────────────┐
                          │ Days/weeks/months pass │
                          └────────────┬───────────┘
                                       │
                                       ▼
   ┌──────────┐  visits  ┌─────────────────────┐
   │ alice    │ ───────▶ │ portal /login/github│
   │ (now     │          │ (OAuth → cookie)    │
   │ wants    │          └──────────┬──────────┘
   │ wallet)  │                     │ session: github_login=alice
   └──────────┘                     ▼
                          ┌─────────────────────────────────────┐
                          │ portal /link-wallet                  │
                          │ form: address=RTCabcd..., pubkey,    │
                          │       signature over canonical JSON  │
                          │ portal verifies Ed25519 (Sec 2 row 4)│
                          │ writes github_wallet_links row       │
                          └──────────────┬──────────────────────┘
                                         ▼
                          ┌─────────────────────────────────────┐
                          │ portal /me shows:                    │
                          │   github:alice balance = 5 RTC       │
                          │   linked wallet = RTCabcd...         │
                          │   [Claim 5 RTC to RTCabcd...]        │
                          └──────────────┬──────────────────────┘
                                         │ alice clicks Claim
                                         ▼
                          ┌─────────────────────────────────────┐
                          │ portal calls Node 1                  │
                          │   POST /wallet/transfer              │
                          │   from: github:alice                 │
                          │   to:   RTCabcd...                   │
                          │   amount: 5 RTC                      │
                          │   memo: "claim by github:alice via   │
                          │          portal, link_id=N"          │
                          └──────────────┬──────────────────────┘
                                         ▼
                          tx_id logged to claim_log table
                          balance now lives at RTCabcd...
```

### 3.2 Returning contributor (wallet already linked)

```
  alice has already linked RTCabcd... via portal.
  award-rtc workflow has been updated to consult the portal
  BEFORE falling back to github:* placeholders.

  ┌──────────┐  PR merged   ┌───────────────────┐
  │ alice    │ ──────────▶  │ award-rtc.yml     │
  └──────────┘              └────────┬──────────┘
                                     │ GET https://portal.../api/v1/lookup?
                                     │       github_login=alice
                                     ▼
                          ┌──────────────────────────┐
                          │ portal returns:           │
                          │   {"rtc_address": "RTCabcd...", │
                          │    "linked_at": "2026-..."}     │
                          └────────────┬──────────────┘
                                       ▼
                          ┌─────────────────────────┐
                          │ Node 1 /wallet/transfer │
                          │ from: founder_community │
                          │ to:   RTCabcd...        │  ← skips github:* entirely
                          │ amount: 5 RTC           │
                          └─────────────────────────┘
```

No placeholder ever opens. No portal claim step needed. This is the steady-state.

### 3.3 AI agent via MCP (Phase 2)

```
  ┌─────────────┐  authenticated  ┌──────────────────────┐
  │ Claude /    │ ───────────────▶│ portal POST /mcp     │
  │ Codex /     │ Bearer: agent_X │ JSON-RPC tools/call  │
  │ GPT-OSS     │                 │   name="get_balance" │
  │ agent       │                 │   args={"github_login": "agent_X_owner"}
  └─────────────┘                 └──────────┬───────────┘
                                             ▼
                                   GET Node 1 /wallet/balance?miner=github:agent_X_owner
                                             │
                                             ▼
                                   tool result: "github:agent_X_owner: 12 RTC"

  Agent decides to claim:
                                  POST /mcp tools/call
                                    name="claim_github_balance"
                                    args={"github_login":..., "to_address":"RTCxyz..."}
                                             │
                                             ▼
                                   portal verifies the bearer token is
                                   permitted to act for that github_login
                                   (out-of-band consent step, NOT OAuth),
                                   then issues the same /wallet/transfer
                                   call as the human flow in §3.1.
```

The bearer-token → github_login authorization model is the open question
(see §9, Q4). The default proposed: agent bearer tokens are issued by Scott
manually, scoped to exactly one `github:<login>`, and revocable.

---

## 4. Trust Boundary

The hard question: who holds `$RC_ADMIN_KEY`?

```
                         ┌─────────────────────────────────┐
                         │ RustChain Node 1 (50.28.86.131) │
                         │ - holds full chain DB           │
                         │ - holds $RC_ADMIN_KEY in env    │
                         │ - exposes /wallet/transfer      │
                         │   (requires X-Admin-Key header) │
                         └────────────────┬────────────────┘
                                          │
                  ╔═══════════════════════╪═══════════════════════╗
                  ║                       │                       ║
                  ║  OPTION A             │           OPTION B    ║
                  ║  portal HOLDS admin   │  portal does NOT hold ║
                  ║  key, calls direct    │  admin key; Node 1    ║
                  ║                       │  exposes a narrow     ║
                  ║                       │  /wallet/claim_github ║
                  ║                       │  endpoint that trusts ║
                  ║                       │  the portal's source  ║
                  ║                       │  IP + a portal-only   ║
                  ║                       │  shared secret        ║
                  ╚═══════════════════════╪═══════════════════════╝
                                          │
                            ┌─────────────┴─────────────┐
                            │ rustchain-claim-portal     │
                            │ - SQLite: oauth_sessions,  │
                            │   github_wallet_links,     │
                            │   claim_log                │
                            │ - flask app on port 8000   │
                            └────────────────────────────┘
```

### Tradeoff honestly

**Option A (portal holds admin key).** Simpler. One env var on the portal box.
Portal can authorize any transfer. **Risk: portal compromise = ability to
drain `founder_community` to attacker wallet.** The admin key on Node 1 is
the most sensitive secret in the entire stack; copying it into a second box
that talks HTTP to the internet doubles the attack surface for zero
mitigation. Not recommended for production.

**Option B (narrow endpoint on Node 1).** Node 1 adds one new route, e.g.:

```python
# Pseudocode on Node 1
@app.route("/wallet/claim_github", methods=["POST"])
def wallet_claim_github():
    if request.remote_addr not in PORTAL_TRUSTED_IPS:
        return jsonify({"error": "forbidden"}), 403
    shared_secret = request.headers.get("X-Portal-Secret", "")
    if not hmac.compare_digest(shared_secret, os.environ["RC_PORTAL_SECRET"]):
        return jsonify({"error": "unauthorized"}), 401
    body = request.json
    github_login = body["github_login"]      # "alice"
    to_address   = body["to_address"]        # "RTCabcd..."
    # Server-side enforced: from_miner is ALWAYS github:<github_login>,
    # amount is ALWAYS the full current balance of that placeholder,
    # and the placeholder is zeroed atomically.
    # The portal CANNOT specify from_miner=founder_community here.
    ...
```

Breach of portal in this model leaks the wallet↔github mapping (privacy bad)
and lets an attacker drain `github:*` placeholder balances into wallets they
control — but they can never mint, never touch founder wallets, never affect
miner rewards. Blast radius = sum of unclaimed `github:*` balances at time
of breach (today: ~150 RTC, ~$15 reference value).

**Recommendation: Option B.** The portal codebase carries the diff for the
new Node 1 endpoint as `deploy/node1-patch/claim_github_endpoint.py.patch`.
Scott applies it once, after review.

---

## 5. Schema

Portal SQLite (`portal.db`) has three tables. That's all.

```sql
-- OAuth state + session cookies. Ephemeral.
CREATE TABLE oauth_sessions (
    state         TEXT PRIMARY KEY,        -- signed_value(secrets.token_urlsafe(24) + "," + next_path)
    cookie_token  TEXT,                    -- HMAC-signed session cookie body
    next_path     TEXT,                    -- post-login redirect (validated via safe_next_path)
    created_at    INTEGER NOT NULL         -- unix epoch; rows older than 600s are pruned
);
CREATE INDEX idx_oauth_sessions_created ON oauth_sessions(created_at);

-- The one durable thing the portal owns: github_login ↔ rtc_address.
CREATE TABLE github_wallet_links (
    github_login  TEXT PRIMARY KEY COLLATE NOCASE,  -- lowercased GitHub login
    rtc_address   TEXT NOT NULL,                    -- ^RTC[0-9a-f]{40}$
    public_key    TEXT NOT NULL,                    -- 64-hex Ed25519 pubkey
    linked_at     INTEGER NOT NULL,                 -- unix epoch
    signed_proof  TEXT NOT NULL                     -- 128-hex Ed25519 signature over
                                                    --   canonical JSON {address, github_login, nonce}
);

-- Write-through cache of claim attempts. Chain is still truth; this is for UX/history.
CREATE TABLE claim_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    github_login  TEXT NOT NULL COLLATE NOCASE,
    to_address    TEXT NOT NULL,
    amount_rtc    REAL NOT NULL,           -- as returned by Node 1; we don't recompute
    tx_id         TEXT,                    -- nullable: populated on Node 1 success
    status        TEXT NOT NULL,           -- 'pending' | 'confirmed' | 'failed' | 'voided'
    error         TEXT,                    -- nullable: Node 1 error body if status='failed'
    created_at    INTEGER NOT NULL,
    updated_at    INTEGER NOT NULL
);
CREATE INDEX idx_claim_log_login ON claim_log(github_login);
CREATE INDEX idx_claim_log_status ON claim_log(status);
```

Notes:

- **No `accounts` table.** Balances live on the chain. Portal asks Node 1.
- **No `wallets` table.** Wallet existence is implicit in `github_wallet_links`.
  If a contributor wants to inspect a wallet they haven't linked, they query
  the chain directly.
- **No `bounties`, `proofs`, `submissions`, `ledger` tables.** All of that
  is GitHub + the RustChain ledger. Portal is not a bounty engine.
- **The `signed_proof` column matters.** It's what protects against a portal
  operator (Scott, or a future maintainer) silently rebinding `github:alice`
  to a wallet alice doesn't control. With the signed proof on file, alice
  can always prove the link was authorized by her private key.

---

## 6. What We Drop from MergeWork, and Why

| Dropped | Why |
|---|---|
| **SQLAlchemy + Alembic** | RustChain Node 1 uses `import sqlite3` from stdlib. Adding SQLAlchemy to the portal would make it the only Python-on-Scott's-stack component requiring an ORM. Three tables, no foreign keys to other systems, no schema evolution beyond ALTER TABLE — stdlib is the right tool. |
| **Jinja2 as separate dep** | Flask ships with Jinja2 built in. No need to pin it separately. |
| **`treasury:mrwk` and `reserve:bounty:*` accounts** | RustChain already has `founder_community` et al. on Node 1. Reservation semantics aren't used — bounties pay on merge, not on label. |
| **Mint-on-label flow** | RustChain mints RTC ONLY via mined epoch rewards on real hardware (Proof of Antiquity, per `CLAUDE.md` §RIP-200). The portal must not have any code path that increases total RTC supply. The auto-pay workflow transfers from existing founder allocations; it does not mint. |
| **`Bounty`, `Submission`, `Proof`, `Ledger` SQLAlchemy models** | All bounty workflow lives in GitHub (issues, PRs, labels). The chain ledger lives on Node 1. Portal owns neither. |
| **`submit_work_proof` MCP tool** | MergeWork's tool returns submission instructions for a bounty. RustChain's bounty submission is "open a PR on the right repo and reference the bounty issue." That guidance lives in `RUSTCHAIN_BOUNTY_OPERATOR.md` and `rustchain-bounties` issue templates, not in the portal. |
| **`bounty_attempts` table and tool** | Same reasoning. Advisory reservations aren't part of the RustChain model. |
| **FastAPI** | Flask matches the rest of the RustChain Python stack on Node 1. One less framework to context-switch. |
| **`/api/v1/transfers` arbitrary signed transfer endpoint** | Anyone with a wallet + private key can already POST signed transfers directly to `https://50.28.86.131/wallet/transfer/signed`. Re-proxying that through the portal adds latency and a second logging surface for zero value. The portal does ONE narrow transfer: claim from `github:<login>` placeholder to linked wallet. |

---

## 7. MIT Compliance Checklist

| Item | Status |
|---|---|
| Upstream LICENSE preserved verbatim | `THIRD_PARTY_LICENSES/mergework-MIT.txt` ✅ (file present at scaffold time) |
| Dual-copyright in our LICENSE | Done — `LICENSE` line 4 cites MergeWork contributors ✅ |
| NOTICE file listing ported pieces | Done — `NOTICE` lines 9-16 enumerate ported components ✅ |
| Per-file attribution headers on ported files | **TODO during port.** Each of `app/auth.py`, `app/me.py`, `app/accounts.py`, `app/wallets.py`, `app/mcp.py`, `app/mcp_tools.py` will carry a top-of-file header: |

```python
# Portions of this file are derived from MergeWork (MIT)
#   https://github.com/ramimbo/mergework
#   Original file: app/auth.py
# Adapted for rustchain-claim-portal: FastAPI → Flask, MRWK → RTC wallet
#   prefix, ledger-via-HTTP-to-Node-1 instead of local SQLAlchemy.
# See NOTICE and THIRD_PARTY_LICENSES/mergework-MIT.txt for full attribution.
```

| Item | Status |
|---|---|
| README cites upstream | Done — `README.md` §Provenance & attribution ✅ |
| No removal of upstream copyright notices | The original `app/auth.py` etc. carry no per-file copyright headers (only the repo LICENSE). MIT requires retaining the LICENSE and copyright notice "in all copies or substantial portions" — we satisfy this via `LICENSE`, `NOTICE`, and `THIRD_PARTY_LICENSES/mergework-MIT.txt`. ✅ |

---

## 8. Phase Plan

### Phase 1 — Claim portal (unblocks ~12 contributors with reserved balances)

Files, in dependency order:

1. `app/config.py` — env-var loading (`PORTAL_DATABASE_URL`, `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `COOKIE_SECRET`, `RUSTCHAIN_NODE_URL`, `RC_PORTAL_SECRET`).
2. `app/db.py` — stdlib `sqlite3` connection helper; `init_db()` runs the three CREATE TABLE statements idempotently.
3. `app/wallets.py` — ported from mergework `app/wallets.py:1-62`, regex changed from `mrwk1` to `RTC`. ~62 LOC.
4. `app/auth.py` — ported from mergework `app/auth.py:1-202`, FastAPI → Flask. Cookie names: `rcp_user`, `rcp_oauth_state`. `safe_next_path` preserved verbatim (lines 24-39). ~200 LOC.
5. `app/chain_client.py` — **NEW.** Thin wrapper around Node 1: `get_balance(miner_id)`, `transfer_from_github_placeholder(github_login, to_address)`. Uses `requests` + `verify=False` for the self-signed cert. ~80 LOC.
6. `app/me.py` — ported from mergework `app/me.py:1-22`, swap SQLAlchemy call → `chain_client.get_balance(f"github:{login}")`. ~25 LOC.
7. `app/links.py` — **NEW.** `link_wallet(github_login, address, pubkey, nonce, signature_hex)` — verify signature, INSERT into `github_wallet_links`. `lookup_wallet(github_login)` — SELECT for the award-rtc workflow's pre-merge lookup. ~80 LOC.
8. `app/main.py` — Flask app, registers routes, serves `/`, `/me`, `/link-wallet`, `/claim`, `/api/v1/lookup`, `/auth/github/login`, `/auth/github/callback`, `/auth/logout`.
9. `templates/me.html`, `templates/link.html` — minimal HTML, no JS framework. The mergework templates are not in scope to read; we write fresh ~30-LOC Jinja each.
10. `deploy/systemd/rustchain-claim-portal.service` — single-process Flask under gunicorn or `flask run`.
11. `deploy/node1-patch/claim_github_endpoint.py.patch` — the narrow `/wallet/claim_github` endpoint to apply to Node 1's `rustchain_v2_integrated_v2.2.1_rip200.py`.

Phase 1 alone delivers the "claim my forgotten bounty" use case for the
contributors listed in `RUSTCHAIN_BOUNTY_OPERATOR.md` §3 and beyond (MolhamHamwi,
eliasx45, and the rest of the `github:*` placeholder set).

### Phase 2 — MCP host

12. `app/mcp.py` — ported from mergework `app/mcp.py:1-141`, FastAPI → Flask. Replace `await request.json()` with `request.get_json()`. ~140 LOC.
13. `app/mcp_tools.py` — **NEW**, much smaller than mergework's. Three tools: `get_balance(github_login)`, `get_linked_wallet(github_login)`, `claim_github_balance(github_login, to_address)`. ~120 LOC.
14. `app/agent_tokens.py` — per-agent bearer tokens stored in a fourth `agent_tokens` table (or initially: a flat config file `agents.toml`).

Phase 2 is not blocking. It can ship after Phase 1 has been in production for a week.

---

## 9. Open Questions — Need Scott's Decision

1. **Trust model: Option A (portal holds admin key) or Option B (Node 1 exposes narrow `/wallet/claim_github` endpoint, portal authenticates via shared secret + IP allowlist)?** This spec recommends Option B. Implementation diff for Node 1 is small (~40 LOC). Confirm before coding.

2. **Subdomain / TLD: where does the portal live?** Candidates: `claim.rustchain.org` (clean, requires DNS), `portal.scottcjn.com`, `rustchain-claim.elyanlabs.com`, or just a path on the existing `50.28.86.131` reverse proxy (`https://50.28.86.131/portal/`). The OAuth callback URL has to be registered with GitHub at app-creation time, so this is a one-time decision per OAuth app.

3. **GitHub OAuth app: new app or reuse an existing one?** If reusing, we need the client_id/client_secret rotated specifically for portal use (the `read:user` scope is minimal but still). If new, we need Scott to create it under his GitHub account or under an org account.

4. **Agent authorization model (Phase 2):** how does an agent prove it acts for `github:agent_X_owner`? Three options: (a) Scott manually issues bearer tokens, each scoped to one github_login, revocable; (b) agents go through full OAuth as the underlying GitHub user (requires GitHub App, not OAuth App); (c) agents present a GitHub PAT belonging to the user. Option (a) is simplest; option (c) is most idiomatic to how Codex/Claude actually authenticate elsewhere.

5. **Should the portal log claim attempts to chain ledger as a memo, or just to portal SQLite?** Currently the spec says portal SQLite is a write-through cache and the chain transfer memo is `"claim by github:alice via portal, link_id=N"`. That gives a forensic trail on both sides. Alternative: push more structured data into the memo (JSON blob). Memo field size on Node 1 is unverified — confirm before designing.

6. **Auto-pay workflow integration:** Phase 1 ships the portal but `award-rtc.yml` doesn't yet consult `GET /api/v1/lookup` before falling back to `github:*`. That workflow update is a separate PR. Phase 1 still has value without it (existing placeholder balances become claimable), but the steady-state §3.2 flow requires both. Sequence: ship Phase 1, observe, then PR the workflow update.

7. **Wallet rebinding / unlinking:** what's the policy when a contributor wants to switch from `RTCabc...` to `RTCdef...`? Options: (a) one-way — first link wins, can't be changed (forces a new GitHub account for a new wallet); (b) signed rebinding — a new signed proof from the OLD wallet authorizes the rebind; (c) signed rebinding from EITHER old or new wallet plus admin approval. MergeWork's model is unclear here; we have a green field.

8. **Privacy posture on the `github_login ↔ rtc_address` map:** is the lookup endpoint `GET /api/v1/lookup?github_login=alice` public, or does it require an auth token? The award-rtc workflow needs it. So does any agent that wants to "pay alice." But it leaks an on-chain identity for every linked GitHub account. Compare to mergework, which keeps this private (mergework's `/me` only shows YOUR link). RustChain's model is more public-by-default than mergework's. Confirm.

---

*End of spec. Comments and corrections via PR. Do not implement until §9 questions have answers.*
