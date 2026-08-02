# Governance Levels

<a id="sage-auth-003"></a>
<a id="sage-auth-004"></a>
<a id="sage-auth-005"></a>
<a id="sage-auth-006"></a>
<a id="sage-auth-007"></a>
<a id="sage-auth-008"></a>

Choose governance from actual risk, not document count or milestone age.

| Level | Typical use | Minimum control |
|---|---|---|
| Light | Small, reversible, low-risk change | bounded scope, focused check, concise evidence |
| Standard | Normal multi-file implementation | explicit plan, affected-boundary review, project CI |
| Heavy | Delegation, security, authority, release, destructive or broad integration work | explicit lanes/Graph when useful, independent review, named human gates |

Permission is separate:

- `READ_ONLY_REVIEW`
- `WRITE_AUTHORIZED`
- `CORRECTIVE_AUTHORIZED`
- `ENVIRONMENT_WRITE_AUTHORIZED`
- `SUBMIT_AUTHORIZED`

No level implies a permission. Final review is read-only unless a separate
corrective worker is authorized. Submit authority is explicit and post-verdict.
Waivers and acceptance belong only to the named human authority.

P0/P1 findings block. P2 blocks only for authority conflict, false-green,
approval gate, security boundary, or failed required verification. Ordinary P2
documentation consistency may be accepted with concerns or corrected directly.
P3 never blocks.
