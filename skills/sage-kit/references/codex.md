---
title: Codex Runtime Profile
runtime: codex
---

# Codex Runtime Profile

Minimal environment profile for running SAGE-Kit in Codex. It is additive:
active project authority, file boundaries, gates, and completion ownership stay
with SAGE-Kit and the active project SPEC.

## Startup And Inheritance

The Root controller resolves the active authority and packet before writable
work, then uses Codex model-native behavior for execution. Every subagent
launch packet carries the applicable authority boundary, allowed and forbidden
paths, gates, stop conditions, resource limit, and this runtime policy. An
authorized descendant that delegates repeats those constraints for each child;
compaction, handoff, and resume do not clear them.

In a Codex runtime running any GPT-5.6 family model, `using-superpowers` and every
Superpowers workflow are `DISABLED_BY_RUNTIME_POLICY`. Root and all descendants must not read, invoke,
route to, reference, or delegate to either.
This is not a prohibition on the underlying engineering practices: use
Codex/model-native brainstorming, planning, test-driven development,
debugging, subagent coordination, and review workflow as native behaviors;
use model-native verification too.

## Roles And Invocation

Root remains the supervisor for authority, host-resource decisions, serial
integration, verification ownership, and final acceptance. A write subagent
implements only its bounded packet and returns evidence. A review subagent is
read-only: it reports findings and does not write implementation or accept the
work. Keep write and review roles separate.

Use native `spawn_agent` for Codex subagent work. Resolve any capability
selection through the active authority and the canonical adapter lifecycle;
an unavailable Superpowers workflow is policy-disabled, not a capability gap
or fallback trigger.

## Boundary And Evidence

Report containment honestly for each managed operation: `HARD` only for a
demonstrably constrained complete process tree, `MANAGED` for a runtime-managed
tree without proof against escape, and `SOFT` when cooperation can bypass the
boundary. Evidence records results and limitations; it never creates authority,
widens scope, passes a gate, or establishes acceptance.

Canonical contracts: [adapter lifecycle](../../../sagekit/resources/docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-003),
[runtime policy](../../../sagekit/resources/docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-007), and
[Host Resource Governance](../../../sagekit/resources/docs/agent/HOST_RESOURCE_GOVERNANCE.md).
They remain authoritative for adapter lifecycle, runtime-policy semantics, Root
supervision, containment, and evidence ownership.
