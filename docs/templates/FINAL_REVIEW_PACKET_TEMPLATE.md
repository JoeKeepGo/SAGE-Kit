# Final Review Packet Template

Use for the one independent final review required by Heavy governance or when
project authority explicitly selects a review. Standard uses one affected
review; Light has no independent review by default.

```markdown
Verdict: `ACCEPTABLE`, `ACCEPTABLE_WITH_CONCERNS`, `NEEDS_CORRECTION`, or `BLOCKED`
Authority and read-only permission:
Review scope / candidate reference:
Acceptance criteria and required project checks:
Evidence inspected and limitations:

| Finding | Severity | Evidence | Blocking reason | Corrective boundary / concern |
|---|---|---|---|---|
| `<id>` | `P0`, `P1`, `P2`, or `P3` | `<ref>` | `<reason or non-blocking>` | `<action>` |

Targeted re-review required for semantic correction:
Remaining concerns:
Recommended next owner/action:
```

P0/P1 always block. P2 blocks only for authority conflict, false-green,
approval gate, safety boundary, or validator/required project-check failure.
P3 never blocks. Mechanical wording, status, and EOF fixes close with a focused
check; semantic correction receives one targeted re-review.
