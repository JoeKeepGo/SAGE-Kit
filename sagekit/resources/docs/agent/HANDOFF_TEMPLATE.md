# Handoff Template

Use this template at phase boundaries, review boundaries, or when a session must
pause.

```markdown
Status: DONE, DONE_WITH_CONCERNS, BLOCKED, or HANDOFF

Objective:

Governance Level:

Permission Mode:

Controls Enabled:

Controls Not Enabled:

Scope Implemented:

Files Read:

Files Changed:

Contracts:

Tests Run:

Runtime Smoke:

Capability Routing:

Capabilities Used:

Capability Adapters:

Adapter Authorization / Fallback:

superpowers Skills Used:

SAGE-Kit Boundary Served:

External Capability Evidence:

Missing Capability Fallback:

External Planning Output Destination:

Wave / Lane Evidence:

Approval Gates:

Security / Data Hygiene:

Memory Maintenance:

Gate Status:

Change Control Status:

Skipped Checks:

Remaining Gaps:

Finding Map:

| Finding ID | Finding Owner | Waiver Authority | Decision / Delegation Ref | Status | Next Action |
|---|---|---|---|---|---|
| `<id>` | `<owner>` | `<authority or n/a>` | `<explicit decision/delegation ref or n/a>` | `<open/fixed/waived/deferred/blocked>` | `<action>` |

Corrective Round:

Corrective Files Changed:

Re-Review Owner:

Re-Review Status: `NOT_STARTED`, `IN_REVIEW`, `PASSED`, `FAILED`, or
`NOT_REQUIRED_DETERMINISTIC`

Deterministic Finding Closure Status: `AUTO_CLOSED_BY_PREDICATE`,
`INVALID_REVIEW_REQUIRED`, or `N/A`

Closure Receipt Owner:

Closure Receipt Ref:

Closure Receipt Destination:

Verdict Finalization Status: `PENDING_CORRECTION`,
`VERDICT_FINALIZED_FROM_RECEIPT`, or `N/A`

Blockers:

Decisions Needed:

Ledger Notes:

Next Action:
```

Use `DONE` only when no blocking gate is failed, blocked, skipped, or
unresolved. Use `DONE_WITH_CONCERNS` when work is mostly complete but requires
controller review before integration or auto-advance. Use `BLOCKED` when
required evidence, authority, environment, or dependency cannot be obtained.
Use `HANDOFF` when review, approval, or controller integration is still
required.

For corrective work, worker `DONE` means fix execution is complete; it does not
close findings or review. A separate re-review result or valid reviewer-authored
Deterministic Closure receipt from a Closure Receipt Owner separate from the
Corrective Worker may close only the predicate-named finding. Record its
re-review status as `NOT_REQUIRED_DETERMINISTIC`, not `PASSED`. The original
Final Review Controller or named review packet author may then record
`VERDICT_FINALIZED_FROM_RECEIPT` for a precommitted verdict; Project Manager
acceptance remains pending. `HANDOFF` is always nonterminal. A blocked
milestone closes only after an authorized owner records close-blocked, abandon,
or defer.
