# Milestone Planning

A milestone is an independently acceptable product outcome. It may include
cohesive UI, API, data, and runtime supporting areas needed to deliver that
outcome. Review is normally a gate or node, not a separate milestone; make it a
milestone only for independent release, authority, or cross-milestone
acceptance.

## Default Planning Shape

Use one planning author. Add one bounded risk review when warranted and apply
one targeted fix. The full Author/Review/Fix/Project Manager/Closeout/Submit
package is an explicit Heavy or formal-approval profile, never the default.
Planning-only work does not automatically create an entry gate, ledger,
per-phase documents, closeout, or submit packet.

Use the canonical control matrix in
`docs/agent/GOVERNANCE_LEVELS.md`:

- Light: zero or one short planning document;
- Standard: a short plan and result;
- Heavy: three to five purposeful documents by default, selected for the
  actual authority, risk, handoff, and evidence needs.

## Readiness

A plan names the product outcome, project authority, scope/non-goals,
acceptance evidence, dependencies, affected paths/contracts, project-required
checks, and stop conditions at the depth needed for its level. Graph, waves,
lanes, packets, ledgers, and structural gates are conditional profiles.

Split a candidate when it cannot be accepted independently, needs a distinct
scope/permission decision, or combines unrelated outcomes. Do not split a
cohesive product outcome merely because its implementation spans UI, API, data,
or runtime support. A capability map is useful for broad discovery but is not a
universal entry gate.

## Execution Shape

Use one bounded loop by default. Add a Graph for meaningful dependencies,
joins, or gates; add waves only for disjoint writers or useful independent
checks. Delegation alone does not select Heavy. Shared mutable state is serial;
an otherwise shared toolchain is not.

## Rollback

Require a rollback owner, trigger, procedure, compatibility impact, and
post-rollback verification only for durable state, public contract, migration,
or release changes. Reversible documentation or local implementation edits do
not need ceremonial rollback sections.

## Planning Result

Return the plan/result references, authority and permission used, applicable
checks/review, unresolved concerns, and `ACTIVE_CONTEXT` next action. Planning
does not start implementation, grant submit authority, or create acceptance.
