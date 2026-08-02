# Document Routing Template

This routing guide prevents future sessions from reading the whole documentation
archive by default.

## Default Rule

Read narrow first, then expand only when the task requires it.
Project-selected SPEC sources are valid; their paths are provenance, not
authority. No SAGE-Kit config filename or fixed milestone directory is
required.

Maintain this file as a stable routing table, not a session log. Do not update
it for ordinary task progress.

Context budget is a guardrail, not a correctness cap. Agents may expand beyond
the default read set when correctness, safety, provenance, full milestone
review, or final acceptance requires it, but they must record why the extra
context is needed and what decision it supports.

Default startup read set:

1. Project-selected active SPEC.
2. Compact current-context record, commonly `ACTIVE_CONTEXT`.
3. Project routing record, when one exists.
4. Active milestone or phase authority only when the current task selects it.
5. Applicable project gates, commands, and evidence owners.

## Read Policy By Task

| Task Type | Read First | Expand Only If Needed |
|---|---|---|
| General orientation | `ACTIVE_CONTEXT.md`, this file | `MILESTONE_ROADMAP.md` if present |
| Thin document review | Project-selected active SPEC and compact current context | Referenced project gates and evidence only |
| Governance and authority selection | Active context, this file, `docs/agent/GOVERNANCE_LEVELS.md` | Active milestone entry gate, phase doc, quality gates, approval gates |
| Project owner intake | `docs/agent/PROJECT_OWNER_ENTRY.md`, `docs/templates/PROJECT_OWNER_INTAKE_TEMPLATE.md`, project profile draft if present | `docs/templates/CAPABILITY_MAP_TEMPLATE.md`, technical design, roadmap template |
| Capability map or roadmap granularity audit | Project profile, `docs/CAPABILITY_MAP.md` if present or `docs/templates/CAPABILITY_MAP_TEMPLATE.md` if creating it, quality gates, `docs/agent/MILESTONE_PLANNING.md` | Technical design, relevant profile templates, prior closeouts only when the capability depends on history |
| New feature planning | Project profile, quality gates, `docs/agent/MILESTONE_PLANNING.md` | Technical design if present or risk-enabled; named or relevant prior milestone closeouts, then ledgers only if needed |
| Milestone planning | Project profile, quality gates, `docs/agent/MILESTONE_PLANNING.md` | Technical design or roadmap if present or Standard/Heavy; named or relevant prior milestone closeouts, then ledgers only if needed |
| Session orchestration | Active context, this file, active milestone entry gate and ledger, `docs/agent/SESSION_ORCHESTRATION.md` | Packet templates and phase docs needed by the current controller |
| Worktree isolation | Active context, this file, active milestone entry gate and ledger, `docs/agent/WORKTREE_ISOLATION.md` | Execution packet, worktree map, branch state, and phase docs needed by the current controller |
| Structured task/evidence records | Active context, this file, active milestone authority, current task/evidence records | `contracts/task-dispatch-v2/` when the project selects that static shape; related dependency records only when needed |
| External capability routing | Active context, this file, `docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-003`, `docs/agent/AGENT_HARNESS.md`, `docs/agent/GOVERNANCE_LEVELS.md` | Selected skill, plugin, connector, MCP tool, project command, CI, or review instructions only when the task will use that execution method |
| Frontend or browser adapter | Active phase doc, UI contract, quality gates, `docs/agent/CAPABILITY_ADAPTERS.md` | Design system, frontend skill instructions, browser QA tools |
| Runtime implementation | Active milestone and phase docs | Exact contract docs for touched modules |
| UI work | Active phase doc, UI contract, quality gates | Design system |
| Contract change | Contract owner doc and consumer docs | Relevant closeout decision summary, then historical decision records |
| Review | Active phase doc, quality gates, changed files | Active task/evidence records when Structured records is used, prior closeout summary, then ledger evidence |
| Historical outcome lookup | Named `MILESTONE_CLOSEOUT.md` | Ledger, phase docs, and completion reports only for provenance |
| Release or publish | Approval gates, release phase doc | Packaging docs |

## Historical Archive Policy

Historical milestones are evidence, not default startup context. Read them only
when:

- the user names the milestone;
- the active doc points to a specific historical decision;
- a review must verify provenance;
- planning needs prior milestone outcomes, gaps, or follow-up decisions;
- implementation touches behavior governed by a historical contract.

When historical context is needed, read `docs/M<ID>/MILESTONE_CLOSEOUT.md`
first. Open historical ledgers, phase docs, completion reports, or logs only
when the closeout does not answer the question or the task requires detailed
provenance.

## Expansion Rule

Before opening broad files or long logs, record:

- why the file is needed;
- what symbols, headings, or ranges are needed;
- what decision the read should support.

Prefer targeted reads before full archives:

1. read closeouts before historical ledgers;
2. read capability metadata before capability bodies;
3. search for headings or symbols before reading whole files;
4. read packet templates only when the current task uses that packet.
5. read optional static task/evidence schemas only when the current project
   selects structured records or an audit needs their shape.
6. read project owner intake before capability maps, and capability maps before
   executable roadmaps for broad, non-technical, or coarse-roadmap projects.
7. read capability adapter policy before external capability bodies, generated
   skills, hooks, MCP config, or provider documentation.

Do not read every phase doc, historical ledger, closeout, skill body, plugin
body, or log unless the task explicitly requires full milestone review,
provenance, safety analysis, or final acceptance.

## Maintenance Rule

Update this file only when the active permission mode and ownership allow direct
writes and the documentation topology or routing policy changes, such as:

- a required project document is added, removed, renamed, or moved;
- a profile adds a new default read path;
- task types or ownership boundaries change;
- a new archive or historical evidence policy is adopted.

If direct writes are not allowed, return a `Memory Update Proposal` or explicit
no-change note.

Do not write task status, command output, review notes, milestone progress, or
agent observations here. Durable current-state facts belong in active context;
observations, evidence, and progress belong in the milestone ledger, phase
document, completion report, or handoff.

At the end of a run, record `No routing change needed` in the handoff or
completion report when this file does not require an edit.

Target size: keep this file compact. If it grows beyond the project routing
budget, split rarely used routes into profile-specific routing notes.
