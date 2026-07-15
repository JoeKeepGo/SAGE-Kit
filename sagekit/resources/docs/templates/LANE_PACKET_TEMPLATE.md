# Lane Packet Template

Use this template for subagent or parallel lane handoff.

```markdown
Status: DONE, DONE_WITH_CONCERNS, HANDOFF, or BLOCKED

Lane:

Role:

Objective:

Governance Level:

Permission Mode:

Controls Enabled:

Controls Not Enabled:

Upgrade Triggers:

Controller Decision Needed:

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

Allowed Files:

Forbidden Files:

Files Read:

Files Changed:

Commands Requested:

Commands Run:

Failed Commands:

Capabilities Used:

Capability Adapters:

Adapter Authorization / Fallback:

superpowers Skills Used:

SAGE-Kit Boundary Served:

External Capability Evidence:

Missing Capability Fallback:

External Planning Output Destination:

Evidence:

Approval Gates:

Contract Notes:

Integration Notes:

Memory Update Proposal:

Risks:

Stopped Because:

Remaining Gaps:

Next Owner:

Next Action:

Ledger Notes:
```

Status rules:

- `DONE` means the lane can be considered for controller integration.
- `DONE_WITH_CONCERNS` requires controller review and cannot auto-advance.
- `HANDOFF` is nonterminal and transfers review, approval, re-review, or
  controller-integration work. It must name both `Next Owner` and `Next Action`.
- `BLOCKED` stops the lane and must name `Stopped Because`.
- Corrective lane `DONE` means assigned fix execution is complete. A finding
  remains open until the named re-review owner records `PASSED` or the named
  Closure Receipt Owner, separate from the Corrective Worker, records a valid,
  reviewer-authored Deterministic Closure receipt. Record deterministic
  re-review as `NOT_REQUIRED_DETERMINISTIC`, never `PASSED`. The receipt closes
  only the predicate-named finding. The original Final Review Controller or
  named review packet author may then record
  `VERDICT_FINALIZED_FROM_RECEIPT` for a precommitted verdict; Project Manager
  acceptance remains pending.

Parallel lanes must not edit shared files or startup context. They return shared
patch and memory proposals; only the named controller/integration owner applies
shared-file proposals, and only the Startup Context Controller applies context
proposals.
