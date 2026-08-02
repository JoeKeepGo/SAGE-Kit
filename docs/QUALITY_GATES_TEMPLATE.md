# Quality Gates Template

Use this template to record project-owned gates. General completion is
canonical at `docs/SAGE_CORE.md#sage-completion-001`; governance and severity
are canonical at `docs/agent/GOVERNANCE_LEVELS.md`. This file selects local
checks and evidence but does not invent product requirements.

## Universal Controls

Only these controls are universal:

| Control | Required result |
|---|---|
| Authority | Current project authority and permission cover the action. |
| Scope | Changed and inspected surfaces stay inside the authorized boundary. |
| Truthful evidence | Results, omissions, limitations, and unavailable checks are reported accurately. |
| Required project checks | Checks named by current project authority pass or their named owner records a waiver. |
| Credentials and host safety | Credentials are not exposed; host/tool safety boundaries are respected. |

A failure in any applicable universal control blocks acceptance. No milestone,
wave, coder split, packet, structural, adapter, Graph, or project security gate
is universal.

## Conditional Profiles

Enable only profiles selected by project authority or concrete scope/risk:

| Profile | Enable when selected or applicable |
|---|---|
| Milestone planning | An independently acceptable product outcome needs milestone planning. |
| Wave or parallel lanes | Disjoint work benefits from parallel execution. |
| Session/controller split | Separate controller, coder, or review roles add value. |
| Packets or structural gate | A Heavy/formal workflow requires structured handoff completeness. |
| Capability adapter | A specialist capability is actually used. |
| Graph | Dependencies, joins, or gates improve a decision. |
| Security, browser, data, redaction, or threat model | The project's own requirements select these checks. |
| Release, migration, or production | The project has a corresponding durable/public change or gate. |

Browser visibility, data handling, redaction, and threat-model questions are
optional prompts for the project owner. SAGE-Kit never turns them into a
requirement, gate, or threat-model decision by itself.

## Local Gate Table

| Gate | Required by | Status | Evidence | Blocking | Owner | Notes |
|---|---|---|---|---|---|---|
| `<project gate>` | `<authority ref>` | `PASS`, `FAIL`, `BLOCKED`, `WAIVED`, or `N/A` | `<evidence ref>` | `<yes/no>` | `<owner>` | `<notes>` |

`PASS` requires checked evidence. `WAIVED` requires the named waiver owner and
decision reference. Missing, `FAIL`, or `BLOCKED` evidence for a blocking gate
is not acceptance eligible. `N/A` records why the project gate does not apply.

## Finding Severity And Correctives

| Severity | Acceptance rule |
|---|---|
| `P0` | Always blocks while open. |
| `P1` | Always blocks while open. |
| `P2` | Blocks only for authority conflict, false-green, approval gate, safety boundary, or validator/required project-check failure; otherwise fix directly or record a concern. |
| `P3` | Never blocks; record as cleanup or follow-up. |

Inside the same authorized corrective scope, continue while findings decrease;
do not request new Project Manager approval each round. Two consecutive
no-progress rounds for the same root cause return `BLOCKED`. Mechanical wording,
status, or EOF fixes close with a direct focused check. A semantic corrective
receives one targeted re-review of the affected boundary.

## Completion Language

Report the authority reference, current-truth reference, applicable gate table,
evidence references, skipped/unavailable checks, and remaining concerns. Refer
to `ACTIVE_CONTEXT` for current status/findings/blockers/next action; do not copy
those facts into this gate catalog.

Allowed: `Focused checks passed; runtime smoke was not a project requirement for
this documentation-only scope.`

Not allowed: `This should work.`
