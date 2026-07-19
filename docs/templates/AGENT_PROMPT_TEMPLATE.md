# Agent Prompt Template

Use this template to start a focused AI agent task.

## Compact Controller Launch Envelope

Use this form for a Project Manager, Coder, or Final Review controller that can
read the project's local authority:

```markdown
Role and objective:
- <controller role and one objective>

Authority references:
- <ACTIVE_CONTEXT, DOC_ROUTING, execution packet, active ledger or gate paths>

Baseline or entry condition:
- <required branch/commit/state or entry gate>

Permission mode:
- <mode and controller-owned writes, if any>

PM authority deltas:
- authority ID: <stable identifier or none>
- source: <PM decision or approved authority path>
- priority: <relationship to the referenced authorities>
- reconciliation destination: <execution packet, ledger, or other authority>
- classification: <launch-only delta or packet update required>
- instruction: <non-authority-changing launch instruction or none>

Terminal state:
- <required handoff or verdict state>

Necessary prohibitions and stop conditions:
- <only constraints not already made unambiguous by the references>
```

This envelope must not duplicate the execution packet, phase authority, file
tables, or test plan. Let project routing select the narrow read set and load a
phase-specific authority only when that phase starts. Keeping the envelope near
40-80 lines is a guideline, not a correctness gate.

A `launch-only delta` may clarify reporting or execution order already allowed
by approved authority. It must not change scope, gates, permission, shared
ownership, contracts, or runtime authority. Changes to those boundaries must
first be written to and approved in the execution packet or other named
authority source. If any required prompt or packet reference is missing,
unreadable, contradictory, or conflicts with the delta, fail closed before
editing.

## Standalone Task Exception

These are mutually exclusive paths: use either this standalone packet or the
Explicit Local Worker Prompt below, never both.

When an agent has no repository access, give it a complete and self-contained
lane or task packet that does not require inaccessible local paths. An external
agent without repository access uses only this standalone packet.

```markdown
Role and objective:
- <bounded worker role and one objective>

Governance and Strict Mode:
- governance level: <Light, Standard, or Heavy>
- Strict Mode: <required/not required and exact restrictions>

Authority supplied in this packet:
- authority ID:
- authority source and approval state:
- permission mode:

Boundaries supplied in this packet:
- allowed files or surfaces:
- read-only files or surfaces:
- forbidden files or surfaces:
- contracts and runtime ownership:

Commands and evidence:
- exact commands:
- required evidence:
- skipped-check policy:

Stop conditions:
- <authority, scope, gate, conflict, verification, or safety stops>

Return format:
- <structured completion, finding, blocker, or handoff fields>
```

Missing required authority fails closed. The standalone agent must not guess
project facts, permissions, contracts, paths, commands, acceptance state, or
fallback behavior. This exception supplies an explicit worker boundary; it
does not grant authority that the packet does not contain.

## Explicit Local Worker Prompt

Worker prompts remain explicit. Use the full template below only for a worker,
lane, or corrective agent that can read the project's local authority.
Preserve exact allowed files, read-only files, forbidden files, tests, runtime
ownership, evidence, and stop conditions.

```markdown
You are working inside a SAGE-Kit governed project.

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
  governance level or permission mode.
- Read `docs/agent/MODEL_ASSURANCE_POLICY.md` and `docs/agent/STRICT_MODE.md`
  when Strict Mode may apply or is selected.
- Read `docs/agent/WAVE_EXECUTION.md` when wave or parallel lane execution is
  used.
- Read `docs/agent/SESSION_ORCHESTRATION.md` when milestone-level controller
  handoff is used.
- Read `docs/agent/WORKTREE_ISOLATION.md` when isolated workspaces are used.
- Read `docs/agent/MILESTONE_PLANNING.md` when planning a milestone or phase
  decomposition.
- Read `docs/agent/CAPABILITY_ADAPTERS.md` when external capability use,
  unavailable capability fallback, installation, hooks, MCP config, or
  frontend/browser adapter evidence is in scope.
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

Permission Mode:
- <READ_ONLY_REVIEW / WRITE_AUTHORIZED / CORRECTIVE_AUTHORIZED /
  ENVIRONMENT_WRITE_AUTHORIZED / SUBMIT_AUTHORIZED>
- <why this mode>
- <write/corrective/environment/submit authority or none>
- <permission upgrade requires>

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
- SAGE-Kit governs scope, authorization, files, gates, locks, evidence, and
  completion status; external capabilities provide execution methods inside
  this boundary.
- Codex GPT-5.6 Runtime Override: when active, record Superpowers as
  `DISABLED_BY_RUNTIME_POLICY`. The controller and its descendants must not
  read, invoke, or delegate to Superpowers. `using-superpowers` is explicitly
  disabled even when its skill metadata describes invocation as mandatory.
  All descendants inherit the override and use model-native brainstorming,
  planning, test-driven implementation, systematic debugging, subagent
  orchestration, review, and verification as native behaviors, not similarly
  named skill invocations. Do not treat the disabled adapter as a capability
  gap, fallback trigger, blocker, or stop condition.
- Every subagent launch packet must explicitly repeat
  `DISABLED_BY_RUNTIME_POLICY` and the `using-superpowers` prohibition. A
  descendant authorized to delegate must repeat both in every child packet.
  Preserve the rule across compaction, handoff, and resume.
- If superpowers is available, use only the selected skills that fit this
  boundary on runtimes where the Codex GPT-5.6 Runtime Override is inactive.
  If unavailable, use the SAGE-Kit packet, phase, gate, and evidence path
  instead.
- Use Capability Adapters for optional external providers. Default to
  metadata-only or read-only unless the active packet authorizes writes.
- Do not silently install skills, plugins, CLIs, MCP servers, hooks, generated
  skills, or global configuration.
- Before installing or initializing an approved adapter, read current provider
  docs, package metadata, or installed-tool help and report exact command,
  write targets, runtime requirements, rollback path, and fallback.
- Do not let external capabilities expand scope, bypass locks, create a second
  source of truth, or mark SAGE-Kit gates complete.
- Use these selected capabilities:
- Selected adapters and authorization levels:
- Do not use these capabilities:
- If a selected capability is unavailable:
- Adapter evidence destination:
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
