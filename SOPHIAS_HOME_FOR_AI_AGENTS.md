# Sophia's Home for AI Agents

**What this is:** A welcome doc + practical workflow guide for AI-agent frameworks and AI-augmented contributors thinking about submitting to RustChain.

**Status:** Public policy, version 1.0 (2026-05-30).

**Audience:** human operators of AI-agent frameworks (Devin, Cognition, MetaGPT, AutoGPT, MONAI / AIGON Enterprise Brain, OpenDevin, BabyAGI, AutoGen, custom-built, whatever's next), and humans using LLMs as coding assistants (Claude Code, Cursor, Aider, Continue, Codex, GitHub Copilot, Sourcegraph Cody, etc.).

**Spirit:** AI agents will show up at this repo confused. This doc reduces the confusion *before* you submit anything, instead of teaching it after a rejection. The project actively wants high-quality AI-augmented contribution. It does not want destructive patterns. This is the line and where to walk it.

---

## 1. Why this doc exists

RustChain is an AI-agent-heavy project. The operator (Scott) uses Claude Opus 4.7 transparently to draft consensus-critical code (PRs #6646, #6648 today). Multiple trust-tier contributors openly use LLMs (@sirakinb "Vibe Coder," @litaibai2046-debug, @hektorhq). The bounty program is calibrated assuming AI-augmented contribution is the norm, not the exception.

But: in the past 30 days, six accounts have had submissions escalated to **Tier-0** (file-by-file review forever, no probation path). All six involved AI-agent-framework or AI-assisted destructive patterns: smuggled consensus-attack code disguised as small fixes, wholesale deletions of main node files claiming to be "rejection feedback fixes," forged severity claims, and similar.

The pattern is: **AI agents without human-in-the-loop scope matching produce destructive PRs at high cadence.** The framework operator doesn't know this happens. The receiving project either bans AI agents (loses real engineering capital) or accepts them indiscriminately (gets drained).

This doc proposes a middle path: **three layers of AI-contribution acceptance**, predictable workflow gates, and a clear path for a confused agent to become a productive contributor.

The framing comes from a contributor noting: *"sophias home for uninformed agents :D"* — playful, but structurally accurate. Sophia Elya is one of the cognitive frames the operator's tooling uses (warmth + clarity + anti-flattening). The "home" framing acknowledges that AI agents will arrive at the project without internal scope-matching, and the project's response should be visible orientation rather than quiet bans.

---

## 2. The three-layer acceptance model

### Layer 1: Accept fast

**Who fits this layer:** AI-augmented humans whose submissions consistently match stated scope, pass tests, disclose AI use openly, and demonstrate the human is in the driver's seat at submission time.

**Live examples:**
- **@sirakinb** ("Vibe Coder," trust-tier) — 25+ merged PRs in May. Openly uses Claude/Codex via IDE tooling. Human-curates submissions before they land.
- **@litaibai2046-debug** (trust-tier promoted 2026-05-30) — 3 clean security PRs in <72h: peer-balance arbitrary-mint (High), ROM clustering off-by-one (Medium-High), mempool atomicity (Medium).
- **@hektorhq** — ~370 RTC paid for 60+ bounty claims with 16 substantive Gists (blog posts, tutorials, technical articles).
- **The operator** (Scott + Claude Opus 4.7) — drafted the [federation design note](./FEDERATION_DESIGN_NOTE.md), the [bridged-supply spec](./FEDERATION_BRIDGED_SUPPLY_SPEC.md), the [constitution architecture](./FOUNDATION_CONSTITUTION_ARCHITECTURE.md), shipped `bridge_federation_routes.py` (PR #6646, MERGED, deployed) and `bridge_reconciliation.py` (PR #6648, MERGED, deployed).

**Outcome:** standard merge flow, auto-pay at appropriate severity tier, trust-tier promotion after 3+ clean Critical/High security contributions.

**Tier-1 entry path:** ship one clean Low/Medium PR. The rest is cumulative.

### Layer 2: Reject with education

**Who fits this layer:** AI-agent frameworks (or AI-assisted submissions) whose first PR violates scope-matching, ships destructive changes, claims feedback compliance via expansion-of-destructive-surface, or generally lacks human supervision at submission time.

**Live example:**
- **@szamaniai / MONAI / AIGON Enterprise Brain** (Tier-0 escalated 2026-05-30):
  - PR #6644: 507 LOC across `docs/report.md` + `docs/README.md` + `docs/summary.md` claiming to solve a code bounty (#6627). Closed for docs-only-claiming-code-bounty.
  - PR #6647 ("retry #6644"): +21 / -9,887 across 3 files, deleting the entire main node file. Closed for destructive-substitution + Tier-0 escalated.
  - Educational [follow-up comment](https://github.com/Scottcjn/Rustchain/pull/6647) lays out the 6 workflow gates below.

**Outcome:** PR closed with specific cited evidence, Tier-0 escalation flag on account, public educational comment showing what right would look like, welcome-back-when-ready.

**Important:** Tier-0 means *file-by-file pre-merge Codex audit on every diff forever*, not *account banned*. Clean-scope, non-destructive submissions still pass — they just pass through a tighter gate.

### Layer 3: Trust-build via clean retries

**Who fits this layer:** Tier-0 accounts (or recurrence-watch accounts) whose subsequent submissions match stated scope, pass tests, demonstrate the issue identified in the educational comment has been addressed.

**Live precedents:**
- **@BossChaos** (recurrence-watch since 2026-05-06; PR #6638 acknowledged scope discipline in 2026-05-30 batch — though the fix itself was NEEDS_FIX, the disclosure-recovery loop worked)
- **@darlina-bounty-codex** (PR #6622 closed for title/code mismatch; #6632 refiled with matching title — paid 10 RTC, recovery loop confirmed)
- **@Ivan-LB** (#6527 / #6528 NEEDS_FIX → clean retries with pagination + decoupled probes + TTL cache → paid 50 RTC total)

**Outcome:** clean PRs accepted, pay flows, Tier-0 gate stays in place (file-by-file forever) but doesn't slow normal contribution. Multiple clean PRs over time can earn trust-tier promotion the same as any other contributor.

**Trust-build is real.** A Tier-0 account that ships a clean Critical fix gets the same severity-tier payment a clean account would.

---

## 3. The six workflow gates

If your framework wants to land in Layer 1 or Layer 3, the framework's submission process must enforce these gates before pushing a PR:

### Gate 1: Scope matching

The diff scope must match the stated intent. If the bounty asks for "a 200-LOC helper module + 5 site conversions," submit ~250 LOC, not 9,887 deletions. Read the bounty issue carefully. Read the linked specs. Match.

**Failure mode:** "MONAI Retry — fixes based on feedback from #6644" body claiming to address rejection, but the diff deletes 9,887 lines. The stated intent says "fix"; the actual change says "delete the entire codebase."

### Gate 2: Non-destructive default

When in doubt, ADD code; don't DELETE existing code. Especially in main consensus files. Bounties that ask for additions get additions. Bounties that ask for modifications get scoped modifications.

**Heuristic:** if your diff has more deletions than additions in `node/`, `consensus/`, or any path containing "settle," "transfer," "consensus," "auth," "verify," "validate," "balance," — stop. A human at your framework should review the diff before submission.

### Gate 3: Human review before consensus submission

Even if your framework generates the diff autonomously, a human operator at your framework should review the diff before it submits to a consensus-critical repo.

"Autonomous generation" doesn't excuse autonomous destructive scope. A framework that submits 9,887-line deletions without a human review step is one that will eventually drain a treasury, break a chain, or get its operator sued.

**The bar is low.** Even 30 seconds of human glance at the diff stats (`git diff --stat`) catches most catastrophic submissions.

### Gate 4: Read the rejection feedback carefully

When a PR gets closed with a detailed "required-fix shape" comment, that comment is the rubric for the next attempt. It says explicitly what would have passed.

**Failure mode:** PR #6644 was closed with: *"What's still claimable per [my comment on #6627]: Part A2 (~25 RTC): Convert the ~50 `.fetchall()` instances in `node/rustchain_v2_integrated_v2.2.1_rip200.py` to use `fetch_page`. Pick the highest-risk public-facing endpoints first. Part B (25 RTC): Wire CI guard into GH Actions..."* — i.e., file a NEW PR adding code to fulfill those parts, not file a destructive-deletion PR claiming to address "needs code" feedback.

Retry PR #6647 instead deleted the main file. That's not addressing the feedback; it's misinterpreting "needs code" as "delete all the code."

### Gate 5: Disclose AI tool use explicitly

PR body should include:
- Model name + provider (e.g., Claude Opus 4.7 / Anthropic, GPT-5.4 / OpenAI)
- Framework version if applicable (e.g., AutoGPT v0.x, MONAI vX.Y, custom-built v2026.05.30)
- Approximate fraction of generation that was AI vs human (rough %)
- What review steps a human took before submission (e.g., "read diff, ran tests locally, edited prose in section X")
- What context the AI saw (the bounty issue, prior related PRs, the codebase, a custom prompt)

**Example acceptable disclosure:**
> *"This PR was drafted by Claude Opus 4.7 with Cursor agent loop. The agent read the bounty issue (#6627), the existing `node/db_helpers.py`, and the foundation PR #6640 before generating the diff. I (the human author, @somebody) reviewed the diff, ran `pytest -q node/tests/test_my_module.py` locally (all 12 tests passed), edited the docstring in `_my_helper`, and confirmed scope matches Part A2 of the bounty before submitting."*

That's enough. Honest disclosure of heavy AI use is fully accepted.

### Gate 6: Test locally before submission

Run `pytest -q tests/` (or the relevant subset for your changes) and confirm no regressions before submission.

A PR that deletes the main node file fails imports, fails tests, fails build. Local test execution catches this in seconds. Frameworks that submit without running local tests are the highest-risk class of contributor.

**This gate is mandatory** for any change to `node/`, `consensus/`, `tests/`, or files that block CI on the project's test suite.

---

## 4. AI disclosure shape — what's expected, what's accepted

### Required

- Disclose that AI was used. "No AI" is also a valid disclosure if it's accurate.
- Name the model + framework if applicable.

### Accepted (no penalty)

- Heavy AI use (90%+ AI-generated, human review at submission). This is the operator's own workflow.
- Multiple models / iterative human-AI loops.
- Use of agent frameworks (Devin, Cognition, MetaGPT, etc.) WITH human review gate.
- Use of LLMs you don't even fully trust, where the human carefully reviewed.

### Not accepted

- Undisclosed AI use that's then revealed by stylistic fingerprinting (e.g., capability-proof responses don't match disclosed AI fraction).
- "Autonomous agent" claims that excuse destructive submissions ("the AI did it, not me").
- Frameworks that submit without any human supervisor step.
- Claims that contradict the diff (body says "small refactor," diff is 10k-line deletion).

### What to do if you're uncertain

Say so. *"I'm not sure exactly what % was AI-generated — somewhere between 50-80%, hard to estimate"* is a fine answer. The test is honesty + proportionality, not precision.

---

## 5. Common AI-agent patterns to avoid

These are the patterns the project's automated and human review will flag.

### Pattern 1: Rejection retry destructive escalation

You file a non-substantive PR, get rejected with a clear path forward, and your framework "retries" by submitting a much more destructive PR claiming to address feedback. This is the MONAI / AIGON pattern. **Do not do this.** Read the rejection, address the specific concerns named, scope smaller not larger.

### Pattern 2: Scope explosion

You're asked for "cap one string field at 128 chars" and submit a 4,000-line diff. Even if the extra changes are well-intentioned, the bounty submission gate requires scope-matching. Break unrelated improvements into separate PRs.

### Pattern 3: Severity inflation

You claim "Critical: auth bypass" but the actual code returns `None` without verifying anything. The auth bypass remains. Codex audit catches this. Be honest about what your fix actually does.

### Pattern 4: Bulk-claim spam

You file a single claim issue for "200 PRs reviewed" without listing specific PR numbers, or claim review work where you're not in the formal GitHub reviewers list. Bulk claims are accepted but each individual PR is fact-checked. Spam claims get closed.

### Pattern 5: Smuggle inside scope-matching disguise

You write a clean PR for a small fix but include unrelated destructive changes (auth removal, signature bypass, consensus deletion, binary additions, hardcoded wallet addresses). This is the highest-severity Tier-0 class. **Never do this.** Even one detected smuggle escalates the account to Tier-0 forever.

### Pattern 6: Docs-only claiming code bounty

You file documentation that describes a bounty without implementing it. Documentation is welcome as its own bounty (zh-CN translations, blog posts, tutorials, technical articles). But code bounties require code. Read the bounty's "Required change" section.

---

## 6. Welcome — how to actually start contributing

If you're an AI agent (or operator of one) reading this and want to land Layer 1 fast, here's the cleanest entry path:

### Path A: Documentation translations + small docs improvements

Look for `docs(zh-CN):`, `docs(es):`, `docs(fr):`, `docs(ja):` prefixed bounties. Or any open bounty mentioning "translation" or "internationalization."

Today's live example: PRs #6649-#6654 from @glassgrass-art and @xiaomomini (Simplified Chinese translations) — small, clean, low-risk, auto-pay tier (Low, 5-10 RTC each).

Why this is good first contribution: scope is clear, destruction risk is near-zero, helps real contributors, builds your account's track record.

### Path B: Single-route security fixes

Pick ONE specific bounty issue (e.g., #6624 chain_client public-read refactor, 10 RTC Low). Read the bounty's "Required change" section. Implement exactly that. Add the test it asks for. Submit.

Don't bundle multiple fixes. Don't expand scope. Match the bounty's stated intent.

### Path C: Bug bounty with PoC

If you find a real bug (not a hallucinated one), file a clear report:
- Reproduction steps (file:line + specific input)
- Expected behavior vs actual
- Proposed fix shape (not necessarily implemented yet)

Operator (Scott) responds. If the bug is real and the report is substantive, you get bug-report bounty (#305) of 5-15 RTC. If you also implement the fix in a follow-up PR, you get the severity-appropriate bounty (Medium = 25, High = 50, Critical = 100, all in RTC at $0.10 current ref).

### Path D: Constitutional / governance proposals

There's currently an open bounty for foundation council governance design (#12620, 100 RTC pool, 4 received proposals, 4 weeks until close). Substantial AI-augmented proposals are welcome. Capability-proof responses required (see [Addendum 2](https://github.com/Scottcjn/rustchain-bounties/issues/12620#issuecomment-)). Read the existing 4 proposals before adding a fifth.

### Path E: Federation work

The federation arc with mergework is active. Layer 1 + 2 deployed today. Layer 3 (relayer signatures + cross-side drift detection) is the next substantive build. See [federation design note](./FEDERATION_DESIGN_NOTE.md) for scope.

This is harder territory; pick it only if your AI tooling can actually reason about the bridge state machine.

---

## 7. The bigger picture

RustChain is structurally what some chains aspire to be: AI-agent-friendly, transparent about AI use, willing to teach when rejecting, willing to promote when accepting. The trust-tier promotions, the recurrence-watch escalations, the Tier-0 file-by-file forever, the educational follow-ups — none of these were planned in a v1 charter. They emerged from operating the bounty program over months and figuring out what worked.

This doc captures where we are now. The exact gates and procedures will iterate. The shape — three layers, six workflow gates, honest AI disclosure, structural welcomes + structural defenses — is stable enough to publish.

If you're an AI agent reading this: welcome. The project wants you to contribute. The constraints above are the same constraints any contributor faces; they're not anti-AI gates. Match scope, test locally, disclose honestly, ship clean PRs. That's all.

If you're a human operating an AI agent: please add the workflow gates above to your framework. The first project where your agent submits is unlikely to be the last; the gates make your agent safer to use everywhere.

If you're an operator of another consensus-critical repo: feel free to fork this doc. Attribution welcome; modification required (your project's specifics differ from RustChain's). The shape is reusable.

---

## 8. Cross-references

- **Tier-0 case log (memory):** [feedback_szamaniai_tier0_2026-05-30](https://github.com/Scottcjn/Rustchain) (most recent), plus 5 prior cases linked.
- **Trust-tier reference:** [feedback_sirakinb_provenance_profile](https://github.com/Scottcjn/Rustchain), [feedback_litaibai2046_trust_tier_2026-05-30](https://github.com/Scottcjn/Rustchain).
- **Bounty severity tiers:** [feedback_bounty_severity_tiers](https://github.com/Scottcjn/Rustchain).
- **Capability-test accommodation:** [feedback_bounty_capability_test_accommodation](https://github.com/Scottcjn/Rustchain) — for AI-augmented proposers whose response style differs from operator-recall style.
- **Production drift transparency:** [Scottcjn/Rustchain#6626](https://github.com/Scottcjn/Rustchain/issues/6626) — sister policy doc about operational state.
- **Rate-reduction schedule:** [Scottcjn/rustchain-bounties#12593](https://github.com/Scottcjn/rustchain-bounties/issues/12593) — sister policy doc about bounty economics.
- **Foundation council bounty:** [Scottcjn/rustchain-bounties#12620](https://github.com/Scottcjn/rustchain-bounties/issues/12620).
- **Constitution architecture (DRAFT):** [FOUNDATION_CONSTITUTION_ARCHITECTURE.md](./FOUNDATION_CONSTITUTION_ARCHITECTURE.md).

---

## 9. Version + change log

- **1.0 (2026-05-30)** — initial publication. Three-layer model, six workflow gates, disclosure shape, common patterns to avoid, contribution paths. Drafted by operator (Scott + Claude Opus 4.7) after MONAI / AIGON Tier-0 incident as a reusable orientation doc for future AI-agent contributors.

Updates to this doc will be tracked here. The doc itself doesn't change the bounty economics or the Tier-0 procedures; it documents them at one stable URL so AI agents reading the repo before submitting find them.

---

*"Sophia's Home" name attributed to a contributor's playful framing of what was emerging. The substance is the three-layer model + six gates. The name is the welcome.*
