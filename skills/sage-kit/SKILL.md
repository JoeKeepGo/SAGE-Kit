---
name: sage-kit
description: "Use when SAGE-Kit is explicit: the user invokes $sage-kit, asks to adopt/bootstrap SAGE-Kit, or references SAGE-Kit-owned docs or constructs such as docs/ACTIVE_CONTEXT.md, docs/DOC_ROUTING.md, docs/agent/AGENT_HARNESS.md, SAGE-Kit Governance Levels, Authority Matrix, Strict Mode, Wave Execution, Session Orchestration, Worktree Isolation, Task Dispatch Profile, or Capability Adapters. Do not use for generic milestones, gates, phase docs, planning, review, or debugging unless tied to SAGE-Kit."
disable-model-invocation: true
---

# SAGE-Kit

Use this Skill only as the activation and routing layer for SAGE-Kit. It does
not replace the project's SPEC, execution authority, approval gates,
permissions, scope, evidence, or acceptance owner.

## Codex GPT-5.6 Pre-Load Guard

Before capability discovery or routing, detect the runtime and model family.
For a Codex session running any GPT-5.6 family model, apply the
`Codex GPT-5.6 Runtime Override`: Superpowers is
`DISABLED_BY_RUNTIME_POLICY`. Root and all descendants must not read, invoke,
route to, reference, or delegate to Superpowers. `using-superpowers` is
explicitly disabled even when its metadata describes invocation as mandatory.

All descendants inherit the override. Every subagent launch packet must
explicitly repeat `DISABLED_BY_RUNTIME_POLICY` and the `using-superpowers`
prohibition; every descendant authorized to delegate must repeat both in every
child packet, including after compaction, handoff, or resume. Use model-native
brainstorming, planning, test-driven implementation, systematic debugging,
subagent orchestration, review, verification, and branch completion as native
behaviors, not similarly named skill invocations. The disabled adapter is not a
capability gap, fallback trigger, blocker, or reason to stop.

This override applies only to Codex GPT-5.6 family sessions. Other model and
host mappings keep their normal adapter policy. The canonical contract is
`docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-007`.

<a id="sage-adp-002"></a>
## Activation And Authority

Activate only when the user explicitly invokes SAGE-Kit, asks to adopt or
bootstrap it, or the active repository routes work through SAGE-Kit-owned
constructs. If the repository is not SAGE-Kit governed and adoption was not
requested, do not impose SAGE-Kit.

Installed Skill is not project authority. Project-owned SPEC and configuration,
plus any explicitly named Project Manager decision, remain authoritative. The
Skill interprets and routes that authority; it must not manufacture missing
scope, permission, gates, file ownership, evidence, fallback, or completion.
Authority precedence and completion ownership remain canonical at
`docs/SAGE_CORE.md#sage-auth-001`; mutation and approval boundaries remain at
`docs/SAGE_CORE.md#sage-auth-009`.

For a governed project:

1. Resolve the repository/worktree boundary and current change-control state.
2. Resolve the configured active context and routing authority. Legacy projects
   may use `docs/ACTIVE_CONTEXT.md` and `docs/DOC_ROUTING.md`; package-bound
   projects may route from machine authority and the active SPEC.
3. If `SAGE_PROJECT.json` exists, validate its contract pin and
   `execution_document_model`, then load only the active `legacy-markdown` or
   `thin-v1` execution authority selected for this task.
4. Apply source precedence and scope classification from
   `docs/agent/SPEC_SOURCE_CONTRACT.md#sage-ctx-001` and
   `docs/agent/SPEC_SOURCE_CONTRACT.md#sage-ctx-002`.
5. Before writable work, resolve allowed, read-only, and forbidden files;
   approval gates; verification; and stop conditions.

A missing optional legacy routing file is not itself a blocker. Missing,
unreadable, contradictory, or unauthorized active authority fails closed before
editing; report the precise gap rather than guessing.

## Proportional Governance

Select the lightest level that preserves the active authority and risk:

- **Light** for bounded, low-risk work without delegation or closed gates.
- **Standard** for ordinary multi-file implementation, review, or verification.
- **Heavy** for controller work, delegation, corrective authority,
  environment writes, submit operations, or elevated risk.

Resolve the matching read-only, write, corrective, environment-write, or submit
permission mode from `docs/agent/GOVERNANCE_LEVELS.md`. A Heavy controller may
delegate Light or Standard work, but delegation never transfers broader
authority than the launch packet states.

## Narrow Task Routing

Read only the canonical owners and host references needed by the current task;
do not load the whole SAGE-Kit or every Skill body by default.

| Situation | Route |
|---|---|
| Adoption or bootstrap | `references/adoption.md` |
| Milestone, roadmap, or phase planning | `references/planning.md` |
| Implementation, debugging, refactor, or bounded workers | Relevant sections of `references/execution.md` |
| Review, handoff, completion, or closeout | `references/review-completion.md` |
| Context loading and controller launch | `docs/agent/AGENT_HARNESS.md#sage-ctx-005` and `docs/agent/AGENT_HARNESS.md#sage-auth-010` |
| Execution economy, verification, convergence, re-review, or normalization | Stable `sage-loop-*` anchors in `docs/agent/EXECUTION_ECONOMY.md` |
| Deterministic Closure | `docs/agent/SESSION_ORCHESTRATION.md#sage-loop-011` |
| Graph admission | `docs/SAGE_CORE.md#sage-grf-001` |
| Wave execution | `docs/agent/WAVE_EXECUTION.md#sage-grf-002` |
| Capability selection and lifecycle | `docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-003` |
| Runtime adapter override | `docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-007` |
| Checkpoint or resume | `docs/agent/CONTINUITY_PROTOCOL.md` plus runtime resume state |
| Validation compatibility | `docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md` |

Load Advanced Execution Economy only for relevant Heavy, corrective, or final
verification work. Preserve accepted history: never infer a new contract,
retrofit current fields, or try multiple validators until one passes.

For host-specific invocation mapping, route only when that host is active:

- Kimi Work or explicitly supported Kimi Code: `references/kimi-runtime.md`
- OpenCode: `references/opencode.md`
- Claude Code: `references/claude.md`

## Capability Coexistence

SAGE-Kit governs boundaries; it does not monopolize tool selection. Use exposed
metadata to select task-relevant specialist skills, plugins, MCP tools, CI,
browser, database, frontend, document, and review capabilities. Load only the
selected instructions. External capability use remains inside project
authority and the lifecycle at
`docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-003`.

Optional capability absence does not become a false product blocker when a safe
native path exists. Fallback must preserve scope, gates, authority,
verification, review, and evidence. External output is evidence input only; it
does not declare `DONE`, pass a gate, or grant Project Manager acceptance.

Capability discovery is metadata-only or read-only by default. Installation,
hooks, environment writes, credentials, external mutation, destructive action,
or submit operations require matching explicit authority. SAGE-Kit does not
silently install or reconfigure capabilities.

## Delegation And Stop Boundary

Every delegated lane must name its objective, authority references, governance
and permission mode, allowed/read-only/forbidden files, applicable capabilities,
commands, evidence, fallback, and stop conditions. Descendants inherit all
forbidden paths and runtime overrides. Parallel writers require disjoint paths
and an integration owner; shared authority/state files remain controller-owned.

Host enforcement must be described honestly. Managed execution may report
`HARD` or `MANAGED` containment through its platform adapter, while arbitrary
direct commands that bypass the managed runtime remain a `SOFT` guarantee.
For `conservative-host-v1` resource governance, use
`docs/agent/HOST_RESOURCE_GOVERNANCE.md` for workspace verification, managed
execution, leases, process trees, and limitations.

Stop and return the narrow authority gap or handoff when required authority is
missing, a closed gate would be crossed, scope or permissions would expand,
required evidence cannot be produced, or a destructive/environment/submit
action lacks approval. Do not convert an optional adapter absence into `BLOCKED`
when an equivalent safe native workflow exists.

For planning-only closeout, preserve separate Planning Author, Planning Review,
Targeted Fix, Closure Verification (`strict Deterministic Closure` or `Targeted
Re-Review`), Closeout/Status, and Submit Controller authority. Under
`docs/agent/SESSION_ORCHESTRATION.md#sage-loop-011`, only Final Review may record
`VERDICT_FINALIZED_FROM_RECEIPT`; that is not milestone acceptance.

At handoff, report the authority used, changed files, focused verification,
review evidence, skipped checks, blockers, deferred items, and next action.
