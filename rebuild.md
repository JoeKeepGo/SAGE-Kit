# SAGE-Kit Incremental Rebuild

Status: living product blueprint, not final authority  
Scope: SAGE-Kit product architecture and implementation sequencing  
Execution model: incremental, compatibility-preserving, evidence-driven  

This file records the current rebuild direction. It is deliberately not a new
governance contract. Existing project authority remains in the adopted SAGE-Kit
contracts until a rebuild stage is reviewed, accepted, and promoted into its
canonical owner.

The rebuild must proceed one bounded stage at a time. A later stage may be
changed or abandoned without invalidating earlier accepted stages.

## Reading And Routing

This blueprint is used only for SAGE-Kit rebuild work. Normal consumer-project
planning, execution, review, and adoption must not load it.

Do not read the whole file by default. A rebuild controller reads:

1. Status, Product Thesis, Goals, and Non-Goals;
2. the currently authorized stage only;
3. Safety and Efficiency Invariants;
4. the Decision Log;
5. another named section only when the current decision needs it.

Current stage pointer: `Stage 0: Baseline And Authority Inventory`.

When a stage is accepted, its stable rules move to their canonical owner and
this blueprint retains only the decision, stage outcome, and design history.

## 1. Product Problem

SAGE-Kit began as a reusable specification and AI-agent governance harness. As
the framework matured, correct rules were added across Core, Harness, Session
Orchestration, Wave Execution, Execution Economy, Skills, references, profiles,
and templates.

Most individual rules are useful. The product problem is their distribution:

- one rule can appear in several documents with normative wording;
- agents read and reconcile multiple copies before acting;
- document consistency findings can trigger review work unrelated to product
  correctness;
- milestone and phase documents can become runtime inputs instead of planning
  and historical records;
- graph topology is described well, but runtime node, edge, join, and state
  semantics are not represented by one compact contract;
- controllers can therefore execute a declared graph as a long serial loop;
- broad re-review and repeated verification can invalidate useful evidence;
- operational state can be repeated across Markdown, packets, ledgers, and
  runtime records;
- adding more enforcement risks rebuilding the removed CLI or creating a new
  coding-agent runtime.

The rebuild must improve execution speed by removing repeated interpretation,
not by weakening authority, verification, review independence, or acceptance.

## 2. Product Thesis

SAGE-Kit should be a:

> Governed graph of bounded loops, expressed through portable contracts and
> executed by the host agent runtime.

The outer graph owns:

- roles and authority;
- node dependencies;
- routing and joins;
- shared state;
- approval gates;
- evidence lineage;
- resource admission;
- final acceptance boundaries.

Each node's loop owns:

- local inspection;
- local planning;
- implementation or review;
- focused verification;
- bounded correction;
- a typed result.

SAGE-Kit must not become another Codex, Claude Code, agent scheduler service, or
IDE. Codex, Claude Code, and other hosts create agents and execute tools.
SAGE-Kit defines what may run, what state it receives, what result it must
return, and what transition is allowed next.

## 3. Goals

1. Give every governance rule one canonical owner.
2. Keep project planning and historical documents valuable but decoupled from
   runtime state.
3. Represent active execution as a compact graph contract.
4. Standardize node results, joins, transitions, and evidence invalidation.
5. Let host runtimes discover safe parallel work without a SAGE-Kit CLI.
6. Reuse unchanged evidence and rerun only affected graph nodes.
7. Preserve PM, Coder, Final Review, worker, corrective, and submit authority
   separation.
8. Keep Light work lightweight, Standard work bounded, and Heavy orchestration
   explicit.
9. Preserve accepted history without rewriting it to the newest format.
10. Remain portable across Windows, macOS, and Linux.
11. Preserve the complete zero-to-product path from a person's initial idea
    through product definition, architecture, roadmap, milestones, execution,
    acceptance, and closeout.
12. Keep product capability monotonic: an accepted rebuild stage may make the
    framework simpler, faster, or more precise, but must not remove an existing
    user outcome, governance strength, compatibility path, or safety boundary
    without an accepted equivalent-or-stronger replacement.

## 4. Non-Goals

The rebuild does not initially include:

- a command-line interface;
- a background scheduler daemon;
- a distributed task queue;
- a Neo4j or external graph database dependency;
- arbitrary runtime graph rewriting;
- unlimited nested executable agents;
- a dashboard;
- mandatory Task Dispatch;
- mandatory worktrees;
- mandatory graph artifacts for Light changes;
- migration or rewriting of accepted milestone history;
- a second source of project product authority inside the Skill;
- model-token or subscription-quota accounting;
- exhaustive analysis of hypothetical risks that are not connected to active
  authority, changed surfaces, observed evidence, or acceptance;
- speculative tests whose result cannot change a current routing, acceptance,
  corrective, or release decision.

## 5. Findings Recorded

### 5.1 The Current Model Is a Graph of Loops

Project Manager, Coder, Final Review, workers, reviewers, and corrective workers
are specialized graph nodes with separate contexts. Phase and lane execution
can fan out and their results fan in. Review failures route to corrective work,
then targeted re-review, before returning to PM acceptance.

Each node still needs its own bounded loop. Graph engineering does not replace
loop engineering; it controls how reliable loops compose.

### 5.2 The Runtime Graph Is Less Explicit Than the Documented Graph

The framework already describes DAGs, waves, serial barriers, role separation,
corrective convergence, and final review. It does not yet have one minimal,
canonical representation for:

- node identity and state;
- edge conditions;
- join policy;
- typed node output;
- dependency-based evidence invalidation;
- graph generation and bounded expansion.

This gap lets host controllers reinterpret the topology and accidentally turn
parallel graph work into a long serial session.

### 5.3 Document Authority Is Too Distributed

Core documents, operational guides, Skills, references, and templates repeat
governance language. Templates and platform guidance can appear authoritative
even when they should only apply canonical rules.

The problem is not merely document count. It is multiple apparent sources of
truth.

### 5.4 Runtime State Must Not Live in Markdown

Milestone and phase documents explain purpose, decomposition, acceptance, risk,
and history. `ACTIVE_CONTEXT` provides compact human handoff. Neither should be
the live scheduler database.

Node state, attempts, joins, leases, candidate identity, and evidence
invalidation belong in ignored runtime state or host memory.

### 5.5 A CLI Is Not Required

Graph operation can be exposed through an embeddable API and language-neutral
contracts. The host runtime can call pure decision functions and launch agents
with native capabilities. Human users should not need to invoke SAGE-Kit shell
commands.

### 5.6 Efficiency Comes From Incremental Execution

Efficiency improves when:

- startup reads only active authority;
- nodes receive narrow context;
- node outputs are structured rather than full transcripts;
- focused verification stays inside the node loop;
- joins run only integration checks;
- a frozen candidate runs final verification once;
- a change invalidates only dependent evidence;
- ordinary corrective work stays inside preauthorized graph edges.

### 5.7 Zero-To-Product Is A Core Capability

The framework is not only an execution harness for prewritten technical work.
It must continue helping a person move from a rough idea to a reviewable and
deliverable product through:

- Project Owner intake;
- problem, user, outcome, and concern clarification;
- Project Profile and Technical Design;
- Capability Map and Roadmap;
- milestone and phase decomposition;
- quality and approval gates;
- Coder and Final Review orchestration;
- PM acceptance and closeout.

Graph contracts are compiled from approved planning authority. They do not
replace product discovery, product judgment, milestone depth, or human-readable
history. A user must not be required to author graph JSON to start a project.

### 5.8 Divergent Reasoning Creates Governance Waste

Agents can expand a bounded task into speculative architecture, security,
compatibility, edge-case, and test work. This can appear prudent while delaying
the accepted objective and producing evidence that no current decision needs.

The rebuild must distinguish:

- `REQUIRED`: directly supports active acceptance, a declared gate, the changed
  surface, or baseline correctness;
- `EVIDENCED_RISK`: responds to an observed failure, concrete dependency, or a
  high-confidence risk on the changed surface;
- `OPTIONAL`: potentially valuable improvement without current decision impact;
- `OUT_OF_SCOPE`: unrelated to active authority or accepted outcomes.

Only `REQUIRED` and authorized `EVIDENCED_RISK` work enters the active graph.
Optional findings are recorded concisely for later prioritization. Out-of-scope
work is not implemented, tested, or repeatedly reviewed.

A declared product threat model and accepted safety requirements remain
authoritative. An agent must report a concrete P0/P1 safety defect discovered on
the changed surface. It must not invent undeclared product capabilities,
infrastructure, adversaries, or defense-in-depth requirements and turn them into
blockers.

### 5.9 Failures Must Be Diagnosed At The Correct Layer

SAGE-Kit uses five cumulative engineering layers:

```text
Prompt -> Context -> Harness -> Loop -> Graph
```

A failure at an inner layer should be corrected there before an outer layer is
expanded. Ambiguous instructions are not repaired by adding reviewers. Excess
context is not repaired by adding graph nodes. A weak verifier is not repaired
by adding another execution agent. A process timeout is not repaired by adding
governance documents.

Every corrective proposal should classify its root cause at one primary layer
and name the smallest layer-local correction. Cross-layer changes require
evidence that the failure actually crosses those boundaries.

### 5.10 Harness Completeness Requires Balance

A production harness must cover six concerns:

| Concern | Product question |
|---|---|
| Context | What does the node see, and what is excluded? |
| Tools | What can it touch, and how are results distilled? |
| Orchestration | What runs next, branches, joins, or escalates? |
| State and memory | What persists for the run, session, and project? |
| Evaluation and observability | Was the result correct, and where did failure occur? |
| Constraints and recovery | What is bounded, and how does the run recover? |

More controls in one concern do not compensate for a missing concern elsewhere.
The rebuild should specifically avoid strengthening constraints and recovery by
adding context, coordination, or verification cost without decision value.

### 5.11 Autonomy And Governance Are Different Axes

Governance level describes risk and required control. Autonomy level describes
which part of the loop the host may execute without another human turn.

A Heavy migration can remain interactive at approval gates. A Light correction
can close a measurable goal automatically. Heavy must not be interpreted as
permission for longer autonomous execution, and high autonomy must not reduce
governance.

Initial contracts need only support interactive/turn-based and verifier-closed
goal-based execution. Time-based and proactive execution remain future optional
profiles and require explicit project authority.

### 5.12 No Work Is A Valid Result

Agents and self-improvement loops can invent changes to justify their run.
SAGE-Kit must allow a node to conclude that existing evidence already satisfies
the requested decision.

`NO_ACTION_REQUIRED` is not an unverified skip. It must identify the inspected
scope, the applicable acceptance or routing decision, and the evidence that
remains valid. A node contract must explicitly allow this outcome before it can
satisfy a required join.

### 5.13 Product Failures Should Become Harness Evaluations

Real framework failures should become anonymized, deterministic scenario cases.
The evaluation corpus should cover authority selection, history isolation,
platform path identity, dirty-worktree handling, process cleanup, timeout
classification, evidence reuse, review convergence, and ordinary formatting or
status findings.

The corpus evaluates decisions and state transitions, not whether documentation
contains preferred wording. It grows from observed failures and protects the
rebuild against repeating expensive incidents.

## 6. Target Information Architecture

### 6.1 Canonical Contracts

Only canonical contracts define normative rules. The target logical ownership
is:

| Contract | Owns |
|---|---|
| Core | principles, precedence, adoption modes, compatibility |
| Authority | roles, permissions, gates, approval and submit boundaries |
| Graph | nodes, edges, joins, graph state and bounded evolution |
| Loop and Verification | local verifier, convergence, evidence and invalidation |
| Resource and Isolation | worktrees, leases, processes and shared resources |

These may initially remain at compatible paths. Physical directory moves are
not required to establish logical ownership.

### 6.2 Operational Guides

Planning, orchestration, execution, review, adoption, and platform documents
explain how to apply canonical contracts. They must link to rules rather than
restate them as independent authority.

### 6.3 Optional Profiles

Task Dispatch, state-machine, control-plane, browser, release, or other
specialized profiles remain opt-in. File presence never activates a profile.

### 6.4 Templates

Templates provide fields and examples. They must be explicitly
non-authoritative and link each governed field to its canonical owner.

This describes template source files. A template instantiated and accepted by a
project may become project authority according to that project's authority
model. The uninstantiated framework template never overrides it.

Template updates must preserve their product-lifecycle capability while
separating planning, runtime, and history:

| Template group | Rebuild treatment |
|---|---|
| Owner Intake, Project Profile, Technical Design | Preserve content; clarify that they own product definition, not runtime state. |
| Capability Map and Roadmap | Preserve breadth and milestone-quality checks; do not make them live schedulers. |
| Milestone, Entry Gate, and Phase | Keep objectives, dependencies, acceptance, risks, rollback, verifier, and stop conditions; remove live attempt, lease, and worker-state duplication. |
| Execution Packet | Become the human-readable authority input or view for a compact Graph Contract. |
| Result and Final Review Packets | Aggregate typed Node Results, joins, findings, corrections, and verdicts without copying full worker transcripts. |
| Closeout | Remain a compact human-readable historical outcome and evidence index, not an event database. |

Templates are selected by task and governance level. Their presence does not
make every template mandatory, and Light work must not inherit the Heavy
template set.

### 6.5 Skill

The Skill is a routing and adoption adapter. It should:

1. identify whether SAGE-Kit is active;
2. resolve project authority;
3. choose Light, Standard, or Heavy;
4. route to the relevant canonical contract;
5. route domain work to specialist capabilities;
6. require a typed result;
7. preserve project authority over Skill defaults.

The Skill must not contain a second copy of the full governance framework.

## 7. Target Runtime Model

### 7.1 Graph Contract

The first contract should be deliberately small:

```json
{
  "graph_id": "M36",
  "generation": 1,
  "nodes": [
    {
      "id": "P01",
      "role": "worker",
      "depends_on": [],
      "permission": "WRITE_AUTHORIZED",
      "verifier": "focused-p01",
      "output_contract": "node-result-v1",
      "resources": ["repo-write"]
    }
  ],
  "joins": [
    {
      "id": "implementation-ready",
      "requires": ["P01", "P02"],
      "policy": "all-required"
    }
  ]
}
```

The contract may be generated from normalized SPEC authority. It is not a new
mandatory project planning document.

### 7.2 Node State

The initial state model is:

```text
PENDING
  -> READY
  -> RUNNING
  -> WAITING_RESOURCE
  -> SUCCEEDED | NO_ACTION_REQUIRED | FAILED
  -> NEEDS_CORRECTION | HANDOFF | BLOCKED | CANCELLED
```

Transitions must be deterministic and auditable. A node cannot grant itself
new authority or mutate an approval gate.

### 7.3 Node Result

Every executable or review node returns the same envelope:

```json
{
  "node_id": "P01",
  "status": "SUCCEEDED",
  "changed_paths": [],
  "evidence_refs": [],
  "findings": [],
  "authority_change": false,
  "proposed_next_nodes": []
}
```

Node results contain decisions and evidence references, not hidden reasoning or
complete chat transcripts.

### 7.4 Join Policies

The initial policies are:

- `all-required`: every required node must pass;
- `required-plus-optional`: required nodes pass; optional evidence may be
  unavailable with a recorded reason;
- `first-success`: redundant, equivalent, read-only exploration only;
- `manual-gate`: PM or owner decision required;
- `corrective-join`: finding, correction, focused evidence, and targeted
  re-review must match.

Authority, safety, approval, validator, and acceptance joins may never use
majority voting to bypass a required failure.

### 7.5 Local State Store

The reference local representation is:

```text
.sagekit/runtime/graph.json
.sagekit/runtime/state.json
.sagekit/runtime/events.jsonl
```

- JSON stores the current contract and snapshot.
- JSONL stores append-only observable events.
- CSV may be exported for analysis but is not authoritative.
- Runtime files remain ignored and are not required in source control.
- Projects may use host memory or another compatible store instead.

### 7.6 Ready-Node Resolver

SAGE-Kit should initially expose a pure decision function, not a scheduler:

```text
resolve_ready_nodes(graph, state, available_resources)
```

It reports ready, waiting, blocked, and completed nodes with reasons. The host
runtime remains responsible for creating agents and running tools.

### 7.7 Bounded Graph Evolution

Arbitrary graph rewriting is out of scope. Later stages may permit only named
operations:

- add a corrective node;
- add focused verification;
- add a read-only investigation node;
- split a pending node;
- disable an optional pending node.

Graph evolution must preserve a parent digest, authority ID, reason, generation,
and immutable completed-node history. It cannot lower verification, widen
permission, remove approval gates, or erase failure evidence.

### 7.8 Mainline And Exploration Admission

Before adding an investigation, safety analysis, compatibility branch, test
matrix, reviewer, or corrective node, the controller must answer:

1. Which active requirement, acceptance criterion, gate, changed surface, or
   observed evidence does this node support?
2. Can its result change the current execution or acceptance decision?
3. Is the work inside current authority?
4. What is the cheapest decisive check?
5. Does an existing node or evidence already answer the question?

If questions 1 or 2 have no concrete answer, the work does not enter the active
graph. If question 3 is no, return a proposal or PM decision request. Questions
4 and 5 prevent broad suites and duplicate reviewers when a focused check is
decisive.

Node-local discovery ends when the next safe action is determined and no
blocking uncertainty remains. Additional exploration requires new evidence,
not merely another imaginable edge case. Findings should be batched once per
review scope; follow-up review targets corrected or newly evidenced surfaces.

Test admission is limited to:

- acceptance or contract verification;
- regression protection for changed behavior;
- reproduction of an observed defect;
- a verifier required by an active gate;
- a concrete safety or compatibility risk on the changed surface.

Combinatorial platform, threat, performance, packaging, or integration testing
requires explicit product authority or evidence that the changed surface
reaches that boundary. General caution alone is not sufficient.

### 7.9 Graph Admission And Collapsibility

A task starts as one bounded loop. It is promoted to a graph only when at least
one concrete signal requires another node:

- a specialist needs a genuinely separate context or tool boundary;
- independent work can run in parallel and later join;
- an auditable branch, independent evaluator, or authority separation is
  required;
- one context can no longer safely hold the relevant state.

Every proposed node must name the signal that justifies it. Before accepting a
graph or graph expansion, ask whether a node can be collapsed into another node
without changing authority, independence, parallelism, verification quality, or
the final result. If it can, remove the node.

Graph admission is independent of milestone size. Heavy controller governance
may still contain Light or Standard single-loop workers.

### 7.10 Autonomy Contract

Graph and node contracts record autonomy separately from governance:

```json
{
  "governance_level": "Heavy",
  "autonomy_level": "goal-based",
  "completion_verifier": "review-join-v1",
  "human_gates": ["product-scope", "submit"]
}
```

The initial autonomy values are:

- `turn-based`: the host may execute allowed tools for the current turn but
  does not start a new turn automatically;
- `goal-based`: the host may continue while an external completion verifier,
  convergence rule, and authority envelope permit it.

Time-based and proactive triggers are not enabled merely by schema presence.

### 7.11 No-Action Result

`NodeResult` includes a distinct terminal outcome:

```json
{
  "node_id": "review-existing-evidence",
  "status": "NO_ACTION_REQUIRED",
  "inspected_scope": ["P03"],
  "decision": "existing focused evidence remains valid",
  "evidence_refs": ["E-P03-04"]
}
```

The transition resolver treats this outcome as successful only when the node
contract permits no action and the referenced evidence matches current inputs.
It is never converted silently into `SUCCEEDED`, `PASS`, or a waived failure.

### 7.12 Observable Trace And Memory Tiers

Runtime events record observable inputs, tool or adapter actions, bounded output
references, state transitions, decision reasons, evidence, timings, and retry
identity. They do not record private chain-of-thought or copy complete tool
transcripts into the event log.

Memory remains separated into:

```text
run state       -> runtime snapshot and events
session handoff -> configured ACTIVE_CONTEXT
project memory  -> Profile, Design, decisions, and Closeout
```

Only relevant summaries cross tiers. A run event does not automatically become
long-term project authority.

## 8. Source-Of-Truth Matrix

| Fact | Canonical location |
|---|---|
| Product purpose and acceptance | Project SPEC / milestone planning |
| Current human handoff | Configured `ACTIVE_CONTEXT` |
| Stable document routing | Configured routing authority |
| Execution topology | Active Graph Contract |
| Live node state | Runtime state store or host memory |
| Node completion | `NodeResult` and evidence references |
| Candidate identity | Candidate/evidence state |
| Accepted history | Closeout and immutable evidence references |
| Framework rules | Canonical SAGE-Kit contracts |
| Platform adaptation | Skill or host adapter guidance |

One fact must not require synchronized writes to several rows in this table.

## 9. Governance Modes

### Light

- one bounded loop;
- no persisted graph required;
- focused verification;
- no independent reviewer by default;
- compact completion result.

### Standard

- a small graph when there are real dependencies or specialist contexts;
- typed node results;
- one integration join;
- targeted review when risk requires it;
- runtime snapshot optional.

### Heavy

- PM, Coder, and Final Review controller graph;
- explicit DAG, joins, authority and resources;
- parallel workers only when ownership is disjoint;
- independent review context;
- bounded corrective evolution;
- frozen final candidate and one final verification graph.

Heavy at the controller layer does not make every child node Heavy.

## 10. Incremental Delivery Plan

Each stage must be independently reviewable and reversible.

### Stage 0: Baseline And Authority Inventory

Purpose: understand the current product without changing behavior.

Deliverables:

- map each repeated rule to its current files;
- nominate one canonical owner per rule;
- classify files as canonical, guide, profile, template, compatibility, or
  historical;
- record compatibility-sensitive paths and packaged mirrors;
- establish targeted tests for existing authority precedence;
- inventory the complete zero-to-product template chain and the accepted user
  outcomes each template supports;
- identify speculative-analysis, duplicate-review, and over-testing rules that
  lack a current decision link;
- classify current responsibilities against Prompt, Context, Harness, Loop, and
  Graph layers;
- map coverage and imbalance across context, tools, orchestration, state,
  evaluation, and constraints/recovery;
- collect observed framework failures as proposed scenario evaluations;
- identify graph nodes that could be collapsed without changing outcomes.

Acceptance:

- no product behavior change;
- no consumer migration;
- no historical rewrite;
- every high-impact rule has one proposed owner.

### Stage 1: Documentation Authority Consolidation

Purpose: eliminate multiple apparent sources of truth.

Deliverables:

- canonical ownership markers;
- references replacing duplicate normative text;
- templates marked non-authoritative;
- Skill reduced toward routing rather than rule duplication;
- compatibility pointers retained at existing paths;
- template responsibilities separated into product planning, active execution,
  runtime state, and historical outcome;
- mainline/exploration admission defined once and referenced by controllers,
  reviewers, and platform adapters.

Acceptance:

- project startup requires a smaller read set;
- no rule loses authority or becomes weaker;
- the zero-to-product path remains complete and demonstrably usable;
- existing project document paths remain usable;
- no new mandatory project artifact.

### Stage 2: Graph Contract And Node Result

Purpose: make the documented graph portable and machine-readable.

Deliverables:

- language-neutral Graph Contract schema;
- Node Result schema;
- node state enum;
- join policy enum;
- graph-admission and collapsibility rules;
- governance and autonomy as separate fields;
- `NO_ACTION_REQUIRED` with evidence-bound semantics;
- normalization from existing SPEC/packet inputs;
- pure validation APIs.

Acceptance:

- the same normalized SPEC produces the same graph digest;
- path relocation does not alter semantic identity;
- invalid authority, dependency cycles, and unsafe joins fail closed;
- Light mode remains graph-artifact optional.

### Stage 3: Runtime Snapshot And Event Log

Purpose: support handoff, replay, and audit without Markdown state churn.

Deliverables:

- JSON graph snapshot;
- JSON state snapshot;
- append-only JSONL events;
- atomic write and recovery rules;
- stable event and run identities;
- observable trace fields without private reasoning or unbounded transcripts;
- explicit run-state, session-handoff, and project-memory tier boundaries;
- export-only CSV view.

Acceptance:

- interrupted runs recover deterministically;
- partial writes cannot produce false success;
- concurrent unauthorized writers are rejected;
- project history documents remain unchanged.

### Stage 4: Ready-Node And Transition Resolver

Purpose: let hosts execute the graph without a SAGE-Kit scheduler service.

Deliverables:

- deterministic ready-node resolution;
- resource-aware waiting reasons;
- transition resolution from typed results;
- dependency-cycle and unreachable-node detection;
- compact graph status output for host adapters.

Acceptance:

- the resolver has no process-launch side effects;
- independent nodes are returned together;
- serial gates remain serial;
- a failed node skips only dependent successors;
- host runtimes retain execution ownership.

### Stage 5: Evidence Lineage And Incremental Invalidation

Purpose: stop broad re-review and repeated verification.

Deliverables:

- node input and output fingerprints;
- evidence dependency edges;
- affected-node invalidation;
- evidence reuse decision records;
- join-level integration invalidation;
- an anonymized scenario-evaluation corpus grown from observed failures;
- fresh-context or deterministic evaluators selected by decision risk.

Acceptance:

- unrelated evidence remains valid after a narrow change;
- authority or contract changes invalidate all dependent evidence;
- status-only corrections trigger targeted consistency review;
- final evidence cannot be reused across a changed candidate;
- a harness change cannot pass solely because its authoring agent approves it;
- previously observed governance failures remain reproducibly covered.

### Stage 6: Bounded Graph Evolution

Purpose: adapt to findings without arbitrary runtime redesign.

Deliverables:

- corrective, verification, investigation, split, and optional-disable
  operations;
- graph generation lineage;
- PM preauthorization envelope;
- graph-change proposal and acceptance flow;
- convergence and no-progress handling.
- explicit permission for an evolve proposal to recommend no change.

Acceptance:

- workers cannot expand their own permission;
- completed nodes cannot be rewritten;
- gates and required verifiers cannot be removed;
- ordinary C0/C1 corrections continue automatically when preauthorized;
- authority-changing proposals return to PM;
- no evolve operation may directly edit canonical governance without an
  independent decision and accepted authority.

### Stage 7: Host Adapters And Skill Simplification

Purpose: make the contracts practical across agent runtimes.

Deliverables:

- Codex-native orchestration guidance;
- Claude Code and other host adapter mappings;
- capability-routing boundary;
- thin Skill routing instructions;
- fallback behavior for hosts without structured state support.

Acceptance:

- no CLI is required;
- no complete framework tree must be copied into consumer projects;
- installed Skill never overrides project authority;
- unsupported host capabilities degrade honestly rather than false-green.

### Stage 8: Compatibility And Deprecation

Purpose: retire duplication without breaking long-lived projects.

Deliverables:

- legacy-path compatibility map;
- explicit contract-version selection;
- deprecation notes without forced migration;
- immutable historical validation routing;
- removal candidates supported by usage evidence.

Acceptance:

- accepted history is not rewritten;
- current authority never falls back to an older contract after failure;
- ambiguous mixed authority fails closed;
- a deprecated document cannot silently remain a second authority.

## 11. Product Metrics

Do not depend on model-token or subscription usage data. Measure observable
workflow events instead:

- number of files in the default controller startup read set;
- number of canonical-rule resolution hops;
- number of duplicate normative rule locations;
- manual handoffs per milestone;
- node invocations and duplicate node invocations;
- focused, lane, and final verification executions;
- reused versus invalidated evidence;
- full review versus targeted re-review count;
- time waiting for resources;
- active and peak managed processes;
- graph nodes completed, blocked, corrected, or handed off;
- false-green findings;
- state reconciliation findings caused only by duplicated records;
- active graph nodes with no acceptance, gate, changed-surface, or evidence
  linkage;
- optional findings incorrectly promoted into blockers;
- tests and reviewers whose result cannot change a current decision;
- repeated exploration of the same question without new evidence;
- nodes admitted without a graph-promotion signal;
- nodes that can be collapsed without changing authority or results;
- `NO_ACTION_REQUIRED` frequency and evidence validity;
- steps and retries to reach each terminal decision;
- scenario-evaluation pass rate for previously observed framework failures.

Metrics diagnose product behavior. They are not universal blockers unless an
adopted project contract explicitly makes one a gate.

## 12. Safety And Efficiency Invariants

Every rebuild stage must preserve:

1. Project authority outranks framework defaults and Skill guidance.
2. A node cannot grant itself authority.
3. Graph routing cannot bypass approval, safety, validator, or acceptance
   failures.
4. Review remains independent from implementation.
5. Submit authority is separate from implementation and review authority.
6. Historical documents are not current execution authority.
7. Runtime state is not committed by default.
8. Unchanged evidence is reused; changed dependencies are invalidated.
9. Full verification runs only for a frozen eligible candidate.
10. Light work is not forced through Heavy orchestration.
11. Parallelism requires dependency, ownership, and resource independence.
12. A host that cannot enforce a boundary reports the limitation honestly.
13. Every accepted rebuild stage preserves or strengthens existing user-visible
    capabilities; simplification removes duplication, not outcomes.
14. Product discovery, roadmap, milestone planning, execution, review,
    acceptance, and closeout remain an end-to-end supported lifecycle.
15. Speculative risk does not become active work without an authority,
    changed-surface, evidence, or acceptance link.
16. Use the minimum decisive verification; do not run broad tests or reviews
    solely to increase perceived confidence.
17. Diagnose and repair the lowest failing layer before expanding an outer
    layer.
18. A graph node must earn its coordination cost through specialization,
    independence, parallelism, or auditable control flow.
19. Governance strength and autonomy are independent; neither implies the
    other.
20. A verified no-action result is valid work and must not be converted into
    invented changes.
21. Self-improvement may propose canonical changes but cannot approve or apply
    them as its own evaluator.

## 13. Migration Rules

- Do not update every existing project when a stage is accepted.
- New projects may adopt the latest contracts directly.
- Existing projects adopt by explicit project authority at a safe boundary.
- Accepted milestones remain under their historical contract.
- Current active work must not change contract version in the middle of an
  executing node unless PM explicitly authorizes the transition.
- Compatibility adapters translate inputs; they do not rewrite history.
- Old documents may remain as audit records after their normative content is
  superseded.

## 14. Immediate Next Step

Start only Stage 0.

The next working session should produce a rule-ownership inventory and a
proposed canonical map. It must not yet move files, rewrite the Skill, add the
Graph Contract, or change runtime behavior.

Stage 0 should answer:

1. Which rules are repeated?
2. Which current file should own each rule?
3. Which copies can become references?
4. Which paths are compatibility-sensitive?
5. Which existing tests protect the meaning of each rule?
6. What is the smallest Stage 1 diff that reduces duplicate authority?

Only after Stage 0 review should Stage 1 receive implementation authority.

## 15. Decision Log

| Decision | Current position | Status |
|---|---|---|
| Product shape | Governance Harness, not coding agent | Proposed for rebuild |
| Execution model | Graph of bounded loops | Proposed for rebuild |
| CLI | Not part of the target product | Retained decision |
| Scheduler | Pure ready-node resolver first | Proposed |
| Dynamic graph | Bounded evolution only | Proposed |
| Graph storage | JSON/JSONL reference store; CSV export | Proposed |
| External graph database | Not required initially | Proposed |
| Historical migration | No automatic rewrite | Retained decision |
| Skill role | Thin router and adapter | Proposed |
| Zero-to-product lifecycle | Preserve as a core product capability | Retained decision |
| Capability monotonicity | Rebuild stages may not reduce accepted capability | Proposed as invariant |
| Divergent reasoning | Admit only decision-linked work into the active graph | Proposed |
| Template strategy | Preserve planning depth; separate runtime state and history | Proposed |
| Failure diagnosis | Correct Prompt, Context, Harness, Loop, or Graph at the lowest failing layer | Proposed |
| Harness completeness | Balance context, tools, orchestration, state, evaluation, and recovery | Proposed |
| Graph admission | Start with a loop; add only nodes that earn their coordination cost | Proposed |
| Autonomy | Model separately from Light, Standard, and Heavy governance | Proposed |
| No-action outcome | Evidence-bound `NO_ACTION_REQUIRED` is valid | Proposed |
| Harness evaluation | Grow deterministic scenarios from real framework failures | Proposed |
| First implementation stage | Authority inventory only | Ready for review |

## 16. Update Protocol For This File

This file remains a living blueprint until the rebuild is complete or
abandoned.

When updating it:

- preserve rejected alternatives and the reason for rejection;
- mark accepted stages and link their canonical contracts or commits;
- do not claim implementation from a proposal;
- do not turn planning metrics into gates without explicit product authority;
- keep immediate next work limited to one stage;
- move stable normative rules into their canonical owners instead of allowing
  this file to become another permanent governance source.

When all accepted decisions have canonical owners, this file should become a
historical design record rather than an active execution dependency.
