# Milestone Roadmap Template

Use this roadmap to define the project sequence from design gates through
implementation and release.

## Roadmap Rules

- Each milestone is an independently acceptable product outcome; cohesive UI,
  API, data, and runtime supporting areas may remain together.
- A capability map is optional discovery support for broad or uncertain work;
  it is not a universal admission gate.
- Review normally remains a gate or Graph node inside the product milestone.
  Make it a separate milestone only for an independent release, authority, or
  cross-milestone acceptance boundary.
- Runtime implementation starts only after required design gates are accepted.
- Approval gates remain closed unless explicitly opened.
- Phase decomposition is optional. Select it for Heavy work or when multiple
  owners, contracts, dependencies, or verification boundaries improve control.
- Split milestones only for unrelated outcomes or distinct release, authority,
  or acceptance boundaries.

## Capability Map Link

- Capability map: `docs/CAPABILITY_MAP.md` or `N/A` with reason
- Granularity audit status: `pending`, `pass`, `fail`, or `n/a`
- Candidates not promoted:

## Overview

| Stage | Milestones | Theme |
|---|---:|---|
| Discovery / Design | `<M1-M?> or n/a` | Product profile, architecture, contracts, test matrix when needed. |
| Foundation Build | `<M?>` | Durable state, core models, basic runtime. |
| Product Build | `<M?>` | User-facing workflows and integrations. |
| Hardening | `<M?>` | Recovery, diagnostics, security, packaging. |
| Release / Acceptance | `<gate/node, or M only if independent>` | Final review, project-required evidence, and acceptance. |

## Milestones

### M<ID>: <Name>

Goal:

- `<goal>`

Primary capability:

- `<capability from docs/CAPABILITY_MAP.md, or direct primary capability with n/a reason>`

Inputs:

- `<input>`

Deliverables:

- `<artifact>`

Validation:

- `<evidence>`

Closeout:

- `<expected outcome summary or follow-up signal>`

Non-goals:

- `<excluded scope>`

Optional Heavy-profile phase decomposition (omit when it adds no control):

| Phase | Objective | Owner | Contract | Expected Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|
| `<phase>` | `<objective>` | `<owner>` | `<contract or none>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |
