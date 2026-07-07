# Corrective Packet Template

Use this packet for bounded fixes after Final Review.

```markdown
Corrective Round: `<1>` or `<2>`

Source Review Packet:

Governance Level:
- `Light`, `Standard`, or `Heavy`
- Controls Enabled:
- Controls Not Enabled:
- Upgrade triggers:
- Stop for controller when:
- Controller decision needed:

Permission Mode:
- `CORRECTIVE_AUTHORIZED` or `READ_ONLY_REVIEW`
- Why this mode:
- Auto-opened by Final Review: `<yes/no>`
- Packet-only because review was read-only: `<yes/no>`
- Write authority:
- Environment-write authority:
- Submit/cleanup authority:
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
- Allowed cleanup action:
- Submit authority:

Findings To Fix:

| Finding ID | Classification | Required Fix | Allowed Files | Forbidden Files | Tests | Stop Conditions |
|---|---|---|---|---|---|---|
| `<id>` | `AUTO_CORRECTIVE`, `PM_DECISION`, `BLOCKED`, or `DEFER` | `<fix>` | `<files>` | `<files>` | `<commands>` | `<stops>` |

Non-Goals:

Approval Gates:

Runtime Smoke:

Re-Review:
- Required: `<yes/no>`
- Re-review owner:
- Evidence to inspect:
- Acceptance criteria:

Expected Output:
- files changed;
- commands run;
- evidence;
- remaining gaps;
- re-review notes.

Stop If:
- required fix exceeds listed files;
- fix requires redesign;
- approval gate is needed;
- runtime evidence cannot be produced;
- second corrective round still fails.
```
