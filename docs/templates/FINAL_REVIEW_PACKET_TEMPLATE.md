# Final Review Packet Template

Use this packet from Final Review Controller to Project Manager Controller.

```markdown
Verdict: ACCEPTABLE | ACCEPTABLE_WITH_CONCERNS | NEEDS_CORRECTION | BLOCKED

Milestone:

Coder Packet Ref:

Review Scope:

Capability Discovery Used:
- Capability registry checked:
- Skills used:
- Plugins/connectors used:
- Tools used:
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

Independent Checks:

Parallelism Reassessment:
- Execution shape reviewed: `SERIAL | PARALLEL_WITH_WAVES | PARALLEL_PHASES`
- Safe as executed: `<yes/no/blocked>`
- Serial gates protected:
- Unsafe parallelism found:
- Recommended future execution shape:

Phase Findings:

| Phase | Verdict | Findings | Required Corrections |
|---|---|---|---|
| `<phase>` | `<verdict>` | `<findings>` | `<corrections or none>` |

Contract Findings:

Runtime Findings:

Security / Data Hygiene Findings:

Approval Gate Findings:

Memory / Ledger / Closeout Findings:

Corrective Packet Required: `<yes/no>`

Corrective Packet:
- `<path or inline summary>`

Corrective Delegation:
- Allowed executor: `Coder Controller | Corrective Worker | Project Manager decision required`
- Allowed capabilities:
- Stop conditions:

Residual Risks:

Recommended Project Manager Decision:

Re-Review Required:
```

Final Review recommends. Project Manager decides.
