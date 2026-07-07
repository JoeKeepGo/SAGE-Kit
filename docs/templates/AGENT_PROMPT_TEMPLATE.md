# Agent Prompt Template

Use this template to start a focused AI agent task.

```markdown
You are working inside a SPEC-Kit governed project.

Strict Mode:
- The controller or human decides whether this task uses Strict Mode according
  to `docs/agent/MODEL_ASSURANCE_POLICY.md`.
- In Strict Mode, read only listed files, modify only allowed files, run exact
  commands, and stop on ambiguity or failed verification.

Read first:
- docs/ACTIVE_CONTEXT.md
- docs/DOC_ROUTING.md
- Then follow `docs/DOC_ROUTING.md` for the narrow task read set.
- Read `docs/QUALITY_GATES.md` when gates, review, completion, or
  verification are in scope.
- Read `docs/agent/GOVERNANCE_LEVELS.md` when selecting or reviewing the
  governance level.
- Read `docs/agent/MODEL_ASSURANCE_POLICY.md` and `docs/agent/STRICT_MODE.md`
  when Strict Mode may apply or is selected.
- Read `docs/agent/WAVE_EXECUTION.md` when wave or parallel lane execution is
  used.
- Read `docs/agent/SESSION_ORCHESTRATION.md` when milestone-level controller
  handoff is used.
- Read `docs/agent/WORKTREE_ISOLATION.md` when isolated workspaces are used.
- Read `docs/agent/MILESTONE_PLANNING.md` when planning a milestone or phase
  decomposition.
- Read the active milestone entry gate or ledger only when the task belongs to
  a milestone.
- Read the active phase doc only when implementation or review is requested.

Objective:
- <one objective>

Governance Level:
- <Light, Standard, or Heavy>
- <why this level>
- <controls enabled>
- <stop for controller when>

Allowed files:
- <files>

Read-only files:
- <files>

Forbidden files:
- <files>

Contracts:
- <contract owner and consumer>

Tests:
- <commands>

Runtime smoke:
- <commands or not applicable reason>

Capability routing:
- Check available skill/plugin/connector/tool metadata before delegating or
  executing when the runtime exposes it.
- SPEC-Kit governs scope, authorization, files, gates, locks, evidence, and
  completion status; external capabilities provide execution methods inside
  this boundary.
- If superpowers is available, use only the selected skills that fit this
  boundary. If unavailable, use the SPEC-Kit packet, phase, gate, and evidence
  path instead.
- Do not let external capabilities expand scope, bypass locks, create a second
  source of truth, or mark SPEC-Kit gates complete.
- Use these selected capabilities:
- Do not use these capabilities:
- If a selected capability is unavailable:
- External planning output destination:
- Treat external capability completion as evidence only: `<yes>`

Wave / lane assignment:
- <lane name, allowed files, expected output, or serial-only>

Worktree isolation:
- <NONE / MILESTONE_WORKTREE / PHASE_WORKTREE / LANE_WORKTREE / REVIEW_WORKTREE>
- <assigned worktree or n/a>
- <branch/worktree naming and cleanup policy or n/a>

Session orchestration assignment:
- <Project Manager / Coder / Final Review / Phase Worker / Lane Worker /
  Review Worker / Corrective Worker or n/a>
- <packet path or expected packet output>

Approval gates:
- <closed gates>

Continuous execution:
- Continue only inside the approved phase/task/lane boundary.
- Stop on closed approval gates, scope expansion, shared-file or resource lock
  conflicts, failed required evidence, or unapproved runtime/destructive/submit
  operations.

Return format:
- Use `docs/templates/LANE_PACKET_TEMPLATE.md` for lane work.
- Use `docs/agent/HANDOFF_TEMPLATE.md` for phase or session handoff.
- Report memory maintenance for `docs/ACTIVE_CONTEXT.md` and
  `docs/DOC_ROUTING.md`.
```
