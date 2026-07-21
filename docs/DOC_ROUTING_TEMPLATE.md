# Document Routing Template

This routing guide prevents future sessions from reading the whole documentation
archive by default.

## Default Rule

Read narrow first, then expand only when the task requires it.
Configured or explicit SPEC sources are valid; their paths are provenance, not
authority. Legacy `docs/<M>` routing remains a compatible default.

Maintain this file as a stable routing table, not a session log. Do not update
it for ordinary task progress.

Context budget is a guardrail, not a correctness cap. Agents may expand beyond
the default read set when correctness, safety, provenance, full milestone
review, or final acceptance requires it, but they must record why the extra
context is needed and what decision it supports.

Default startup read set:

1. Configured `ACTIVE_CONTEXT` (legacy default `docs/ACTIVE_CONTEXT.md`)
2. `docs/DOC_ROUTING.md`
3. `SAGEKIT_CONFIG.json`, when present, for source mapping, configured context,
   project identity, and stable public contract binding
4. `SAGE_PROJECT.json`, when present, to select `execution_document_model` and
   its pinned execution-policy contract after source resolution
5. Active `MILESTONE_MANIFEST.json` or legacy entry gate and ledger, if the task
   belongs to a milestone
6. Active thin phase manifest or legacy phase document, if implementation or
   review is requested

## Read Policy By Task

| Task Type | Read First | Expand Only If Needed |
|---|---|---|
| General orientation | `ACTIVE_CONTEXT.md`, this file | `MILESTONE_ROADMAP.md` if present |
| Thin document validation | `SAGEKIT_CONFIG.json` when present, `SAGE_PROJECT.json`, configured or explicit active SPEC sources; legacy default `docs/<M>` | Referenced project gates and evidence only |
| Thin packet compilation | Project lock, active milestone manifest, selected phase manifest | Exact pinned contract/profile resources; standalone output only when the runtime cannot load them |
| Governance and authority selection | Active context, this file, `docs/agent/GOVERNANCE_LEVELS.md` | Active milestone entry gate, phase doc, quality gates, approval gates |
| Project owner intake | `docs/agent/PROJECT_OWNER_ENTRY.md`, `docs/templates/PROJECT_OWNER_INTAKE_TEMPLATE.md`, project profile draft if present | `docs/templates/CAPABILITY_MAP_TEMPLATE.md`, technical design, roadmap template |
| Capability map or roadmap granularity audit | Project profile, `docs/CAPABILITY_MAP.md` if present or `docs/templates/CAPABILITY_MAP_TEMPLATE.md` if creating it, quality gates, `docs/agent/MILESTONE_PLANNING.md` | Technical design, relevant profile templates, prior closeouts only when the capability depends on history |
| New feature planning | Project profile, quality gates, `docs/agent/MILESTONE_PLANNING.md` | Technical design if present or risk-enabled; named or relevant prior milestone closeouts, then ledgers only if needed |
| Milestone planning | Project profile, quality gates, `docs/agent/MILESTONE_PLANNING.md` | Technical design or roadmap if present or Standard/Heavy; named or relevant prior milestone closeouts, then ledgers only if needed |
| Session orchestration | Active context, this file, active milestone entry gate and ledger, `docs/agent/SESSION_ORCHESTRATION.md` | Packet templates and phase docs needed by the current controller |
| Worktree isolation | Active context, this file, active milestone entry gate and ledger, `docs/agent/WORKTREE_ISOLATION.md` | Execution packet, worktree map, branch state, and phase docs needed by the current controller |
| Task dispatch | Active context, this file, active milestone ledger, active task `task.yaml`, active task `evidence.yaml`, `docs/profiles/task-dispatch/DISPATCH_PROFILE.md` | Dispatch board, schemas, validator output, related dependency task records |
| External capability routing | Active context, this file, `docs/SAGE_CORE.md#external-capability-boundary`, `docs/agent/AGENT_HARNESS.md`, `docs/agent/GOVERNANCE_LEVELS.md`, `docs/agent/CAPABILITY_ADAPTERS.md` | Selected skill, plugin, connector, MCP tool, CLI, CI, or review instructions only when the task will use that execution method |
| Frontend or browser adapter | Active phase doc, UI contract, quality gates, `docs/agent/CAPABILITY_ADAPTERS.md` | Design system, frontend skill instructions, browser QA tools |
| Runtime implementation | Active milestone and phase docs | Exact contract docs for touched modules |
| UI work | Active phase doc, UI contract, quality gates | Design system |
| Contract change | Contract owner doc and consumer docs | Relevant closeout decision summary, then historical decision records |
| Review | Active phase doc, quality gates, changed files | Active task/evidence records when Task Dispatch is used, prior closeout summary, then ledger evidence |
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
5. read task-dispatch schemas and validator internals only when adopting the
   profile, debugging validation, or closing a gate that depends on them.
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
