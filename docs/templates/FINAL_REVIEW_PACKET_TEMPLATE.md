# Final Review Packet Template

Use this packet from Final Review Controller to Project Manager Controller.

```markdown
Verdict: ACCEPTABLE, ACCEPTABLE_WITH_CONCERNS, NEEDS_CORRECTION, or BLOCKED

Milestone:

Primary Capability:

Coder Packet Ref:

Review Scope:

Governance Review:
- Controller level reviewed:
- Worker levels reviewed:
- Heavy controls enabled only when triggered:
- Over-governance found:
- Under-governance found:

Permission Review:
- Final Review mode: `READ_ONLY_REVIEW` or `CORRECTIVE_AUTHORIZED`
- Mode allowed by execution packet:
- Write/corrective authority preserved:
- Submit/cleanup authority preserved:
- Permission overreach found:
- Permission underreach found:

Capability Discovery Used:
- Capability registry checked:
- SPEC-Kit boundary preserved:
- Skills used:
- superpowers skills used:
- superpowers boundary violations:
- Plugins/connectors used:
- Tools used:
- Capability adapters reviewed:
- Adapter authorization/fallback reviewed:
- External capability evidence verified:
- External planning output mapped to SPEC-Kit docs:
- Missing capabilities and fallback:

Review Delegation Plan:
- Controller role:
- Review workers:
- Validation lanes:
- Parallel checks allowed:
- Files or evidence to inspect:
- Stop conditions:

Review Workers:

| Worker | Focus | Status | Evidence | Findings |
|---|---|---|---|---|
| `<worker>` | `<phase/contract/runtime/security/etc>` | `<status>` | `<evidence>` | `<findings>` |

Worker Governance Findings:

| Worker | Governance Level | Permission Mode | Appropriate | Finding |
|---|---|---|---|---|
| `<worker>` | `Light, Standard, or Heavy` | `<mode>` | `<yes/no>` | `<finding or none>` |

Independent Checks:

Parallelism Reassessment:
- Execution shape reviewed: `SERIAL`, `PARALLEL_WITH_WAVES`, `PARALLEL_PHASES`, or `STOP_FOR_PM`
- Wave readiness reviewed:
- Cosmetic wave plan found:
- Safe as executed: `<yes/no/blocked>`
- Serial gates protected:
- Unsafe parallelism found:
- Recommended future execution shape:

Coder Execution Mode Review:
- Coder self-executed: `<yes/no>`
- Self-execution allowed by packet: `<yes/no/n/a>`
- Self-execution stayed narrow: `<yes/no/n/a>`
- Worker dispatch should have been used: `<yes/no>`
- Additional review risk:

Worktree Review:
- Worktree isolation authorized: `<yes/no/n/a>`
- Worktree map reviewed:
- File boundaries preserved:
- Runtime or dependency conflicts:
- Integration evidence:
- Stale worktrees:
- Submit authority preserved:
- Cleanup authority preserved:
- Submit recommendation:
- Cleanup recommendation:

Task Dispatch Review:
- Task Dispatch active: `<yes/no>`
- Task/evidence records reviewed:
- Validator command:
- Validator result:
- L0-L4 evidence gaps:
- Resource lock or lease gaps:
- Mock or fallback concerns:
- Records needing Project Manager decision:

Phase Findings:

| Phase | Verdict | Findings | Required Corrections |
|---|---|---|---|
| `<phase>` | `<verdict>` | `<findings>` | `<corrections or none>` |

Finding Classification:

| Finding ID | Severity | Classification | Corrective Allowed | Required Packet / Decision | Verification | Re-Review |
|---|---|---|---|---|---|---|
| `<id>` | `<P0/P1/P2/P3>` | `AUTO_CORRECTIVE`, `PM_DECISION`, `BLOCKED`, or `DEFER` | `<yes/no>` | `<packet/ref/decision/blocker>` | `<commands/evidence>` | `<yes/no>` |

Contract Findings:

Runtime Findings:

Security / Data Hygiene Findings:

Approval Gate Findings:

Memory / Ledger / Closeout Findings:

Corrective Packet Required: `<yes/no>`

Corrective Packet:
- `<path or inline summary>`

Corrective Closure:
- Closure mode: `NONE`, `READ_ONLY_PACKET_ONLY`, `AUTO_OPEN_AUTHORIZED`,
  `PM_DECISION_REQUIRED`, or `BLOCKED`
- If required, packet/handoff/blocker provided: `<yes/no/n/a>`
- Auto-open authorized by execution packet: `<yes/no/n/a>`
- Corrective round: `<0/1/2>`
- Maximum corrective rounds:
- Re-review owner:
- "Corrective required: yes" without packet/handoff/blocker: `<yes/no>`

Corrective Delegation:
- Allowed executor: `Coder Controller`, `Corrective Worker`, or `Project Manager decision required`
- Allowed capabilities:
- Capability adapter boundaries:
- SPEC-Kit boundary for external capabilities:
- Stop conditions:

Residual Risks:

Recommended Project Manager Decision:

Re-Review Required:
```

Final Review recommends. Project Manager decides.
