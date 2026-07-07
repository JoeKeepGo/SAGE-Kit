# Milestone Roadmap Template

Use this roadmap to define the project sequence from design gates through
implementation and release.

## Roadmap Rules

- Each milestone proves one primary capability.
- Broad, non-technical, or coarse-roadmap projects must create `docs/CAPABILITY_MAP.md`
  before this roadmap becomes executable.
- Draft milestone candidates from Project Owner Entry are not executable until
  they pass Milestone Granularity Gate.
- Review gates are first-class milestones.
- Runtime implementation starts only after required design gates are accepted.
- Approval gates remain closed unless explicitly opened.
- Milestones must be decomposed into phases before implementation starts.
- Broad phases must be split until each has one owner, one contract boundary,
  bounded files, and clear verification.
- Broad milestones must be split until each maps to one primary capability.

## Capability Map Link

- Capability map: `docs/CAPABILITY_MAP.md` or `N/A` with reason
- Granularity audit status: `pending | pass | fail | n/a`
- Candidates not promoted:

## Overview

| Stage | Milestones | Theme |
|---|---:|---|
| Design Gate | `<M1-M?>` | Product profile, architecture, contracts, test matrix. |
| Foundation Build | `<M?>` | Durable state, core models, basic runtime. |
| Product Build | `<M?>` | User-facing workflows and integrations. |
| Hardening | `<M?>` | Recovery, diagnostics, security, packaging. |
| Release Gate | `<M?>` | Final review and release evidence. |

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

Required phase decomposition:

| Phase | Objective | Owner | Contract | Expected Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|
| `<phase>` | `<objective>` | `<owner>` | `<contract or none>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |
