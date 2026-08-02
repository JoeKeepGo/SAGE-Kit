# Model-Native Agent Harness

The Harness is the repeatable way a model applies current project authority. It
is an interaction contract, not software running beside the model.

<a id="sage-auth-010"></a>
<a id="sage-ctx-005"></a>
## Launch Envelope

Every bounded task should identify:

- objective and acceptance criteria;
- current authority and active SPEC references;
- Light, Standard, or Heavy governance;
- permission mode and human-only decisions;
- allowed, read-only, and forbidden surfaces;
- project-native focused checks;
- evidence and review expectations;
- stop conditions and next owner.

Missing fields may be inferred only when project authority makes them
unambiguous and the inference does not broaden scope or permission.

## Context Loading

Load authority and capability metadata first, then only task-relevant SPEC,
code, tests, and references. Use `ACTIVE_CONTEXT` for current handoff truth.
Accepted history is not loaded or reconciled unless the task is an explicit
historical audit.

## Execution

The controller creates a bounded plan or optional Graph, delegates only
disjoint work, integrates changes, and runs project-native checks. The model's
native planning, TDD, debugging, subagent, and review capabilities remain
available. Specialist capabilities do not replace project authority.

## Truthful Boundaries

No model instruction can guarantee operating-system containment. Describe
host-enforced restrictions as hard only when the host actually enforces them;
otherwise report them as procedural boundaries. Unknown capability, missing
evidence, or failed checks remain explicit and never become `PASS`.
