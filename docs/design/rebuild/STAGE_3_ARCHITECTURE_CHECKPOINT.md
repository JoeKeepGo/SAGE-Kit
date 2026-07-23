# Stage 3 Architecture Checkpoint

## 1. Executive Verdict

**Verdict: `STAGE_3_CORRECTIVE_REQUIRED`.**

Stage 3 preserves the intended product boundary: the local runtime store is an
optional reference implementation, imports are inert, the host still owns
execution, and the export views remain `REFERENCE_ONLY`. The implementation
also has one canonical event reducer, deterministic state projection, state-last
commit ordering, bounded on-disk parsing, and fail-closed authority checks.

It is not ready for Stage 3 acceptance. Under the ordered rebuild boundary,
Stage 4 therefore is not yet authorized, although its pure resolver must remain
technically independent from this optional store. Static review found five P1
defects:

1. a Graph Contract v1 node identifier can be valid for Stage 2 but rejected by
   Stage 3 runtime state and initialization;
2. a process crash leaves a persistent writer lock that no successor writer can
   safely acquire for recovery;
3. a graph-only partial initialization has no API recovery or retry path;
4. two operations using the same valid writer handle can race and append the
   same next sequence;
5. an exactly persisted `RECOVERY_STARTED` state is classified as
   `CONSISTENT`, so recovery does not complete it.

These are bounded compatibility, ownership, atomicity, and recovery defects.
They do not justify a rewrite, database, CLI, scheduler, service, or new threat
model. The ordered rebuild must close the exact Stage 3 corrective boundary in
section 16 before separately deciding whether to authorize Stage 4.

Finding counts are **P0: 0, P1: 5, P2: 5, P3: 1**.

## 2. Baseline And Scope

| Item | Frozen value |
|---|---|
| Repository | `D:\Projects\SPEC Framework` |
| Audit worktree | `D:\Projects\SPEC Framework\.worktrees\rebuild-stage3-checkpoint` |
| Branch | `codex/rebuild-stage3-architecture-checkpoint` |
| Required baseline | `17f0de198679a88fb51273b342583c8ba1c76ace` |
| Remote authority | `origin/codex/rebuild-stage3c2-runtime-views` |
| Baseline check | Remote authority resolved exactly to the required baseline |
| Branch parent before this report | The required baseline |
| Product/test execution | None; prohibited by checkpoint policy |
| Audit method | Read-only code/contract review, Python AST statistics, import scan, and existing focused-test inventory |

Primary files:

- `sagekit/runtime_store.py`
- `sagekit/runtime_recovery.py`
- `sagekit/runtime_views.py`
- `tests/unit/test_runtime_store.py`
- `tests/unit/test_runtime_recovery.py`
- `tests/unit/test_runtime_views.py`

Narrow reference authority:

- `sagekit/graph_contract.py` and Stage 2 Graph contracts;
- Stage 3A runtime-state contracts;
- `rebuild.md` Stage 3/4 boundaries;
- the proposed Stage Boundary Contract in
  `docs/design/rebuild/STAGE_0_REPORT.md:411-424`.

The audit did not scan a consumer repository or accepted project history. It
did not invoke the Installed Skill, create governance artifacts, run tests,
simulate filesystem failures, build packages, or start Stage 4.

## 3. Stage 3 Capability Inventory

| Capability | Current owner | Observed boundary |
|---|---|---|
| Runtime State Contract v1 | `docs/contracts/runtime-state/v1/**` with packaged mirrors | Language-neutral state/event shape; presence does not activate execution |
| Graph snapshot binding | `runtime_store._validate_graph` delegating to `graph_contract` | Stage 2 validation and semantic digest remain authoritative |
| Stable run/event/attempt identities | `runtime_store.derive_*` | Repository-neutral, deterministic, bounded identities |
| Single-writer store | `acquire_runtime_writer` / `release_runtime_writer` | Cooperative persistent lock file, exact run/graph/authority/controller/writer binding |
| Atomic initialization | `initialize_runtime_store` | Same-directory temporary files; graph, events, then state |
| Append-only event mutation | `append_runtime_event` | Event append and file fsync precede state replacement |
| Runtime inspection | `inspect_runtime_store` | Read-only, bounded, fail-closed classifications |
| Canonical event projection | `_expected_state_after_event` and `_replay_event_history` | One reducer/replay path shared by mutation and recovery |
| Recovery assessment and execution | `runtime_recovery` | Pure replay/assessment plus explicit mutation through a live writer |
| Handoff and CSV views | `runtime_views` | Pure, bounded, immutable/reference-only output; never execution authority |

The Stage 3 cumulative change from the Stage 2C baseline is additive: runtime
contracts and mirrors, the three runtime modules, and their focused tests. It
does not modify the Stage 1/2 product modules or expose the runtime API from
`sagekit.__init__`.

## 4. Module Dependency Graph

Arrows below mean “imports or delegates to”:

```text
runtime_views
  |---> runtime_recovery DTOs and classifications
  `---> runtime_store private validation constants/helpers

runtime_recovery
  `---> runtime_store public writer/error types and 13 private symbols

runtime_store
  `---> graph_contract:
         NODE_STATUSES
         validate_graph_contract
         canonical_graph_digest
         validate_node_transition

graph_contract
  `---> no Stage 3 module
```

There is no circular import. The effective bottom-up layering is:

```text
graph_contract -> runtime_store -> runtime_recovery -> runtime_views
```

The layering is directionally correct, but pure runtime contract/projection
semantics are physically embedded in the 2,517-line filesystem store. Recovery
uses 13 distinct store-private symbols. Views use 16 distinct store-private
symbols and repeat the graph-independent portion of state validation. This is
structural debt, not evidence of a second event reducer.

## 5. Canonical Ownership Matrix

| Semantic fact | Canonical owner | Audit disposition |
|---|---|---|
| Graph v1 structural validation | `graph_contract.validate_graph_contract` | Unique |
| Graph semantic digest | `graph_contract` | Unique; store delegates |
| Node transition legality | `graph_contract.validate_node_transition` | Unique; store does not copy the transition table |
| Runtime state/event persisted validation | `runtime_store.validate_runtime_state` / `validate_runtime_event` | Canonical Python owner |
| Runtime language-neutral schema | Runtime State Contract v1 JSON Schemas | Intentionally independent contract validation |
| Attempt ordinal and derived ID | `runtime_store` reducer | Unique |
| Single-event state projection | `runtime_store._expected_state_after_event` | Unique |
| Full event replay | `runtime_store._replay_event_history` | Unique; recovery delegates |
| Store canonical resource bytes | `runtime_store._canonical_json_bytes` | Full payload plus LF |
| Graph semantic canonicalization | `graph_contract` | Different projection/domain; do not merge with store bytes |
| View state digest | `runtime_views._source_state_digest` | Normalized, domain-separated view identity; intentionally separate |
| Persisted reference grammar | `runtime_store` and Runtime State Contract v1 | Canonical persisted-data boundary |
| Export privacy/path safety | `runtime_views._reference_is_export_safe` | Intentionally stricter and view-owned |
| Filesystem/link/lock safety | `runtime_store` | Unique |
| Recovery classification | `runtime_recovery` | Unique |

Necessary defensive duplication:

- recovery pre-checks bindings so it can return precise classifications rather
  than a generic store error;
- views independently reject absolute paths, UNC/file references, spreadsheet
  formulas, and obvious secret-bearing reference strings because export safety
  is stricter than persisted reference validity.

Meaningful duplication/debt:

- `runtime_views._validate_and_normalize_state` repeats most graph-independent
  state-shape checks from `runtime_store.validate_runtime_state`;
- recovery and views reach through broad private store internals instead of a
  narrow internal seam;
- bulk parse/replay repeatedly validates and digests the same graph.

## 6. Complexity And Size Evidence

Static statistics were calculated from the frozen baseline. “Code lines” means
token-bearing lines excluding blank/comment-only lines; docstrings count as
code. “Branch points” is an AST proxy over conditionals, loops, exception
branches, boolean branches, match branches, and comprehensions. These numbers
describe cost and concentration; they are not findings by themselves.

| File | Physical LOC | Token-bearing lines | Classes | Functions/methods | Branch proxy | Longest function |
|---|---:|---:|---:|---:|---:|---|
| `runtime_store.py` | 2,517 | 2,325 | 11 | 58 | 333 | `_inspect_runtime_store`, 186 lines |
| `runtime_recovery.py` | 675 | 620 | 6 | 11 | 53 | `_read_snapshot`, 167 lines |
| `runtime_views.py` | 744 | 666 | 1 | 20 | 74 | `_validate_and_normalize_state`, 155 lines |
| **Product subtotal** | **3,936** | **3,611** | **18** | **89** | **460** | — |
| `test_runtime_store.py` | 1,266 | 1,162 | 8 | 68 | 52 | 47 test methods |
| `test_runtime_recovery.py` | 738 | 662 | 2 | 35 | 24 | 16 test methods |
| `test_runtime_views.py` | 561 | 509 | 3 | 27 | 21 | 22 test methods |
| **Test subtotal** | **2,565** | **2,333** | **13** | **130** | **97** | **85 test methods** |

Filesystem fixture sites are concentrated but bounded: 41
`TemporaryDirectory` sites in store tests and 15 in recovery tests; views use
none. Static scanning found no product `sleep`, polling, subprocess,
multiprocessing, threading, socket, network, or background-worker behavior.
The test references to `subprocess`, `threading`, and `time.sleep` are forbidden
token assertions rather than execution.

## 7. Correctness And Atomicity Review

| Scenario | Assessment |
|---|---|
| Clean initialization | Correct order: graph, events, state; state is last |
| Successful append | Event bytes are appended and file-fsynced before state replace |
| Event durable, state replace fails | Correctly returns `RECOVERY_REQUIRED`; recoverable only while ownership remains usable |
| Partial/torn final event | Detected and never reported as valid; no automatic truncation |
| State behind complete events | Deterministic replay can reconstruct it with the original live writer |
| State ahead | Fails closed; recovery does not overwrite |
| State diverged | Fails closed; recovery does not overwrite |
| Event sequence gap/duplicate | Fails closed |
| Run/graph/authority/controller binding | Checked at lock, graph, state, event, writer, and recovery layers |
| Input mutation | Replay, assessment, recovery result, and views use copies/immutable outputs |
| Interrupted recovery with original handle | Continuation of a missing completion or state replace is supported |
| Process crash / successor writer | Not supported because the persistent lock cannot be reacquired; P1 |
| Graph-only partial initialization | Not retryable or recoverable through the API; P1 |
| Concurrent operations through one handle | Not serialized; can duplicate the next event sequence; P1 |
| Exact persisted recovery-in-progress state | Misclassified as consistent; P1 |

State-last ordering prevents a state snapshot from claiming an uncommitted
event. It does not by itself make the store a crash-proof database. The
implementation is strongest for cooperative, single-operation use while the
original `RuntimeWriter` remains live. Current tests exercise that condition;
they do not establish restart recovery ownership or same-handle concurrency.

## 8. Cross-Platform And Threat Boundary

The honest durability claim is:

- canonical UTF-8 bytes;
- same-directory temporary files and `os.replace`;
- file `fsync` calls;
- append-before-state logical ordering;
- directory `fsync` when the platform/filesystem supports it.

`runtime_store._directory_fsync` explicitly returns unavailable on Windows and
can degrade honestly on unsupported Unix filesystems. On macOS, ordinary
`fsync` is not a universal `F_FULLFSYNC`/power-loss guarantee. Recovery
currently drops the directory-fsync capability result, which is P2-003 below.
No platform should be described as providing database-grade or power-loss-proof
durability.

The link/path defenses are substantial: `lstat`, reparse/symlink rejection,
single-link checks, `O_NOFOLLOW` where present, device/inode checks, directory
identity checks, fixed paths, and bounded reads. They remain cooperative
same-user protections. Path-based check/use windows remain, Windows has no
portable `O_NOFOLLOW` equivalent here, and an administrator or malicious
same-account filesystem process can race or replace objects. That is outside
the intended governance-store boundary and must not be represented as a
sandbox, high-security isolation system, or administrator defense.

## 9. Execution Economy Assessment

Ordinary Light/Standard projects pay no Stage 3 runtime cost unless they
explicitly import/use it:

- `sagekit.__init__` imports the existing Harness surface, not the runtime
  modules;
- Graph contract/normalization modules do not import Stage 3;
- module top levels contain definitions only and create no files;
- no runtime module starts a process, agent, thread, scheduler, poller, or
  service;
- a project may use host memory or another compatible store.

The explicit store path is bounded but not cheap at its declared maxima.
`append_runtime_event` performs a full inspection/replay before mutation,
another full history replay for the proposed state, and a full inspection after
commit. Each event projection deep-copies the state and rebuilds a node lookup.
Across a growing history this is approximately `O(E * N)` per append and
`O(E^2 * N)` cumulatively, with repeated graph validation. Recovery similarly
re-reads/replays history several times. This is a P2 execution-economy issue,
not a P1 solely because of line count or an unrun benchmark.

The Stage 4 resolver must remain data-only. It must return decisions first; the
host may then choose whether and how to persist resulting events. Runtime-store
cost must not become mandatory for Light work or for every pure readiness
query.

## 10. Stage 1/2 Capability Non-Regression

Observed non-regression:

- Stage 3 is additive relative to Stage 2C; existing Stage 1/2 product modules
  were not edited by the Stage 3 cumulative commits.
- Graph validation, semantic digest, cycle checks, join checks, NodeResult
  validation, and transition decisions remain owned by `graph_contract`.
- Stage 3 does not activate Graph execution, scheduling, process launch, or
  runtime persistence merely by importing a contract.
- `ACTIVE_CONTEXT` remains a compact human handoff; runtime state stays in
  `.sagekit/runtime` or host memory and is not written into Markdown.
- accepted history remains outside runtime execution.
- Light remains graph-artifact optional and runtime-persistence optional.
- CSV/handoff views always emit `authority_class=REFERENCE_ONLY` and
  `valid_for_execution=false`.
- the host still creates agents and invokes tools; there is no CLI target or
  scheduler service.
- the zero-to-product planning, architecture, roadmap, milestone, execution,
  review, acceptance, and closeout path was not modified.

One compatibility regression is nevertheless present at the Stage 2/3
boundary: Stage 3 narrows valid Graph node identities without an admitted
contract boundary. That is P1-001.

## 11. Stage 4 Readiness

The intended Stage 4 architecture is feasible, but Stage 3 is not currently
ready to authorize it because the P1 findings must first close.

The minimum recommended decision-only boundary is:

```text
resolve_ready_nodes(graph, state, available_resources)
```

- `graph`: an immutable Graph Contract v1 value already validated by the pure
  graph validator;
- `state`: an immutable, graph-bound decision projection containing the
  complete node-status map and any host-supplied manual-gate decisions;
- `available_resources`: an immutable snapshot of abstract resource identities
  and availability, with no paths, locks, process/agent/tool handles, callbacks,
  or acquisition side effects.

The result should contain stable ordered `ready`, `waiting_resource`, `blocked`,
and `completed` node identities plus bounded reason codes. It must not:

- import or discover the filesystem runtime store;
- acquire a writer or resource lock;
- start a process, agent, tool, service, or scheduler;
- require `runtime_views`;
- mutate Graph, state, resources, `ACTIVE_CONTEXT`, or history;
- infer that a missing manual-gate decision is approval.

Graph Contract v1 represents `manual-gate` joins and named human gates, while
Runtime State v1 does not currently represent the human decision. This is
**Stage 4 input constraint `S4-INPUT-001`**, not a Stage 3 finding and not part
of the finding count. Stage 4 must treat the decision as an explicit
host-supplied, data-only state projection or return a fail-closed
unsupported/missing-decision result. It is not authority to change Runtime
State v1 or expand Stage 3 into a scheduler or gate service.

## 12. Findings By Severity

### P0

No P0 finding was observed. The reviewed paths do not produce a deterministic
false success, silently bypass authority, or knowingly overwrite divergent
state.

### P1-001 — Stage 2-valid node identities are rejected by Stage 3

- **Severity:** P1.
- **Exact file/function:** `docs/contracts/graph/v1/graph.schema.json`
  `$defs.node.id` at lines 125-127;
  `sagekit/graph_contract.py::_validate_node` at lines 393-405;
  `docs/contracts/runtime-state/v1/state.schema.json::$defs.identity` and
  `node_id` at lines 99-103 and 140-142;
  `sagekit/runtime_store.py::_require_identity`,
  `validate_runtime_state`, `_initial_payloads`, and `derive_attempt_id`.
- **Observed evidence:** Graph Contract v1 requires only a non-empty node ID.
  Stage 3 requires the ASCII pattern
  `^[A-Za-z0-9][A-Za-z0-9._:+-]{0,255}$`. Initialization copies Graph IDs into
  state and immediately validates them, so spaces, slashes, Unicode, or longer
  Stage 2-valid IDs fail.
- **Product impact:** The optional reference runtime silently imposes a
  character-set, syntax, and fixed per-ID length subset that its contract does
  not declare, breaking the claimed Stage 2/3 compatibility boundary.
- **Blocks Stage 4:** It blocks Stage 3 acceptance and therefore blocks
  procedural authorization of the next stage. It does not make the optional
  store a technical dependency of the pure Stage 4 resolver.
- **Minimum fix boundary:** Remove the extra character-set/syntax restriction
  for runtime `node_id` in state, event, attempt derivation, views, and
  validation. Replace the fixed 256-character node-ID rule with deterministic
  pre-write runtime admission based only on the existing canonical resource
  byte budgets, and declare that bounded optional-store admission explicitly.
  Retain the stricter grammar for run/authority/controller identities and do
  not normalize or rewrite node IDs.
- **Adjacent scope not to fix:** Graph digest projection, transition rules,
  Graph normalization, general identifier policy, or accepted Graph history.

### P1-002 — Recovery ownership cannot survive a writer-process crash

- **Severity:** P1.
- **Exact file/function:** `sagekit/runtime_store.py::acquire_runtime_writer`
  at lines 1094-1189 and `sagekit/runtime_recovery.py::recover_runtime_state`
  at lines 545-568.
- **Observed evidence:** The persistent `O_EXCL` lock file is the only ownership
  signal. A crash leaves it present, so every successor acquisition is busy.
  Recovery mutation requires the original live `RuntimeWriter` and writer ID.
  Existing interrupted-recovery tests retain the same in-process handle.
- **Product impact:** A consistent store, a state-behind store, or an
  interrupted recovery can be permanently unavailable after process exit
  unless a caller bypasses the API and deletes authority state.
- **Blocks Stage 4:** It blocks Stage 3 acceptance and therefore procedural
  authorization of the next stage. The pure Stage 4 resolver remains
  technically independent of this optional recovery implementation.
- **Minimum fix boundary:** Add an explicit, exact-binding, auditable recovery
  owner acquisition/takeover path for a host-confirmed abandoned writer. It
  must validate run/graph/authority/controller/prior-writer identity, replace
  ownership atomically, and invalidate the old handle before future mutation.
- **Adjacent scope not to fix:** No timeout scheduler, process supervisor,
  distributed lease, administrator defense, same-user sandbox, or database.

### P1-003 — Graph-only partial initialization has no recovery path

- **Severity:** P1.
- **Exact file/function:**
  `sagekit/runtime_store.py::initialize_runtime_store` at lines 1317-1459 and
  `sagekit/runtime_recovery.py::_read_snapshot` / `recover_runtime_state` at
  lines 303-315 and 574-584.
- **Observed evidence:** Initialization commits graph, events, then state. If
  the events replace fails after graph commit, retry is rejected because
  `graph.json` exists, while recovery rejects the missing event log as corrupt.
  Existing tests prove “not valid” but do not establish an API continuation.
- **Product impact:** An ordinary I/O failure can wedge a brand-new optional
  store and require out-of-band deletion.
- **Blocks Stage 4:** It blocks Stage 3 acceptance and therefore procedural
  authorization of the next stage; it does not make Stage 4 depend on the
  store.
- **Minimum fix boundary:** Only when canonical graph bytes and all bindings
  match exactly and both events/state are absent, permit idempotent
  initialization continuation. Preserve unknown or non-initial data.
- **Adjacent scope not to fix:** No general store reset, garbage collector,
  unknown-file cleanup, history rewrite, or automatic deletion of evidence.

### P1-004 — A valid writer handle does not serialize its own operations

- **Severity:** P1.
- **Exact file/function:** `sagekit/runtime_store.py::RuntimeWriter` at lines
  233-245; `append_runtime_event` at lines 2194-2330; and
  `_commit_runtime_recovery` at lines 2333-2496.
- **Observed evidence:** There is no operation mutex/active-operation guard.
  Two callers can both inspect the same event tail, both validate the same next
  sequence, and both append it before either state replacement. The file-level
  writer lock prevents a second writer ID, not concurrent calls through the
  same handle or a copied handle.
- **Product impact:** Legitimate host concurrency can create duplicate event
  sequences and permanently corrupt the append-only authority.
- **Blocks Stage 4:** It blocks Stage 3 acceptance and therefore procedural
  authorization of the next stage. Stage 4 may expose independent decisions,
  but it must not be technically coupled to this optional persistence path.
- **Minimum fix boundary:** Ensure all same-process calls that pass writer
  verification for one live lock identity share one operation critical section
  across initialize/append/recover/release, including handle copies. Keep the
  guard across the final compare-and-append/state-last boundary.
- **Adjacent scope not to fix:** No multi-writer database, scheduler, worker
  pool, resource allocator, or general thread framework.

### P1-005 — Exact recovery-in-progress state is misclassified as consistent

- **Severity:** P1.
- **Exact file/function:**
  `sagekit/runtime_recovery.py::replay_runtime_events` at lines 184-188,
  `_assess_with_snapshot` at lines 482-488, and `recover_runtime_state` at lines
  569-573; `sagekit/runtime_store.py::_replay_event_history` at lines
  2089-2115.
- **Observed evidence:** Replay correctly reports `RECOVERY_IN_PROGRESS` when
  the final event is `RECOVERY_STARTED`. If the state bytes exactly equal that
  projection, assessment overwrites the classification with `CONSISTENT`, and
  recovery returns without adding the required completion.
- **Product impact:** The observable event log and recovery classification
  disagree, and a supported persisted state cannot complete recovery.
- **Blocks Stage 4:** It blocks Stage 3 acceptance and therefore procedural
  authorization of the next stage; the pure resolver is not technically
  dependent on recovery.
- **Minimum fix boundary:** Preserve `RECOVERY_IN_PROGRESS` on exact state
  equality and append exactly one matching completion.
- **Adjacent scope not to fix:** Run lifecycle redesign, Stage 4 transition
  policies, new recovery event types, or scheduler behavior.

### P2-001 — Broad private coupling and duplicated state-shape validation

- **Severity:** P2.
- **Exact file/function:** `runtime_recovery.py` imports/uses 13 distinct
  `_store._*` symbols; `runtime_views.py::_validate_and_normalize_state` at
  lines 203-357 uses 16 store-private symbols.
- **Observed evidence:** Pure schema/projection logic and filesystem mechanics
  share one module; views repeat graph-independent validation.
- **Product impact:** Internal changes have a large blast radius and Stage 4
  could be tempted to import the filesystem-heavy store or copy semantics.
- **Blocks Stage 4:** No after the P1 corrective, provided Stage 4 accepts
  already validated data-only inputs and does not import store internals.
- **Minimum fix boundary:** A later semantic-preserving internal seam for
  shape validation/projection and a narrow recovery store adapter.
- **Adjacent scope not to fix:** Public API expansion, contract changes,
  transition ownership, persisted formats, or filesystem ordering.

### P2-002 — Append and recovery repeatedly replay full history

- **Severity:** P2.
- **Exact file/function:**
  `runtime_store.py::_inspect_runtime_store`,
  `_replay_event_history`, `_validate_state_update`,
  `append_runtime_event`, `_commit_runtime_recovery`; and
  `runtime_recovery.py::recover_runtime_state`.
- **Observed evidence:** A normal append performs multiple full parse/replay
  passes; each event projection deep-copies state. Recovery performs additional
  full passes and prefix replay. Bulk paths also repeat Graph validation.
- **Product impact:** Legal large histories can produce synchronous CPU/memory
  amplification and slow focused tests or host handoff. No leak/background
  process was found.
- **Blocks Stage 4:** No; the store is optional and the resolver must remain
  in-memory/data-only.
- **Minimum fix boundary:** Reuse a validated replay continuation and perform
  one-event projection while retaining byte/identity checks and state-last
  persistence.
- **Adjacent scope not to fix:** No cache service, database, scheduler,
  benchmark-driven rewrite, or weakening of full standalone validators.

### P2-003 — Recovery drops directory-durability capability

- **Severity:** P2.
- **Exact file/function:** `runtime_store.py::_directory_fsync` at lines
  940-973 and `_commit_runtime_recovery` at lines 2466-2473;
  `runtime_recovery.py::recover_runtime_state` at lines 635-661.
- **Observed evidence:** Initialization/append report directory fsync
  `SUPPORTED` or `UNAVAILABLE`; recovery ignores the boolean and returns a
  `RecoveryResult` with no capability field.
- **Product impact:** Logical consistency can be confused with durable rename
  metadata on Windows or unsupported filesystems.
- **Blocks Stage 4:** No if documentation remains honest.
- **Minimum fix boundary:** Propagate the capability or define `RECOVERED` as
  current logical consistency only.
- **Adjacent scope not to fix:** Power-loss guarantees, macOS full-fsync
  guarantees, crash-proof claims, or platform-specific services.

### P2-004 — Deep JSON can escape fail-closed classification

- **Severity:** P2.
- **Exact file/function:** `runtime_store.py::_canonical_json_bytes` at lines
  279-290 and `_strict_json_loads` at lines 308-317.
- **Observed evidence:** `RecursionError`/related nesting failures are not
  mapped to `RuntimeStoreIntegrityError`, even though byte sizes are bounded.
- **Product impact:** A malformed but size-bounded file can raise an unexpected
  exception instead of producing a bounded corrupt/torn classification.
- **Blocks Stage 4:** No.
- **Minimum fix boundary:** Map recursion/overflow parsing failures to integrity
  errors and, if necessary, impose a deterministic nesting budget.
- **Adjacent scope not to fix:** General untrusted-input sandboxing or a new
  parser implementation.

### P2-005 — Direct replay has no aggregate work bound

- **Severity:** P2.
- **Exact file/function:**
  `runtime_recovery.py::replay_runtime_events` at lines 123-194 and
  `runtime_store.py::_replay_event_history` at lines 2027-2124.
- **Observed evidence:** The public in-memory replay accepts any list/tuple
  length. Disk reads have a 64 MiB cap, but direct callers have no equivalent
  event-count or aggregate-byte budget.
- **Product impact:** Explicit callers can cause unexpectedly large synchronous
  CPU/memory work.
- **Blocks Stage 4:** No; Stage 4 must not use event replay for readiness.
- **Minimum fix boundary:** Add an incremental event-count/aggregate canonical
  byte budget aligned with the persisted log contract.
- **Adjacent scope not to fix:** Rate limiting, process isolation, scheduler
  quotas, or network threat models.

### P3-001 — Import-inert tests are not all cold imports

- **Severity:** P3.
- **Exact file/function:** import-side-effect tests in
  `test_runtime_store.py:221-245`,
  `test_runtime_recovery.py:213-229`, and
  `test_runtime_views.py:106-154`.
- **Observed evidence:** Test collection imports modules before some assertions;
  cached imports/reloads do not uniformly re-execute the complete dependency
  chain.
- **Product impact:** The implementation is statically inert, but future
  import-time I/O regression protection is weaker than the test names imply.
- **Blocks Stage 4:** No.
- **Minimum fix boundary:** A focused cold-import isolation test with no
  consumer scan.
- **Adjacent scope not to fix:** Public top-level runtime exports, packaging,
  CLI entry points, or consumer validation.

## 13. Consolidation Candidates

These are candidates, not authorization for the immediate corrective:

1. Split graph-independent runtime shape validation from graph/binding
   validation so views can reuse one internal contract seam.
2. Keep one canonical reducer/replay implementation, but place its pure
   continuation behind a narrow non-public interface that Stage 4 cannot
   confuse with persistence.
3. Give recovery one narrow snapshot/compare-and-commit adapter instead of 13
   unrelated store-private dependencies.
4. Reuse the semantic digest returned by the first Graph validation in bulk
   operations rather than validating/digesting the same Graph per event.
5. Keep persisted reference validation and export privacy validation separate.
6. Keep Graph semantic canonicalization, store resource bytes, and view
   domain-separated digest canonicalization separate; they are not equivalent
   duplicates.

No candidate is a recommendation to rewrite the 3,936 product lines. A
consolidation must be justified by a stable semantic seam and unchanged
contract bytes/behavior.

## 14. Do-Not-Change Boundaries

The checkpoint and its corrective do not authorize changes to:

- Stage 4 implementation or a ready-node resolver;
- `graph_contract` transition, join, digest, or normalization semantics;
- host ownership of process, agent, or tool execution;
- CLI, scheduler, service, database, resource allocator, or graph database;
- `ACTIVE_CONTEXT`, document routing, project memory, or accepted history;
- Light/Standard optionality or zero-to-product capability;
- runtime state in Markdown;
- CSV/handoff `REFERENCE_ONLY` and `valid_for_execution=false` boundaries;
- security claims against administrators or malicious same-user processes;
- consumer repositories, Installed Skill, README, `rebuild.md`, Stage 0
  artifacts, product history, or unrelated tests/contracts.

## 15. Recommendation

Choose **C. `STAGE_3_CORRECTIVE_REQUIRED`**.

The recommendation is evidence-bound to the five P1 findings. Stage 3 is not
rejected as a product direction: its optionality, authority separation,
canonical reducer, state-last ordering, deterministic replay, views, and
fail-closed classifications are sound foundations. The corrective must be
small and must preserve them.

P2/P3 items remain recorded debt or Stage 4 input constraints. They must not be
used to enlarge the corrective into a broad refactor.

## 16. Exact Next Stage

The exact next stage is a bounded **Stage 3D Runtime Corrective**. It is not
Stage 4.

Exact candidate manifest:

```text
docs/contracts/runtime-state/v1/contract.json
docs/contracts/runtime-state/v1/event.schema.json
docs/contracts/runtime-state/v1/state.schema.json
sagekit/resources/contracts/runtime-state/v1/contract.json
sagekit/resources/contracts/runtime-state/v1/event.schema.json
sagekit/resources/contracts/runtime-state/v1/state.schema.json
sagekit/runtime_store.py
sagekit/runtime_recovery.py
sagekit/runtime_views.py
tests/unit/test_runtime_state_contract_v1.py
tests/unit/test_runtime_store.py
tests/unit/test_runtime_recovery.py
tests/unit/test_runtime_views.py
```

Exact acceptance boundary:

1. Runtime node references remove the character-set/syntax narrowing relative
   to non-empty Graph Contract v1 node IDs without rewriting IDs. A
   deterministic pre-write admission applies the existing canonical graph,
   state, and event byte budgets rather than a separate 256-character node-ID
   grammar; run/authority/controller identity grammar remains unchanged,
   optional-store bounds are explicit, and contract mirrors remain
   byte-equivalent.
2. A successor can explicitly acquire recovery ownership only for an exactly
   bound, host-confirmed abandoned writer; unknown/mismatched locks remain
   fail-closed, and the previous handle cannot perform a later mutation.
3. Graph-only partial initialization continues idempotently only when the
   canonical graph and all bindings match and both events/state are absent; it
   never deletes the committed graph or unknown data.
4. All same-process calls admitted for one live writer-lock identity, including
   handle copies, share one initialize/append/recover/release critical section;
   no duplicate next sequence can be appended by same-owner concurrency.
5. Exact `RECOVERY_STARTED` state remains `RECOVERY_IN_PROGRESS` and completes
   with exactly one matching completion.
6. Existing append-only event bytes, state-last commit order, authority
   bindings, divergent/ahead fail-closed behavior, export privacy, optional
   adoption, and import inertness do not regress.
7. Only focused contract/store/recovery/view tests and low-cost static checks
   are required for the corrective; no full suite, build, wheel, consumer,
   scheduler, or Stage 4 work is implied by this checkpoint.

Successful Stage 3D closure requires a fresh targeted review of these five P1
paths. Only after that closure may a separate authority decide whether to start
Stage 4.
