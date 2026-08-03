# Corrective Packet Template

Use this optional packet for a bounded semantic correction or an explicit
Heavy/formal workflow. Ordinary mechanical fixes may be closed directly with a
focused check.

```markdown
Source review / finding IDs:
Authorized corrective scope and permission:
Allowed / read-only / forbidden paths:
Required fix and acceptance:
Focused checks:
Targeted re-review owner and affected boundary:
Findings trend: `decreasing`, `unchanged`, or `increasing`
Same-root consecutive no-progress rounds: `<0, 1, or 2>`
Stop conditions:
Evidence return / ACTIVE_CONTEXT proposal:
```

P0/P1 always block. P2 blocks only for authority conflict, false-green,
approval gate, safety boundary, or validator/required project-check failure;
ordinary P2 may be fixed directly or retained as a concern. P3 never blocks.

Continue without new Project Manager approval while findings decrease inside
the same authorized scope. At two consecutive no-progress rounds for the same
root cause return `BLOCKED`. Stop earlier for scope/permission expansion, a new
threat-model or safety decision, destructive/production work, credentials, or
merge/release gates.
