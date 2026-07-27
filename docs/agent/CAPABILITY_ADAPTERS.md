# Capability Adapters

Capability Adapters are the canonical boundary for using an optional external
capability within an approved SAGE-Kit task. They normalize the interaction;
they do not make the capability a core dependency or define its runtime.

Authority precedence and completion ownership remain with
`docs/SAGE_CORE.md#sage-auth-001`. This document owns adapter routing,
authorization, evidence capture, and fallback only. It does not redefine Core,
Loop, Graph, or Harness authority; their Stage 1 owner anchors remain the
source for those contracts.

## Classification

| Type | Meaning |
|---|---|
| Built-in profile | An opt-in SAGE-Kit control with its own owner contract. |
| Reference integration | An optional external method known to the kit but never required by this document. |
| External adapter | An optional provider selected by available capability metadata and active project authority. |

Availability is advisory routing input. It neither grants permission nor adds a
requirement, gate, or completion state.

<a id="sage-adp-003"></a>
## Canonical Lifecycle

Every adapter interaction follows this ordered contract:

1. **Detect**: inspect only the available capability metadata and declared
   configuration needed to determine whether the capability is present.
2. **Authorize**: confirm that the active authority permits this capability and
   the requested action.
3. **Bound**: record the allowed and forbidden surface, approval gates,
   resource limits, evidence expectation, and stop condition.
4. **Invoke**: use only the authorized capability operation inside that bound.
5. **Capture**: retain the concise, relevant external result and any limitation
   as evidence.
6. **Map**: link or place the useful result in the active SAGE-Kit artifact
   without changing the artifact's owner or authority.
7. **Fallback**: use a safe native path, or return the authority-defined
   handoff or blocker state.

An adapter may not skip, reorder, or use a later lifecycle step to infer an
earlier authorization. Runtime-specific discovery and invocation mechanics
belong to the relevant runtime adapter, not this canonical contract.

## Authority and Bounds

Adapter authorization is separate from role permission. Both the active role
or packet and this lifecycle must permit an action before it occurs. A bound
must state the relevant writable and read-only surface, prohibited changes,
approval gates, resource ceiling, expected evidence, and stop conditions.

No adapter result can create authority, widen scope, bypass a gate, reduce
required verification, or promote an external provider into Core, Loop, Graph,
or Harness authority. Adapter outputs are evidence only. They are not `DONE`,
gate `PASS`, acceptance, or a waiver, and they cannot open a closed gate.

## Fallback and Optionality

When an optional capability is unavailable, unsafe, or inconclusive, record
that condition and continue through a safe model-native or project-native path
when one preserves the approved authority, scope, acceptance standard, and
required evidence. Its absence is not a blocker in that case.

`BLOCKED` is valid only when active project authority explicitly makes the
capability necessary for authority, safety, or gate completion and no approved
safe native path exists. Fallback changes the method provider only; it cannot
change the governing contract.

## Descendant Inheritance

Adapter bounds and applicable runtime/model policy are inherited by every
descendant. A controller must place the inherited bound in each child launch
packet, and any authorized descendant must propagate it again to its own
children. Compaction, handoff, resume, and re-entry do not clear the bound.

A worker that cannot propagate the applicable bound must not delegate further;
it returns the authority-defined handoff instead. Adapters cannot use
delegation to elevate their authorization, resource limit, or evidence status.

<a id="sage-adp-007"></a>
## Runtime/Model Policy: Superpowers

A Superpowers prohibition applies only when the applicable runtime/model policy
states that it applies. Within that scope, Superpowers and
`using-superpowers` are `DISABLED_BY_RUNTIME_POLICY`; controllers and all
descendants must not read, invoke, route to, reference, or delegate to them.
The prohibition must be repeated in every descendant launch packet.

The prohibition disables an optional adapter, not engineering discipline.
Within the active authority boundary, the model must instead use its own native
brainstorming, planning, test-driven implementation, systematic debugging,
subagent orchestration, review, and verification workflow. These are native
model behaviors, not substitute adapter invocations.

Discovery records a policy-disabled capability as disabled. It is not a
capability gap, fallback trigger, blocker, stop reason, or authority change.
Outside the applicable runtime/model scope, this document does not create a
Superpowers prohibition.
