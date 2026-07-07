# Corrective Packet Template

Use this packet for bounded fixes after Final Review.

```markdown
Corrective Round: `<1 | 2>`

Source Review Packet:

Capability Routing:
- Required skills:
- Required plugins/connectors:
- Required tools:
- Forbidden capabilities:
- Fallback if missing:

Worktree Isolation:
- Assigned worktree:
- Branch:
- Allowed cleanup action:
- Submit authority:

Findings To Fix:

| Finding ID | Required Fix | Allowed Files | Forbidden Files | Tests | Stop Conditions |
|---|---|---|---|---|---|
| `<id>` | `<fix>` | `<files>` | `<files>` | `<commands>` | `<stops>` |

Non-Goals:

Approval Gates:

Runtime Smoke:

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
