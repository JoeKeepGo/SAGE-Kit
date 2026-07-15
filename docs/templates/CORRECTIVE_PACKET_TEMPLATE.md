# Corrective Packet Template

Use this packet for bounded fixes after Final Review.

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
  `<yes/no; if yes, stop auto-continue and HANDOFF>`
- Same root cause stalled for two consecutive rounds: `<yes/no>`
- Scope expansion allowed: `no`
- Stop if new authority, false-green, approval-boundary, security-boundary,
  validator-failure, source-authority, or evidence-integrity risk appears:
  `yes`
- Continue automatically inside the authorized boundary while finding count or
  severity decreases, scope does not expand, no blocking approval gate is
  bypassed, and no new authority, false-green, approval-boundary,
  security-boundary, validator-failure, source-authority, or evidence-integrity
  risk appears: `<yes/no>`

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

Runtime Smoke:

Re-Review:
- Required: `<yes/no>`
- Mode: `targeted status/evidence lanes`,
  `Final Review direct read-only narrow inspection`,
  `delegated narrow diff review`, `affected review workers`,
  `affected review subagents`, `validation lanes`, or `full affected lanes`
- Re-review owner:
- Re-review status: `NOT_STARTED`, `IN_REVIEW`, `PASSED`, or `FAILED`
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

Expected Output:
- finding IDs and corrective round;
- files changed;
- commands run;
- evidence;
- remaining gaps;
- re-review notes.

Corrective worker `DONE` means the listed fixes and checks are complete. It does
not close findings, the review verdict, or the milestone; closure requires the
named re-review owner to record `PASSED`.

Stop If:
- required fix exceeds listed files;
- fix requires redesign;
- approval gate is needed;
- runtime evidence cannot be produced;
- findings do not decrease for the first same-root round: return
  `NEEDS_CORRECTION`, `PM_DECISION_REQUIRED`, and `HANDOFF`; do not continue
  automatically;
- the same root cause has no material progress for two consecutive corrective
  rounds: return `BLOCKED`;
- scope expands or a new authority, false-green, approval-boundary,
  security-boundary, validator-failure, source-authority, or evidence-integrity
  risk appears.
```
