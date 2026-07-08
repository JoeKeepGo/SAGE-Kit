# Capability Map

Use this file before creating an executable milestone roadmap, especially when
the project starts from a broad idea or non-technical intake.

The capability map prevents broad epics from being mislabeled as milestones.

## Project Outcome

State the user or operator outcome the project should make possible.

## Capability Areas

| Capability Area | User/Operator Outcome | Owner Boundary | Evidence | Candidate Milestones |
|---|---|---|---|---|
| `<area>` | `<outcome>` | `<component/runtime/data boundary or unknown>` | `<visible or runtime proof>` | `<M?>` |

Suggested areas:

- user-facing workflows;
- operator or administrator workflows;
- data and state;
- API, event, CLI, or worker contracts;
- integrations;
- runtime, deployment, recovery;
- observability, diagnostics, support;
- security and privacy.

## Milestone Candidate Split

Each candidate milestone must map to one primary capability.

| Candidate Milestone | Primary Capability | Observable Result | Contract | Verification | Split Needed |
|---|---|---|---|---|---|
| `<candidate>` | `<capability>` | `<result>` | `<contract or none>` | `<test/smoke/evidence>` | `<yes/no + reason>` |

## Granularity Audit

Mark `FAIL` when any candidate milestone:

- spans multiple capability areas;
- covers multiple user workflows or runtimes;
- mixes design, implementation, integration, review, and release;
- cannot be reviewed without unrelated history;
- cannot name file ownership;
- cannot name verification evidence.

| Candidate Milestone | Status | Reason | Required Split |
|---|---|---|---|
| `<candidate>` | `PASS` or `FAIL` | `<reason>` | `<split or n/a>` |

## Roadmap Promotion

Promote only `PASS` candidates into `docs/MILESTONE_ROADMAP.md`.

Failed candidates stay in planning until they are split into independently
reviewable, verifiable, and bounded milestones.
