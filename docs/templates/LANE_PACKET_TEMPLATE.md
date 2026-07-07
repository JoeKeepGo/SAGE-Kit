# Lane Packet Template

Use this template for subagent or parallel lane handoff.

```markdown
Status: DONE | DONE_WITH_CONCERNS | BLOCKED

Lane:

Role:

Objective:

Allowed Files:

Forbidden Files:

Files Read:

Files Changed:

Commands Requested:

Commands Run:

Failed Commands:

Capabilities Used:

Evidence:

Approval Gates:

Contract Notes:

Integration Notes:

Memory Update Proposal:

Risks:

Stopped Because:

Remaining Gaps:

Ledger Notes:
```

Status rules:

- `DONE` means the lane can be considered for controller integration.
- `DONE_WITH_CONCERNS` requires controller review and cannot auto-advance.
- `BLOCKED` stops the lane and must name `Stopped Because`.

Parallel lanes must not edit shared startup context files. Return proposed
active-context or routing changes in `Memory Update Proposal`; only the serial
controller or integration lane applies them.
