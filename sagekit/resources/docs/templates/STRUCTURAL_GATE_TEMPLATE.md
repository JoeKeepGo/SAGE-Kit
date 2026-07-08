# Structural Gate Template

Use this checklist after Coder returns a Milestone Result Packet and before
sending it to Final Review.

This is a completeness gate, not a technical review.

```markdown
Structural Gate Status: PASS, REPAIR_REQUIRED, or BLOCKED

Milestone:

Packet Ref:

Checked By:

Required Sections Present:

| Section | Present | Notes |
|---|---|---|
| Status | `<yes/no>` | `<notes>` |
| Primary capability / capability map or n/a | `<yes/no>` | `<notes>` |
| Scope implemented / not implemented | `<yes/no>` | `<notes>` |
| Governance level and controls | `<yes/no>` | `<notes>` |
| Permission mode and authority boundaries | `<yes/no>` | `<notes>` |
| Capability discovery used | `<yes/no>` | `<notes>` |
| Capability adapter authorization/fallback recorded when used | `<yes/no/n/a>` | `<notes>` |
| superpowers boundary recorded when used | `<yes/no/n/a>` | `<notes>` |
| Coder execution mode and self-execution policy recorded | `<yes/no/n/a>` | `<notes>` |
| Wave readiness decision recorded when parallelism was used | `<yes/no/n/a>` | `<notes>` |
| Parallelism assessment | `<yes/no>` | `<notes>` |
| Worktree authorization or n/a | `<yes/no>` | `<notes>` |
| Worktree map or n/a | `<yes/no>` | `<notes>` |
| Submit and cleanup authority or n/a | `<yes/no>` | `<notes>` |
| Phase results | `<yes/no>` | `<notes>` |
| Files changed | `<yes/no>` | `<notes>` |
| Contract evidence | `<yes/no>` | `<notes>` |
| Coder self review | `<yes/no>` | `<notes>` |
| Tests run | `<yes/no>` | `<notes>` |
| Runtime smoke | `<yes/no>` | `<notes>` |
| Approval gates | `<yes/no>` | `<notes>` |
| Memory maintenance | `<yes/no>` | `<notes>` |
| Ledger notes | `<yes/no>` | `<notes>` |
| Closeout notes | `<yes/no>` | `<notes>` |
| Skipped checks and blockers | `<yes/no>` | `<notes>` |

Stop Conditions Surfaced:

Approval Gate Risk:

Scope Drift Risk:

Packet Repair Required:

Decision:
- Forward to Final Review only when Structural Gate Status is `PASS`
- Return to Coder for packet repair only
- Stop for Project Manager / human decision
```

## Post-Final-Review Closure Gate

Use this short check after Final Review when the verdict is not cleanly
acceptable.

```markdown
Review Closure Status: CLOSED, CORRECTIVE_OPENED, PM_DECISION_REQUIRED, or BLOCKED

Final Review Packet Ref:

Verdict:

Corrective Required:

Verdict Closure Branch:
- `ACCEPTABLE`: Project Manager may record final decision.
- `ACCEPTABLE_WITH_CONCERNS`: Project Manager may accept with recorded concerns,
  waiver, deferred owner, or return for decision.
- `NEEDS_CORRECTION`: open corrective round, request PM waiver/decision, or mark
  blocker. Do not close as accepted without the PM record.
- `BLOCKED`: mark blocked or return for blocker resolution. Do not accept.

| Check | Status | Notes |
|---|---|---|
| Permission mode recorded | `<yes/no>` | `<notes>` |
| Findings classified | `<yes/no>` | `<notes>` |
| Corrective packet attached when required | `<yes/no/n/a>` | `<notes>` |
| PM decision request attached when required | `<yes/no/n/a>` | `<notes>` |
| Blocker named when correction cannot proceed | `<yes/no/n/a>` | `<notes>` |
| Re-review required and owner named | `<yes/no/n/a>` | `<notes>` |

Decision:
- Open corrective round for `AUTO_CORRECTIVE` findings
- Return to Project Manager for decision, waiver, defer, or scope authority
- Mark blocked for `BLOCKED` verdicts or unresolved blockers
- Close only after the verdict branch above is satisfied
```
