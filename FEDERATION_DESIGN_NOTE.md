# Federation Design Note: RTC ↔ MRWK Bridge

**Status:** DRAFT (for public review)
**Authors:** Scott Boudreaux (RustChain), incorporating input from @ramimbo's reply on `mergework#571`
**Date:** 2026-05-29
**Companion threads:**
- RustChain: `Scottcjn/Rustchain#6522` (RFC)
- MergeWork: `ramimbo/mergework#571` (proposal)
**Intended reviewers:** @ramimbo, public MergeWork community, public RustChain community
**Lifecycle:** DRAFT → REVIEWED → ADOPTED (process described in §12)

---

## 1. Purpose & non-goals

### Purpose

This document proposes a federated bridge between **RustChain** (RTC) and
**MergeWork** (MRWK) — two ledgers that already overlap on contributor
identity (the `github:<login>` lazy-pay primitive) but do not currently share
any cross-side value path. The goal of the bridge is to let a balance on one
side mirror a balance on the other side under a strict **1:1 lock-and-mirror**
model, with the conservation rules of *both* sides preserved.

This is a design note, not a commitment. Its purpose is to make the trust
model, supply accounting, failure modes, and staged rollout legible enough
that both maintainers and both communities can argue with the design *before*
any code is built or any value moves.

### Non-goals

To match @ramimbo's "evidence-backed and auditable before operational" framing,
this design explicitly does **not** propose any of the following in v1:

- **No off-ramp.** Neither side has a public exchange or fiat path. The
  bridge connects two on-chain ecosystems; it does not connect either of
  them to USD.
- **No fixed conversion rate baked in.** The bridge operates on **1:1
  mirror semantics** (1 RTC locked on the RustChain side ⇔ 1 MRWK mirrored
  on the MergeWork side, and vice versa). This is *not* a claim that 1 RTC
  is economically equivalent to 1 MRWK — it is a supply-accounting choice
  that lets both sides' conservation rules hold simultaneously. Market rate
  is a separate, later RFC topic (see §11).
- **No bridge-specific MCP execution tools.** Read-only reconciliation
  surfaces only, in v1. This directly follows @ramimbo's guidance.
- **No Ergo anchoring or third-leg external anchoring in v1.** Interesting,
  but deferred until the two-party event format and reconciliation model
  are stable (see §11).
- **No committed rollout timeline.** Step `N+1` of the staged path (§9)
  begins only when step `N` has produced reviewed, public evidence that it
  works.
- **No implication that MergeWork has agreed to build this.** @ramimbo's
  reply expressed interest in the design conversation, not a build
  commitment. Nothing in this document binds MergeWork to anything.

---

## 2. Trust model

### 2.1 What each side enforces

| Constraint | RustChain side | MergeWork side |
|---|---|---|
| **Supply cap** | 8,192,000 RTC (consensus-enforced) | 100,000,000 MRWK (genesis, ledger-conserved per @ramimbo's reply on `mergework#571`) |
| **Issuance rule** | Mined: 94% block rewards / 6% premine across community / dev / foundation; halving 1.5 → 0.75 → 0.375 RTC per epoch every 2 years | Minted on labeled, merged work inside MergeWork's bounty workflow |
| **Issuance gate** | Hardware fingerprint + antiquity multiplier + Proof-of-Antiquity attestation | Maintainer signature on bounty labels |
| **Public controls** | RIP-200 / RIP-PoA consensus rules, plus admin-key gated `/wallet/transfer` with 24h void window | Maintainer-driven today; treasury-action public controls in scope of `mergework#458` |
| **Identity primitive** | `github:<login>` lazy-pay (also used on RustChain) | `github:<login>` lazy-pay (native primitive) |

This is an **asymmetric pair**: RustChain's issuance is constrained by
consensus rules that no relayer can override. MergeWork's issuance is
constrained by maintainer policy, which is more flexible but currently has
smaller public guarantees — precisely what `mergework#458` is intended to
address.

### 2.2 Where the trust burden lives

The trust burden of a federated bridge does **not** live on either chain.
It lives on the **relayer set** — the small group whose signatures
authorize cross-side actions on bridge custody wallets.

This is the unavoidable shape of any federated bridge between asymmetric
ledgers. Neither chain can verify the other's state natively, so a set of
parties has to act as the cross-side oracle.

What this means concretely:

- A compromise of either chain's broader admin key is *not* a bridge
  compromise. The bridge's custody wallets are separate.
- A compromise of the relayer set is *not* a chain compromise. The blast
  radius is bounded to whatever the bridge custody wallets hold.
- The bridge therefore inherits **the harder of the two sides' constraints**
  for any given action. The 8.192M RTC cap binds the bridge. The 100M MRWK
  conservation binds the bridge. Neither can be overridden by relayer
  action.

### 2.3 Asymmetry to be honest about

@ramimbo's reply correctly notes that MergeWork has no public bridge,
exchange, off-ramp, or external value path. The bridge does not change
this. It is a value path *between* the two ledgers, not *out* of either.
Both ledgers remain inward-facing systems with no fiat off-ramp. The
bridge is an interoperability primitive between two contributor-economy
ledgers that already share the `github:<login>` identity primitive — not
a liquidity event.

---

## 3. Supply accounting model

### 3.1 1:1 lock-and-mirror

The proposed primitive is **lock-and-mirror**:

- To move N units from side A to side B, a user sends N units to the
  bridge custody wallet on side A. After finality (see §5), the relayer
  set authorizes the issuance of N mirror units to the user's destination
  address on side B.
- The original N units on side A are **not burned**. They are **locked**
  in the custody wallet. They remain part of side A's accounted supply.
- The mirror N units on side B are **issued from a bridge reserve** that
  is itself bounded by side B's conservation rule.

### 3.2 The invariant

At any point in time, the following must hold:

```
(RTC locked in bridge custody on RustChain side)
   ==
(MRWK mirrored from RTC currently circulating on MergeWork side)

AND

(MRWK locked in bridge custody on MergeWork side)
   ==
(RTC mirrored from MRWK currently circulating on RustChain side)
```

Both sides therefore expose a **bridged-supply counter** that is readable
by anyone with chain read access on that side. Reconciliation (§6) is
defined as verifying that the two counters agree.

### 3.3 Why not mint-and-burn

A cheaper design would burn N RTC on the source side and mint N MRWK
on the destination side. v1 rejects this because RustChain's 8.192M cap
is consensus-enforced (no "bridge burn" opcode exists and we don't
propose adding one), and MergeWork's 100M conservation rules out
minting outside the ledger rules — @ramimbo's reply explicitly flagged
that minting beyond ledger rules is out of scope. Lock-and-mirror
sidesteps both constraints: nothing is destroyed on the source side,
nothing is created beyond destination-side reserve.

### 3.4 Where the reserves come from

On the MergeWork side, mirrored MRWK draws from a pre-allocated
**bridge reserve** within the 100M conservation rule. The reserve cap
*is the bridge capacity ceiling for that direction*. Sizing it is a
MergeWork governance question, not decided here. The same applies in
reverse: the RustChain-side MRWK→RTC reserve draws from existing RTC
allocations (likely community vault or a dedicated bridge sub-allocation)
within the 8.192M cap.

### 3.5 Capacity ≠ throughput

The reserve cap is the *total simultaneous bridged supply ceiling*, not
the throughput limit. Throughput is bounded separately by pilot caps
(§9) and per-epoch rate limits.

---

## 4. Relayer model

### 4.1 v1: 2-of-2 manual review

For v1, the relayer set is **Scott (RustChain) + @ramimbo (MergeWork)**,
requiring both signatures on every cross-side action. Every operation is
manually reviewed by both relayers before signing.

This is deliberately slow. The point of v1 is to surface design problems,
not to scale.

### 4.2 v2: 2-of-3 with a community-elected third

After v1 has produced some defined period of clean operation (suggested:
90 days, see §9), the relayer set expands to 2-of-3 with a third relayer
either community-elected or randomized via a Proof-of-Antiquity stake
mechanism on the RustChain side. The third relayer holds bridge custody
signing keys *only* — not broader chain admin keys.

The choice between "elected" and "randomized via PoA stake" is an open
question (§10).

### 4.3 Blast radius

The relayer set holds **only** the bridge custody wallets' signing keys.
It does **not** hold RustChain's `RC_ADMIN_KEY` (which gates internal
`/wallet/transfer` calls; remains with RustChain ops independently) or
MergeWork's maintainer keys (which gate native MRWK minting via the
bounty workflow; remain with @ramimbo / future MergeWork maintainers).
Maximum loss from a complete relayer-set compromise is therefore
**the bridge custody balance**, not either ledger's broader admin
scope.

### 4.4 Kill switch (single-relayer pause)

**Any single relayer** can pause cross-side issuance unilaterally on
either direction. Restart requires **all relayers** to sign (in v1, both
relayers; in v2, all three).

This asymmetry — easy to pause, hard to resume — is the right shape: a
suspected compromise should be paused immediately on one party's
judgment, but resuming should require independent confirmation that the
suspicion is resolved.

### 4.5 Why this conservative posture

Operational context that should be on the record: RustChain has handled
**five Tier-0 destructive-PR cases in the last 27 days**, most recently
`Scottcjn/Rustchain#6267` (today, 2026-05-29) — a 4400-LOC scope-exploded
PR pretending to be a "cap string lengths" cleanup that smuggled a WSL
anti-fingerprint module and a hardcoded wallet. The wallet had zero
balance and the PR was caught pre-merge, but the pattern is real.

A bridge concentrates custody and is therefore a higher-value attack
target than either ledger's normal operations. The design must assume
bridge code *will* be the target of smuggle attempts and bridge custody
keys *will* be the target of compromise attempts. The relayer model
above is designed to bound the blast radius of both.

---

## 5. RTC-side mechanics: void window + finality

### 5.1 The 24h void window is a hard constraint

RustChain's `/wallet/transfer` endpoint exposes a **24-hour void window**.
Within that 24h, the sender can cancel the transfer. This is intrinsic
to RustChain's finality model and is **not negotiable from our side**.

The bridge inherits this constraint: it cannot credit the MergeWork side
until the void window has fully elapsed on the RustChain side. Otherwise:

```
T+0      User sends N RTC to bridge custody on RustChain
T+0      Relayer (wrongly) credits N MRWK on MergeWork side
T+12h    User voids the RTC transfer
T+12h+   Bridge has lost N units net: MRWK was credited, RTC was returned
```

That failure mode is unrecoverable without a clawback on the MergeWork
side, which we do not assume MergeWork has.

### 5.2 Concrete RTC → MRWK timeline

```
T+0          User sends N RTC to bridge custody on RustChain
             RTC transfer enters pending state (subject to void window)
T+24h        Void window closes; transfer becomes confirmed
T+24h+ε      Relayer observes the confirmation via RustChain read API
T+24h+δ      Both relayers manually review the operation (in v1)
T+24h+δ'     Both relayers sign; N MRWK issued to user's destination
             address from bridge reserve on MergeWork side
```

Total user-visible delay: ~24 hours plus operational latency (in v1,
expected on the order of hours, not minutes).

### 5.3 Concrete MRWK → RTC timeline

The reverse direction depends on MergeWork's finality model
(label-applied + defined challenge/dispute period before commitment).
The bridge MUST wait for whatever that is before releasing RTC from
custody. The exact MergeWork finality definition is an open question
for @ramimbo and the MergeWork community (§10.9).

### 5.4 Why this is non-negotiable

The 24h void window is RustChain's soft-finality + user-reversibility
primitive on `/wallet/transfer`. The endpoint is shared across all
transfer use cases, so weakening it for bridge operations would weaken
it for every other transfer too. The bridge inherits the void window;
the void window does not change for the bridge.

---

## 6. Pause / refund / reconciliation paths

### 6.1 Pause

**Trigger:** any single relayer signs a pause message for either
direction (RTC→MRWK, MRWK→RTC, or both).

**Effect:** no new cross-side operations are authorized. In-flight
operations either complete on their original path (if they have already
reached the irreversible point on both sides) or roll back to a safe
state.

**Restart:** requires all relayers to sign a restart message.

### 6.2 Refund

A bridge operation can be **aborted** by the sender before the relayer
set has issued the mirror, subject to the following:

- **RTC → MRWK abort:** the user voids the RTC transfer within the 24h
  void window. The relayer set observes the void and never issues MRWK.
  No relayer signature needed for the abort itself; the abort is
  enforced by the RustChain void primitive.
- **MRWK → RTC abort:** depends on MergeWork's finality model. If
  MergeWork supports an analogous user-controlled cancellation within
  the finality window, the same pattern applies. If it does not, the
  abort path requires relayer-set signature, which is a heavier
  operation.

The asymmetry here is real and should be acknowledged in user-facing
copy (§7).

### 6.3 Reconciliation

**Cadence:** at least once per RustChain epoch (~24h). Possibly more
frequent (§10 open question).

**Per-cycle action:** both sides publish a state attestation containing:

- Locked-on-this-side bridge custody balance
- Mirrored-on-other-side bridge supply counter
- Expected delta (should be zero modulo in-flight operations within the
  reconciliation window)
- Tail of recent bridge events (lock, mirror-issue, abort, pause/resume)
- Signature(s) from the relayer set on the attestation itself

**Mismatch:** any reconciliation that shows a delta beyond a defined
tolerance triggers an **automatic pause** of both directions and a
mandatory manual audit before resume. The tolerance threshold is itself
an open question (§10).

### 6.4 Reconciliation as MCP read-only surface

Each side exposes (at minimum) these MCP tools, **all read-only**:

- `bridge.state.get` — current locked balance + mirrored supply counter
  + last reconciliation timestamp + last reconciliation result.
- `bridge.events.list` — paginated recent bridge events with cursor.
- `bridge.reconcile.compare` — fetch both sides' state attestations,
  return delta + verifiable signature trail.

These map directly to @ramimbo's "read-only MCP/status/reconciliation
surfaces are a safer first step" guidance. Agents can audit bridge
health without execution authority.

`rustchain-claim-portal` Phase 2 already ships a read-only MCP layer on
the RustChain side; the bridge surfaces can sit alongside or inside it
(implementation detail; see §10).

---

## 7. Public wording (user-facing)

The bridge's public copy should be **deliberately under-promising**.
Here are concrete user-facing strings the design assumes will be present:

### 7.1 Initiation copy (RTC → MRWK)

> Send N RTC to the bridge custody address `RTC<...>`. Your equivalent
> N MRWK will become available on MergeWork approximately 24 hours after
> RustChain confirms your transfer. You can void the transfer within
> the first 24 hours; doing so will cancel the bridge operation and no
> MRWK will be issued. There is no fee currently, but the operation may
> be paused at any time by either bridge operator.

### 7.2 Initiation copy (MRWK → RTC)

> Send N MRWK to the bridge custody label on MergeWork. Your equivalent
> N RTC will become available on RustChain after MergeWork finalizes
> your transfer (timing depends on MergeWork's finality rules; see
> [MergeWork finality docs]). The operation may be paused at any time
> by either bridge operator. Refunds in this direction require operator
> action and are not user-cancellable after MergeWork commits.

### 7.3 Bridge state display

> **Bridge state, last reconciled YYYY-MM-DD HH:MM UTC:**
>
> - X RTC currently locked in bridge custody (RustChain side)
> - X MRWK currently mirrored (MergeWork side, sourced from this lock)
> - Y MRWK currently locked in bridge custody (MergeWork side)
> - Y RTC currently mirrored (RustChain side, sourced from this lock)
> - Reconciliation result: OK / MISMATCH (delta: Δ)
> - Bridge status: ACTIVE / PAUSED-IN / PAUSED-OUT / PAUSED-BOTH

### 7.4 Things the copy must NOT say

- It must not say "convert" or "exchange." It says "mirror" or "bridge."
- It must not imply a market rate. The 1:1 is a *supply-accounting
  semantic*, not a price claim.
- It must not promise liquidity on either side.
- It must not promise an off-ramp to fiat.
- It must not promise that the bridge will remain active. It must
  acknowledge that either operator can pause.

### 7.5 Why this matters

Bridge UI copy is a real attack surface — legal/regulatory and
expectation-setting both. The defensible pattern is documentation that
under-promises plus verifiable on-chain state that over-delivers. The
bridge copy should follow it.

---

## 8. Failure modes

This section is the substantive one. Each failure mode lists its
trigger, blast radius, detection path, and mitigation.

### 8.1 Single-relayer key compromise

- **Trigger:** one relayer's signing key is exfiltrated.
- **Blast radius:** in v1 (2-of-2), **zero** — the attacker cannot
  unilaterally sign any cross-side action. In v2 (2-of-3), **zero** —
  same reason; 2-of-3 still requires a second valid signature.
- **Detection:** the compromised key signs a request the legitimate
  relayer did not propose, surfaced via the relayer set's pre-sign
  review channel.
- **Mitigation:** the uncompromised relayer pauses both directions
  (§6.1). Key rotation procedure run before resume. Reconciliation
  audit before any new operations.

### 8.2 Full relayer-set compromise

- **Trigger:** all relayer signing keys compromised simultaneously.
- **Blast radius:** entire bridge custody balance, not either chain's
  broader admin scope.
- **Detection:** reconciliation drift between expected and actual
  on-chain state. Public bridge state is independently verifiable, so
  detection does not depend on relayer honesty.
- **Mitigation:** any public observer (including read-only MCP agents)
  can flag the drift. Social recovery via community statement on both
  ledgers. If unrecoverable, the affected bridge reserves are deemed
  lost; the underlying ledgers remain intact.
- **Lesson:** bridge custody balances should be sized as what we are
  willing to lose to worst-case relayer compromise, not as what we wish
  were available. Cap sizing in §9 reflects this.

### 8.3 Source-side reorg after mirror commit

- **Trigger:** RustChain reorgs past the block where a bridged transfer
  was confirmed, *after* the relayer set has already issued the mirror
  MRWK.
- **Blast radius:** mismatched bridged-supply counters (more MRWK
  mirrored than RTC locked, because the RTC lock got reorg'd out).
- **Detection:** next reconciliation cycle.
- **Mitigation primary:** the 24h void window already buys us 24h of
  finality buffer. A reorg deeper than 24h on RustChain is the trigger
  scenario for an emergency pause, not a routine operation.
- **Mitigation secondary:** if it happens, the relayer set executes a
  signed "undo" on the MergeWork side to retire the orphaned mirror.
  This is heavy and requires public disclosure.
- **Open question:** what reorg depth on the RustChain side should
  trigger the emergency pause? See §10.

### 8.4 Destination-side reorg / dispute after RTC release

- **Trigger:** MergeWork's finality is challenged after the relayer set
  has already released RTC from custody.
- **Blast radius:** mismatched bridged-supply counters in the opposite
  direction.
- **Detection:** next reconciliation cycle, plus MergeWork dispute
  notification (mechanism TBD by MergeWork's finality rules).
- **Mitigation:** the same "signed undo + pause" pattern applies in
  reverse. The relayer set issues a signed undo on the RustChain side
  to retire the orphaned mirror.

### 8.5 Reconciliation feed lies

- **Trigger:** relayer set publishes a false attestation claiming the
  bridged-supply counters match when they don't.
- **Blast radius:** detection delay only — on-chain state is
  independently verifiable, not direct loss.
- **Detection:** any third party can fetch both sides' on-chain state
  via public read APIs and compare to the relayer-signed attestation.
  `bridge.reconcile.compare` (§6.4) reproduces the honest answer, so a
  dishonest attestation is detectable by anyone who runs the comparison.
- **Note:** this is the strongest argument for read-only MCP first. The
  reconciliation surface IS the bridge's accountability mechanism;
  exposing it for read-only agent access amplifies the auditor pool by
  orders of magnitude.

### 8.6 Bridge endpoint DOS

- **Trigger:** transfer queue grows unbounded due to malicious or
  accidental flood of bridge requests.
- **Blast radius:** bridge throughput degraded; no fund loss.
- **Detection:** queue depth metrics, request rate metrics.
- **Mitigation:** rate limit per source address (RTC side) or per
  GitHub identity (MergeWork side); bounded queue with reject-excess
  semantics; queue depth published on read-only MCP surface so
  observers can see when the bridge is congested.

### 8.7 Tier-0-style smuggle attempt against bridge code

- **Trigger:** a PR (from either side) modifies bridge code with hidden
  destructive behavior — e.g., a "cleanup" PR that quietly disables a
  validator, swaps a custody address, or removes a void-window check.
- **Blast radius:** if merged, could drain bridge custody.
- **Detection:** file-by-file diff review on every bridge code change.
  Codex (or equivalent independent agent) audit on every bridge PR
  before merge. Cross-relayer review (each relayer reviews every bridge
  PR independently before either side merges).
- **Mitigation policy:** the file-by-file audit policy that applies to
  consensus-critical code on the RustChain side applies to bridge code
  **without exception**. No emergency hotfix path bypasses this. If we
  cannot afford the review time, we pause instead.

### 8.8 Custody address substitution

- **Trigger:** the public bridge custody address gets quietly replaced
  (in docs, in client code, in a transaction) with an attacker-
  controlled address.
- **Blast radius:** users who follow the wrong address lose their
  source-side funds.
- **Detection:** the custody address is pinned in multiple
  independently-controlled places (RustChain repo README, MergeWork
  repo README, both maintainers' personal channels). Any divergence is
  a red flag.
- **Mitigation:** custody address changes require a public,
  cross-signed (both relayers) announcement with a defined notice
  period before the new address goes live. No "silent rotation."

### 8.9 Mismatched supply counter drift

- **Trigger:** subtle accounting bug or partial reconciliation failure
  causes the two sides' counters to drift slowly out of sync.
- **Blast radius:** if undetected, equals the drift accumulated over
  detection delay.
- **Detection:** every reconciliation cycle checks for delta beyond
  tolerance.
- **Mitigation:** automatic pause on mismatch (§6.3). Resume requires
  manual audit signed by both relayers. The reconciliation tolerance
  is itself an open question (§10) — a tighter tolerance means more
  false pauses but tighter bound on undetected drift.

### 8.10 Out of scope for v1 (acknowledged)

The following failure modes exist but are explicitly out of scope for
v1 because they only apply once the bridge supports market-rate
operation, which v1 does not:

- Front-running / sandwich attacks on either side
- MEV extraction from cross-side arbitrage
- Oracle manipulation for a market-rate feed

These re-enter scope if and when the bridge moves beyond 1:1 mirror
semantics (§11).

---

## 9. Staged rollout

@ramimbo's reply proposed a four-step path. This section maps each step
to concrete artifacts and entry/exit criteria.

### Stage 1 — MergeWork governance settles

- **Owner:** @ramimbo + MergeWork community.
- **What:** `mergework#458` (governance) reaches ADOPTED on the
  MergeWork side, producing public controls around treasury actions:
  proposal visibility, delay, challengeability, caps, reconciliation,
  clear limits.
- **RustChain side action:** observe only; no upstream PRs. Design
  feedback only if requested.
- **Exit:** `mergework#458` (or its successor) ADOPTED.

### Stage 2 — Federation spec lands

- **Owner:** joint (this document + public review).
- **What:** this design note reaches REVIEWED (process in §12) with
  both maintainers + at least 3 public review comments incorporated.
- **Exit:** document status DRAFT → REVIEWED, both maintainers signed,
  public changelog of substantive revisions.
- **Estimated:** 2-4 weeks of public review; no hard deadline.

### Stage 3 — Read-only reconciliation surfaces ship

- **Owner:** joint (each side ships its own read-only surfaces).
- **What:** both sides deploy the MCP tools from §6.4
  (`bridge.state.get`, `bridge.events.list`, `bridge.reconcile.compare`).
  Both publish bridged-supply counters + event tails. Zero mutation.
  Zero value movement. Surfaces are deployed *before* any custody wallet
  exists and return empty state initially — stage 3 proves out the
  observability infrastructure before any value is at stake.
- **Exit:** surfaces live on both sides for ≥30 days with public access,
  no downtime that would have masked a real reconciliation failure.
- **Estimated:** 2-4 weeks of build + 30-day operating period.

### Stage 4 — Small manually-reviewed pilot

- **Owner:** joint (both relayers manually review every operation).
- **What:** v1 operational bridge with hard caps:
  - Direction: RTC → MRWK only in first month; MRWK → RTC opens after
    one clean month.
  - Total bridged-supply cap per direction: suggested **100 RTC** (and
    100 MRWK reserve) for first 30 days. Open question (§10).
  - Per-operation cap: suggested 10 RTC.
  - Per-day op cap: suggested 5.
  - Eligible users in first month: suggested single named pilot
    contributor (jointly chosen), to remove the unknown-attacker
    failure mode during bring-up.
  - Manual review: every operation reviewed by both relayers pre-sign.
    No automation.
  - Public dashboard: the stage-3 read-only MCP surfaces.
- **Exit:** 90 consecutive days clean (no reconciliation mismatches
  beyond tolerance, no unplanned pauses or key rotations).
- **Estimated:** 90+ days minimum.

### Stage 5+ — Expansion

Cap expansion is **geometric, not linear**, gated on clean operating
periods:

- 90 days clean at 100 RTC → expand to 1,000 RTC, 90 more clean.
- 90 days clean at 1,000 RTC → expand to 10,000 RTC, 90 more clean.
- Beyond 10,000 RTC, every expansion requires a fresh design review
  and public RFC.

The 2-of-3 relayer expansion (§4.2) is also a stage-5 decision and
should not happen during stage 4.

### Non-stages (explicitly not on the path)

- Automated market-making on top of the 1:1 mirror.
- Off-ramp.
- Third-leg anchor (Ergo or otherwise).
- Bridge-specific MCP execution tools.
- Timeline commitments measured in weeks rather than "after prior
  stage's exit criteria."

---

## 10. Open questions for joint review

Explicitly open — not decided here. Listed so public review can
converge on answers before stage 3.

1. **MCP tool schema.** What exact schema should `bridge.state.get`,
   `bridge.events.list`, and `bridge.reconcile.compare` use? The
   RustChain side is shipping `rustchain-claim-portal` Phase 2 with a
   read-only MCP layer; that schema could be a starting point, but
   MergeWork's `mcp.mrwk.ltclab.site` is already live and the
   conventions there may make more sense as the canonical schema.
2. **Reconciliation cadence.** Per-RustChain-epoch (~24h) is the
   default. Should it be shorter (every block, every hour)? Tradeoff:
   shorter cadence → faster detection of drift, more relayer
   operational load.
3. **Reorg depth threshold for emergency pause.** What RustChain
   reorg depth triggers the §8.3 emergency pause? The 24h void window
   provides a natural buffer, but a reorg deeper than ~few hours is
   already abnormal.
4. **Pause policy.** Is it "any single relayer can pause" (1-of-N
   veto, proposed) or "majority of relayers must pause" (M-of-N
   threshold)? 1-of-N veto is the more conservative posture; M-of-N
   might be too slow when speed of pause matters.
5. **Pilot cap value.** 100 RTC is a placeholder. What's the right
   number? Considerations: small enough that loss is tolerable; large
   enough that real operational signal is generated; aligned with what
   MergeWork can reserve from the 100M cap as a mirror.
6. **Single pilot contributor identity.** Should the first-month pilot
   be limited to one named contributor? If yes, who? If no, what
   bounded eligibility rule replaces it?
7. **Ergo anchoring in v1 reconciliation.** RustChain already has Ergo
   anchoring infrastructure (`rustchain_v2_integrated_v2.2.1_rip200.py`
   wires `ergo_miner_anchor.py`). Should v1 reconciliation
   attestations also be anchored to Ergo as a third-party witness, or
   is that deferred to a later RFC?
8. **Reconciliation tolerance.** Should the auto-pause threshold be
   exact-match (zero delta), or accept a small tolerance for in-flight
   operations that straddle the reconciliation boundary? If
   non-zero, what value?
9. **MRWK side finality definition.** What is MergeWork's finality
   model for a labeled, merged bounty? When does the bridge consider
   an MRWK lock to be "committed" enough to release the RTC mirror?
10. **Public wording on each side's official site.** Who drafts the
    initial copy for each side? When does it ship? Suggested: it
    ships as part of stage 3 (read-only surfaces), before any value
    moves.
11. **Single bug-bounty surface.** Does the bridge get covered by
    RustChain's existing bounty surface? MergeWork's? Both? A new
    joint surface? Bridge code as a Tier-0 target argues for explicit
    coverage somewhere, not implicit "well, it's covered because
    each side has its own bounty program."
12. **Custody wallet implementation.** On the RustChain side, custody
    is just a `/wallet/transfer` destination address. What's the
    equivalent on the MergeWork side, given that MRWK's primitives
    are bounty-label-driven rather than address-transfer-driven?

---

## 11. Deferred to later RFCs

Out of scope for v1, noted here so v1 review does not get diluted:

- **Market rate.** v1 is strictly 1:1 mirror semantics. Market rate
  needs an external oracle (new trust dependency) or a bridge-aware
  AMM (much larger surface). Neither is appropriate now.
- **Sig schemes beyond 2-of-2 / 2-of-3.** Threshold sigs, FROST, BLS
  aggregation — defer to v3+ when the relayer set has grown.
- **Anti-replay beyond the 24h void window.** Void window + per-op
  nonces from the bridge custody address are sufficient for v1. More
  sophisticated coordination defers.
- **MEV / sandwich protection.** N/A while there is no market rate.
- **Cross-bridge with other chains.** Ergo as a third-leg witness
  anchor is occasionally floated, but a *bridge* to Ergo (or any other
  chain) is out of scope. RTC-MRWK is one bridge, not a hub.
- **Smart-contract / trustless bridge logic.** Neither side is an
  EVM-style smart-contract platform. The bridge is intentionally
  federated/custodial. Moving trustless later would need both sides to
  add light-client-verifiable state proofs, which neither currently
  has.

---

## 12. Sign-off and process

### 12.1 This is a proposal

This document is a **proposal**, not a commitment. Neither maintainer
is bound until ADOPTED status. @ramimbo's `mergework#571` reply called
for "evidence-backed and auditable before operational"; this document
is the evidence, public review delivers the auditability.

### 12.2 Intended reviewers

- **@ramimbo** — primary on §2-§4, §6, §10.
- **Scott Boudreaux** — primary on §5, §8, §9.
- **Public MergeWork community** — §7 wording, §10.6 pilot eligibility.
- **Public RustChain community** — §8 failure modes (esp. §8.7 Tier-0
  smuggle defense), §10.6 pilot eligibility.

### 12.3 Status lifecycle

- **DRAFT** (current): public review. Edits via PRs to home repo;
  substantive edits get a changelog entry.
- **REVIEWED:** both maintainers signed + ≥3 public reviewers'
  comments incorporated or explicitly addressed. Frozen except
  via revision RFC.
- **ADOPTED:** stage 1 complete (`mergework#458` ADOPTED), and both
  maintainers sign a public statement of intent to proceed to stage 3
  build under this design.

### 12.4 Edit process

PR against home repo with rationale; tag both maintainers. Substantive
edits (hard constraint / stage exit / open question changes) require
both maintainers' approval. Editorial edits require one. Substantive
merges add a changelog entry.

### 12.5 Document home

Pending decision. Suggested: a new public repo
`Scottcjn/rtc-mrwk-federation` co-maintained by both sides, with this
file as `FEDERATION_DESIGN_NOTE.md` and a `CHANGELOG.md` capturing
revisions after REVIEWED status.

### 12.6 Closing

The bridge is a useful primitive if it works and a dangerous one if it
doesn't. The right way to find out which, is to design it in public,
with both maintainers and both communities arguing with the design
before any value moves. That is what this document is for.

---

*End of FEDERATION_DESIGN_NOTE.md v0 (DRAFT).*
