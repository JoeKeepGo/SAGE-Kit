# SAGE-Kit Rebuild Stage 0 Report

## 1. Status And Baseline

- **Observed fact:** Stage: `Stage 0: Baseline And Authority Inventory` only.
- **Observed fact:** Isolated worktree: `D:\Projects\SPEC Framework\.worktrees\rebuild-stage0`.
- **Observed fact:** Branch: `codex/rebuild-stage0`.
- **Observed fact:** Baseline and current HEAD at creation: `9c63ed187535b492b261bce1089bb552eecc619d`.
- **Observed fact:** Blueprint source worktree: `D:\Projects\SPEC Framework\.worktrees\cli-removal-harness-core`, branch `codex/cli-removal-harness-core`, HEAD `9c63ed187535b492b261bce1089bb552eecc619d`.
- **Observed fact:** `rebuild.md` was mechanically copied and both source and Stage 0 copies had SHA-256 `a90d1d9670d6bdce0f2814785733c06010d21844ce94bc754a1a164ab8aa2b2a` immediately after copy.
- **Observed fact:** Main worktree baseline was clean on branch `main` at `33ef90086508ece1ff4fb6bdc76c3f7abcfb85ab`.
- **Observed fact:** This report, `RULE_OWNERSHIP.csv`, and `SCENARIO_EVAL_CANDIDATES.json` are the only Stage 0 design outputs. No product code, governance source, Skill, template, schema, contract, validator, packaged mirror, or test was changed.
- **Observed fact:** `rebuild.md` is a blueprint, not current framework authority. Every owner in this report is a nomination until accepted in a later authorized stage.

Status: `STAGE_0_READY_FOR_REVIEW`.

## 2. Method And Read Scope

The controller followed `rebuild.md` Reading And Routing: Status, Product Thesis, Goals, Non-Goals, Stage 0, Safety And Efficiency Invariants, Decision Log, and only the named sections needed for the current classification. The repository was inspected with file inventories, heading extraction, targeted ranges, targeted test-source inspection, hash/layout comparisons, and narrowly scoped Git history for failure provenance. No test was executed.

Eight bounded investigation lanes were used:

| Lane | Scope | Completion |
|---|---|---|
| A | Core, Harness, governance, approval and quality authority | Complete, read-only subagent |
| B | Session, wave, phase, worktree, milestone graph/orchestration | Complete, read-only subagent |
| C | Execution economy, continuity, review, evidence, convergence | Complete, read-only subagent |
| D | Zero-to-product and templates | The read-only subagent was stopped after it did not return; Root completed the same bounded targeted read without starting a duplicate lane |
| E | Skill, generic references, host adapters and hooks | Complete, read-only subagent |
| F | Optional profiles, validation contracts, resources and compatibility | Complete, read-only subagent |
| G | Six-component and five-layer synthesis from A-F findings | Complete, read-only subagent; no repository reread |
| H | Failure scenarios from tests, design notes, code and targeted history | Complete, read-only subagent |

- **Observed fact:** Subagents wrote no files and ran no tests.
- **Observed fact:** Duplicate classification used normalized meaning, not text similarity alone: exact duplicate, same rule with different wording, rule plus stronger local constraint, guide/example repetition, compatibility mirror, and actual authority conflict.
- **Inference:** The 83-row inventory is a high-impact semantic baseline, not a claim that every sentence in the repository is a separate rule.

## 3. Repository Information Architecture

- **Observed fact:** The baseline contains 285 tracked files: 81 under `docs`, 142 under `sagekit`, 40 under `tests`, 13 under `skills`, and the remaining top-level/build metadata files.
- **Observed fact:** `docs` separates root product/templates, 18 agent documents, 23 general templates, 18 profile files, 13 contract files, and design material.
- **Observed fact:** `sagekit/resources` contains 80 packaged documentation resources, 13 validation-contract resources, 12 execution-document resources, and one resource-governance resource.

The current logical information architecture is:

| Class | Current examples | Stage 0 classification |
|---|---|---|
| Core/current contracts | `SAGE_CORE`, `SPEC_SOURCE_CONTRACT`, `GOVERNANCE_LEVELS`, `EXECUTION_ECONOMY`, validation contracts | Normative or compatibility authority at existing paths |
| Operational guides | Harness, Session, Wave, Phase, Worktree, Milestone Planning, Skill references | Application guidance; some currently restates rules normatively |
| Optional profiles | Task Dispatch, state-machine, control-plane-agent | Opt-in profile authority only when project authority activates it |
| Templates | Intake, profile, design, roadmap, milestone, packet, review, corrective, closeout | Fields and lifecycle outcomes; adopted instances may become project authority |
| Skill and host adapters | `skills/sage-kit/SKILL.md`, host references, agents, hooks | Trigger, routing, host-specific mapping and enforcement |
| Packaged resources | `sagekit/resources/**` | Distribution/compatibility copies or executable frozen bundles, never a second business authority |
| Runtime implementations | candidate, evidence, convergence, validators, process supervisor | Executable semantics and evidence, not competing documentation authority |
| Historical/provenance | closeouts, frozen versions, design notes | Audit/history; not current execution authority |

Rule-location interpretation is explicit and deterministic:

| File class | Exact paths or defined family | Default rule-location action |
|---|---|---|
| Canonical/current contract | `docs/SAGE_CORE.md`; `docs/agent/SPEC_SOURCE_CONTRACT.md`; `docs/agent/GOVERNANCE_LEVELS.md`; `docs/agent/EXECUTION_ECONOMY.md`; `docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md`; accepted version-local `contract.json` files | Retain the nominated rule; proposal remains unaccepted until review |
| Specialist operational owner | `docs/agent/SESSION_ORCHESTRATION.md`; `docs/agent/WAVE_EXECUTION.md`; `docs/agent/WORKTREE_ISOLATION.md`; `docs/agent/CAPABILITY_ADAPTERS.md`; `docs/agent/HOST_RESOURCE_GOVERNANCE.md`; `docs/agent/MILESTONE_PLANNING.md`; `docs/agent/AGENT_HARNESS.md` | Retain its local specialization; replace only duplicated generic semantics with a pointer |
| Generic guide/router | `skills/sage-kit/SKILL.md`; `skills/sage-kit/references/adoption.md`; `planning.md`; `execution.md`; `review-completion.md` | Retain trigger, route, checklist and example; convert copied normative blocks to references |
| Host adapter | `skills/sage-kit/references/claude.md`; `opencode.md`; `kimi-runtime.md`; `skills/sage-kit/agents/openai.yaml`; Claude agents and the `.sh`/`.ps1` hook pair | Retain platform-specific discovery, permission, hard/soft limitation and enforcement delta |
| Optional profile | `docs/profiles/task-dispatch/**`; `docs/profiles/state-machine/**`; `docs/profiles/control-plane-agent/**` | Retain profile-local authority and opt-in behavior; templates retain fields |
| Source template | Root `docs/*_TEMPLATE.md` files and tracked `docs/templates/*_TEMPLATE.md` files | Retain lifecycle/configuration fields; convert generic rule definitions to owner pointers |
| Documentation mirror | The corresponding tracked path below `sagekit/resources/docs/**` | Retain compatibility and required parity; never count as a business owner |
| Execution-contract source/mirror family | For each of versions `2026.7.19.3` and `2026.7.20.1`: `contract.json`, three schemas and two profile JSON files below each of `docs/contracts/execution-documents`, `sagekit/resources/execution_documents`, and `sagekit/resources/docs/contracts/execution-documents` | Source version owns local identity; both packaged roots retain byte mirrors |
| Validation resource family | Named files below `sagekit/resources/contracts/v0`, `v1`, and `v2` | v0/v1 retain frozen snapshots; v2 retains current canonical-JSON resources; none is an independent prose owner |
| Runtime implementation/test | `sagekit/*.py`, `sagekit/validation_contracts/*.py`, and `tests/**` cited in the CSV | Implementation or evidence, not a competing documentation authority |
| Historical/provenance | `docs/design/EXECUTION_ECONOMY_REDESIGN.md`, accepted closeouts, and frozen version provenance | Retain as history; do not route current execution from it |

`RULE_OWNERSHIP.csv.current_locations` is the exact semicolon-separated occurrence set for ordinary files. Defined version/resource families are expanded by the table above and by repository inventory during validation. `current_authority_class` describes the semantic relationship of that set; `other_locations_action` is the dominant non-owner action; any stronger local constraint, template-field exception, or mirror exception is stated in the row notes. Vague placeholders such as “multiple templates” or “host-specific references” are not used.

- **Inference:** The dominant information-architecture defect is duplicated normative prose across otherwise useful classes, not a lack of documents.
- **Proposal:** Establish logical ownership at compatible existing paths before considering physical moves.

## 4. Canonical Ownership Summary

`RULE_OWNERSHIP.csv` contains 83 normalized rules. The largest proposed-owner concentrations are:

| Proposed owner | Rules |
|---|---:|
| `docs/agent/EXECUTION_ECONOMY.md` | 13 |
| `docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md` | 10 |
| `docs/agent/WAVE_EXECUTION.md` | 7 |
| `docs/agent/GOVERNANCE_LEVELS.md` | 6 |
| `docs/SAGE_CORE.md` | 6 |
| `docs/agent/CAPABILITY_ADAPTERS.md` | 5 |
| `docs/agent/SESSION_ORCHESTRATION.md` | 5 |
| `docs/agent/AGENT_HARNESS.md` | 3 |
| `docs/agent/SPEC_SOURCE_CONTRACT.md` | 3 |
| `docs/profiles/task-dispatch/DISPATCH_PROFILE.md` | 3 |
| All remaining proposed owners | 22 across 19 existing paths |

Logical nominations are:

- **Proposal:** Core owns precedence, adoption principles, proportionality, and broad graph admission.
- **Proposal:** `SPEC_SOURCE_CONTRACT` owns source selection and active/context/history classification.
- **Proposal:** `GOVERNANCE_LEVELS` owns roles, permission modes, waiver, approval and submit separation.
- **Proposal:** `EXECUTION_ECONOMY` owns local review topology, verification admission, candidate/evidence lifecycle, convergence and normalization.
- **Proposal:** `WAVE_EXECUTION` owns DAG, dependency, join/barrier, parallel admission and affected-node serialization at its current path.
- **Proposal:** `SESSION_ORCHESTRATION` retains Heavy controller topology and detailed deterministic closure unless a later accepted move is demonstrably smaller.
- **Proposal:** `WORKTREE_ISOLATION`, `CAPABILITY_ADAPTERS`, `HOST_RESOURCE_GOVERNANCE`, and optional profile READMEs retain their specialist local rules.
- **Proposal:** Lifecycle templates retain their outcome and input fields while routing generic governance to owners.
- **Unresolved question:** There is no accepted standalone Graph contract today. `WAVE_EXECUTION` is the smallest existing-path nomination, not an already-promoted authority.
- **Unresolved question:** Universal optional-profile activation is clearly intended and explicit for Task Dispatch, but the proposed cross-profile Core owner is not yet an accepted general rule for every profile.

## 5. Duplicate Authority Findings

| Group | Classification | Finding | Proposed treatment |
|---|---|---|---|
| Source precedence and source classes | Same rule, different wording | Core, Harness, Skill and generic references repeat `SPEC_SOURCE_CONTRACT` subsets | Canonical owner plus pointers |
| Governance, roles, permissions, waiver and submit | Guide/template repetition with weaker local wording | Governance meaning is copied into Harness, engineering and packet templates | Retain fields; replace definitions with pointers |
| Final Review corrective authority | Actual authority conflict risk | Engineering template can be read as permitting the reviewer itself to become corrective-authorized | Correct wording to separate controller and worker authority |
| Waiver authority | Weaker template wording | Some templates say project owner while Governance requires named Waiver Authority/delegation | Align to named authority without changing project gates |
| DAG, parallelism, barriers and shared files | Same rule plus stronger local constraints | Milestone, Session and Wave each appear normative | Wave owns base rule; Session/Worktree keep local deltas |
| Lane status | Actual ambiguity | Wave status list omits nonterminal `HANDOFF` supported by lane/result templates | Normalize one definition |
| Review, evidence and convergence | Same rule plus one current conflict | Economy, Session, Skill references and packets repeat semantics; first no-progress handling conflicts | Economy owns semantics; Session/templates point to it |
| Deterministic closure | Guide/template repetition | Detailed Session contract is repeated in three templates and a Skill reference | Keep current detailed owner; retain fields and pointers |
| Lifecycle closeout order | Complete rule plus incomplete copy | Entry Gate omits Final Review/corrective/PM decision steps present in Milestone template | Align the incomplete copy |
| Adapter lifecycle | Guide repetition | Skill and task guides copy Capability Adapter rules | Retain host/task deltas; point generic semantics |
| Validation compatibility | Same rule plus compatibility implementations | Profile docs repeat selector, manifest and no-fallback rules | Compatibility document owns human-readable selection |
| Packaged resources | Compatibility mirrors | Copies can look like independent authority | Retain and classify; never delete as deduplication |

- **Observed fact:** Runtime/tests follow the Execution Economy rule that one same-root stagnant round is recorded and two consecutive rounds block. Session and an early Corrective field instead stop automatic continuation on the first round.
- **Inference:** This is a bounded documentation-authority conflict, not a P0/P1 runtime defect, because current precedence, implementation, and tests agree.
- **Proposal:** Resolve only the conflicting copies in Stage 1; do not alter convergence code.

## 6. Five-Layer Failure Classification

The inventory distribution is Prompt 3, Context 18, Harness 22, Loop 19, and Graph 21.

| Layer | Current modules | Main finding | Smallest correction class |
|---|---|---|---|
| Prompt | Skill trigger/router, Project Owner Entry, launch envelope | Prompt surfaces copy authority they should route to | Thin routing plus authority pointers |
| Context | Core, SPEC Source, active context, profile/design/capability/roadmap artifacts | Strong coverage but excessive downstream restatement | One source-selection owner and smaller startup set |
| Harness | Harness, Governance, Capability Adapters, Host Resource, profiles/contracts | Controls are broad; specialist owners are obscured by generic copies | Retain specialist owners; reduce generic duplicates |
| Loop | Execution Economy, Continuity, candidate/evidence/convergence/review, final/corrective packets | Mature evidence model; repeated broad review and no-progress wording are the main defects | Canonical economy rule plus targeted closure |
| Graph | Milestone Planning, Session, Wave, Phase, Worktree, execution/result packets | Procedural graph is rich but distributed; no runtime Graph contract exists yet | Optional admission rule and collapsible-node test; no Stage 1 runtime work |

- **Observed fact:** Graph/runtime proposals such as GraphContract, NodeResult, resolver and state store do not exist as current Stage 0 authority.
- **Proposal:** Correct the lowest failing layer. Do not answer ambiguous prompts with reviewers, context duplication with graph nodes, verifier weakness with workers, or runtime timeouts with governance prose.

## 7. Harness Six-Component Balance

The primary-component distribution is Context 10, Tools 5, Orchestration 22, State/Memory 10, Evaluation/Observability 13, and Constraints/Recovery 23.

| Component | Coverage | Duplication or gap | Balance judgment |
|---|---|---|---|
| Context | Precedence, source selection, source classes, lifecycle context | Skill/templates restate source rules | Strong but duplicative |
| Tools | Adapter lifecycle, resource contracts, install gates, host mappings | Uneven hard versus soft host enforcement; generic adapter prose repeats | Concentrated, not absent; enforcement honesty matters more than more controls |
| Orchestration | Single-loop path, Heavy controllers, waves, milestones, worktrees, packets | Most procedural duplication; no single accepted Graph owner | Over-invested in overlapping descriptions |
| State/Memory | Active context, checkpoint, candidate/evidence, historical closeout, frozen history | Ownership spans Context, Continuity, Session and Compatibility; graph state store is future work | Conceptually complete, operationally dispersed |
| Evaluation/Observability | Candidate/evidence, verification ladder, validators, review and acceptance artifacts | Broad re-review repetition; deterministic scenarios not yet uniform | Strong but repeatedly exercised |
| Constraints/Recovery | Governance, gates, stops, waiver, convergence, fallback, worktree and contract safety | Largest duplicate count; first no-progress wording conflict | Over-invested; repeated safeguards can become false blockers |

- **Inference:** Constraints/Recovery and Orchestration dominate the inventory because the same safety and coordination rules are narrated at several layers.
- **Proposal:** Remove only copies without decision value. Do not remove approval, role independence, exact-version validation, cleanup, or evidence invalidation boundaries.

## 8. Zero-To-Product Lifecycle Preservation

- **Observed fact:** The baseline supports a complete chain:

```text
idea
  -> Project Owner Entry / Intake
  -> Project Profile
  -> Technical Design
  -> Capability Map and Granularity Audit
  -> Milestone Roadmap
  -> Milestone and Entry Gate
  -> Phase plan
  -> Execution Packet
  -> Coder Result Packet
  -> Structural Gate
  -> Independent Final Review
  -> Bounded Corrective / Closure Verification
  -> PM or project-owner acceptance decision
  -> Ledger
  -> Closeout historical index
```

- **Observed fact:** Intake and candidate milestones are planning material, not implementation authority.
- **Observed fact:** Product Profile and Technical Design preserve product and architecture depth.
- **Observed fact:** Capability Map prevents a broad idea from being mislabeled as one executable milestone and forbids invented requirements outside active scope.
- **Observed fact:** Execution, review, correction, acceptance, submission, and history are separate outcomes.
- **Inference:** The lifecycle is complete. The risk is premature compression or making planning/history artifacts live runtime state, not a missing major stage.
- **Proposal:** Preserve every user outcome and field category while replacing generic governance prose with pointers.

## 9. Template Responsibility Matrix

| Template or guide | User outcome | Responsibility class | Preserve |
|---|---|---|---|
| Project Owner Entry / Intake | Convert an idea into understandable planning inputs | Prompt/planning | Five questions, observable outcomes, non-goals, risk, no implementation authority |
| Project Profile | Durable product boundary | Project planning authority when adopted | Users, problems, goals, constraints, requirements, privacy, runtime/data ownership |
| Technical Design | Architecture and contract boundary | Project planning authority when adopted | Components, data, public contracts, runtime, failure, security, tests |
| Capability Map | Complete capability view and milestone granularity | Planning | Capability outcomes, ownership, evidence, split decision |
| Milestone Roadmap | Sequenced product outcomes | Planning | One capability per milestone, validation, non-goals, phase decomposition |
| Milestone / Entry Gate | Accepted milestone envelope | Planning and approval input | Objective, inputs, gates, ownership, phases, stops, closure prerequisites |
| Phase | Bounded execution slice | Active execution authority when adopted | Files, ownership, contract, tests, runtime smoke, profiles, completion evidence |
| Execution Packet | Human-readable controller authority input | Active execution view | Authority refs, governance, permissions, DAG, resources, candidate, evidence, stops |
| Lane / Result Packet | Typed worker/controller outcome | Active result and handoff | Implemented scope, evidence, skips, concerns, HANDOFF/BLOCKED semantics |
| Structural Gate | Packet completeness before Final Review and post-review closure routing | Structural/evaluation gate, not technical review or acceptance | Scope, capability, governance, permission, ownership, evidence, tests, runtime smoke, gates, skips, blockers, waiver, receipt, convergence, PM-pending fields |
| Final Review Packet | Independent verdict | Review/evaluation | Scope, independence, findings, evidence, verdict, closure route |
| Corrective Packet | Bounded fix authority | Loop/recovery | Finding, exact writable scope, invariant, checks, stop and handoff rules |
| Completion Report | Per-phase or package completion evidence | Evaluation record | Gates, checks, runtime evidence, gaps, closure status |
| Ledger | Current milestone decision index | Project state record | Phase dispositions, decisions, evidence links; not duplicated runtime worker state |
| Closeout | Compact accepted historical outcome | History | Shipped outcome, decisions, evidence index, gaps, follow-up; not startup context |

Field-level lifecycle preservation is also explicit:

| Required concern | Current carriers | Proposed rebuild treatment |
|---|---|---|
| Dependencies | Capability Map, Roadmap, Milestone/Entry, Phase, Execution Packet DAG | Preserve fields; governance text may point to Wave/Milestone owners |
| Acceptance | Profile requirements, Entry/Phase gates, Structural Gate, Final Review, PM decision, Closeout | Preserve the entire review/corrective/PM sequence |
| Risks and non-goals | Intake, Project Profile, Entry Gate, Final Review residual risks | Preserve project-owned scope and evidence; do not invent requirements |
| Rollback/recovery | Technical Design error handling, Phase/Entry stop conditions, Corrective Packet, Worktree/process cleanup guidance | Preserve existing recovery carriers; no dedicated lifecycle `rollback` field was observed, so adding one is deferred rather than silently claimed |
| Verification and verifier independence | Technical Design, Capability Map, Phase, Execution/Result, Structural Gate, Final Review, Completion Report | Preserve exact checks, owner separation and targeted/full decision |
| Runtime smoke | Milestone, Entry, Phase, Result, Structural Gate, Corrective, Completion and Closeout | Preserve applicable evidence and explicit N/A reasoning |
| Stop and handoff | Entry, Phase, Execution Packet, Result, Structural Gate, Corrective, Completion | Preserve nonterminal HANDOFF and authority-bound stops |
| Evidence and history | Result, Structural Gate, Final Review, Completion, Ledger, Closeout | Link evidence; keep runtime state out of Markdown and closeout out of startup context |

Compatibility aliases and non-core execution helpers are not missing lifecycle stages: `ROADMAP_TEMPLATE.md` routes to `MILESTONE_ROADMAP_TEMPLATE.md`; `BOUNDARY_TEMPLATE.md` is a profile compatibility alias; Agent Prompt, Wave Plan, Lane Packet, Thin execution templates, adapter templates and validation-scope templates are optional operational/profile/compatibility support. No Stage 1A-1D proposal deletes or moves any of them.

- **Proposal:** Mark source templates as non-authoritative framework artifacts while preserving the possibility that completed project-adopted instances become project authority.
- **Proposal:** Planning owns intent, runtime state remains outside Markdown by default, and closeout owns compact history.
- **Unresolved question:** The targeted baseline found recovery/stop semantics but no dedicated lifecycle rollback field. This is a field-level baseline gap, not evidence that the end-to-end lifecycle chain is absent, and it is outside the Stage 1A-1D manifests.

## 10. Graph Admission And Collapsibility Findings

- **Observed fact:** Current Graph behavior is procedural and optional. Light work has a valid bounded-loop path without persisted Graph artifacts.
- **Proposal:** Admit another node only for separate authority, independent judgment, distinct context/tool boundary, safe parallel ownership, a real dependency/join, or auditable control flow.

Nodes or hops that may collapse when their condition is met:

| Candidate | Collapse condition |
|---|---|
| Extra Coder Controller | No separate scope, contaminated context, specialist boundary, or independent runtime owner |
| Duplicate Final Review Controller | Same scope, evidence and decision with no distinct contract/risk |
| Narrow integration worker | Coder owns the named integration files and all direct-edit conditions remain true |
| Workspace/environment setup controller | PM explicitly assigns setup ownership to Coder; never collapse into Final Review |
| Duplicate read-only discovery lanes | Same inputs and output cannot change a distinct decision |
| Milestone-wide serial barrier | Shared resource can be isolated to the affected node while a serial integration owner remains |

Never collapse:

- PM versus Coder versus Final Review;
- Final Review versus Corrective Worker;
- Final Review versus review-worktree creator;
- implementation versus an independent evaluator required by gate/risk;
- genuinely disjoint parallel writable ownership;
- post-verdict submit authority into implementation or review authority.

- **Unresolved question:** Whether a future formal Graph owner should remain physically in `WAVE_EXECUTION` or move later cannot be decided by Stage 0; no move is required for logical ownership.

## 11. Divergent Reasoning And Over-Testing Findings

- **Observed fact:** Templates expose many reviewer, validation, gate, stop and capability fields. Without one-topology guidance, fields can be interpreted as mandatory agents or repeated runs.
- **Observed fact:** Existing tests sometimes require identical governance phrases in the Skill and references, protecting duplication instead of an owner-plus-pointer relation.
- **Observed fact:** Full-suite/candidate counters protect against duplicate final verification more strongly than the general one-full-review rule protects against duplicate reviewer waves.
- **Observed fact:** Record-, evidence-, status- and pointer-only corrections already have targeted or deterministic closure paths.
- **Inference:** The main divergence mechanism is work admission without a current decision link: speculative architecture/safety work, second reviewers over identical scope, broad tests after unchanged evidence, and documentation consistency treated as product correctness.
- **Proposal:** Require every added reviewer, test, governance artifact or graph node to name the routing, acceptance, corrective or release decision it can change.
- **Proposal:** Classify work as REQUIRED, EVIDENCED_RISK, OPTIONAL or OUT_OF_SCOPE; only required and authorized evidenced-risk work enters the active graph.
- **Proposal:** Treat `NO_ACTION_REQUIRED` as a later evaluation/runtime proposal, not a current result type or Stage 1 behavior.

## 12. Compatibility-Sensitive Paths And Mirrors

| Path family | Relationship and required treatment |
|---|---|
| `sagekit/resources/docs/**` | Packaged documentation mirrors; source/mirror parity is tested; never an independent business owner |
| `docs/contracts/execution-documents/<version>/**` | Canonical versioned source contracts; exact layout and version locks are sensitive |
| `sagekit/resources/execution_documents/<version>/**` | Runtime loader mirrors; all 12 compared files were byte-identical to source |
| `sagekit/resources/docs/contracts/execution-documents/<version>/**` | Packaged documentation mirrors; byte-identical to source |
| `docs/profiles/task-dispatch/schemas/*.json` and `sagekit/resources/contracts/v2/*.schema.json` | Parsed/canonical-JSON equivalent, not raw-byte identical; line-ending normalization is not required |
| `sagekit/resources/contracts/v0/**` and `v1/**` | Frozen semantic snapshots with pinned resources, digests and provenance; do not regenerate or merge |
| `sagekit/resources/contracts/v2/**` | Current runtime resource paths and policy identity; templates embed its policy digest |
| `docs/contracts/resource-governance/conservative-host-v1.json` and packaged copy | Byte-identical source/mirror relationship |
| `docs/profiles/control-plane-agent/BOUNDARY_TEMPLATE.md` | Declared compatibility alias; retain until consumer/path provenance permits a smaller stub |
| configured source/context/routing paths and legacy fixed defaults | Configured paths take precedence; fixed paths remain compatibility defaults |
| `.sagekit/runtime/**` | Runtime state, gitignored by design; must not become committed project authority |
| Candidate fingerprint and continuity/checkpoint versions | Serialized compatibility and no-fallback semantics are behavior-sensitive |
| Host Skill profiles, Claude agents/hooks and OS-paired hook files | Platform discovery, permission and hard/soft enforcement compatibility |

- **Observed fact:** Packaged mirrors were not reread as independent rule sources.
- **Proposal:** Any future source-doc change updates its required packaged mirror atomically, but Stage 0 changes none.

## 13. Existing Test/Evidence Coverage

No tests were executed. Targeted inspection found existing coverage in these semantic groups:

| Semantic boundary | Existing evidence |
|---|---|
| Source precedence, no fallback, active/history classification | `tests/test_spec_sources.py`, `tests/test_active_scope.py`, `tests/test_validation_compatibility.py` |
| Optional profile activation and adapter declaration | `tests/test_spec_sources.py`, `tests/test_sagekit_check.py`, `tests/test_thin_documentation.py` |
| Frozen v0/v1 integrity and v2 current binding | `tests/test_frozen_contracts_and_containers.py`, `tests/test_validation_compatibility.py` |
| Execution-document exact version and mirrors | `tests/test_thin_execution_documents.py`, `tests/test_thin_routing.py`, `tests/test_thin_documentation.py` |
| Governance, change-control and review/corrective authority | `tests/unit/test_change_control_authority.py`, `tests/unit/test_review_corrective_contracts.py`, `tests/test_sagekit_check.py` |
| Candidate, evidence, verification and convergence | `tests/test_execution_economy.py`, `tests/test_verification_lifecycle.py`, `tests/test_convergence_authority.py`, related unit tests |
| Cross-platform paths and serial-file hooks | `tests/test_pathing.py`, `tests/test_claude_hooks.sh`, `tests/test_claude_hooks.ps1` |
| Process timeout, containment and cleanup | `tests/integration/test_process_supervisor.py`, `tests/integration/test_managed_execution.py` |
| Planning depth and parallel/barrier prose contracts | `tests/unit/test_planning_depth_contract.py`, targeted `tests/test_sagekit_check.py` |
| Mirror/reference closure | `tests/test_sagekit_check.py`, `tests/test_thin_documentation.py` |

Coverage gaps:

- **Observed fact:** No direct runtime Graph topology or join semantics test exists.
- **Observed fact:** No current `NO_ACTION_REQUIRED` implementation or test exists.
- **Observed fact:** No direct shallow-clone baseline regression was found.
- **Observed fact:** No macOS-specific path-alias case was found; Windows and POSIX cases exist.
- **Observed fact:** Optional capability absence has partial activation tests but no dedicated end-to-end fallback evaluation.
- **Observed fact:** General duplicate reviewer-wave prevention is less executable than duplicate final-suite prevention.
- **Proposal:** Address these through deterministic scenario evaluations at the authorized later stage, not Stage 1 product changes.

## 14. Scenario Evaluation Summary

`SCENARIO_EVAL_CANDIDATES.json` defines 12 anonymous, observable candidates:

1. accepted history isolation;
2. selected contract no-fallback;
3. shallow Git history baseline uncertainty;
4. cross-platform path aliases;
5. dirty worktree candidate binding;
6. process timeout and descendant cleanup;
7. duplicate full review/final verification;
8. evidence-only targeted review;
9. EOF/whitespace false blocker;
10. optional capability absence;
11. runtime limitation versus product failure;
12. divergent analysis and evidence-bound no-action.

- **Observed fact:** Every expected decision is externally observable; no scenario requests private reasoning.
- **Observed fact:** Scenarios contain no consumer project names, accounts, credentials, consumer paths or private internal fields.
- **Observed fact:** Shallow history, macOS-specific aliases, end-to-end optional fallback and no-action are explicitly labeled gaps or proposals rather than verified incidents.
- **Observed fact:** Schema version 2 separates 7 `direct_regression`, 2 `observed_failure`, and 3 `prospective_hypothesis` candidates, and records both `first_relevant_stage` and `admission_status`.
- **Observed fact:** First-relevant-stage routing is Stage 2: 1, Stage 3: 4, Stage 5: 3, Stage 7: 2, and Stage 8: 2. This routing is not implementation authorization.
- **Observed fact:** The 7 direct regressions and 2 observed failures are `admitted_candidate`; all 3 prospective hypotheses are `hypothesis_unadmitted`.
- **Proposed rebuild control:** A `hypothesis_unadmitted` scenario cannot automatically generate a test or implementation node, expand a stage, or become an acceptance blocker. Admission requires project authority, real observed evidence, or explicit authorization for the relevant stage.

## 15. Capability Non-Regression Risks

The following must remain true through any accepted rebuild stage:

- project authority and exact approval gates outrank framework and adapters;
- explicit/configured source failure never falls back silently;
- accepted history retains frozen semantics and is not active execution input;
- Light, Standard and Heavy remain selectable per scope;
- PM, Coder, Final Review, Corrective Worker, waiver and submit authority stay independent;
- zero-to-product remains complete from idea to closeout;
- optional profiles and capabilities remain opt-in and have safe absence behavior;
- host hard/soft limitations remain honest across Windows, macOS and Linux;
- working-tree candidates stay explicit and digest-bound;
- evidence is reused only while dependencies match;
- packaged paths, versioned contracts, semantic mirrors, byte mirrors and compatibility aliases remain usable;
- template field removal never loses product goals, boundaries, gates, rollback, verification, runtime smoke, evidence, stop, handoff or history outcomes;
- Graph is not imposed on Light work and node collapse never weakens independent authority or safe parallel ownership.

- **Inference:** The largest regression risk in Stage 1 is deleting duplicate-looking content before replacing its routing/load-order or template-field function.

## 16. Proposed Stage 1 Minimal Scope

Stage 1 remains unauthorized. The former 33-rule Stage 1A proposal is split into four independently acceptable and non-auto-mergeable proposals. Only **Stage 1A: Authority Kernel** is a candidate for the next implementation session; Stage 1B, 1C and 1D are recorded but unauthorized later work. Physical file overlap does not merge manifests: every later stage must rebaseline and edit only the sections needed for its own rules.

### Stage 1A: Authority Kernel — next candidate, not yet authorized

- **Single objective:** Make Core/Governance ownership unambiguous, correct direct authority conflicts, and turn in-manifest duplicate definitions into canonical pointers while preserving project gates, template fields, Light/Standard/Heavy selection, role separation, waiver authority and submit authority.
- **Exact rule manifest (8):** `SAGE-AUTH-001`, `SAGE-AUTH-003`, `SAGE-AUTH-004`, `SAGE-AUTH-005`, `SAGE-AUTH-006`, `SAGE-AUTH-007`, `SAGE-AUTH-008`, `SAGE-AUTH-009`.
- **Proposed canonical owners:** `docs/SAGE_CORE.md` (`SAGE-AUTH-001`, `SAGE-AUTH-009`); `docs/agent/GOVERNANCE_LEVELS.md` (`SAGE-AUTH-003` through `SAGE-AUTH-008`). These remain nominations until an authorized implementation accepts them.
- **Exact candidate source file manifest:** `docs/SAGE_CORE.md`; `docs/agent/GOVERNANCE_LEVELS.md`; `docs/agent/AGENT_HARNESS.md`; `docs/agent/SESSION_ORCHESTRATION.md`; `docs/APPROVAL_GATES_TEMPLATE.md`; `docs/ENGINEERING_SYSTEM_TEMPLATE.md`; `docs/QUALITY_GATES_TEMPLATE.md`; `docs/templates/AGENT_PROMPT_TEMPLATE.md`; `docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md`; `docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md`; `docs/templates/FINAL_REVIEW_PACKET_TEMPLATE.md`; `docs/templates/CORRECTIVE_PACKET_TEMPLATE.md`; `docs/templates/ENTRY_GATE_TEMPLATE.md`; `docs/templates/MILESTONE_CLOSEOUT_TEMPLATE.md`.
- **Packaged mirrors:** only the exact relative counterparts of the candidate `docs/**` files under `sagekit/resources/docs/**`, and only when their source counterpart changes.
- **Directly coupled tests:** `tests/test_spec_sources.py`; `tests/test_active_scope.py`; `tests/unit/test_planning_depth_contract.py`; `tests/unit/test_review_corrective_contracts.py`; `tests/unit/test_change_control_authority.py`; `tests/test_sagekit_check.py`.
- **Forbidden scope:** Context, Graph, Loop, Skill, adapter, host hook, profile, runtime, schema, contract and validator behavior; template-field deletion; consumer adoption; history rewrite; any rule outside the eight-rule manifest.
- **Acceptance claim:** For the eight manifested rules and candidate files only, each rule has one explicit owner, direct conflicting authority wording is removed, other normative copies point to that owner, and no project gate, role/permission separation, governance level, waiver, submit boundary, template outcome or compatibility path is weakened.

### Stage 1B: Context And Graph Pointers — unauthorized later work

- **Single objective:** Consolidate launch-envelope, source-classification, context-loading and existing Graph/Wave pointers without creating an execution runtime.
- **Exact rule manifest (9):** `SAGE-AUTH-010`, `SAGE-CTX-001`, `SAGE-CTX-002`, `SAGE-CTX-005`, `SAGE-GRF-001`, `SAGE-GRF-002`, `SAGE-GRF-005`, `SAGE-GRF-006`, `SAGE-GRF-011`.
- **Proposed canonical owners:** `docs/agent/AGENT_HARNESS.md` (`SAGE-AUTH-010`, `SAGE-CTX-005`); `docs/agent/SPEC_SOURCE_CONTRACT.md` (`SAGE-CTX-001`, `SAGE-CTX-002`); `docs/SAGE_CORE.md` (`SAGE-GRF-001`); `docs/agent/WAVE_EXECUTION.md` (`SAGE-GRF-002`, `SAGE-GRF-005`, `SAGE-GRF-006`, `SAGE-GRF-011`).
- **Exact candidate source file manifest:** `docs/SAGE_CORE.md`; `docs/agent/AGENT_HARNESS.md`; `docs/agent/SPEC_SOURCE_CONTRACT.md`; `docs/agent/MILESTONE_PLANNING.md`; `docs/agent/SESSION_ORCHESTRATION.md`; `docs/agent/WAVE_EXECUTION.md`; `docs/templates/AGENT_PROMPT_TEMPLATE.md`; `docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md`; `docs/templates/LANE_PACKET_TEMPLATE.md`; `docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md`; `skills/sage-kit/SKILL.md`; `skills/sage-kit/references/adoption.md`; `skills/sage-kit/references/planning.md`; `skills/sage-kit/references/execution.md`; `skills/sage-kit/references/review-completion.md`.
- **Packaged mirrors:** only exact relative counterparts under `sagekit/resources/docs/**` for the listed `docs/**` files; Skill/reference files have no packaged-document mirror claim here.
- **Directly coupled tests:** `tests/test_spec_sources.py`; `tests/test_active_scope.py`; `tests/test_validation_compatibility.py`; `tests/test_thin_documentation.py`; `tests/unit/test_planning_depth_contract.py`; targeted Graph/Wave and launch-envelope assertions in `tests/test_sagekit_check.py`.
- **Forbidden scope:** GraphContract, NodeResult, ready-node resolver, scheduler, dynamic graph mutation, runtime state store, mandatory Graph admission, Loop/review consolidation, adapter capability changes, or any unmanifested rule.
- **Acceptance claim:** The nine manifested routing rules resolve to the proposed owners from every changed copy, preserve no-fallback and source classification, keep Graph optional for Light work, and introduce no executable Graph or runtime behavior.

### Stage 1C: Loop And Review Consolidation — unauthorized later work

- **Single objective:** Consolidate execution-economy, review, evidence, convergence, normalization, completion and closeout pointers while preserving existing behavior and independent verdict authority.
- **Exact rule manifest (13):** `SAGE-LOOP-001`, `SAGE-LOOP-002`, `SAGE-LOOP-003`, `SAGE-LOOP-006`, `SAGE-LOOP-007`, `SAGE-LOOP-008`, `SAGE-LOOP-009`, `SAGE-LOOP-010`, `SAGE-LOOP-011`, `SAGE-LOOP-012`, `SAGE-LOOP-013`, `SAGE-LIF-011`, `SAGE-LIF-012`.
- **Proposed canonical owners:** `docs/agent/EXECUTION_ECONOMY.md` (`SAGE-LOOP-001`, `002`, `003`, `006`, `007`, `008`, `009`, `010`, `012`, `013`); `docs/agent/SESSION_ORCHESTRATION.md` (`SAGE-LOOP-011`); `docs/templates/MILESTONE_TEMPLATE.md` (`SAGE-LIF-011`); `docs/templates/STRUCTURAL_GATE_TEMPLATE.md` (`SAGE-LIF-012`).
- **Exact candidate source file manifest:** `docs/SAGE_CORE.md`; `docs/agent/AGENT_HARNESS.md`; `docs/agent/EXECUTION_ECONOMY.md`; `docs/agent/CONTINUITY_PROTOCOL.md`; `docs/agent/SESSION_ORCHESTRATION.md`; `docs/ENGINEERING_SYSTEM_TEMPLATE.md`; `docs/QUALITY_GATES_TEMPLATE.md`; `docs/templates/FINAL_REVIEW_PACKET_TEMPLATE.md`; `docs/templates/CORRECTIVE_PACKET_TEMPLATE.md`; `docs/templates/COMPLETION_REPORT_TEMPLATE.md`; `docs/templates/STRUCTURAL_GATE_TEMPLATE.md`; `docs/templates/MILESTONE_TEMPLATE.md`; `docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md`; `docs/templates/ENTRY_GATE_TEMPLATE.md`; `docs/templates/MILESTONE_CLOSEOUT_TEMPLATE.md`; `skills/sage-kit/SKILL.md`; `skills/sage-kit/references/execution.md`; `skills/sage-kit/references/review-completion.md`.
- **Packaged mirrors:** only exact relative counterparts under `sagekit/resources/docs/**` for the listed `docs/**` files, synchronized only with a changed canonical source.
- **Directly coupled tests:** `tests/test_execution_economy.py`; `tests/test_verification_lifecycle.py`; `tests/test_convergence_authority.py`; `tests/unit/test_lane_c_review_convergence.py`; `tests/unit/test_candidate_snapshot.py`; `tests/unit/test_normalization.py`; targeted closure and template assertions in `tests/test_sagekit_check.py` and `tests/test_thin_documentation.py`.
- **Forbidden scope:** changes to `sagekit/candidate.py`, `sagekit/evidence.py`, `sagekit/review.py`, `sagekit/convergence.py` or any runtime behavior; Graph runtime; authority-role merging; new reviewer waves; schema/contract/validator changes; any unmanifested rule.
- **Acceptance claim:** Changed documentation and templates resolve the 13 manifested semantics to their proposed owners, retain evidence reuse/invalidation, one-full-review discipline, convergence, normalization, structural-gate, completion and closeout outcomes, and do not change runtime behavior.

### Stage 1D: Skill And Adapter Thinning — unauthorized later work

- **Single objective:** Reduce the SAGE-Kit Skill to activation/routing while preserving host/runtime-specific enforcement and all specialist Skill, plugin, adapter and native-workflow capabilities.
- **Exact rule manifest (3):** `SAGE-ADP-002`, `SAGE-ADP-003`, `SAGE-ADP-007`.
- **Proposed canonical owners:** `skills/sage-kit/SKILL.md` (`SAGE-ADP-002`); `docs/agent/CAPABILITY_ADAPTERS.md` (`SAGE-ADP-003`, `SAGE-ADP-007`).
- **Exact candidate source file manifest:** `skills/sage-kit/SKILL.md`; `skills/sage-kit/references/planning.md`; `skills/sage-kit/references/execution.md`; `skills/sage-kit/agents/openai.yaml`; `docs/agent/CAPABILITY_ADAPTERS.md`; `docs/agent/AGENT_HARNESS.md`; `docs/templates/AGENT_PROMPT_TEMPLATE.md`; `docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md`.
- **Packaged mirrors:** `sagekit/resources/docs/agent/CAPABILITY_ADAPTERS.md`; `sagekit/resources/docs/agent/AGENT_HARNESS.md`; `sagekit/resources/docs/templates/AGENT_PROMPT_TEMPLATE.md`; `sagekit/resources/docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md`, each only with its changed source.
- **Directly coupled tests:** `tests/test_thin_documentation.py`; `tests/test_sagekit_check.py`.
- **Forbidden scope:** weakening specialist Skill/plugin/adapter/native workflow capability; changing host hooks or runtime-specific enforcement; product/runtime, schema, contract, validator, Graph or Loop behavior; any unmanifested rule.
- **Acceptance claim:** The Skill remains a usable activation/routing layer, host/runtime enforcement stays intact, optional capabilities remain honestly declared and opt-in, and no specialist or native workflow capability is removed.

The CSV is the machine-readable allocation: 8/9/13/3 rules use the four exact stage actions, and the other 50 rules are explicitly outside Stage 1A-1D. A proposed owner or stage remains a proposal, not accepted SAGE-Kit authority or implementation permission.

### Proposed Stage Boundary Contract

**Classification:** This contract is a proposed rebuild control for later rebuild sessions. It is not current SAGE-Kit normative authority and does not itself authorize any stage.

1. Before any editing, a stage freezes its single objective, exact rule manifest, exact candidate file manifest, forbidden scope, acceptance claim, and required targeted evidence.
2. Rules, files, scenarios and product issues absent from the manifest go to backlog by default and cannot enter the current stage automatically.
3. A newly discovered issue can block the current stage only when it directly disproves the acceptance claim, creates an authority conflict, breaches a safety boundary, creates a validator/contract false-green, or proves the change cannot preserve capability monotonicity.
4. Ordinary consistency issues, future optimization, adjacent-module defects and prospective hypotheses are recorded, classified and deferred; they do not expand the current stage.
5. If a stage contains two independently acceptable objectives, it must split rather than expand.
6. A stage proposal is not implementation authority, and the current stage never automatically authorizes the next stage.
7. A packaged mirror or directly coupled assertion changes only with its canonical source and cannot be used to expand business-rule scope.
8. Fresh review is limited to the current manifest, current diff, current acceptance claim and capability non-regression; a reviewer cannot restart a repository-wide investigation.
9. A corrective addresses only its original findings and direct regressions. A new finding that does not disprove the current acceptance claim goes to backlog.
10. Fixed token, time or subagent counts are not correctness conditions. Convergence is determined by non-expanding scope, decreasing findings and a decidable acceptance claim.

## 17. Deferred Proposals

- Formal GraphContract, NodeResult, ready-node resolver, scheduler, runtime state store and event log.
- Evidence-lineage runtime changes beyond current behavior.
- Executable `NO_ACTION_REQUIRED` semantics.
- General graph admission and reviewer-dedup runtime enforcement.
- Shallow-history behavior correction pending a deterministic reproduction.
- macOS-specific path-alias evaluation.
- Custom configured serial-path hard enforcement in host hooks.
- Moving deterministic closure into a different physical owner.
- Removing or shrinking `BOUNDARY_TEMPLATE.md` before consumer/path provenance.
- Universal optional-profile activation wording until the accepted Core owner is confirmed.
- Any source-tree reorganization, path move, contract migration or historical rewrite.

Each deferred item either lacks current authority/evidence, belongs to a later authorized stage, or can be handled later without blocking the proposed Stage 1A Authority Kernel.

## 18. Stage 0 Acceptance Checklist

Independent review disposition:

- **Observed fact:** Authority/Coverage review found aggregated location classification, cross-version owner conflation, count, and evidence-wording issues. Exact locations, deterministic file classes, version-local owners, and regenerated counts resolved them; targeted re-review reported no remaining important issue.
- **Observed fact:** Capability Non-Regression review found Structural Gate/field coverage and Stage 1 boundary ambiguity. `SAGE-LIF-012`, the field preservation matrix, the explicit rollback/recovery gap, and the 33-rule Stage 1A-1D allocation resolved them; targeted re-review reported no remaining important issue.
- **Observed fact:** Efficiency/Scope review found Stage 1 action ambiguity, missing scenario provenance, count drift, and rollback wording. The machine-readable Stage 1A-1D allocation, scenario provenance/admission fields and corrected scope language resolved them; targeted re-review reported no remaining important issue.
- **Observed fact:** The sole fresh-context corrective reviewer found two stale references that still called all 33 rules “Stage 1A”; this targeted correction replaces them with the four-stage 8/9/13/3 allocation without changing any rule, capability or compatibility classification.
- **Observed fact:** No second broad review was run; only the affected targeted re-reviews were performed.

- [x] Baseline and isolated worktree created from the exact expected source HEAD.
- [x] `rebuild.md` copied mechanically and initial source/target hashes matched.
- [x] High-impact normalized rules have one proposed owner in `RULE_OWNERSHIP.csv`.
- [x] Proposed owners are explicitly nominations, not accepted authority.
- [x] Packaged mirrors and versioned compatibility paths are classified.
- [x] Five layers and six Harness components are mapped.
- [x] Zero-to-product chain and template responsibilities are inventoried.
- [x] Graph admission, collapsibility and non-collapsible authority boundaries are recorded.
- [x] Divergent-review/test/governance risks are recorded.
- [x] Twelve anonymous deterministic scenario candidates are recorded.
- [x] Stage 1A-1D have independent 8/9/13/3 manifests; only the 8-rule Authority Kernel is a next candidate, and product/runtime behavior is excluded from all four proposals.
- [x] Fresh-context independent reviews complete with no unresolved important finding.
- [x] CSV, JSON, report sections, owner/current-location paths, allowlist, `git diff --check` and scenario privacy checks pass.
- [x] Final source, Stage 0, and main worktree HEAD/status/hash invariants pass.
- [x] Stage 1 was not started.

## 19. Final Verdict

`STAGE_0_READY_FOR_ACCEPTANCE`

Stage 0 design artifacts are ready for acceptance. This verdict does not authorize Stage 1, including Stage 1A.
