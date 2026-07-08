# Corrective Packet Template

Use this packet for bounded fixes after Final Review.

```markdown
Corrective Round: `<n>` of `<configured maximum>`

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
| `<id>` | `AUTO_CORRECTIVE` | `<fix>` | `<files>` | `<files>` | `<commands>` | `<stops>` |

Only `AUTO_CORRECTIVE` findings may appear in `Findings To Fix`.

Not Fixable / PM Decision / Blocked / Deferred:

| Finding ID | Classification | Required Owner | Reason Not In Fix Queue | Required Record Or Next Action |
|---|---|---|---|---|
| `<id>` | `PM_DECISION`, `BLOCKED`, or `DEFER` | `<Project Manager/blocker owner/follow-up owner>` | `<scope/authority/evidence/dependency/defer reason>` | `<decision request/blocker/follow-up>` |

Non-Goals:

Approval Gates:

Runtime Smoke:

Re-Review:
- Required: `<yes/no>`
- Mode: `Final Review narrow diff`, `affected review workers`, `affected review subagents`, or `validation lanes`
- Re-review owner:
- Affected review workers/subagents/lanes to rerun:
- Skip rerun rationale, if using narrow diff review:
- Evidence to inspect:
- Acceptance criteria:
- Closure blocked if re-review evidence is missing: `<yes/no>`

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
- corrective round `<n>` reaches the configured maximum and findings still fail.
```
