# Corrective Packet Template

Use this packet for bounded fixes after Final Review.

Review/corrective authority is canonical at
`docs/agent/GOVERNANCE_LEVELS.md#sage-auth-006`. This packet retains the named
findings, worker/reviewer modes, allowed surfaces, evidence return, re-review,
and receipt-owner fields for one bounded correction.
Change classification, convergence, opt-in windows, and targeted re-review are
canonical at `docs/agent/EXECUTION_ECONOMY.md#sage-loop-001`,
`#sage-loop-008`, `#sage-loop-009`, and `#sage-loop-010`; Deterministic Closure
is canonical at `docs/agent/SESSION_ORCHESTRATION.md#sage-loop-011`.

```markdown
Corrective Round / Convergence Budget: `<round n; budget/control signal>`

Source Review Packet:

Convergence Control:
- Findings before this round:
- Findings after previous round:
- Expected finding reduction:
- Expected severity reduction:
- Material progress this round: `<finding count decreased/severity decreased/neither>`
- Authorized corrective packet or boundary: `<ref>`
- First same-root stagnant round:
  `<yes/no; record and apply canonical convergence outcome>`
- Same root cause stalled for two consecutive rounds: `<yes/no>`
- Scope expansion allowed: `no`
- Stop if new authority, false-green, approval-boundary, security-boundary,
  validator-failure, source-authority, or evidence-integrity risk appears:
  `yes`
- Continue automatically inside the authorized boundary under the canonical
  convergence decision: `<yes/no; decision ref>`
- Canonical convergence decision / evidence: `<outcome/ref>`

Governance Level:
- `Light`, `Standard`, or `Heavy`
- Controls Enabled:
- Controls Not Enabled:
- Upgrade triggers:
- Stop for controller when:
- Controller decision needed:

Permission Mode:
- Corrective worker: `CORRECTIVE_AUTHORIZED`
- Final Review Controller: `READ_ONLY_REVIEW`
- Why this mode:
- Corrective orchestration authorized for Final Review: `<yes/no>`
- Corrective worker write authority:
- Final Review write authority: `none`
- Environment-write authority:
- Submit/cleanup authority: `none`
- Permission upgrade requires:

Capability Routing:
- Required skills:
- Selected superpowers skills, if available:
- superpowers boundary, if used:
- Required plugins/connectors:
- Required tools:
- Required capability adapters:
- Adapter authorization/fallback:
- Forbidden capabilities:
- Fallback if missing:

Worktree Isolation:
- Assigned worktree:
- Branch:
- Allowed cleanup action: `none; post-verdict grant required`
- Submit authority: `none`

Findings To Fix:

| Finding ID | Classification | Finding Owner | Waiver Authority | Waiver Decision Or Delegation Ref | Required Fix | Allowed Files | Forbidden Files | Tests | Stop Conditions |
|---|---|---|---|---|---|---|---|---|---|
| `<id>` | `AUTO_CORRECTIVE` | `<owner>` | `<authority>` | `<ref or n/a>` | `<fix>` | `<files>` | `<files>` | `<commands>` | `<stops>` |

Only `AUTO_CORRECTIVE` findings may appear in `Findings To Fix`.

Not Fixable / PM Decision / Blocked / Deferred:

| Finding ID | Classification | Finding Owner | Waiver Authority | Decision Or Delegation Ref | Reason Not In Fix Queue | Required Record Or Next Action |
|---|---|---|---|---|---|---|
| `<id>` | `PM_DECISION`, `BLOCKED`, or `DEFER` | `<owner>` | `<authority or n/a>` | `<explicit decision/delegation ref or n/a>` | `<scope/authority/evidence/dependency/defer reason>` | `<decision request/blocker/follow-up>` |

Non-Goals:

Approval Gates:

Preauthorized Convergence Window (optional; omit or mark inactive unless
explicitly approved):
- Active: `<yes/no>`
- Authority ID:
- Execution scope / PR / branch unit:
- Root-cause family:
- Allowed paths:
- Approved invariant:
- Semantic change policy: `implementation-preserving-only`
- Targeted review required: `<yes/no>`
- Targeted review closed: `<yes/no>`
- Stop conditions:
- Approved by role:
- Authority reference:
- Authority digest:
- Current root-cause ID:
- Finding count and severity:
- Finding trend: `initial`, `finding-count-decreased`, `severity-decreased`,
  `next-layer-exposed`, or `no-progress`
- Consecutive no-progress rounds:

Apply the window authority at
`docs/agent/EXECUTION_ECONOMY.md#sage-loop-009`. The fields above record its
explicit opt-in authority and do not activate or expand it.

Runtime Smoke:

Re-Review:

Apply `docs/agent/EXECUTION_ECONOMY.md#sage-loop-010`; do not repeat the initial
full review.
- Required: `<yes/no>`
- Mode: `deterministic closure`, `targeted status/evidence lanes`,
  `Final Review direct read-only narrow inspection`,
  `delegated narrow diff review`, `affected review workers`,
  `affected review subagents`, `validation lanes`, or `full affected lanes`
- Re-review owner:
- Re-review status: `NOT_STARTED`, `IN_REVIEW`, `PASSED`, `FAILED`, or `NOT_REQUIRED_DETERMINISTIC`
- Deterministic rule: use `NOT_REQUIRED_DETERMINISTIC`; never record deterministic closure as `PASSED` re-review
- Affected review workers/subagents/lanes to rerun:
- Skip rerun rationale, if using narrow diff review:
- Targeted review allowed because only ledger, evidence, status, closeout, or
  packet bookkeeping changed: `<yes/no>`
- Full review required because semantics, permission, source authority,
  information architecture, public contract, runtime, security, approval gate,
  validator meaning, or required evidence changed: `<yes/no>`
- Evidence to inspect:
- Acceptance criteria:
- Closure blocked if re-review evidence is missing: `<yes/no>`

Deterministic Closure (only when Re-Review Required is `no`):

Apply `docs/agent/SESSION_ORCHESTRATION.md#sage-loop-011`; the fields below are
predicate and receipt inputs, not an independent review verdict.
- Finding classification: `AUTO_CORRECTIVE`
- Closure eligibility class: `MECHANICAL_STATUS`
- Reviewer-authored predicate ref:
- Finding ID:
- Exact allowed files and fields:
- Authoritative value and source ref:
- Allowed diff:
- Closure commands:
- Out-of-scope protected hashes:
- Substantive evidence and authoritative value already reviewed: `<yes/no>`
- Mirrors an existing decision; creates no gate/approval decision: `<yes/no>`
- Exact predicate match: `<yes/no>`
- Closure commands passed: `<yes/no>`
- Out-of-scope protected hashes unchanged: `<yes/no>`
- State Truth Reconciliation passed: `<yes/no>`
- Extra or ambiguous diff found: `<yes/no>`

Corrective Worker Evidence Return:
- finding IDs and corrective round;
- files changed;
- commands run;
- evidence;
- remaining gaps;
- re-review notes.

The Corrective Worker stops after evidence return and must not fill or record receipt or verdict-finalization fields.

Receipt Owner Follow-Up (outside Corrective Worker authority):
- Closure receipt status: `PENDING_RECEIPT` (default before owner follow-up), `AUTO_CLOSED_BY_PREDICATE`, or `INVALID_REVIEW_REQUIRED`
- Closure Receipt Owner: `<original Final Review Controller or named review packet author; must differ from Corrective Worker>`
- Closure Receipt Ref: `<pending until owner follow-up>`
- Closure Receipt Destination: `<receipt owner's review packet/output>`
- Verdict finalization status: `PENDING_CORRECTION`, `VERDICT_FINALIZED_FROM_RECEIPT`, or `INVALID_REVIEW_REQUIRED`
- Finalized verdict: `ACCEPTABLE`, `ACCEPTABLE_WITH_CONCERNS`, or `N/A`
- PM acceptance pending: `yes`

Corrective worker `DONE` closes nothing. The named re-review owner records
`PASSED`, or the separate Closure Receipt Owner performs the strict follow-up
under `docs/agent/SESSION_ORCHESTRATION.md`.

Stop If:
- required fix exceeds listed files;
- fix requires redesign;
- approval gate is needed;
- runtime evidence cannot be produced;
- the canonical candidate/convergence decision at
  `docs/agent/EXECUTION_ECONOMY.md#sage-loop-008` or `#sage-loop-009` requires
  `HANDOFF_READY` or `BLOCKED`; record the outcome and evidence reference;
- scope expands or a new authority, false-green, approval-boundary,
  security-boundary, validator-failure, source-authority, or evidence-integrity
  risk appears.
```
