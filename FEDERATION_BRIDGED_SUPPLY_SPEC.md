# Federation Bridged-Supply Counter Spec (Layer 2 follow-up)

**Status:** DRAFT (companion to FEDERATION_DESIGN_NOTE.md §3.2)
**Date:** 2026-05-30
**Depends on:** Layer 1 public read APIs (`/bridge/state`, `/bridge/events`, `/bridge/transfers/recent`) — already shipped at [Rustchain PR #TBD](https://github.com/Scottcjn/Rustchain/pulls)

---

## 1. Why this is a separate doc

The federation design note §3.2 asserts the invariant:

> At any point in time, (RTC locked in custody on RustChain side) MUST equal (MRWK in circulation that was mirrored from RTC), and vice versa.

The Layer 1 routes shipped today expose **per-side state**: how much RTC sits in each status bucket on the RustChain side. They do **not** yet expose the cross-side **bridged-supply counter** that the invariant requires.

This spec defines:
- What the bridged-supply counter actually is
- How it's computed
- How both sides expose it
- What "drift" means and how it triggers automatic pause

## 2. The two counter values

Each side publishes two paired numbers:

| Field | RustChain side meaning | MergeWork side meaning |
|---|---|---|
| `locked_here_rtc` | Sum of RTC in `pending` + `locked` + `confirming` + `completed` direction=deposit on this side (RTC waiting to be mirrored as MRWK) | N/A |
| `mirrored_there_mrwk` | Sum of MRWK issued from RustChain-bridged deposits | Sum of MRWK in circulation that came from a RustChain lock |
| `locked_here_mrwk` | N/A | Sum of MRWK in `bridge_lock` status on MergeWork (MRWK waiting to be mirrored as RTC) |
| `mirrored_there_rtc` | Sum of RTC released from custody to fulfill MergeWork-side locks | Sum of RTC paid out for MRWK burns |

The invariant in cross-side form:

```
RustChain.locked_here_rtc == MergeWork.mirrored_there_mrwk * rate
MergeWork.locked_here_mrwk == RustChain.mirrored_there_rtc * (1/rate)
```

At 1:1 rate (v1), the multipliers are 1.0. The counters should match byte-for-byte if accounting is correct.

## 3. How RustChain computes it

Already shipped in `bridge_federation_routes.py:_aggregate_bridge_state()`:

- `locked_in_rtc` = sum(amount_rtc) WHERE status IN (`pending`, `locked`, `confirming`) AND direction = `deposit`
- `completed_in_rtc` = sum(amount_rtc) WHERE status = `completed`

For Layer 2, we need to additionally publish:

- `mirrored_there_mrwk_estimate` = sum(amount_rtc * rate) WHERE direction = `deposit` AND status IN (`completed`)
- `bridged_supply_committed` = `locked_in_rtc` + `completed_in_rtc` − `voided_in_rtc`

`bridged_supply_committed` is the headline counter both sides display publicly. It represents *the total RTC that has been bridge-committed, net of voids, regardless of where it currently sits in the state machine*. This is the conservation quantity that must match across sides.

## 4. How MergeWork mirrors it

(Spec, NOT implementation — MergeWork side is ramimbo's call.)

MergeWork ledger exposes:

- `locked_here_mrwk` = sum of MRWK currently in the bridge-lock status
- `mirrored_there_mrwk` = sum of MRWK that exists in circulation BECAUSE of a RustChain lock (vs MRWK issued via mergework's normal `mrwk:accepted` label path)

The second number is the load-bearing one for federation: it answers *"how much MRWK is currently in circulation that depends on an unrevoked RustChain lock?"*

## 5. Reconciliation cadence

**Per-epoch snapshot** (RustChain epoch = 144 blocks ≈ 24 hours):

1. At each epoch boundary, RustChain side computes the full state aggregate and writes a row to a new `bridge_reconciliation_snapshots` table:

   ```sql
   CREATE TABLE bridge_reconciliation_snapshots (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       epoch INTEGER NOT NULL UNIQUE,
       computed_at INTEGER NOT NULL,
       locked_in_rtc REAL NOT NULL,
       completed_in_rtc REAL NOT NULL,
       voided_in_rtc REAL NOT NULL,
       bridged_supply_committed REAL NOT NULL,
       state_hash TEXT NOT NULL,  -- sha256 of canonical JSON of full by_status + by_direction maps
       relayer_signatures TEXT      -- JSON array of relayer signatures (added in Layer 3)
   );
   ```

2. MergeWork side does the same on its epoch (or some agreed cadence).

3. The new public route `GET /bridge/reconciliation/latest` returns the most recent snapshot row. (Stub now, populated when snapshot mechanic ships.)

4. A pause condition fires automatically if:

   - RustChain side observes that the MergeWork side's `mirrored_there_mrwk` deviates from RustChain's `bridged_supply_committed * rate` by more than a **tolerance** (proposed: 0.01% OR 10 RTC equivalent, whichever is larger).
   - Same check on MergeWork side.

   Pause = freeze new bridge initiations on both sides until manual operator review reconciles the drift.

## 6. What Layer 2 ships (concretely)

This spec lands as a tracking doc only today. The implementation work (Layer 2 build):

1. **Add `bridge_reconciliation_snapshots` schema** to `bridge_api.init_bridge_schema()`.
2. **Add `record_reconciliation_snapshot(conn, epoch)` function** to `bridge_federation_routes.py` (or a new `bridge_reconciliation.py`).
3. **Wire it into the epoch-settler hook**: when epoch closes, snapshot fires.
4. **Add `GET /bridge/reconciliation/latest` and `GET /bridge/reconciliation/by_epoch/<n>` routes** (public read-only, same pattern as Layer 1).
5. **Add `_check_drift_against_external(other_side_url)` function** with config gate (off by default) for future automated drift checks.
6. **Tests.**

Estimated scope: ~400-600 LOC + tests. Target ship: within 2 weeks of MergeWork-side counter parity agreement.

## 7. What's left to Layer 3

- Relayer-set signatures on snapshot rows (multi-party signing)
- Cross-side drift checker actually running (`_check_drift_against_external` enabled)
- Auto-pause on drift detection (mutation surface, NOT in Layer 1/2)
- Recovery protocol from a paused state

These all require ramimbo's sign-off on the snapshot row format + signing protocol. Hold until federation note reaches REVIEWED status.

## 8. Open questions for joint review (in addition to FEDERATION_DESIGN_NOTE §10)

1. **Snapshot cadence: per-epoch or shorter?** RustChain epoch is ~24h. If we want faster drift detection, snapshot every 4 hours OR at every state transition (more expensive but more responsive).
2. **Tolerance band**: 0.01% / 10 RTC is a guess. Real value depends on rate slippage during cross-side latency and ramimbo's accounting precision.
3. **Drift recovery process**: what happens after pause? Manual reconciliation, signed delta correction, audit log, etc. Needs design.
4. **Reorg handling**: if RustChain side reorgs and a recently-committed deposit gets reverted, the bridged_supply_committed counter changes after-the-fact. How does the snapshot mechanic handle this? Proposed: snapshots are only created at epoch finality (epoch N is final at epoch N+2 boundary, etc.). Needs ramimbo's input on whether MergeWork side has analogous finality.

## 9. Source

Federation design note §3.2 invariant + §6.3-6.4 reconciliation cadence + Codex code-state audit §5 (missing public reconciliation surfaces).

This doc filed 2026-05-30 as Layer 2 of the federation design work. Layer 1 (public read APIs) shipped concurrently; Layer 3 (RFC iteration of design note) and Layer 4 (MCP tools sketches) follow.
