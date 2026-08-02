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
human authority, or rollback planning when durable state, a public contract,
migration, or release is changed.

## Current Truth And History

The active SPEC defines current work. A compact `ACTIVE_CONTEXT` records only
current objective, status, findings, blockers, and next action, together with
the authority and evidence references needed to resume. It is the exclusive
owner of those current facts. Historical ledgers are immutable event/evidence
indexes; handoffs are bounded transfer views. Neither becomes executable
authority merely because it exists.

Each fact has one owner. Completion and handoff records point to current truth,
authority, and evidence instead of copying status, rules, logs, or findings.

<a id="sage-grf-001"></a>
## Loop And Optional Graph

The bounded model loop is the default execution unit. A Graph is optional and
is introduced only when explicit dependencies, joins, gates, or parallel lanes
improve execution or review. Graph schemas are static descriptions; they do not
schedule nodes, mutate state, or grant authority.

<a id="sage-completion-001"></a>
## Evidence And Completion

Evidence records what was checked, against which scope and inputs, and with
what result. It never creates permission or acceptance. `PASS`, `WAIVED`,
`SKIPPED`, `UNAVAILABLE`, and incomplete are distinct.

Completion is eligible only when the authorized scope is finished, applicable
project-required checks pass or are explicitly waived by their owner, evidence
is truthful, and no blocking finding or approval gate remains. Mechanical
wording, status, or EOF fixes close with a direct focused check; a semantic
corrective receives one targeted re-review of the affected boundary.

Implementation completion, review verdict, submit authorization, and human
acceptance are separate events. A framework or agent may recommend acceptance;
only the project-named acceptance owner may accept the product outcome.

The table below is only a completion/acceptance projection of existing
cross-layer statuses. It is not a state machine and does not replace the Graph
contract's node status vocabulary:

| Status | Terminal for current execution | Acceptance eligible | Auto-advance |
|---|---|---|---|
| `DONE` / Graph `SUCCEEDED` or evidence-backed `NO_ACTION_REQUIRED` | yes | when the completion rule above passes | only when current authority permits |
| `DONE_WITH_CONCERNS` | yes | only when every concern is non-blocking and the acceptance owner permits it | no |
| `DONE_PENDING_ACCEPTANCE` | yes for the completed work, no for product acceptance | yes | only inside an explicit preauthorization |
| `HANDOFF` / Graph `HANDOFF` | no | no | no |
| `BLOCKED` / Graph `BLOCKED`, `FAILED`, or `NEEDS_CORRECTION` | no | no | no |
| Graph `PENDING`, `READY`, `RUNNING`, or `WAITING_RESOURCE` | no | no | only through project/Graph rules outside this projection |
| Graph `CANCELLED` | yes for the cancelled attempt, no for completion | no | no |

## Execution Model

```text
read authority + active SPEC
-> bounded plan / optional Graph
-> implementation loop
-> project-native focused checks
-> risk-based independent review
-> targeted corrective and re-review when needed
-> required project CI once per unchanged candidate
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
