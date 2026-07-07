# Milestone Execution Packet Template

Use this packet from Project Manager Controller to Coder Controller.

```markdown
Milestone:

Objective:

Source Docs:
- Active context:
- Document routing:
- Entry gate:
- Milestone ledger:
- Phase docs:
- Quality gates:
- Approval gates:

Execution Mode:
- `Phase Execution | Wave Execution | Session Orchestration`

Execution Shape:
- `SERIAL | PARALLEL_WITH_WAVES | PARALLEL_PHASES | STOP_FOR_PM`

Parallelism Rationale:

Capability Discovery:
- Capability registry checked: `<yes/no/not available>`
- Selected skills:
- Selected plugins/connectors:
- Selected tools:
- Forbidden capabilities:
- Worker must check own capability list: `<yes/no>`
- Fallback if capability is missing:

Allowed Scope:

Non-Goals:

Phase Plan:

| Phase | Objective | Owner | Contract | Allowed Files | Read-Only Files | Forbidden Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|---|---|
| `<phase>` | `<objective>` | `<owner>` | `<contract or none>` | `<files>` | `<files>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |

Shared Files:

| File | Owner | Rule |
|---|---|---|
| `<file>` | `<controller or worker>` | `<serial-only or exclusive lane>` |

Worker Delegation Rules:
- Controller role:
- Worker types allowed:
- Parallel lanes allowed:
- Parallel phases allowed:
- Worker output format:
- Worker stop conditions:
- Integration owner:
- Required capability routing:

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
