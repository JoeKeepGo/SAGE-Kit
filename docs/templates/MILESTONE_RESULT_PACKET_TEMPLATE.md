# Milestone Result Packet Template

Use this packet from Coder Controller to Project Manager Controller and Final
Review Controller.

```markdown
Status: DONE | DONE_WITH_CONCERNS | HANDOFF | BLOCKED

Milestone:

Execution Packet Ref:

Scope Implemented:

Scope Not Implemented:

Capability Discovery Used:
- Capability registry checked:
- Skills used:
- Plugins/connectors used:
- Tools used:
- Missing capabilities and fallback:

Parallelism Assessment:
- Execution shape used: `SERIAL | PARALLEL_WITH_WAVES | PARALLEL_PHASES`
- Why this was safe:
- What remained serial:
- Conflicts found:
- Recommended shape for next run:

Phase Results:

| Phase | Status | Files Changed | Contract Evidence | Tests | Runtime Smoke | Skipped Checks | Blockers | Next Action |
|---|---|---|---|---|---|---|---|---|
| `<phase>` | `DONE | DONE_WITH_CONCERNS | HANDOFF | BLOCKED | SUPERSEDED` | `<files>` | `<evidence>` | `<commands>` | `<evidence or n/a>` | `<checks>` | `<blockers>` | `<action>` |

Worker / Lane Summary:

| Worker Or Lane | Role | Status | Files | Evidence | Notes |
|---|---|---|---|---|---|
| `<worker>` | `<phase/lane/review/corrective>` | `<status>` | `<files>` | `<evidence>` | `<notes>` |

Contracts:

Approval Gates:

Coder Self Review:
- File boundary review:
- Contract review:
- Test and smoke review:
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

Suggested Final Review Focus:

Project Manager Structural Gate Notes:
```

Coder Controller must not mark the milestone accepted. That decision belongs to
Project Manager after Final Review.
