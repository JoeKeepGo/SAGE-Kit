# Governance Levels

<a id="sage-auth-003"></a>
<a id="sage-auth-004"></a>
<a id="sage-auth-005"></a>
<a id="sage-auth-006"></a>
<a id="sage-auth-007"></a>
<a id="sage-auth-008"></a>

Choose governance from actual risk, not document count, milestone age, model
identity, or delegation alone. This is the canonical control matrix.

| Level | Typical scope | Documents | Execution and review | Verification and gates |
|---|---|---|---|---|
| Light | Small, reversible, low-risk, bounded work | 0-1 short documents | Controller may execute; no independent review by default | 1-2 focused checks; CI only when a project, merge, or release gate requires it |
| Standard | Normal multi-file or affected-boundary work | Short plan plus result | Controller or useful subagents selected by risk; one affected-boundary review | Focused checks and project CI once per unchanged candidate when required |
| Heavy | Concrete safety, authority, destructive, production, release, or broad integration risk | 3-5 purposeful documents by default | Explicit lanes or Graph only when useful; one independent final review | Risk checks, project-required final CI when selected, and explicit human gates for the high-risk actions |

Unknown model identity does not select Strict Mode. Strict Mode is enabled only
by explicit project/human policy or a concrete low-assurance, high-risk trigger.
Delegation does not select Heavy by itself. A shared toolchain is serial only
while mutable state is actually shared. An isolated lane may commit locally
when authorized; the controller serializes push and merge. Final CI runs once
for an unchanged candidate; a successor candidate may run it again.

Permission is separate:

<a id="authority-matrix"></a>

- `READ_ONLY_REVIEW`
- `WRITE_AUTHORIZED`
- `CORRECTIVE_AUTHORIZED`
- `ENVIRONMENT_WRITE_AUTHORIZED`
- `SUBMIT_AUTHORIZED`

No level implies a permission. Final review is read-only unless a separate
corrective worker is authorized. Submit authority is explicit and post-verdict.
Waivers and acceptance belong only to the named human authority.

P0/P1 findings always block acceptance. P2 blocks only for an authority
conflict, false-green, approval gate, safety boundary, or validator/required
project-check failure; ordinary P2 findings may be fixed directly or retained
as concerns. P3 never blocks.
