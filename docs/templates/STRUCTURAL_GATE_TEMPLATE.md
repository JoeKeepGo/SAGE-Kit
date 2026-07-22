# Structural Gate Template

<a id="sage-lif-012"></a>

Use this checklist after Coder returns a Milestone Result Packet and before
sending it to Final Review.

This is the canonical Coder-result completeness gate. It routes a complete
packet to independent Final Review; it does not perform technical review, make
Project Manager acceptance, or close the milestone.

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
| Ownership and contracts | `<yes/no>` | `<owners/boundaries/contracts>` |
| Contract evidence | `<yes/no>` | `<notes>` |
| Evidence references | `<yes/no>` | `<refs or n/a reason>` |
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

This separate record retains post-review routing fields; it is not part of the
Structural Gate `PASS`, a technical re-review, Project Manager acceptance, or
milestone closeout. Apply convergence and targeted re-review from
`docs/agent/EXECUTION_ECONOMY.md#sage-loop-008` and
`docs/agent/EXECUTION_ECONOMY.md#sage-loop-010`, and Deterministic Closure from
`docs/agent/SESSION_ORCHESTRATION.md#sage-loop-011`.

```markdown
Review Closure Status: VERDICT_READY_FOR_PM, CORRECTIVE_OPENED,
CORRECTIVE_CONTINUING, VERDICT_FINALIZED_FROM_RECEIPT,
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
| Re-review or Deterministic Closure required and owner named | `<re-review/deterministic/n/a>` | `<owner and predicate ref when deterministic>` |
| Re-review status | `NOT_STARTED`, `IN_REVIEW`, `PASSED`, `FAILED`, or `NOT_REQUIRED_DETERMINISTIC` | `<never use PASSED for deterministic closure>` |
| Deterministic finding closure status | `AUTO_CLOSED_BY_PREDICATE`, `INVALID_REVIEW_REQUIRED`, or `N/A` | `<predicate/command/State Truth result>` |
| Closure Receipt Owner | `<owner/n/a>` | `<original Final Review Controller or named packet author; separate from fixer>` |
| Closure Receipt Ref | `<ref/n/a>` | `<immutable or packet-local receipt reference>` |
| Closure Receipt Destination | `<review packet/output/n/a>` | `<receipt owner's own output>` |
| Verdict finalization status | `VERDICT_FINALIZED_FROM_RECEIPT` or `N/A` | `<precommitted verdict; PM acceptance pending>` |
| PM acceptance pending | `<yes/no>` | `<must remain yes until Project Manager decision>` |
| Convergence trend recorded | `<yes/no/n/a>` | `<finding count/severity trend and root-cause progress>` |
| Targeted or full re-review scope justified | `<yes/no/n/a>` | `<targeted status/evidence lanes or full affected lanes>` |

Decision:
- Record the canonical convergence and re-review outcome from the Final Review
  packet and attach the named corrective packet, handoff, or blocker
- Return Project Manager decisions, waivers, defers, and scope-authority needs
  to their named owner
- Mark `VERDICT_READY_FOR_PM` only after the verdict branch above is satisfied;
  this closes the review loop, not the milestone
- Record strict Deterministic Closure fields only when the canonical predicate
  and receipt contract has produced them; do not mark re-review `PASSED`
```
