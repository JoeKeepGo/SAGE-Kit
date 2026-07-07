# Phase Execution

Phase execution keeps work reviewable and bounded.

For large milestones with multiple phases and separate Project Manager, Coder,
and Final Review controllers, wrap phase execution with
`docs/agent/SESSION_ORCHESTRATION.md`. Phase Execution still defines what each
phase must satisfy.

## Phase Requirements

Every non-trivial phase, as defined in `docs/SPEC_CORE.md`, must define:

- governance level;
- goal;
- requirement IDs;
- inputs;
- outputs;
- non-goals;
- file boundary;
- module ownership;
- public contract;
- capability routing;
- test plan;
- runtime smoke;
- edge cases;
- completion gate.

## Execution Loop

1. Read the phase doc and quality gates.
2. Select `Light`, `Standard`, or `Heavy` for the phase or task scope.
3. Inspect capability metadata and select specialist skills, plugins,
   connectors, or tools when available.
4. If superpowers is available and relevant, select the specific execution
   skills that fit the approved phase boundary.
5. Check change-control state.
6. Confirm file ownership.
7. Create a wave plan when parallel lanes can help.
8. Freeze public contracts and shared file ownership before writable lanes.
9. Write or update focused tests when behavior changes.
10. Implement the narrowest change.
11. Run focused checks.
12. Run runtime smoke if the phase makes runtime claims.
13. Maintain active context and document routing.
14. Update completion report with memory maintenance status.
15. Update milestone ledger.
16. Hand off or submit.

## Wave Execution

Use `docs/agent/WAVE_EXECUTION.md` when a phase has independent read-only,
writable, or validation lanes.

The controller may parallelize safe lanes, but these remain serial:

- contract freeze;
- shared file changes;
- real runtime smoke;
- approval gates;
- final integration;
- ledger update;
- active context and routing maintenance;
- git operations when used.

## Strict Mode Execution

Use `docs/agent/MODEL_ASSURANCE_POLICY.md` to decide whether the executor must
use Strict Mode.

When Strict Mode is required, the controller or human converts the phase into a
Strict Mode task card before writable work begins. Strict Mode agents execute
the card and stop on ambiguity. They do not design new scope, choose
architecture, open approval gates, infer missing contracts, or create their own
task card.

## Stop Conditions

Stop and return to planning when:

- required files are outside the phase boundary;
- a closed approval gate is needed;
- contract owner and consumer disagree;
- runtime verification contradicts the phase assumptions;
- local data hygiene is at risk;
- the change would combine unrelated milestones.
