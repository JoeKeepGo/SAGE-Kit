# Session Orchestration

Use one controller to coordinate integration and the next decision within
project-granted scope. The controller does not own or widen project scope.

## Worker Envelope

Each worker receives objective, authority, permission, paths, acceptance,
checks, stop conditions, and return shape. Add governance, Graph, specialist,
or host blocks only when applicable. Shared current truth stays with the named
`ACTIVE_CONTEXT` owner.

## Parallelism

Parallelize independent investigations or disjoint writers. Dependencies,
shared mutable files/state, integration, push, merge, and acceptance are serial
barriers. A shared toolchain alone is not a reason to serialize when its state
is isolated. An authorized isolated lane may commit locally; the controller
serializes push and merge.

<a id="final-review-rules"></a>
## Review And Corrective

Implementation, review, corrective work, submit, and human acceptance remain
separate grants. Mechanical wording, status, or EOF fixes close with a focused
check. Semantic corrective work receives one targeted independent re-review of
the affected boundary. Continue inside the same authorized scope while findings
decrease; after two consecutive no-progress rounds for one root cause return
`BLOCKED`.

## Bounded Multi-Milestone Continuation

SAGE-Kit cannot promise autonomous cross-milestone operation; continuation
depends on the host. A coordinator may continue only within already admitted,
preauthorized milestones. Its compact envelope records:

- authority boundary and admitted milestones;
- completion predicate and next-admission rule;
- scope/evidence drift check;
- resume state and host continuation dependency;
- failure/handoff destination;
- corrective convergence rule.

Stop for product acceptance, scope/permission expansion, a new threat-model or
safety decision, destructive or production action, credentials, or a merge or
release gate. Within explicit project preauthorization,
`DONE_PENDING_ACCEPTANCE` may advance to another already admitted milestone;
it never creates acceptance or admits new scope.

## Handoff

Write current objective/status/findings/blockers/next action only to the
project-owned `ACTIVE_CONTEXT`. A handoff is a bounded transfer view containing
authority, evidence, changed surfaces, next owner, and the `ACTIVE_CONTEXT`
reference. It is not a second current-state record.
