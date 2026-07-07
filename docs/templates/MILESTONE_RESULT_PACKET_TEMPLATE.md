# Milestone Result Packet Template

Use this packet from Coder Controller to Project Manager Controller and Final
Review Controller.

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
- Corrective authority used:
- Environment-write authority used:
- Submit/cleanup authority used:
- Permission upgrade triggers found:
- Permission gaps needing Project Manager:

Capability Discovery Used:
- Capability registry checked:
- SPEC-Kit boundary preserved:
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
- Mode used: `WORKER_ORCHESTRATION`, `BOUNDED_SELF_EXECUTION`, or `MIXED`
- Self-execution allowed by packet: `<yes/no>`
- Why self-execution was used:
- Worker dispatch skipped:
- Why dispatch was skipped:
- Files changed directly by Coder Controller:
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
- Submit authority:
- Cleanup authority:
- Cleanup recommendation:

Task Dispatch Results:
- Task Dispatch active: `<yes/no>`
- Dispatch board:
- Task records updated:
- Evidence records updated:
- Validator command:
- Validator result:
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
- Self-execution policy review:
- Worker separation review:
- Permission mode review:
- Runtime gap review:
- Security or data hygiene review:
- Issues corrected before Final Review:
- Issues requiring Final Review or Project Manager:

Tests Run:

Runtime Smoke:

Memory Maintenance:

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

Project Manager Structural Gate Notes:
```

Coder Controller must not mark the milestone accepted. That decision belongs to
Project Manager after Final Review.
