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
| Coder execution mode and controller integration edit policy recorded | `<yes/no/n/a>` | `<notes>` |
| Wave readiness decision recorded when parallelism was used | `<yes/no/n/a>` | `<notes>` |
| Parallelism assessment | `<yes/no>` | `<notes>` |
| Worktree authorization or n/a | `<yes/no>` | `<notes>` |
| Worktree map or n/a | `<yes/no>` | `<notes>` |
| Initial submit/cleanup authority is none; post-verdict owner is named | `<yes/no>` | `<notes>` |
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
Review Closure Status: VERDICT_READY_FOR_PM, CORRECTIVE_OPENED, CORRECTIVE_CONTINUING,
PM_DECISION_REQUIRED, or BLOCKED

Final Review Packet Ref:

Verdict:

Corrective Required:

Verdict Closure Branch:
- `ACCEPTABLE`: Project Manager may record final decision.
- `ACCEPTABLE_WITH_CONCERNS`: Project Manager may accept with recorded concerns,
  owner-authorized waiver, deferred owner, or return for decision.
- `NEEDS_CORRECTION`: open corrective round, request owner-authorized quality
  waiver/decision, or mark blocker. Continue automatic correction only inside an authorized corrective
  packet or boundary while convergence is proven and scope does not expand. Do
  not close as accepted without the PM record.
- `BLOCKED`: mark blocked or return for blocker resolution. Do not accept.

| Check | Status | Notes |
|---|---|---|
| Permission mode recorded | `<yes/no>` | `<notes>` |
| Findings classified | `<yes/no>` | `<notes>` |
| Severity gate applied | `<yes/no>` | `<P0/P1 block; authority/false-green/approval-boundary/security-boundary/validator-failure/source-authority/evidence-integrity P2 block; ordinary P2 may auto-fix or carry concerns; P3 does not block>` |
| Finding owner and waiver authority recorded | `<yes/no/n/a>` | `<finding owner; waiver authority>` |
| Waiver decision or delegation reference recorded | `<yes/no/n/a>` | `<explicit decision/delegation ref>` |
| Corrective packet attached when required | `<yes/no/n/a>` | `<notes>` |
| PM decision request attached when required | `<yes/no/n/a>` | `<notes>` |
| Blocker named when correction cannot proceed | `<yes/no/n/a>` | `<notes>` |
| Re-review required and owner named | `<yes/no/n/a>` | `<notes>` |
| Convergence trend recorded | `<yes/no/n/a>` | `<finding count/severity trend and root-cause progress>` |
| Targeted or full re-review scope justified | `<yes/no/n/a>` | `<targeted status/evidence lanes or full affected lanes>` |

Decision:
- Open corrective round for `AUTO_CORRECTIVE` findings
- Continue corrective work only inside an authorized corrective packet or
  boundary when finding count or severity is decreasing, scope does not expand,
  no blocking approval gate is bypassed, and no new authority, false-green,
  approval-boundary, security-boundary, validator-failure, source-authority, or
  evidence-integrity risk appears
- On the first same-root stagnant round, stop automatic continuation and return
  `NEEDS_CORRECTION`, `PM_DECISION_REQUIRED`, and `HANDOFF`
- Return to Project Manager for decision, waiver, defer, or scope authority
- Mark blocked for unresolved blockers or two consecutive rounds with the same
  root cause and no material progress
- Do not close `BLOCKED` until an authorized owner records close-blocked,
  abandon, or defer
- Mark `VERDICT_READY_FOR_PM` only after the verdict branch above is satisfied;
  this closes the review loop, not the milestone
```
