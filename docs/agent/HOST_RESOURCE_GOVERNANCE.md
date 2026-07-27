# Host Resource Governance

This document defines the runtime-neutral canonical host boundary for adopted
SAGE-Kit projects. A runtime adapter may implement this contract, but it must
report its actual capability and limitations rather than extend the contract.
Authority precedence remains with `docs/SAGE_CORE.md#sage-auth-001`.

This document does not redefine Core, Loop, Graph, or Harness authority. Their
Stage 1 owner anchors remain authoritative; host governance only constrains how
an already-authorized operation uses host resources.

## Root Supervision

The Root controller is the sole host-resource supervisor. Only Root may
authorize, launch, observe, release, or decide the outcome of a managed host
operation. Workers and adapters may request a bounded operation and return its
evidence, but cannot acquire an independent host authority, elevate a bound,
or decide a host gate.

Before a managed operation, Root binds the active authority, workspace,
writable and forbidden surface, resource class, concurrency limit, timeout,
expected evidence, and stop condition. A changed binding, occupied resource,
or failed precondition must use the authority-defined wait, handoff, or blocker
state; it must not silently widen execution.

## Descendant Inheritance

Every managed descendant inherits the Root-approved binding, including the
workspace, authority ceiling, resource limit, timeout, and containment
expectation. A descendant cannot transfer, re-delegate, or elevate that binding
unless the Root-approved contract explicitly permits the next boundary and it
is bound again there. Compaction, handoff, resume, and re-entry do not clear
these restrictions.

Runtime adapters must report whether descendant inheritance was established
for the operation. A missing or incomplete inheritance report is evidence of a
limited boundary, not proof of complete containment.

## Enforcement Levels

Containment is reported per managed operation with one of these levels:

| Level | Meaning |
|---|---|
| `HARD` | The selected host mechanism demonstrably constrains the complete launched process tree for the declared boundary. |
| `MANAGED` | The runtime manages the normal launched process group or tree, but cannot prove that deliberate or malicious escape is impossible. |
| `SOFT` | The boundary relies on command, agent, or provider cooperation and can be bypassed outside the managed path. |

`HARD` is never inferred from intent, an adapter name, or a successful command.
`MANAGED` and `SOFT` must preserve their stated limitations. The broader
interception guarantee remains `SOFT` whenever an agent, plugin, shell, or
arbitrary child can bypass the managed boundary. No adapter may report a
stronger level than the selected host mechanism actually supplies.

## Resource and Evidence Boundary

Root serializes conflicting resource use according to the active contract and
keeps waiting distinct from test, review, or implementation failure. A managed
operation records its binding, resource decision, containment level, descendant
inheritance result, result, cleanup status, limitations, and concise output.

That record is external execution evidence only. It does not create authority,
turn a gate into `PASS`, establish `DONE`, or alter Graph, Loop, or Harness
authority. Final acceptance and completion remain with their Stage 1 owners.
