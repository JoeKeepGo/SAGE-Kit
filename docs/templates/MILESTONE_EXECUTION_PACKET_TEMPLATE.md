# Milestone Execution Packet Template

Use this packet from Project Manager Controller to Coder Controller.

Level/permission and submit semantics are canonical at
`docs/agent/GOVERNANCE_LEVELS.md#sage-auth-004` and
`docs/agent/GOVERNANCE_LEVELS.md#sage-auth-007`. This packet retains every
project-instance field that assigns those boundaries to controllers and workers.

```markdown
Milestone:

Objective:

Primary Capability:

Source Docs:
- Active context:
- Document routing:
- Entry gate:
- Milestone ledger:
- Capability map:
- Phase docs:
- Quality gates:
- Approval gates:

Execution Mode:
- `Phase Execution`, `Wave Execution`, or `Session Orchestration`

Governance:
- Controller level: `Light`, `Standard`, or `Heavy`
- Why this level:
- Controls Enabled:
- Controls Not Enabled:

Permission Mode:
- Coder Controller mode: `READ_ONLY_REVIEW` or `WRITE_AUTHORIZED`
- Why this mode:
- Controller-owned writable files only:
- Worker-owned implementation files: `<Coder Controller must not edit>`
- Project Manager final decision authority: `<separate PM decision record; not Final Review acceptance>`
- Final Review mode: `READ_ONLY_REVIEW`
- Final Review corrective orchestration authorized: `<yes/no; does not grant controller writes>`
- Corrective convergence budget:
- Preauthorized Convergence Window active: `<yes/no; opt-in>`
- Convergence authority ID and digest:
- Stable execution scope:
- Approved root-cause family:
- Component-aware allowed paths:
- Approved invariant:
- Semantic change policy: `implementation-preserving-only`
- Targeted review requirement:
- Convergence stop conditions:
- Approval source:
- Environment-write authority:
- Initial submit/commit/push/cleanup authority: `none`
- Post-verdict submit/cleanup grant: `<separate grant required; not issued here>`
- Permission upgrade requires:

Execution Shape:
- `SERIAL`, `PARALLEL_WITH_WAVES`, `PARALLEL_PHASES`, or `STOP_FOR_PM`
- Canonical Graph admission and execution-shape semantics:
  `docs/SAGE_CORE.md#sage-grf-001` and
  `docs/agent/WAVE_EXECUTION.md#sage-grf-002`

Dependency DAG:
- `<phase/lane>` depends on `<phase/lane or none>` because `<contract/evidence/gate>`

Parallel candidates:
- `<phases or phase-internal lanes with disjoint ownership>`

Serial barriers:
- `<shared file, gate, runtime owner, integration point, or dependency>`

Parallelism Rationale:
- `<project-specific dependency, ownership, gate, runtime constraint, or reason
  one bounded loop is sufficient under the canonical rules>`

Wave Readiness:
- Useful parallel lanes:
- Exclusive writable files:
- Shared files kept serial:
- Shared-file controller/integration owner:
- Contracts frozen before writable work:
- Runtime ownership:
- Validation lanes:
- Integration owner:
- Conflict stop conditions:
- Decision: `SERIAL`, `PARALLEL_WITH_WAVES`, `PARALLEL_PHASES`, or `STOP_FOR_PM`

Controller Launch Guidance:
- Use a Compact Controller Launch Envelope when the controller can read this
  packet and its authority references locally.
- Include role and objective, authority references, baseline or entry
  condition, permission mode, PM authority deltas, terminal state, and only
  necessary prohibitions or stop conditions.
- The launch envelope must not duplicate the execution packet.
- 40-80 lines is a guideline, not a correctness gate.
- Worker prompts remain explicit and carry their exact files, tests, evidence,
  runtime ownership, and stop conditions.
- PM authority deltas in the envelope must record authority ID, source,
  priority, and reconciliation destination.
- Classify launch deltas and authority gaps under
  `docs/agent/AGENT_HARNESS.md#sage-auth-010`. This packet retains the referenced
  authority, field values, and reconciliation destination used by that rule.

Coder Controller Integration Edit Policy:
- Direct controller edits allowed: `<yes/no>`
- Allowed only for: `<named controller-owned integration or packet files/n/a>`
- Maximum files or surfaces:
- Worker dispatch required for:
- Direct edits forbidden when: `<any file is worker-owned>`
- Result packet must explain skipped worker dispatch: `<yes/no>`

Worktree Isolation Policy:
- Allowed mode: `NONE`, `MILESTONE_WORKTREE`, `PHASE_WORKTREE`, `LANE_WORKTREE`, or `REVIEW_WORKTREE`
- Maximum worktree count:
- Branch naming:
- Worktree naming:
- Base branch or commit:
- Allowed phases or lanes:
- Shared files that remain serial:
- Runtime ownership:
- Integration owner:
- Review worktree creator: `<Coder or named Workspace/Environment Controller; created before review handoff>`
- Post-verdict submit owner:
- Post-verdict cleanup policy:
- Forbidden scenarios:

Task Dispatch Policy:
- Active: `<yes/no>`
- Dispatch board:
- Task record root:
- Evidence record root:
- Required L0-L4 levels:
- Resource lock policy:
- Run/Attempt/Lease policy:
- Validator command:
- Validator required before: `<task gate/phase gate/milestone gate/not an acceptance gate>`
- Gate-ready validator required when active: `<yes/no; yes for task/phase/milestone acceptance>`
- If validator is not required, name the non-acceptance task or gate:
- Task/evidence update owner:

Capability Discovery:
- Adapter contract: `docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-003`
- Runtime override contract: `docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-007`
- Capability registry checked: `<yes/no/not available>`
- Runtime/model family:
- Execution method owner: `<MODEL_NATIVE / ADAPTER>`
- Codex GPT-5.6 Runtime Override: `<active/inactive>`
- Superpowers policy: `<DISABLED_BY_RUNTIME_POLICY / optional / selected>`
- `using-superpowers` policy: `<disabled for Codex GPT-5.6 / runtime default>`
- Prohibited adapter actions when override is active: `<read/invoke/route/reference/delegate>`
- Native workflow coverage: `<brainstorming, planning, TDD, debugging, subagent orchestration, review, verification, branch completion; behaviors, not skill invocations>`
- Descendant policy inheritance: `<explicitly repeat the status and using-superpowers prohibition in every child launch packet>`
- SAGE-Kit boundary: `<scope/files/gates/locks/evidence controlled by this packet>`
- Selected skills:
- Selected superpowers skills: `<skills or N/A when DISABLED_BY_RUNTIME_POLICY>`
- superpowers boundary:
- Selected plugins/connectors:
- Selected tools:
- Selected capability adapters:
- Adapter authorization levels:
- Adapter fallback policy:
- Forbidden capabilities:
- Worker must check own capability list: `<yes/no>`
- Fallback if capability is missing:
- External planning output destination:
- External capability completion counts as: `execution evidence only`

Candidate Snapshot Policy:
- Snapshot mode: `<clean-head / working-tree>`
- Working-tree snapshot authority (`snapshot_authority` API/config field): `<authority id/digest or n/a>`
- Expected staged state:
- Expected unstaged state:
- Expected non-ignored untracked scope:
- Dirty submodule policy: `<fail closed>`
- Snapshot assessment points: `<before and after final verification nodes>`
- Candidate snapshot does not grant commit/submit/acceptance authority: `<confirmed>`

Allowed Scope:

Non-Goals:

Phase Plan:

| Phase | Governance Level | Permission Mode | Objective | Owner | Contract | Allowed Files | Read-Only Files | Forbidden Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `<phase>` | `Light, Standard, or Heavy` | `<mode>` | `<objective>` | `<owner>` | `<contract or none>` | `<files>` | `<files>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |

Worker Governance:

| Worker Or Lane | Scope | Governance Level | Permission Mode | Controls Enabled | Controls Not Enabled | Upgrade Triggers | Stop For Controller |
|---|---|---|---|---|---|---|---|
| `<worker>` | `<scope>` | `Light, Standard, or Heavy` | `<mode>` | `<controls>` | `<controls or none>` | `<triggers or none>` | `<conditions>` |

Shared Files:

| File | Owner | Rule |
|---|---|---|
| `<file>` | `<named controller or integration owner>` | `<serial-only; workers propose patches>` |

Worker Delegation Rules:
- Controller role:
- Controller permission mode:
- Worker types allowed:
- Worker permission modes:
- Coder direct integration edits allowed:
- Controller-owned edit criteria:
- Parallel lanes allowed:
- Parallel phases allowed:
- Worktree isolation allowed:
- Worker output format:
- Worker stop conditions:
- Integration owner:
- Startup Context Controller:
- Startup-context worker rule: `proposal only`
- Required capability routing:
- Continuous execution allowed only within approved phase/task/lane boundaries:

Review Expectations:

Convergence Review Rules:
- Semantic-preserving implementation corrective may continue only inside an
  explicit Preauthorized Convergence Window.
- Policy-changing semantic change, scope/path/invariant expansion, new gate or
  permission, consumer mutation, or test/security/evidence weakening returns
  `HANDOFF_READY`.
- Security, authority, containment, validator, package, or release-gate
  implementation corrective requires targeted review closure.
- Finding or severity convergence is not stopped by a fixed candidate count;
  two consecutive no-progress rounds for the same root cause return `BLOCKED`.
- Every successor has a new fingerprint and independent one-time final
  verification counters.
- The window is not an unlimited retry mechanism. Transient rerun is separate
  from code corrective; deterministic failures are not rerun speculatively.

Approval Gates:

Runtime Ownership:

Memory Maintenance Requirements:

Ledger Requirements:

Closeout Requirement:

Stop Conditions:

Expected Coder Output:
- `docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md`
```
