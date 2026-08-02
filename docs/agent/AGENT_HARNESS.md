# Model-Native Agent Harness

The Harness is the repeatable way a model applies current project authority. It
is an interaction contract, not software running beside the model.

<a id="sage-auth-010"></a>
<a id="sage-ctx-005"></a>
## Launch Envelope

Every bounded task should identify the eight core fields: objective, authority,
permission, paths, acceptance, checks, stop conditions, and return shape.
Governance, dependencies, specialist routing, Graph, rollback, review, or host
adapter blocks are optional and referenced only when applicable.

Missing fields may be inferred only when project authority makes them
unambiguous and the inference does not broaden scope or permission.

When a project wants a thin structured record, use those same eight fields as
keys and return `status`, `changed_paths`, `evidence_refs`, `findings`, and
`next_owner`. This optional project-native shape needs no framework validator.
Task Dispatch v2 is legacy static compatibility only and is not used for new
default routing.

## Context Loading

Load authority and capability metadata first, then only task-relevant SPEC,
code, tests, and references. Use `ACTIVE_CONTEXT` for current handoff truth.
Accepted history is not loaded or reconciled unless the task is an explicit
historical audit.

## Execution

The controller coordinates only within project-granted scope; it never owns or
widens project scope. It creates a bounded plan or optional Graph, delegates
only disjoint work, integrates changes, and runs project-native checks. The model's
native planning, TDD, debugging, subagent, and review capabilities remain
available. Specialist capabilities do not replace project authority.

## Truthful Boundaries

No model instruction can guarantee operating-system containment. Describe
host-enforced restrictions as hard only when the host actually enforces them;
otherwise report them as procedural boundaries. Unknown capability, missing
evidence, or failed checks remain explicit and never become `PASS`.
