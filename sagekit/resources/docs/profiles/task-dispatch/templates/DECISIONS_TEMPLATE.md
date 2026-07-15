# Dispatch Decisions: M<ID>

Use this file only for decisions that affect task dispatch, dependencies,
resource locks, evidence requirements, fallback acceptance, or gate closure.

Do not copy full task evidence here. Link to task and evidence records.

- Decision-log owner: `Project Manager Controller`
- Mutation authority: `<source / grant / scope>`

Only `ACTIVE` decisions supply current authority. Historical stop decisions
must be `SUPERSEDED`, `REVOKED`, or `EXPIRED` and linked to their replacement
when one exists.

## Decisions

| Date/Ref | Status | Decision | Scope | Owner | Authority Ref | Supersedes | Superseded By | Evidence | Follow-Up |
|---|---|---|---|---|---|---|---|---|---|
| `<date/ref>` | `PROPOSED/ACTIVE/SUPERSEDED/REVOKED/EXPIRED` | `<decision>` | `<task/phase/milestone>` | `<owner>` | `<authority source>` | `<ref/none>` | `<ref/none>` | `<link>` | `<follow-up or none>` |

## Waivers And Fallbacks

| Date/Ref | Status | Task | Waiver Or Fallback | Accepted By | Authority Ref | Supersedes | Superseded By | Expiry Or Follow-Up |
|---|---|---|---|---|---|---|---|---|---|
| `<date/ref>` | `PROPOSED/ACTIVE/SUPERSEDED/REVOKED/EXPIRED` | `<task>` | `<waiver/fallback>` | `<owner>` | `<authority source>` | `<ref/none>` | `<ref/none>` | `<follow-up>` |
