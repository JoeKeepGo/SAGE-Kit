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

Permission Mode:
- Current mode: `READ_ONLY_REVIEW`, `WRITE_AUTHORIZED`,
  `CORRECTIVE_AUTHORIZED`, `ENVIRONMENT_WRITE_AUTHORIZED`, or
  `SUBMIT_AUTHORIZED`
- Why this mode:
- Writable authority:
- Project Manager final decision authority: `<separate PM decision record; not Final Review acceptance>`
- Corrective auto-open allowed: `<yes/no>`
- Corrective packet-only when read-only: `<yes/no>`
- Maximum corrective rounds:
- Environment-write authority:
- Submit/cleanup authority:
- Permission upgrade requires:

Execution Shape:
- `SERIAL`, `PARALLEL_WITH_WAVES`, `PARALLEL_PHASES`, or `STOP_FOR_PM`

Parallelism Rationale:

Wave Readiness:
- Useful parallel lanes:
- Exclusive writable files:
- Shared files kept serial:
- Contracts frozen before writable work:
- Runtime ownership:
- Validation lanes:
- Integration owner:
- Conflict stop conditions:
- Decision: `SERIAL`, `PARALLEL_WITH_WAVES`, `PARALLEL_PHASES`, or `STOP_FOR_PM`

Coder Self-Execution Policy:
- Self-execution allowed: `<yes/no>`
- Allowed only for: `<single phase/glue step/integration repair before Final Review/n/a>`
- Maximum files or surfaces:
- Worker dispatch required for:
- Self-execution forbidden when:
- Result packet must explain skipped worker dispatch: `<yes/no>`

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
- Validator required before: `<task gate/phase gate/milestone gate/not an acceptance gate>`
- Gate-ready validator required when active: `<yes/no; yes for task/phase/milestone acceptance>`
- If validator is not required, name the non-acceptance task or gate:
- Task/evidence update owner:

Capability Discovery:
- Capability registry checked: `<yes/no/not available>`
- SAGE-Kit boundary: `<scope/files/gates/locks/evidence controlled by this packet>`
- Selected skills:
- Selected superpowers skills:
- superpowers boundary:
- Selected plugins/connectors:
- Selected tools:
- Selected capability adapters:
- Adapter authorization levels:
- Adapter fallback policy:
- Forbidden capabilities:
- Worker must check own capability list: `<yes/no>`
- Fallback if capability is missing:
- External planning output destination:
- External capability completion counts as: `execution evidence only`

Allowed Scope:

Non-Goals:

Phase Plan:

| Phase | Governance Level | Permission Mode | Objective | Owner | Contract | Allowed Files | Read-Only Files | Forbidden Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `<phase>` | `Light, Standard, or Heavy` | `<mode>` | `<objective>` | `<owner>` | `<contract or none>` | `<files>` | `<files>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |

Worker Governance:

| Worker Or Lane | Scope | Governance Level | Permission Mode | Controls Enabled | Controls Not Enabled | Upgrade Triggers | Stop For Controller |
|---|---|---|---|---|---|---|---|
| `<worker>` | `<scope>` | `Light, Standard, or Heavy` | `<mode>` | `<controls>` | `<controls or none>` | `<triggers or none>` | `<conditions>` |

Shared Files:

| File | Owner | Rule |
|---|---|---|
| `<file>` | `<controller or worker>` | `<serial-only or exclusive lane>` |

Worker Delegation Rules:
- Controller role:
- Controller permission mode:
- Worker types allowed:
- Worker permission modes:
- Coder self-execution allowed:
- Self-execution criteria:
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
