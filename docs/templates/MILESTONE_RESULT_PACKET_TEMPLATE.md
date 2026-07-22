# Milestone Result Packet Template

Use this packet from Coder Controller to Project Manager Controller.

Role and submit authority are canonical at
`docs/agent/GOVERNANCE_LEVELS.md#sage-auth-005` and
`docs/agent/GOVERNANCE_LEVELS.md#sage-auth-007`. This result retains the local
handoff, level/mode, changed-surface, evidence, and permission-gap fields.
Canonical lane-result status semantics are owned by
`docs/agent/WAVE_EXECUTION.md#sage-grf-011`; `SUPERSEDED` below is a
phase-result extension, not a lane status.

Coder does not send this packet directly to Final Review. Project Manager runs
the Structural Gate first and forwards the packet to Final Review only after the
Structural Gate status is `PASS`.

```markdown
Status: DONE, DONE_WITH_CONCERNS, HANDOFF, or BLOCKED

Milestone:

Primary Capability:

Execution Packet Ref:

Scope Implemented:

Scope Not Implemented:

Governance Used:
- Controller level:
- Worker levels:
- Controls Enabled:
- Controls Not Enabled:
- Upgrade triggers found:
- Workers stopped for controller:

Permission Used:
- Controller permission mode:
- Worker permission modes:
- Write authority used:
- Integration repair worker authority used:
- Environment-write authority used:
- Submit/commit/push/cleanup authority used: `none; requires post-verdict grant`
- Permission upgrade triggers found:
- Permission gaps needing Project Manager:

Capability Discovery Used:
- Capability registry checked:
- SAGE-Kit boundary preserved:
- Skills used:
- superpowers skills used:
- superpowers boundary notes:
- Plugins/connectors used:
- Tools used:
- Capability adapters used:
- Adapter authorization/fallback:
- External capability evidence produced:
- External planning output mapped to:
- Missing capabilities and fallback:

Parallelism Assessment:
- Execution shape used: `SERIAL`, `PARALLEL_WITH_WAVES`, `PARALLEL_PHASES`, or `STOP_FOR_PM`
- Wave readiness decision:
- Wave readiness gaps:
- Why this was safe:
- What remained serial:
- Conflicts found:
- Recommended shape for next run:

Coder Execution Mode:
- Mode used: `WORKER_ORCHESTRATION` or `WORKER_ORCHESTRATION_WITH_CONTROLLER_INTEGRATION`
- Direct controller integration allowed by packet: `<yes/no>`
- Why direct controller integration was used:
- Worker dispatch skipped:
- Why dispatch was skipped:
- Controller-owned files changed directly by Coder Controller:
- Worker-owned implementation files changed by Coder Controller: `none`
- Independent review risk:

Worktree Map:

| Worktree | Branch | Scope | Owner | Allowed Files | Runtime | Status | Integration |
|---|---|---|---|---|---|---|---|
| `<path or n/a>` | `<branch>` | `<phase/lane/review>` | `<owner>` | `<files>` | `<runtime or n/a>` | `<status>` | `<owner/action>` |

Worktree Decisions:
- Worktrees authorized by execution packet:
- Worktrees created:
- Work kept serial and why:
- Integration status:
- Review worktree creator/status:
- Post-verdict submit/cleanup grant: `not issued during Coder execution`
- Cleanup recommendation:

Task Dispatch Results:
- Task Dispatch active: `<yes/no>`
- Dispatch board:
- Task records updated:
- Evidence records updated:
- Validator command:
- Validator result:
- Acceptance gate covered by this packet: `<task/phase/milestone/not an acceptance gate>`
- Gate-ready validator evidence: `<command/result, or n/a only when not an acceptance gate>`
- Resource lock status:
- Lease status:
- Records needing Project Manager decision:

Phase Results:

| Phase | Status | Files Changed | Contract Evidence | Tests | Runtime Smoke | Skipped Checks | Blockers | Next Action |
|---|---|---|---|---|---|---|---|---|
| `<phase>` | `DONE`, `DONE_WITH_CONCERNS`, `HANDOFF`, `BLOCKED`, or `SUPERSEDED` | `<files>` | `<evidence>` | `<commands>` | `<evidence or n/a>` | `<checks>` | `<blockers>` | `<action>` |

Worker / Lane Summary:

| Worker Or Lane | Role | Status | Files | Evidence | Notes |
|---|---|---|---|---|---|
| `<worker>` | `<phase/lane/review/corrective>` | `<status>` | `<files>` | `<evidence>` | `<notes>` |

Worker Governance Summary:

| Worker Or Lane | Governance Level | Permission Mode | Stayed In Level/Mode | Upgrade Trigger | Controller Decision |
|---|---|---|---|---|---|
| `<worker>` | `Light, Standard, or Heavy` | `<mode>` | `<yes/no>` | `<trigger or none>` | `<decision or n/a>` |

Contracts:

Approval Gates:

Coder Self Review:
- File boundary review:
- Contract review:
- Test and smoke review:
- Controller integration-edit policy review:
- Worker separation review:
- Permission mode review:
- Runtime gap review:
- Security or data hygiene review:
- Integration repairs completed before Project Manager structural gate:
- Issues requiring Final Review or Project Manager:

Tests Run:

Runtime Smoke:

Memory Maintenance:
- Startup Context Controller:
- Worker/integration proposals applied or rejected:

Milestone Ledger Notes:

Closeout Notes:

Security / Data Hygiene:

Skipped Checks:

Known Gaps:

Stop Conditions Triggered:
- Closed approval gate:
- Scope expansion:
- Shared-file or resource lock conflict:
- Failed required evidence:
- Unapproved runtime/destructive/submit operation:

Suggested Final Review Focus:
```

Apply `docs/agent/GOVERNANCE_LEVELS.md#sage-auth-005`; this packet records the
Coder-to-Project-Manager handoff and leaves the post-review decision field
pending.

When Task Dispatch is active, a packet that asks Project Manager to advance a
task, phase, or milestone acceptance gate must include gate-ready validator
evidence. `n/a` is valid only when the named task is explicitly not an
acceptance gate.
