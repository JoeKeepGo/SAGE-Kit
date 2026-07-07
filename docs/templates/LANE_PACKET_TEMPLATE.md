# Lane Packet Template

Use this template for subagent or parallel lane handoff.

```markdown
Status: DONE, DONE_WITH_CONCERNS, or BLOCKED

Lane:

Role:

Objective:

Governance Level:

Permission Mode:

Controls Enabled:

Controls Not Enabled:

Upgrade Triggers:

Controller Decision Needed:

Corrective Closure:

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

Ledger Notes:
```

Status rules:

- `DONE` means the lane can be considered for controller integration.
- `DONE_WITH_CONCERNS` requires controller review and cannot auto-advance.
- `BLOCKED` stops the lane and must name `Stopped Because`.

Parallel lanes must not edit shared startup context files. Return proposed
active-context or routing changes in `Memory Update Proposal`; only the serial
controller or integration lane applies them.
