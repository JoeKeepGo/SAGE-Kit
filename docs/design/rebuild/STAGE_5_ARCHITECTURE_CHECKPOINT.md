# Stage 5 Architecture Checkpoint

## 1. Executive Verdict

**Verdict: `STAGE_5_READY_FOR_ACCEPTANCE`.**

This is an architecture-checkpoint record at
`719c16fc64166b554d8ecb36051fce955cc1afc4`. It records the Stage 5 contract,
pure evidence-lineage resolver, risk-based evaluator selection, observed
failure corpus, integration evidence, and corrective closure that are ready
to be presented to the responsible acceptance authority.

This checkpoint is not a new review, PM acceptance, merge approval, release
approval, or publication approval. Stage 6 has not started.

## 2. Frozen Baseline And Recorder Scope

| Item | Frozen value |
|---|---|
| Worktree | `D:\Projects\SPEC Framework\.worktrees\rebuild-stage5-checkpoint` |
| Branch | `codex/rebuild-stage5-architecture-checkpoint` |
| Required baseline and parent | `719c16fc64166b554d8ecb36051fce955cc1afc4` |
| Baseline subject | `fix: bind evaluator receipts to assignments` |
| Stage 4 architecture parent | `eb4a98407f49f57194d44a59054b2bbfa0c455d2` |
| Checkpoint change | This report only |
| Recorder authority | Record frozen evidence; do not perform a new review |

The checkpoint adds no product, contract, resolver, evaluator, corpus, test,
runtime, CLI, package, or Stage 6 behavior. Its write allowlist contains only
`docs/design/rebuild/STAGE_5_ARCHITECTURE_CHECKPOINT.md`.

## 3. Stage 5 Lineage And 15-File Manifest

Stage 5 is the eight-commit additive lineage from the accepted Stage 4
architecture checkpoint:

1. `8dc502b` introduced Evidence Lineage Contract v1.
2. `b4f66c9` made lineage comparisons and canonical-owner reuse explicit.
3. `cddfaaf` added the pure evidence-lineage resolver.
4. `0240d01` added risk-based evaluator selection.
5. `459d217` added the bounded observed-failure corpus.
6. `67c8340` closed the Stage 5 integration oracles and final manifest.
7. `43c29f5` closed evidence-lineage propagation findings.
8. `719c16f` bound evaluator receipts to externally supplied assignments.

The exact Stage 5 delta from `eb4a984` through `719c16f` is 15 files:

| Status | Path |
|---|---|
| Added | `docs/contracts/evidence-lineage/v1/contract.json` |
| Added | `docs/contracts/evidence-lineage/v1/error.schema.json` |
| Added | `docs/contracts/evidence-lineage/v1/input.schema.json` |
| Added | `docs/contracts/evidence-lineage/v1/result.schema.json` |
| Modified | `sagekit/evidence.py` |
| Added | `sagekit/resources/contracts/evidence-lineage/v1/contract.json` |
| Added | `sagekit/resources/contracts/evidence-lineage/v1/error.schema.json` |
| Added | `sagekit/resources/contracts/evidence-lineage/v1/input.schema.json` |
| Added | `sagekit/resources/contracts/evidence-lineage/v1/result.schema.json` |
| Modified | `sagekit/review.py` |
| Added | `tests/fixtures/stage5_observed_failure_corpus_v1.json` |
| Added | `tests/unit/test_evidence_lineage.py` |
| Added | `tests/unit/test_evidence_lineage_contract_v1.py` |
| Added | `tests/unit/test_risk_based_evaluator.py` |
| Added | `tests/unit/test_stage5_observed_failure_corpus.py` |

No runtime or CLI file is in the manifest.

## 4. Contract Digests Computed From Files

The following SHA-256 values were computed directly from the frozen canonical
files, using the repository contract test's line-ending normalization
(`CRLF` to `LF`). They were not copied from a checkpoint narrative:

| Evidence Lineage v1 resource | File SHA-256 |
|---|---|
| `contract.json` | `240c98234e04e1c97414dae86fadd6a94de16649f71c2dc023e1a2ddf04cbe2a` |
| `input.schema.json` | `b57340367797f69001afbbcfbcb337412109f415eac99ea9d9e18a412d309901` |
| `result.schema.json` | `46bf939a7b802dde95628079855eb1904e584ff68b574551183ff02c631bae8a` |
| `error.schema.json` | `ed86e040b8fc64e6003dbf163172700faec608d6f73463092005c9ac82aa5019` |

The four files under `docs/contracts/evidence-lineage/v1/` and their four
packaged mirrors under
`sagekit/resources/contracts/evidence-lineage/v1/` are byte-identical after
the same repository normalization. Mirror mismatches: `0`. The three schema
digests also equal the values bound by the frozen `contract.json`.

## 5. Pure Architecture And Canonical Owners

### Evidence-Lineage Resolver

`resolve_evidence_lineage(graph, lineage_input)` consumes one valid current
Graph and two complete, independently closed lineage snapshots. It strictly
validates and bounds supplied data, verifies identity and fingerprint
bindings, constructs the complete propagation graph, rejects cycles, and
returns one deterministic decision for every candidate lineage node:
`REUSE`, `REVERIFY_TARGETED`, or `INVALIDATE`.

The resolver does not read or write a runtime store, discover current state,
run tests or tools, select a final artifact, mutate a Graph, apply a
transition, grant authority, or authorize reuse. Its Result is a bounded
classification over the exact supplied snapshots. Any host that acts on it
must independently bind the unchanged current candidate, authority, Graph,
Stage 4 inputs, and owner-produced fingerprints.

### Risk-Based Evaluator

`select_evaluator(...)` is a pure, closed, bounded selection function. A
fixed machine oracle with no semantic or elevated risk may select
`DETERMINISTIC`; semantic judgment, missing oracle, or elevated topology
selects `FRESH_CONTEXT`. It reuses the existing review topology and blocking
boundaries.

`validate_evaluator_receipt(...)` validates a receipt against a separately
supplied immutable assignment. Deterministic receipts must match the assigned
oracle and input/result fingerprints. Fresh-context receipts must match the
assigned author/evaluator identities and assignment digests, and canonical
principal aliases cannot satisfy independence. Selection and receipt
validation do not execute an evaluator, create an assignment, close a review,
or grant acceptance authority.

### Observed-Failure Corpus

The corpus is a bounded, non-normative regression fixture. It contains 12
anonymized cases: 3 executable Stage 5 adapters and 9 reference-only cases.
The executable cases cover duplicate full review, status-only targeted
review, and deterministic whitespace normalization. Each executable adapter
calls both Stage 5 APIs and checks deterministic expected outcomes.

The corpus records provenance and admission status but cannot grant
authority, rewrite source scenarios, promote unadmitted hypotheses, or make
cases assigned to other stages block Stage 5.

### Canonical Owner Reuse

| Concern | Canonical owner reused by Stage 5 |
|---|---|
| Graph shape, identity, generation, joins, topology, and semantic digest | Graph Contract v1 and `sagekit.graph_contract` |
| Ready snapshot and `ready_input_digest` | Ready Resolution Contract v1 and `sagekit.ready_resolver` |
| Transition snapshot, `transition_input_digest`, and Node Result digest | Transition Resolution Contract v1 and `sagekit.transition_resolver` |
| Candidate output fingerprint | Existing `CandidateFingerprint` owner |
| Path overlap semantics | Existing `sagekit.pathing` owner |
| Review topology and blocking boundaries | Existing `sagekit.review` review model |
| Final apply, execution, current-state proof, and acceptance authority | Independently authorized host or owner; not Stage 5 pure functions |

Evidence Lineage adds comparison fingerprints and typed lineage edges. It
does not redefine Graph, Ready, Transition, Node Result, candidate, path, or
review semantics.

## 6. Initial Findings And Five Closures

The initial Stage 5 findings and their frozen closures are:

| Finding | Closure at `719c16f` |
|---|---|
| Propagation considered explicit lineage edges without all Graph dependency and join-contributor edges, so transitive decisions and cycle detection could be incomplete | Baseline and candidate now receive complete propagation adjacency; the candidate additionally uses current Graph dependencies and joins. Topological closure is required before classification, Ready changes propagate to bound Graph/join lineage, Graph identity changes invalidate, and any complete propagation cycle returns Error only |
| A candidate bound to the current Graph could omit Graph nodes, transition bindings, joins, or join integrations and still appear closed | Candidate validation now requires exact set equality and cardinality across current Graph nodes, GRAPH_NODE lineage owners, transition bindings, Graph joins, JOIN owners, and join integrations |
| A supplied join `definition_fingerprint` was not proven to come from the canonical Graph join definition | The resolver now derives a domain-separated fingerprint from the Graph-owned join ID, policy, required contributors, and optional membership, then requires the supplied binding to match it |
| A deterministic receipt could carry arbitrary well-formed hashes without an externally frozen oracle/input/result assignment | Immutable deterministic assignments now bind oracle, input fingerprint, and result fingerprint; receipt validation requires exact assignment and selection agreement |
| Fresh-context receipt identities were not bound to an external assignment, and principal aliases could weaken author/evaluator independence | Immutable fresh-context assignments now bind exact identities and assignment digests; receipt validation compares all fields and rejects NFKC/case-folded aliases or equal assignment digests |

No blocking Stage 5 finding remains open in the recorded closure. These
closures harden validation and provenance without moving execution, review
closure, or acceptance authority into Stage 5.

## 7. Overlapping Validation Evidence

The recorded Stage 5 evidence views are:

| Evidence view | Recorded result | Frozen point |
|---|---|---|
| Contract | `21 passed` | Evidence Lineage Contract v1 |
| Integration | `49 passed` | `67c8340`, all four Stage 5 test modules |
| Lineage corrective | `43 passed` | contract + corrected lineage resolver + corpus |
| Evaluator corrective | `15 passed` | corrected evaluator selection/receipt module |
| Targeted review | `7 passed` | focused closure probes |

These are overlapping views over shared contract, resolver, evaluator,
corpus, integration, and corrective cases. They are **not additive**. In
particular, the 21 contract cases are present in other views, the 43 and 15
corrective views overlap the earlier 49-case integration surface, and the 7
targeted probes exercise already represented closure behavior. No aggregate
grand total may be derived by summing these numbers.

This recorder checkpoint did not rerun those product tests. It records the
frozen Stage 5 evidence and independently checks only its one-file
allowlist/diff boundary.

## 8. Explicitly Unrun And Nonblocking Backlog

No full test suite, full unit suite, source-distribution check, build, wheel
build, package/install check, downstream consumer check, or CI run was
performed for this checkpoint. No cross-platform claim is made.

The following remain nonblocking backlog for final integration:

- run the complete unit suite;
- run source-distribution validation;
- run package/build/install validation;
- run cross-platform CI.

Existing managed-execution failures are not Stage 5 evidence. They are
neither counted in the Stage 5 validation views nor reclassified by this
checkpoint and remain owned by their existing integration surface.

## 9. Acceptance Boundary

`STAGE_5_READY_FOR_ACCEPTANCE` means this architecture checkpoint may be
submitted to the responsible acceptance authority with its findings,
closures, evidence overlap, and backlog visible. It does not:

- record PM or owner acceptance;
- authorize merge;
- authorize release or publication;
- claim full/build/package/consumer/CI coverage;
- introduce runtime or CLI behavior;
- start or authorize Stage 6.

Stage 6 is not started. The next action is an external acceptance decision,
not merge or release.
