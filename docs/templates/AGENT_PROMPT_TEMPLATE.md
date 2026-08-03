# Agent Prompt Template

Use these eight core fields. Keep them concrete and omit unused optional
profiles.

```markdown
Objective:

Authority:
- current SPEC/decision references
- project-granted scope owner

Permission:
- mode and human-only actions

Paths:
- allowed
- read-only
- forbidden

Acceptance:
- observable outcome and blocking findings/gates

Checks:
- focused and project-required checks

Stop:
- authority/scope/permission expansion, safety or approval decision, missing
  required evidence, destructive/production/merge/release gate

Return:
- changed surfaces, evidence references, review/concerns, blocker or next owner,
  and `ACTIVE_CONTEXT` update/proposal when durable truth changed
```

Optional blocks are referenced rather than embedded: governance level,
dependencies/Graph, specialist capability routing, rollback for durable/public
changes, independent review, host adapter, or bounded multi-milestone
continuation. Use the formal packet templates only when an explicit Heavy or
formal-approval profile selects them.
