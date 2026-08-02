# SAGE-Kit Core

SAGE-Kit is a model-native SPEC and Harness governance framework. It supplies
shared language, contracts, templates, and routing for reliable agent-assisted
delivery. It is not an executable project manager and owns no product policy.

<a id="sage-auth-001"></a>
<a id="sage-auth-009"></a>
## Authority

Authority is ordered and scoped:

1. host/system safety and tool boundaries;
2. explicit human decisions for the task;
3. project-owned current authority, SPEC, gates, and tests;
4. SAGE-Kit defaults;
5. adapter, Skill, and agent suggestions.

Lower layers cannot infer, widen, waive, or replace higher authority. Governance
level and permission are independent. Review, corrective, submit, waiver, and
acceptance authority remain separate grants.

## Product Lifecycle

SAGE-Kit preserves the complete path from idea to accepted product:

```text
idea -> owner intake -> blueprint -> technical design -> capability map
     -> roadmap -> milestone -> wave -> phase -> lane
     -> implementation -> verification -> independent review/corrective
     -> human acceptance -> ledger/closeout
```

Projects choose the depth appropriate to risk. Thin documents remove repeated
governance prose, not design depth, acceptance criteria, dependency analysis,
rollback planning, or human authority.

## Current Truth And History

The active SPEC defines current work. A compact `ACTIVE_CONTEXT` records only
handoff facts: current objective, authority, state, blockers, decisions, and
next action. Historical milestone documents are auditable references and never
become executable authority merely because they exist.

Each fact has one owner. Other documents point to it instead of copying status,
rules, command logs, findings, or receipts.

<a id="sage-grf-001"></a>
## Loop And Optional Graph

The bounded model loop is the default execution unit. A Graph is optional and
is introduced only when explicit dependencies, joins, gates, or parallel lanes
improve execution or review. Graph schemas are static descriptions; they do not
schedule nodes, mutate state, or grant authority.

## Evidence And Completion

Evidence records what was checked, against which scope and inputs, and with
what result. It never creates permission or acceptance. `PASS`, `WAIVED`,
`SKIPPED`, `UNAVAILABLE`, and incomplete are distinct.

Implementation completion, review verdict, submit authorization, and human
acceptance are separate events. A framework or agent may recommend acceptance;
only the project-named human owner may accept or close the milestone.

## Execution Model

```text
read authority + active SPEC
-> bounded plan / optional Graph
-> implementation loop
-> project-native focused checks
-> risk-based independent review
-> targeted corrective and re-review when needed
-> one final project CI run
-> human gate for product/authority/security decisions
```

SAGE-Kit introduces no CLI, package runtime, daemon, process supervisor,
resource governor, checkpoint store, candidate service, or hidden validator.
Projects keep using their own source control, tests, CI, and deployment tools.

## Canonical Repository Owners

- `docs/`: governance, profiles, and templates;
- `contracts/`: optional language-neutral static contracts;
- `skills/sage-kit/`: activation and host routing;
- project repository: current SPEC, authority, commands, tests, and evidence.
