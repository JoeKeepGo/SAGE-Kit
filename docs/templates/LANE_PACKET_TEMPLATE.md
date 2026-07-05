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

Evidence:

Approval Gates:

Contract Notes:

Integration Notes:

Risks:

Stopped Because:

Remaining Gaps:

Ledger Notes:
```

Status rules:

- `DONE` means the lane can be considered for controller integration.
- `DONE_WITH_CONCERNS` requires controller review and cannot auto-advance.
- `BLOCKED` stops the lane and must name `Stopped Because`.
