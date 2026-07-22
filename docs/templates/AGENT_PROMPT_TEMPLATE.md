# Agent Prompt Template

Use this template to start a focused AI agent task.

Approval semantics are owned by `docs/SAGE_CORE.md#sage-auth-009`. This
template retains the exact authority inputs, permission fields, file boundary,
closed-gate list, stop conditions, and evidence return required by a launch.

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

The canonical `launch-only delta` and fail-closed boundary is owned by
`docs/agent/AGENT_HARNESS.md#sage-auth-010`. This template retains the envelope
fields, standalone exception, explicit local-worker form, and task-specific
reporting needed to apply that rule; it does not define a second authority.

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
- Resolve `active_context` and optional `doc_routing` in `SAGEKIT_CONFIG.json`.
- Read the configured paths; use `docs/ACTIVE_CONTEXT.md` and
  `docs/DOC_ROUTING.md` only as legacy defaults.
- Then follow the configured routing authority for the narrow task read set.
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
- Apply `docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-003` for lifecycle,
  authorization, fallback, evidence, credentials, installation, and mutation.
- Apply `docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-007` before generic routing;
  repeat an active prohibition and descendant inheritance in every child
  launch packet.
- Codex GPT-5.6 launch guard when active: Superpowers is
  `DISABLED_BY_RUNTIME_POLICY`; controllers and descendants must not read,
  invoke, route to, reference, or delegate to Superpowers, and
  `using-superpowers` remains disabled. Use the canonical model-native fallback.
- Runtime/model family:
- Runtime override ID/status:
- Prohibited actions/capabilities:
- Native execution method when an adapter is disabled or unavailable:
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
- Apply `docs/SAGE_CORE.md#sage-auth-009`; record the exact approved
  phase/task/lane boundary and every gate that remains closed.
- Stop on local shared-file or resource-lock conflicts and failed required
  evidence.

Return format:
- Use `docs/templates/LANE_PACKET_TEMPLATE.md` for lane work.
- Use `docs/agent/HANDOFF_TEMPLATE.md` for phase or session handoff.
- Report memory maintenance for the configured `ACTIVE_CONTEXT` and configured
  document-routing authority.
```
