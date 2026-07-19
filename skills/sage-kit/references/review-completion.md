# SAGE-Kit Review And Completion

Review topology, finding severity, corrective re-review scope, evidence reuse,
and convergence are canonical in `docs/agent/EXECUTION_ECONOMY.md`. C0
record-only corrections receive targeted consistency verification rather than
implementation re-review. A local review count produces `HANDOFF_READY`;
`BLOCKED` requires an unavailable dependency or two no-progress rounds for the
same root cause.

Use this reference for reviews, handoff, completion reports, milestone ledgers,
memory maintenance, closeout, commit, or push.

## Thin Document Review

For `thin-v1`, review `SAGE_PROJECT.json`, the active
`MILESTONE_MANIFEST.json`, and selected phase manifests as structured authority.
Confirm their contract/profile references and digests, dependency integrity,
path containment, approval/permission consistency, acceptance, state, and
evidence references. Generic governance prose is not required in the project
manifest because it is resolved from the pinned contract.

Accepted historical legacy documents remain immutable and are not reviewed
against thin fields. An active milestone that mixes `legacy-markdown` and
`thin-v1`, lacks model authority, or selects an unknown profile must not fall
back and cannot receive a completion verdict.

## Review Stance

Review for:

- spec compliance;
- milestone granularity and primary capability alignment;
- file boundary drift;
- missing tests or smoke;
- unproven runtime claims;
- approval gate violations;
- hidden fallback behavior;
- stale active context;
- ledger or closeout gaps;
- ignored specialist capabilities when the runtime exposed relevant skills,
  plugins, connectors, or tools;
- external capability output treated as gate completion instead of evidence;
- adapter authorization, fallback, or evidence mapping missing when an external
  capability was selected;
- external plans that were not mapped into tracked SAGE-Kit docs;
- unauthorized or unsafe worktree isolation;
- incomplete task-dispatch records or failed validator results when Task
  Dispatch Profile is active;
- stale task-dispatch truth when task, evidence, board, ledger, run, lease,
  authority, closure note, or next action disagree;
- session orchestration packet completeness when used.
- Coder Controller self-executed broad milestone work instead of staying within
  the execution packet's self-execution policy;
- Wave Execution was claimed without lane independence, exclusive writable
  files, runtime ownership, integration owner, or serial gate protection.
- governance level was recorded without a matching permission mode;
- read-only review was treated as closure after required corrections were
  found;
- `Corrective Packet Required: yes` appeared without a corrective packet,
  Project Manager decision request, blocker, or waiver path.

Lead with blocking findings before summaries.

## Severity And Acceptance

Use severity to decide whether Project Manager acceptance is blocked:

- Open `P0` and `P1` findings block acceptance. They may close only after the
  issue is fixed or explicitly reclassified with evidence by the required
  authority.
- `P2` findings block acceptance only when they involve authority conflict,
  false-green risk, approval gates, security boundaries,
  validator/gate-ready requirements, source authority, or evidence integrity.
- Ordinary documentation consistency `P2` findings may be accepted with
  concerns or auto-corrected when they do not affect authority, gate, security,
  validator, or evidence boundaries.
- `P3` findings do not block acceptance. Record them as concerns, follow-up, or
  cleanup.

## Corrective Convergence

Do not mark work `BLOCKED` merely because a fixed corrective round count was
reached.

Continue automatic correction only inside an authorized corrective packet or
boundary while findings are decreasing in count or severity, scope is not
expanding, no blocking approval gate is bypassed, and no new authority,
false-green, approval-gate, security, validator/gate-ready, source-authority, or
evidence-integrity risk appears.

Return `BLOCKED` when the same root cause has no material progress for two
consecutive corrective rounds, required evidence or authority is missing, the
fix exceeds the approved boundary, or no authorized path can make progress. Use
`NEEDS_CORRECTION` with `PM_DECISION_REQUIRED` closure/status when Project
Manager judgment is needed.

Use the Deterministic Closure eligibility, owner separation, evidence, State
Truth, receipt, verdict-finalization, and reject/fallback contract in
`docs/agent/SESSION_ORCHESTRATION.md`. It is the authoritative choice between
strict no-review closure, targeted re-review, and full affected review lanes;
Project Manager acceptance remains pending after Final Review finalization.

## Completion Report Must Name

- scope implemented;
- governance level;
- permission mode;
- controls enabled, and controls not enabled when the control was considered or
  relevant;
- upgrade triggers when relevant, or a `none` note when the governance decision
  needs an explicit record;
- stopped worker or controller decision status when applicable;
- Coder execution mode and self-execution policy status when Session
  Orchestration is used;
- wave readiness decision when Wave Execution or parallel phases are used;
- corrective closure status when a review finds required corrections;
- files changed;
- contract evidence;
- specialist capabilities used when relevant;
- capability adapters selected, authorization level, fallback, and evidence
  mapping when an adapter was selected, considered, unavailable, or produced
  evidence;
- superpowers skills used when available and relevant;
- external capability boundary and evidence produced when external capability
  output was used;
- external planning output destination when external planning was used;
- tests run;
- runtime smoke or non-applicability reason;
- approval gates;
- task-dispatch validator result when the profile is active for the current
  task, phase, or gate;
- task-dispatch state truth when task/evidence records, board, ledger, run,
  lease, authority, blocker, closure note, or next action changed;
- security or data hygiene checks;
- memory maintenance;
- skipped checks;
- remaining gaps;
- handoff or next action.

Skipped blocking gates make the work `BLOCKED` or `HANDOFF`, not `DONE`.

## Task Dispatch State Truth Review

When Task Dispatch Profile is active, review the structured records as current
state, not as decorative evidence.

State Truth conflicts block closure until the responsible surface owners
reconcile them under matching write/corrective authority. A deterministic
receipt is reachable only after task, evidence, board, ledger, run, lease,
authority, blocker, review-result, and next-action values agree. The Closure
Receipt Owner verifies that agreement and may write only its own review
packet/output; it does not gain mutation authority over those surfaces.

Flag as blocking when:

- `task.yaml` claims active run, lease, or implementation authority while
  closure notes still say planning-only, future, waiting, or no implementation;
- `evidence.yaml` keeps placeholder reasons, next action, or artifacts after
  active evidence collection began;
- dispatch board, task record, evidence record, milestone ledger, or result
  packet disagree about status, blockers, authority, lease, review result, or
  next action;
- old STOP, waiting, or future decisions remain active after accepted authority
  unlocked them;
- gate-ready or next-phase movement is requested before review result is
  recorded and active leases are released, renewed, or intentionally carried.

Ordinary wording cleanup can be P2/P3 only after the current truth is
unambiguous. State truth conflicts are false-green, authority, or evidence
integrity risks.

## Memory Maintenance

Maintain `ACTIVE_CONTEXT.md` as a current-state snapshot:

- update current milestone, phase, objective, blocker, and next action;
- replace stale facts;
- delete completed or irrelevant facts;
- move evidence and historical detail to ledger, phase doc, completion report,
  closeout, or handoff.

Update `DOC_ROUTING.md` only when routing policy, document paths, ownership
boundaries, or archive policy changed.

Direct edits to `ACTIVE_CONTEXT.md` or `DOC_ROUTING.md` require permission mode
and ownership. If either is missing, return a `Memory Update Proposal` or record
an explicit no-change note.

If neither file needs an edit, record:

```text
Memory Maintenance: ACTIVE_CONTEXT no change; DOC_ROUTING no change.
```

## Milestone Closeout

Write or update `MILESTONE_CLOSEOUT.md` only when closing a milestone.

The closeout is a compact historical outcome index. It records:

- outcome;
- source documents;
- what shipped;
- what changed;
- key decisions;
- verification summary;
- approval gates;
- known gaps;
- follow-up milestones;
- superseded assumptions.

Do not copy raw logs, full evidence tables, or full phase reports into the
closeout. Link to evidence.

## Session Orchestration Review

When Session Orchestration is used:

- Project Manager structural gate checks packet completeness only.
- Final Review verifies independently and returns a verdict.
- Final Review records its permission mode and preserves write, corrective,
  submit, and cleanup authority boundaries.
- Final Review checks whether Coder self review and capability routing were
  performed.
- Final Review checks whether selected superpowers skills, if available and
  relevant, stayed inside SAGE-Kit scope, locks, gates, and evidence
  requirements.
- Final Review treats external skill, plugin, connector, or tool completion as
  evidence to verify, not as SAGE-Kit acceptance.
- Final Review checks whether Worktree Isolation was authorized, mapped,
  integrated, and safe when used.
- Final Review reassesses whether the milestone execution shape was safe:
  serial, waves inside phases, or parallel phases.
- Final Review checks whether Coder self-execution was allowed, narrow, and
  independently verified. Broad self-executed milestone implementation is a
  review risk and may require correction or Project Manager decision.
- Final Review cannot accept the milestone directly.
- Final Review classifies each required correction as `AUTO_CORRECTIVE`,
  `PM_DECISION`, `BLOCKED`, or `DEFER`.
- If Final Review is read-only, it must return a packet-only corrective handoff,
  Project Manager decision request, blocker, or waiver path instead of editing.
- If corrective execution is authorized, Final Review may open a bounded
  corrective round through separately authorized corrective workers and must
  require verification plus re-review or a valid reviewer-authored
  Deterministic Closure receipt. It must not edit implementation or corrective
  files itself.
- Corrective closure must produce independent re-review evidence or a valid
  `AUTO_CLOSED_BY_PREDICATE` receipt followed by
  `VERDICT_FINALIZED_FROM_RECEIPT` before a precommitted Final Review verdict is
  ready for Project Manager decision.
- Outside strict Deterministic Closure, rerun affected review workers, review
  subagents, or validation lanes when the original review used them, the fix
  touches behavior, contracts, runtime, shared files, gates, or the regression
  surface is unclear.
- Use targeted status/evidence re-review for ledger, evidence, status, closeout,
  or packet-only correction that is not eligible for strict Deterministic
  Closure and does not change semantic, permission, source authority,
  information architecture, contract, runtime, security, gate, validator, or
  required-evidence meaning.
- Corrective packets must name findings, classification, files, commands,
  permission mode, and stop conditions.
- Continue correction under the convergence rule only inside an authorized
  corrective packet or boundary when findings or severity are still decreasing,
  scope is stable, no blocking approval gate is bypassed, and no new authority,
  false-green, approval-gate, security, validator/gate-ready, source-authority,
  or evidence-integrity risk appears. In Final Review, use `NEEDS_CORRECTION`
  with `PM_DECISION_REQUIRED` closure/status when Project Manager judgment is
  needed; return `BLOCKED` only when no authorized path can make progress,
  required evidence or authority is missing, or the approved boundary would be
  exceeded. Use `HANDOFF` only as a milestone/session handoff target, not as a
  Final Review verdict.

## Submit Gate

Before commit, push, PR, or final handoff:

1. Check change-control state.
2. Review changed and staged files.
3. Scan for secrets or local data when applicable.
4. Run required verification.
   Treat successful line-ending notices, such as `git diff --check` reporting
   LF-to-CRLF conversion with exit code `0`, as non-blocking platform warnings.
   Treat trailing whitespace, conflict markers, malformed patches, or any
   non-zero verification exit as blocking.
5. Confirm completion report, ledger, and memory maintenance are current.
6. Confirm worktree submit and cleanup authority when worktrees were used.
7. Confirm Task Dispatch validator success when the profile is active and the
   gate requires it.
8. Confirm State Truth Reconciliation when task/evidence records, board,
   ledger, run, lease, authority, blocker, review result, or next action
   changed. Confirm each correction was made by the named owner with suitable
   authority, or was returned as an update proposal, corrective packet, or
   handoff.
9. For planning package closeout, confirm the diff is planning-only and that
   Planning Author, Planning Review, Targeted Fix, Closure Receipt Owner,
   Verdict Finalization, Targeted Re-Review when selected, Closeout/Status, and
   Submit Controller authority stayed separate. Strict closure still follows
   `docs/agent/SESSION_ORCHESTRATION.md`.
10. Commit or hand off only intended scope.
