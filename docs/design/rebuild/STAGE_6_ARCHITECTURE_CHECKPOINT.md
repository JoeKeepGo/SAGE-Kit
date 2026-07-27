# Stage 6 Architecture Checkpoint

## 1. Executive Verdict

**Verdict: `STAGE_6_READY_FOR_ACCEPTANCE`.**

This is a recorder-only architecture checkpoint for the frozen Stage 6
product integration at `9b5258aa203b51c130b5e36647e0078bb25885d9` on
`codex/rebuild-stage6-graph-evolution`. It records the accepted Stage 6A/B/C
proposal, convergence, and acceptance architecture; its integrated lineage;
the five historical corrective findings and their closure evidence; and the
focused test surface already present in that lineage.

It is not a new review, product acceptance, merge approval, release approval,
or publication approval. Stage 7 has not started.

## 2. Frozen Baseline And Recorder Scope

| Item | Frozen value |
|---|---|
| Worktree | `D:\Projects\SPEC Framework\.worktrees\rebuild-stage6-checkpoint` |
| Checkpoint branch | `codex/rebuild-stage6-architecture-checkpoint` |
| Final product branch | `codex/rebuild-stage6-graph-evolution` |
| Final product HEAD | `9b5258aa203b51c130b5e36647e0078bb25885d9` |
| Required checkpoint parent | `9b5258aa203b51c130b5e36647e0078bb25885d9` |
| Parent subject | `test: bind stage5 ownership oracle to content` |
| Stage 5 architecture parent | `fdeb91cdc3a013776544769ae61aeda28d844f92` |
| Checkpoint change | This report only |
| Write allowlist | `docs/design/rebuild/STAGE_6_ARCHITECTURE_CHECKPOINT.md` |
| Recorder authority | Record frozen evidence; do not perform a new review |

The checkpoint adds no product, contract, resolver, test, runtime, CLI,
scheduler, runtime executor, or dynamic mutation behavior. It does not modify
the Stage 6 integration. Its only permitted write is this record.

## 3. Stage 6 A/B/C Architecture

### Stage 6A: Contract And Proposal

Graph Evolution Contract v1 introduces closed, bounded Request,
Preauthorization, Proposal, Acceptance, Result, and Error documents under
`docs/contracts/graph-evolution/v1/`, with byte-identical packaged mirrors.
It reuses the existing Graph Contract v1 owner and frozen Evidence Lineage v1
resource rather than copying their semantics. The six closed operations are
`ADD_CORRECTIVE`, `ADD_VERIFICATION`, `ADD_INVESTIGATION`, `SPLIT_PENDING`,
`DISABLE_OPTIONAL_PENDING`, and `NO_CHANGE`.

`build_graph_evolution_proposal(...)` accepts supplied snapshots, validates
the parent Graph and closed preauthorization, binds the owner-produced Stage 5
lineage digest, and produces one immutable proposal/result or bounded Error.
It is not an apply path: no proposal grants authority, executes a node,
creates or activates a Graph generation, writes state, or performs dynamic
mutation.

### Stage 6B: Convergence

`evaluate_graph_evolution_convergence(...)` adapts the existing convergence
authority and produces an immutable decision bound to one bounded observation.
Its closed outcomes are `CONTINUE`, `HANDOFF`, `BLOCKED_NO_PROGRESS`,
`PM_DECISION_REQUIRED`, and `NO_CHANGE_ACCEPTED`. It preserves the existing
two-round no-progress behavior, requires closed targeted review and bound
evidence for no-change acceptance, and routes worsening findings to a Project
Manager decision. It neither changes a Graph nor grants authority.

### Stage 6C: Acceptance

`resolve_graph_evolution_acceptance(...)` snapshots supplied sources, rebuilds
the inert proposal, evaluates convergence, validates the evaluator receipt and
independence boundary, and returns an immutable resolution. Its closed
outcomes are `AUTO_ACCEPTED`, `PM_DECISION_REQUIRED`, `PM_ACCEPTED`,
`NO_CHANGE_ACCEPTED`, `REJECTED`, and `BLOCKED_NO_PROGRESS`.

Acceptance remains a digest-bound decision record. A proposal or evaluator
receipt alone cannot confer Project Manager authority, and an independently
authorized host retains any future apply responsibility. The resolver has no
runtime store access, scheduler, runtime executor, process launch, CLI,
network, filesystem traversal, or Graph-application behavior.

## 4. Final Integration Lineage

The exact Stage 6 lineage from the Stage 5 checkpoint to the final product
HEAD is:

1. `1410f8e` `feat: add graph evolution contract v1`
2. `0b4e1d8` `fix: enforce graph evolution decision chain`
3. `0175dbe` `feat: add pure graph evolution proposals`
4. `5b187b4` `feat: add graph evolution convergence decisions`
5. `610288b` `feat: add graph evolution acceptance decisions`
6. `a8fa0a0` `test: stabilize rebuild stage ownership oracles`
7. `bdf325f` `fix: separate evolution authority and evaluator`
8. `c29378f` `fix: bind evolution proposals to lineage evidence`
9. `c17effa` `fix: preserve evolution gates and verifier semantics`
10. `3e4c611` `test: bind evolution acceptance lineage fixtures`
11. `a6bb352` `fix: separate evolution evaluator from PM authority`
12. `9b5258a` `test: bind stage5 ownership oracle to content`

The final delta from `fdeb91c` to `9b5258a` is exactly 26 files: seven
canonical Graph Evolution resources, seven packaged mirrors, four Stage 6
pure modules, the Stage 5 evidence binding update, a fixed Stage 5 owner
content fixture, and seven focused test files. No CLI, scheduler, runtime
executor, or runtime-state writer is in that manifest.

## 5. Historical Findings And Closed Evidence

This section records the original five historical corrective findings. It
does not perform or add a review.

| Historical finding | Closure evidence | Status |
|---|---|---|
| Fresh-context evaluation could overlap the proposer, acceptance evaluator, or authority principal. | `bdf325f` makes the fresh evaluator external to the proposer, acceptor, and both authority identities; it also rejects alias-equivalent identities and requires distinct assignment digests. `test_fresh_evaluator_must_be_external_to_acceptor`, `test_fresh_evaluator_aliasing_pm_authority_fails_closed`, and `test_external_fresh_evaluator_is_bound_to_assignment_digests` cover the boundary. | `CLOSED` |
| A request could carry an arbitrary Stage 5 lineage digest without proving it came from the owner-produced lineage input/result pair. | `c29378f` adds a domain-separated Evidence Lineage binding digest to resolver-created outcomes and requires exact reuse by the proposal builder. `test_request_must_reuse_owner_produced_stage5_binding_digest` rejects substituted and unbound outcomes. `3e4c611` replaces fabricated acceptance fixtures with resolver-produced lineage fixtures and rebinding. | `CLOSED` |
| Delta validation could weaken verification meaning or rewrite parent human-gate joins. | `c17effa` requires a non-optional `Verifier` with `READ_ONLY_REVIEW` and an explicit verification verifier for `ADD_VERIFICATION`; it preserves every parent human-gate join byte-for-byte for `SPLIT_PENDING`. `test_add_verification_rejects_optional_investigation_and_verifier_attacks` and `test_split_pending_cannot_rewrite_or_enter_parent_human_gates` reject the attacks, while `test_delta_hardening_preserves_all_six_legal_operations` preserves the legal set. | `CLOSED` |
| The preauthorized contract acceptance evaluator could be the Project Manager authority even when the receipt named an external evaluator. | `a6bb352` rejects the preauthorization evaluator when it normalizes to either authority principal. `test_pm_authority_cannot_be_contract_evaluator_with_external_receipt` asserts the failure-closed result. | `CLOSED` |
| The Stage 5 ownership oracle checked that 15 owner paths existed but did not bind their content. | `9b5258a` adds `tests/fixtures/stage5_owner_content_manifest_v1.json` and hashes every Stage 5 owner file. `test_stage5_owner_content_manifest_binds_every_owner_file` checks exact membership and all file digests. | `CLOSED` |

The earlier decision-chain hardening in `0b4e1d8` is also retained in the
final lineage: all five documents are revalidated and digest-bound to the
parent Graph, authority scope, budgets, and operation-specific inert target
delta. It is not an additional sixth historical finding in this record.

## 6. Focused Test Evidence

The final lineage contains these focused test modules and static test counts:

| Focused surface | Tests present at frozen HEAD |
|---|---:|
| `tests/unit/test_graph_evolution_contract_v1.py` | 29 |
| `tests/unit/test_graph_evolution_proposal.py` | 7 |
| `tests/unit/test_graph_evolution_convergence.py` | 11 |
| `tests/unit/test_graph_evolution_acceptance.py` | 12 |
| `tests/unit/test_evidence_lineage.py` | 15 |
| `tests/unit/test_evidence_lineage_contract_v1.py` | 23 |

The Stage 6-focused modules exercise closed schemas and mirrors, all six
operations, decision-chain binding, operation-specific delta rejection,
proposal immutability, lineage binding, convergence/no-progress behavior,
acceptance/evaluator separation, source snapshotting, stale proposal
rejection, and deterministic resolver outcomes. The Evidence Lineage modules
carry the Stage 5 binding and ownership-oracle closure checks needed by the
Stage 6 dependency.

These are overlapping focused surfaces, not additive independent coverage.
This recorder did not run product tests, and no new pass count is claimed by
this checkpoint. It ran only the document and one-file change-boundary checks
described below.

## 7. Checkpoint Verification And Remaining Boundary

This recorder verifies Markdown structure, the exact one-file allowlist, and
`git diff --check`. It does not run a product test, full suite, package build,
install check, runtime smoke, scheduler, executor, or CLI command.

`STAGE_6_READY_FOR_ACCEPTANCE` means the frozen architecture, final lineage,
closed historical findings, and focused test surface are ready to be presented
to the responsible acceptance authority. It does not record acceptance,
authorize merge, authorize release or publication, grant apply authority, or
claim full-suite, build, package, downstream, runtime, or cross-platform
coverage.

Stage 7 is not started. The next action is an external Stage 6 acceptance
decision.
