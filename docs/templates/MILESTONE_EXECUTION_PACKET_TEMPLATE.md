# Milestone Execution Packet Template

Use this packet from Project Manager Controller to Coder Controller.

```markdown
Milestone:

Objective:

Primary Capability:

Source Docs:
- Active context:
- Document routing:
- Entry gate:
- Milestone ledger:
- Capability map:
- Phase docs:
- Quality gates:
- Approval gates:

Execution Mode:
- `Phase Execution`, `Wave Execution`, or `Session Orchestration`

Governance:
- Controller level: `Light`, `Standard`, or `Heavy`
- Why this level:
- Controls Enabled:
- Controls Not Enabled:

Execution Shape:
- `SERIAL`, `PARALLEL_WITH_WAVES`, `PARALLEL_PHASES`, or `STOP_FOR_PM`

Parallelism Rationale:

Worktree Isolation Policy:
- Allowed mode: `NONE`, `MILESTONE_WORKTREE`, `PHASE_WORKTREE`, `LANE_WORKTREE`, or `REVIEW_WORKTREE`
- Maximum worktree count:
- Branch naming:
- Worktree naming:
- Base branch or commit:
- Allowed phases or lanes:
- Shared files that remain serial:
- Runtime ownership:
- Integration owner:
- Submit authority:
- Cleanup policy:
- Forbidden scenarios:

Task Dispatch Policy:
- Active: `<yes/no>`
- Dispatch board:
- Task record root:
- Evidence record root:
- Required L0-L4 levels:
- Resource lock policy:
- Run/Attempt/Lease policy:
- Validator command:
- Validator required before: `<task gate/phase gate/milestone gate/n/a>`
- Task/evidence update owner:

Capability Discovery:
- Capability registry checked: `<yes/no/not available>`
- SPEC-Kit boundary: `<scope/files/gates/locks/evidence controlled by this packet>`
- Selected skills:
- Selected superpowers skills:
- superpowers boundary:
- Selected plugins/connectors:
- Selected tools:
- Forbidden capabilities:
- Worker must check own capability list: `<yes/no>`
- Fallback if capability is missing:
- External planning output destination:
- External capability completion counts as: `execution evidence only`

Allowed Scope:

Non-Goals:

Phase Plan:

| Phase | Governance Level | Objective | Owner | Contract | Allowed Files | Read-Only Files | Forbidden Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|---|---|---|
| `<phase>` | `Light, Standard, or Heavy` | `<objective>` | `<owner>` | `<contract or none>` | `<files>` | `<files>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |

Worker Governance:

| Worker Or Lane | Scope | Governance Level | Controls Enabled | Controls Not Enabled | Upgrade Triggers | Stop For Controller |
|---|---|---|---|---|---|---|
| `<worker>` | `<scope>` | `Light, Standard, or Heavy` | `<controls>` | `<controls or none>` | `<triggers or none>` | `<conditions>` |

Shared Files:

| File | Owner | Rule |
|---|---|---|
| `<file>` | `<controller or worker>` | `<serial-only or exclusive lane>` |

Worker Delegation Rules:
- Controller role:
- Worker types allowed:
- Parallel lanes allowed:
- Parallel phases allowed:
- Worktree isolation allowed:
- Worker output format:
- Worker stop conditions:
- Integration owner:
- Required capability routing:
- Continuous execution allowed only within approved phase/task/lane boundaries:

Review Expectations:

Approval Gates:

Runtime Ownership:

Memory Maintenance Requirements:

Ledger Requirements:

Closeout Requirement:

Stop Conditions:

Expected Coder Output:
- `docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md`
```
