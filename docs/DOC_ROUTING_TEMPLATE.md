# Document Routing Template

This routing guide prevents future sessions from reading the whole documentation
archive by default.

## Default Rule

Read narrow first, then expand only when the task requires it.

Maintain this file as a stable routing table, not a session log. Do not update
it for ordinary task progress.

Default startup read set:

1. `docs/ACTIVE_CONTEXT.md`
2. `docs/DOC_ROUTING.md`
3. Active milestone entry gate and ledger, if the task belongs to a milestone
4. Active phase document, if implementation or review is requested

## Read Policy By Task

| Task Type | Read First | Expand Only If Needed |
|---|---|---|
| General orientation | `ACTIVE_CONTEXT.md`, this file | `MILESTONE_ROADMAP.md` |
| New feature planning | Project profile, technical design, quality gates, `docs/agent/MILESTONE_PLANNING.md` | Related prior milestone docs |
| Milestone planning | Project profile, technical design, roadmap, quality gates, `docs/agent/MILESTONE_PLANNING.md` | Prior milestone ledgers |
| Runtime implementation | Active milestone and phase docs | Exact contract docs for touched modules |
| UI work | Active phase doc, UI contract, quality gates | Design system or product profile sections |
| Contract change | Contract owner doc and consumer docs | Historical decision records |
| Review | Active phase doc, quality gates, changed files | Prior ledger evidence |
| Release or publish | Approval gates, release phase doc | Packaging docs |

## Historical Archive Policy

Historical milestones are evidence, not default startup context. Read them only
when:

- the user names the milestone;
- the active doc points to a specific historical decision;
- a review must verify provenance;
- implementation touches behavior governed by a historical contract.

## Expansion Rule

Before opening broad files or long logs, record:

- why the file is needed;
- what symbols, headings, or ranges are needed;
- what decision the read should support.

## Maintenance Rule

Update this file only when the documentation topology or routing policy changes,
such as:

- a required project document is added, removed, renamed, or moved;
- a profile adds a new default read path;
- task types or ownership boundaries change;
- a new archive or historical evidence policy is adopted.

Do not write task status, command output, review notes, milestone progress, or
agent observations here. Durable current-state facts belong in active context;
observations, evidence, and progress belong in the milestone ledger, phase
document, completion report, or handoff.

At the end of a run, record `No routing change needed` in the handoff or
completion report when this file does not require an edit.

Target size: keep this file under 100 lines unless the project profile
explicitly raises the routing budget.
