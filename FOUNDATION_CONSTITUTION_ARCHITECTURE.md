# Foundation Constitution Architecture — Hard Layer vs Soft Layer

**Status:** DRAFT (operator-authored synthesis)
**Date:** 2026-05-30
**Companion to:** [Council RFC bounty #12620](https://github.com/Scottcjn/rustchain-bounties/issues/12620), [FEDERATION_DESIGN_NOTE.md](./FEDERATION_DESIGN_NOTE.md)
**Question this doc answers:** can the foundation council's charter be **partially blockchain-embedded** rather than purely off-chain, and what does the architecture look like if yes?

---

## 0. TL;DR

Four substantive proposals from the council bounty converge on a recognizable governance shape: 7 seats, equal voting weight year 1, three-criteria eligibility (build / hold / advertise), tiered decision thresholds, IP separation from BoTTube/Elyan Labs, operator transition mechanic. These convergences are not coincidental — they reflect the constraints of the problem.

**The next move is structural, not just contractual.** Rather than choosing one proposal and writing a charter PDF that lives on a website, we can split the charter into:

1. **HARD LAYER** — consensus-enforced rules embedded in the protocol (like the 8.192M RTC cap is today). These are immune to council majority abuse because they're enforced by every node.
2. **SOFT LAYER** — off-chain human-judged interpretations: what counts as "build", what makes an "advertise" artifact substantive, when a Tier-0 escalation applies, how to interpret edge cases the charter doesn't anticipate.

The hard layer IS the constitution. The soft layer is the common law that interprets it.

RustChain is uniquely positioned to embed governance in consensus rules because the chain already has a `governance_propose` / `governance_vote` surface that's signed Ed25519 with anti-replay. Extending this into a full council mechanic is a known-scope engineering task (~1,500-2,500 LOC), comparable to bridge_api.py + lock_ledger.py.

This document does NOT propose adopting any specific charter today. It proposes a **two-layer architectural framework** that any of the four bounty proposals (or a synthesis of them) can be expressed in. The bounty close (2026-06-29) chooses the specific values for the hard-layer constants; this doc establishes what those constants *are*.

---

## 1. Synthesis of 4 council proposals

### 1.1 Convergent concepts (all 4 agree → load-bearing for charter)

| Concept | Detail |
|---|---|
| Council size | **7 seats** (all 4) |
| Vote weight year 1 | **Equal per seat** (all 4 explicit; reject token-weighted) |
| Eligibility criteria | **Build + Hold + Advertise** (all 4 use this triple) |
| Hold threshold | **~500 RTC** sustained 30-45 days minimum (luisalias 30d, qingfeng 45d; alan/zqleslie similar order) |
| Term length | **12 months default** with **staggered rotation** (zqleslie/alan explicit; qingfeng implied) |
| Seat loss conditions | Three criteria lapse beyond grace period (all 4 reference this) |
| IP separation | **BoTTube/Elyan Labs explicit out of foundation scope** (all 4) |
| Public votes | All votes recorded with proposer rationale (all 4) |
| Quorum requirements | Per-decision-type quorum (all 4) |
| Anti-capture | No token-weighted vote weight; hold-as-eligibility-gate-only (all 4) |
| Operator transition | From authority → charter custodian or step-down (all 4) |
| Tiered decision thresholds | Routine vs protocol vs charter (zqleslie/qingfeng/alan explicit) |

These are not coincidences. They're the natural attractor when you constrain on:
- IP separation is non-negotiable (Scott's commercial)
- Capture resistance can't depend on token holdings (defeats Proof of Antiquity ethos)
- Small council is fast enough to govern; large enough to avoid 3-person bloc capture
- Build criterion requires demonstrated work; hold requires skin in the game; advertise requires public-facing commitment

### 1.2 Divergent concepts (charter open questions)

| Question | Proposals' positions |
|---|---|
| **Seat archetypes** | luisalias: 5 contributor + 2 at-large; zqleslie: 4 Core + 3 Rotating (tiered); qingfeng: 2 protocol/sec + 1 infra + 1 tooling + 1 miner + 2 at-large; alan: protocol + security + infra + miner + ecosystem + community + 1 public-interest |
| **Tier structure** | zqleslie alone explicit Core/Rotating tiers; others equal seats |
| **Emergency mechanism** | qingfeng: operator+security lead can pause 72h then 14d ratification; alan: 4-of-7 emergency for 72h, continuation needs 5-of-7 |
| **Election process** | zqleslie: RTC-weighted with 10k vote cap per wallet, 20% participation quorum; alan: hybrid (eligibility check + contributor preference vote, council veto needs 6-of-7); others less specific |
| **Independent public-interest seat** | alan explicit; others implicit via at-large |
| **Operator transition timeline** | alan: 6-month charter custodian with single 7-day veto then no veto; others less specific |

These are not "wrong vs right" — they're the choices the charter has to make. The two-layer architecture below treats them as **soft-layer parameters** that the charter sets and that future council votes can amend (within hard-layer constraints).

### 1.3 What each proposal contributes uniquely

- **luisalias007-cmyk:** Most explicit on hold-as-liquidity-engineering and the threshold-review cadence ("hold threshold should be reviewed quarterly")
- **zqleslie:** Best tier structure (Core continuity + Rotating freshness) and the no-tie-breaker mechanic ("if 3-3 with abstention, motion fails and is revisited in 30 days")
- **qingfeng:** Most pragmatic emergency mechanic (pause-then-ratify with explicit 72h/14d windows)
- **alan:** Most rigorous IP-capture protection clause and the 7-day operator veto sunset

These are not in conflict — a charter can adopt all four contributions simultaneously by assigning them to different sections.

---

## 2. The two-layer architecture

### 2.1 Hard layer (chain-enforced via consensus rules)

The hard layer is **immune to council majority abuse** because every node validates the consensus rules. A 7-0 council vote that tries to violate a hard-layer rule produces an invalid transaction that no honest node accepts. This is the same property that makes the 8.192M RTC cap unattackable.

Hard-layer concepts:

| Concept | Implementation |
|---|---|
| **Council seat count** | Charter constant (default 7). Adding/removing seats requires charter amendment (special threshold + time delay). |
| **Active seat registry** | On-chain `council_seats` table: seat_id → holder_miner_id, archetype, elected_at_epoch, term_ends_epoch. |
| **Hold threshold check** | Consensus rule: any signed council action checks `balance(seat_holder) >= hold_threshold AND continuously_held_for(seat_holder) >= hold_duration`. If false, tx rejected. |
| **Vote threshold per decision type** | Decision-type enum: ROUTINE / PROTOCOL / TREASURY / CHARTER / EMERGENCY. Each has a chain-constant required threshold (e.g., simple majority for ROUTINE, 5-of-7 for PROTOCOL, 6-of-7 for CHARTER, 4-of-7 for EMERGENCY-START + 5-of-7 for EMERGENCY-CONTINUE). |
| **Term length boundaries** | Epoch-counted. At each epoch, nodes check whether any seat's term has expired and reject votes from expired seats. |
| **Treasury action constraints** | Treasury wallet has consensus-enforced spending rules: amounts above N RTC require council-signed `treasury_propose` with threshold satisfied. Hardcoded treasury wallets cannot move funds without governance. |
| **IP-protected wallets** | A list of consensus-protected wallets (BoTTube/Elyan-Labs related) that the council CANNOT vote to drain. Any tx that touches them requires the operator's permanent multisig (not the council). Charter amendment cannot change this without unanimous council + operator + 7-epoch delay. |
| **Charter amendment** | Special tx type with: supermajority required (6-of-7), 7-epoch delay between proposal and ratification, public proposal text hash committed to chain. |
| **Vote recording** | Signed Ed25519 governance transactions. Vote = seat_id + proposal_id + yes/no/abstain + rationale_url + nonce. Consensus rejects votes from non-current seat holders. |
| **Anti-capture: nominal supply cap on vote-relevant hold** | Charter constant: max effective hold for purposes of threshold computation = X RTC, so a whale accumulating 10× the threshold doesn't get 10× votes. |

### 2.2 Soft layer (off-chain human judgment)

The soft layer is everything the consensus rules can't decide:

| Concept | Why off-chain |
|---|---|
| **"Build" criterion verification** | Did this PR count as "non-trivial"? Was that security severity assignment correct? Codex audits + reviewer-of-record judgment. |
| **"Advertise" criterion verification** | Is this blog post substantive? Is this tutorial complete enough? Community judgment via comments. |
| **Tier-0 escalation judgment** | Which PR submissions constitute destructive smuggle vs legitimate fix? Operator + Codex + reviewer-of-record. |
| **Charter interpretation** | What counts as "foundation-scope"? Council deliberation. |
| **Emergency invocation judgment** | When does a council member decide to invoke pause? Their discretion. |
| **Edge cases the charter doesn't anticipate** | Common law. Council establishes precedent over time, recorded in council_proposals + their resolutions. |

The soft layer is governed by the council itself (acting under hard-layer constraints), not by every node.

### 2.3 The interaction: hard layer limits what soft layer can decide

Examples:

1. **Soft layer decides what "Critical" means for a bug bounty pay; hard layer enforces that the bounty pay can't exceed the treasury's chain-enforced spending cap without council vote.**
2. **Soft layer decides whether a proposed federation partnership is acceptable; hard layer enforces that the federation custody wallet can't move funds without 5-of-7 council signatures.**
3. **Soft layer decides if a council member's commercial conflict of interest is material; hard layer enforces that any vote where the seat-holder has a chain-disclosed material interest is automatically counted as abstain.**

The pattern: **hard layer makes catastrophic outcomes impossible; soft layer makes everyday outcomes good.**

---

## 3. Concrete protocol additions

If the council adopts this architecture, the protocol needs:

### 3.1 New tables (schema additions)

```sql
CREATE TABLE governance_state (
    -- Single-row state machine for the foundation
    council_seat_count INTEGER NOT NULL DEFAULT 7,
    active_term_start_epoch INTEGER NOT NULL,
    voting_threshold_routine INTEGER NOT NULL,    -- e.g., 4 (simple majority)
    voting_threshold_protocol INTEGER NOT NULL,   -- e.g., 5
    voting_threshold_charter INTEGER NOT NULL,    -- e.g., 6
    voting_threshold_treasury INTEGER NOT NULL,   -- e.g., 5
    voting_threshold_emergency_start INTEGER NOT NULL,  -- e.g., 4
    voting_threshold_emergency_continue INTEGER NOT NULL,  -- e.g., 5
    charter_hash TEXT NOT NULL,    -- sha256 of immutable charter text
    operator_authority_phase TEXT NOT NULL,    -- 'charter_custodian' | 'fully_council' | 'transitional'
    hold_threshold_rtc REAL NOT NULL,         -- e.g., 500.0
    hold_duration_days INTEGER NOT NULL       -- e.g., 30
);

CREATE TABLE council_seats (
    seat_id INTEGER PRIMARY KEY CHECK (seat_id BETWEEN 1 AND 7),
    holder_miner_id TEXT,
    holder_pubkey TEXT,
    seat_archetype TEXT,    -- 'protocol' | 'security' | 'infra' | 'miner' | 'ecosystem' | 'community' | 'public_interest'
    elected_at_epoch INTEGER,
    term_ends_epoch INTEGER,
    eligibility_hold_verified_at_epoch INTEGER,  -- last hold check
    eligibility_build_verified_at_epoch INTEGER, -- last build check
    eligibility_advertise_verified_at_epoch INTEGER,
    status TEXT NOT NULL DEFAULT 'active'    -- 'active' | 'expired' | 'vacated' | 'recalled'
);

CREATE TABLE council_proposals (
    proposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposer_seat_id INTEGER,
    proposal_body_url TEXT NOT NULL,
    proposal_body_hash TEXT NOT NULL,    -- sha256 of body text
    decision_type TEXT NOT NULL,    -- 'routine' | 'protocol' | 'treasury' | 'charter' | 'emergency'
    voting_window_start_epoch INTEGER NOT NULL,
    voting_window_end_epoch INTEGER NOT NULL,
    required_threshold INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'passed' | 'failed' | 'expired' | 'cancelled'
    final_tally_yes INTEGER,
    final_tally_no INTEGER,
    final_tally_abstain INTEGER,
    resolved_at_epoch INTEGER
);

CREATE TABLE council_votes (
    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER NOT NULL,
    seat_id INTEGER NOT NULL,
    vote TEXT NOT NULL CHECK (vote IN ('yes', 'no', 'abstain')),
    rationale_url TEXT,
    signature TEXT NOT NULL,        -- Ed25519 over (proposal_id, seat_id, vote, nonce, charter_hash)
    nonce INTEGER NOT NULL,
    cast_at_epoch INTEGER NOT NULL,
    UNIQUE(proposal_id, seat_id)
);

CREATE TABLE charter_amendments (
    amendment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposed_at_epoch INTEGER NOT NULL,
    earliest_ratification_epoch INTEGER NOT NULL,   -- proposed + 7 epochs minimum
    new_charter_hash TEXT NOT NULL,
    body_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE protected_treasury_wallets (
    -- Consensus-protected wallets that COUNCIL CANNOT touch.
    -- Operator + permanent multisig only. Used for BoTTube/Elyan Labs IP boundary.
    wallet_address TEXT PRIMARY KEY,
    protection_reason TEXT NOT NULL,
    added_at_epoch INTEGER NOT NULL,
    -- Removal requires: unanimous council + operator + 7-epoch delay
);
```

### 3.2 New consensus-enforced transaction types

- `council_propose` — file a proposal for vote
- `council_vote` — cast a signed vote
- `council_seat_nominate` — nominate a candidate
- `council_seat_confirm` — confirm an election result on-chain
- `treasury_propose` — request treasury allocation
- `treasury_execute` — execute approved treasury action (verifies signatures meet threshold)
- `charter_amend_propose` — file a charter amendment
- `charter_amend_ratify` — ratify after delay
- `emergency_pause` — invoke 72h pause (requires 4-of-7)
- `emergency_continue` — extend pause beyond 72h (requires 5-of-7)
- `seat_recall_propose` — propose recalling a seat (requires 5-of-7)

### 3.3 New consensus rules

- Reject any council action where the actor isn't an active seat holder
- Reject any council action where the actor doesn't meet hold threshold at the action's epoch
- Reject treasury actions exceeding chain-enforced cap without sufficient signatures
- Reject any transaction touching a `protected_treasury_wallets` address without operator-permanent-multisig signature
- Auto-advance term boundaries at epoch boundaries (mark expired seats, prevent expired-seat votes)
- Auto-detect quorum failures (return 'failed' if voting window closes without quorum)
- Enforce vote signature scheme: Ed25519 over canonical-JSON payload including charter_hash (so a charter change invalidates in-flight votes from before the change)

### 3.4 Estimated implementation scope

~1,500-2,500 LOC across:
- `node/governance.py` (~600 LOC) — schema + state machine
- `node/council_routes.py` (~500 LOC) — read endpoints (public) + write endpoints (signed)
- `node/governance_consensus.py` (~400 LOC) — consensus rule extensions
- `node/tests/test_governance.py` (~600 LOC) — full test coverage
- Integration into main node file (~50 LOC of wire-in)

Comparable in scope to bridge_api.py + lock_ledger.py combined.

---

## 4. Trade-offs

### 4.1 Hard-layer rigidity

The strength of chain-embedded governance is also its weakness: rules are hard to change. Even a unanimous council voting to fix a bug in the consensus rule for vote signature verification can't change the rule without a charter amendment that goes through the 7-epoch delay.

**Mitigation:** the hard layer should be **minimal**. Embed only the catastrophic-failure-mode protections (treasury draining, IP boundary violation, vote forgery). Everything else stays soft-layer so it can adapt.

### 4.2 Initial chicken-and-egg

You can't have a council enforced by consensus before there IS a council. The bootstrap problem:

**Mitigation:** the operator manually populates `council_seats` for the first 7 elected members after the bounty cycle closes (2026-06-29 → inaugural council formation). After that, all seat changes go through governance proposals.

### 4.3 Cost of charter amendments

Hard-layer rules can only change via charter amendment, which is 6-of-7 + 7-epoch delay. If the council finds a bug in its own design, fixing it is slow.

**Mitigation:** include an `emergency_charter_patch` mechanism — 7-of-7 unanimous council + operator co-sign can patch within a 24h window. Used only for security holes.

### 4.4 Operator-centric early phase

For ~6 months while the council establishes norms, the operator remains the charter custodian and has emergency veto. This is necessary but not ideal.

**Mitigation:** the operator veto sunsets automatically at a chain-recorded epoch boundary. No further governance is required to remove it.

### 4.5 Forking risk

A blockchain-embedded constitution makes RustChain's governance much harder to fork — a fork that ignores the council rules looks visibly different and contributors choose. Good against capture. Bad if the constitution itself has a flaw.

**Mitigation:** the architectural design (this doc) gets public review before any of it ships. The bounty proposal cycle is part of that review.

---

## 5. Risks unique to blockchain-embedded governance

1. **Single-point-of-protocol-failure:** if there's a bug in the governance consensus code, the whole chain can halt. Mitigation: extensive testing, gradual rollout, emergency patch mechanism.

2. **Treasury attack via charter amendment:** if a council majority votes to amend the charter to remove treasury protections, the 7-epoch delay buys time but doesn't prevent it. Mitigation: protected_treasury_wallets requires UNANIMOUS council + operator + delay. Operator's permanent multisig is the last-line defense for the IP boundary.

3. **Hold-threshold gaming:** a contributor borrows RTC to qualify, then returns it. Mitigation: hold_duration_days check requires CONTINUOUS hold, not snapshot. Lend-borrow-return doesn't satisfy.

4. **Vote-buying:** seat holder is offered RTC for a specific vote. Mitigation: votes are public + signed + rationale-required. Bribed-then-detected votes can be recalled via `seat_recall_propose`.

5. **Whale capture of elections:** if seat elections are RTC-weighted (zqleslie's proposal), a whale could swing them. Mitigation: vote cap per wallet (10,000 RTC max effective vote weight) + 20% participation quorum.

6. **Constitutional crisis:** the council can deadlock (3-3-1 abstention). Mitigation: per zqleslie, motion fails and is re-proposed in 30 days. Per alan, public-interest seat breaks ties.

---

## 6. Recommended path

### 6.1 Now (this week — 2026-05-30 through 2026-06-06)

- This document gets posted publicly as a synthesis + architecture proposal
- Council bounty proposers (luisalias / zqleslie / qingfeng / alan) review whether the hard/soft layer framework fits their thinking
- Their capability-proof responses (Addendum 2 deadline 2026-06-06) can address whether they support the chain-embedded constitution approach or prefer pure-document governance

### 6.2 Council bounty close (2026-06-29)

- Operator selects winning proposal (or synthesizes a hybrid)
- Charter text gets locked: hard-layer constants chosen, soft-layer parameters defined
- Inaugural council members nominated (operator selects 5-7 from contributors who meet build + hold + advertise criteria)

### 6.3 Implementation phase (2026-07 through 2026-09)

- Build the protocol additions (governance.py + council_routes.py + consensus extensions + tests)
- Stage on testnet first, then production
- Run inaugural council under operator transitional authority for 6 months
- Operator veto sunsets at chain-recorded epoch boundary

### 6.4 Steady state (2026-12-ish onward)

- Council operates under full hard-layer constraints
- Soft-layer interpretation via council deliberation, recorded as precedents
- Quarterly transparency report (per alan / qingfeng proposals)
- Charter amendments possible via 6-of-7 + 7-epoch delay
- Emergency patches possible via 7-of-7 + operator + 24h window

---

## 7. Open questions for joint review (this doc)

In addition to the bounty's section A-H, this architecture raises:

1. **Hard-layer scope:** should it be smaller (only treasury + IP + vote signature) or larger (also term length + seat count + hold threshold)? Larger = stronger but less flexible.

2. **Charter hash binding:** votes must include the active `charter_hash`. If charter is amended mid-voting-window, do in-flight votes auto-invalidate? Proposed: yes (votes signed against old hash become invalid).

3. **Hold-threshold continuous check:** how often does consensus re-verify continuous hold? Proposed: per-action check, since balances are queryable in O(1) per the existing balance schema.

4. **Treasury cap:** what's the chain-enforced max single treasury transfer without council vote? Proposed: 1,000 RTC at $0.10 ref (~\$100). Halves at each rate-reduction milestone in line with [#12593](https://github.com/Scottcjn/rustchain-bounties/issues/12593).

5. **Protected wallets list:** which specific addresses go in `protected_treasury_wallets` from the BoTTube/Elyan Labs scope? Operator declares at chain-genesis-for-governance.

6. **Council bootstrap signing:** the very first council vote (charter-adopt) is signed by what? Proposed: operator's permanent multisig, with subsequent votes signed by the elected council per their charter-defined process.

7. **Emergency veto window for operator:** alan proposes 6 months. Should this be epoch-anchored (sunset at epoch N+1100 = ~6 months) or vote-anchored (sunset after first 10 successful council votes)?

8. **MergeWork federation interaction:** if federation pilot lands during the operator-transitional phase, who decides yes/no — operator alone or council majority? See [federation design note §9 stage 4](./FEDERATION_DESIGN_NOTE.md).

---

## 8. Sign-off and process

This document is a **synthesis + architectural proposal**, not a charter. It:

- Maps the 4 bounty proposals' convergences and divergences
- Defines a two-layer architecture that any winning proposal can be expressed in
- Specifies the protocol additions needed to embed the hard layer
- Lists the trade-offs and risks
- Recommends a staged implementation path through 2026-12

**Lifecycle:** DRAFT → REVIEWED → ADOPTED. Promotion to REVIEWED requires the 4 bounty proposers' read + at least 3 substantive public comments addressed. Promotion to ADOPTED requires inaugural council confirmation after they're seated.

**Operator note:** this synthesis was written by the operator (Scott) AI-assisted, not a bounty submission. It's the operator's reading of how the bounty proposals interact with RustChain's existing protocol surface. Bounty proposers can rebut, refine, or replace this synthesis in their capability-proof responses.

---

## 9. Why this matters

A document-only constitution can be ignored. A blockchain-embedded constitution cannot.

If the council votes 7-0 to drain the foundation treasury into one member's wallet, a chain-embedded constitution makes the transaction invalid at the consensus layer. No fork. No social-coordination crisis. The protocol rejects it.

That's the difference between "we have a foundation" and "we have a foundation that **structurally cannot be captured**." The first is a community claim. The second is a property.

RustChain's existing primitives (signed governance proposals, Ed25519 vote signatures, hardware-attested miner identity, consensus-enforced 8.192M cap) make this structurally possible in a way most chains can't easily do. The bridge_federation_routes and bridge_reconciliation work done today are the same architectural pattern at the cross-chain layer.

Embedding the foundation constitution in consensus rules is the natural extension of those patterns. Same engineering discipline; same trust-minimization principle; same operator-bearing standard.

---

*Companion docs: [FEDERATION_DESIGN_NOTE.md](./FEDERATION_DESIGN_NOTE.md), [FEDERATION_BRIDGED_SUPPLY_SPEC.md](./FEDERATION_BRIDGED_SUPPLY_SPEC.md). Council bounty: [Scottcjn/rustchain-bounties#12620](https://github.com/Scottcjn/rustchain-bounties/issues/12620).*
