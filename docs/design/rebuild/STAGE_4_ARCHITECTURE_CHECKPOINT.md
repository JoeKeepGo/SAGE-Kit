# Stage 4 Architecture Checkpoint

## 1. Executive Verdict

**Verdict: `STAGE_4_READY_FOR_ACCEPTANCE`.**

This is an architecture-checkpoint verdict at
`5a8f0b8c1bda21386dbea6a8089e104a899e0ee2`. It records that the Stage 4
architecture and the Stage 4E corrective findings are ready to be presented
for acceptance. It is not PM acceptance, merge approval, release approval, or
evidence that a package or downstream consumer has been exercised.

Stage 5 is deferred. No Stage 5 work is started or authorized by this report.

## 2. Frozen Baseline And Scope

| Item | Frozen value |
|---|---|
| Worktree | `D:\Projects\SPEC Framework\.worktrees\rebuild-stage4-checkpoint-final` |
| Branch | `codex/rebuild-stage4-architecture-checkpoint-final` |
| Required baseline and parent | `5a8f0b8c1bda21386dbea6a8089e104a899e0ee2` |
| Baseline subject | `fix: propagate stage 4 contract digests` |
| Checkpoint change | This report only |
| Product/test execution for this checkpoint | None |

This checkpoint was recovered directly from the required baseline. Its scope
is architecture and recorded evidence only. It does not modify resolver,
runtime, graph, contract, package-resource, test, or consumer behavior.

## 3. Stage 4 Lineage

Stage 4 is additive to the corrected Stage 3 runtime foundation:

1. Stage 3D closed the Stage 3 runtime correctness gaps and supplied the
   bounded, graph-bound state/recovery foundation consumed by Stage 4.
2. Stage 4A introduced Ready Resolution Contract v1, then corrected identity
   separation, corrective-join closure, validated-input binding, and
   cardinality bounds.
3. Stage 4B implemented `sagekit.ready_resolver` as a pure, bounded readiness
   resolver.
4. Stage 4C introduced Transition Resolution Contract v1 and implemented
   `sagekit.transition_resolver` as a pure, bounded node-transition resolver.
   Its corrective lineage separated graph/input classifications, bounded
   admission, preserved large-integer digest semantics, and hardened outcomes.
5. Stage 4D enforced serial external-gate topology: same-join prerequisite
   dependencies remain valid, but work beyond a containing `manual-gate` or
   `corrective-join` belongs to a later host-authorized Graph generation.
6. Stage 4E closed the architecture review findings without introducing a
   scheduler, executor, dynamic Graph rewrite, gate authority, or implicit
   runtime activation.

The resulting architecture retains these owners:

| Concern | Canonical owner |
|---|---|
| Graph shape, topology, semantic projection, and graph digest | Graph Contract v1 and `sagekit.graph_contract` |
| Persisted state/event shape and writer/recovery boundary | Runtime State Contract v1 and Stage 3 runtime modules |
| Ready decision for one supplied snapshot | Ready Resolution Contract v1 and `sagekit.ready_resolver` |
| One node-result transition decision for one supplied snapshot | Transition Resolution Contract v1 and `sagekit.transition_resolver` |
| Current-state proof, authority, compare/revalidate, and apply | Independently authorized host/runtime writer |

## 4. Pure Resolver And Host Apply Boundary

The Stage 4 decision functions are:

- `resolve_ready_nodes(graph, resolution_input)`;
- `resolve_node_transition(graph, transition_input, node_result)`.

They validate and defensively freeze supplied data, enforce resolver-local
admission bounds, calculate deterministic digests, and return bounded,
machine-readable Result or Error values. They do not read the runtime store,
discover current state, acquire a writer or resource, execute a node, open or
satisfy a gate, emit an event, persist state, mutate a Graph, create a later
Graph generation, start a process/agent/tool, or grant authority.

Resolver output is therefore a decision about one exact immutable snapshot,
not permission and not an applied transition. Before any effect, the
independently authorized host/runtime writer must revalidate the current Graph
identity, generation and digest; run, authority and controller bindings; node
and attempt identity; state revision and last event sequence; input digest;
and, for transition resolution, Node Result digest. A mismatch fails closed.
Only that host boundary may map an unchanged decision to a runtime event,
state update, resource action, execution action, or later separately
authorized Graph generation.

Manual-gate and corrective-join evidence is explicit host-supplied data.
Missing evidence never implies approval. Automatic join policy remains
binding, and resolver output cannot bypass required failures or external
authority.

## 5. Stage 4E Findings Closure

Stage 4E closes the blocking architecture findings as follows:

| Finding area | Closure recorded at the frozen baseline |
|---|---|
| Outcome provenance | Ready and transition outcomes bind to the complete validated/admitted source snapshots and their canonical digests; direct construction or stale rebinding cannot manufacture success |
| Mutation during validation | Transition inputs, Graph data, and Node Result data are frozen before validation and decision, preventing post-validation source mutation from changing meaning |
| Admission and classification | Graph, input, structural, and result-size failures retain distinct fail-closed classifications; resolver limits do not redefine Graph Contract validity |
| Runtime size safety | Runtime generation reads avoid unbounded host integer conversion, and runtime-state serialization is bounded before persistence |
| Gate topology | Dependencies inside one external join remain valid; edges escaping a containing external gate are invalid; post-gate work requires a later host-authorized generation |
| Ready admission | Ready-resolution structural work is bounded before resolution, with inclusive limits and no truncation or partial processing |
| Contract identity | Final Graph, Runtime, Ready, and Transition contract digests are propagated through canonical sources, packaged mirrors, and fixed contract expectations |

No blocking Stage 4E finding remains open in this checkpoint. The closure
preserves the core separation: Graph validity is not narrowed by a particular
resolver's capacity, resolver presence is execution-inert, and host apply
authority is not moved into a pure function.

## 6. Overlapping Validation Evidence

The accepted Stage 4 evidence record reports:

- `235` focused observations in the aggregate checkpoint view;
- overlapping component views of `97`, `73`, and `60`;
- overlapping review/probe views of `104` and `117`;
- independent `reviewer21` plus probe evidence.

These are overlapping views over shared contract, resolver, runtime, boundary,
and regression cases. They are **not additive**: `235`, `97/73/60`,
`104/117`, and `reviewer21+probe` must not be summed into a larger test count
or represented as disjoint executions. This checkpoint did not rerun them.

## 7. Contract Digests And Mirror State

| Contract family | Frozen SHA-256 |
|---|---|
| Graph | `bdd68d8b252de9095831d9d6b802aecee133d85002f1281d1d836ff0a98b52a4` |
| Runtime State | `b74ede0245a124b49e8078a2388099f17084624a815fb4812231a04b52020728` |
| Ready Resolution | `9eb5f0f94b3b01f6c71a525bb3ef65ddca31fc9f3fb1eb9b59a1d093aae78f67` |
| Transition Resolution | `385a33f82ea9a65cb90649a4ba7a87fda7eb7035b696766339c691093f7d1291` |

Canonical contract resources and packaged mirrors are recorded as aligned.
Mirror mismatches: `0`. Stale digest references: `0`.

## 8. Explicitly Unrun And Nonblocking Backlog

This checkpoint did not run a full suite, build, wheel build, package/install
check, downstream consumer check, or CI. It makes no claim for those surfaces.

The following work remains nonblocking backlog and does not change the
checkpoint verdict:

- establish a true upper-bound oracle for the `RESULT_TOO_LARGE` path;
- implement and verify the authorized host apply integration boundary;
- exercise the architecture in cross-platform CI.

Those items must remain separate from Stage 4 acceptance evidence. In
particular, host apply work must not move filesystem/runtime mutation or
authority into either pure resolver.

## 9. Acceptance Boundary

`STAGE_4_READY_FOR_ACCEPTANCE` means the architecture checkpoint may be
submitted to the responsible acceptance authority with its limits and backlog
visible. It does not itself:

- record PM acceptance;
- authorize merge;
- authorize release or publication;
- claim full/build/wheel/package/consumer/CI coverage;
- start Stage 5.

The next action is an external acceptance decision. Until that decision, the
frozen Stage 4 baseline and the pure-resolver/host-apply boundary remain
unchanged.
