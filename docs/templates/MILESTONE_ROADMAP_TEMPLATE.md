# Milestone Roadmap Template

Use this roadmap to define the project sequence from design gates through
implementation and release.

## Roadmap Rules

- Each milestone proves one primary capability.
- Review gates are first-class milestones.
- Runtime implementation starts only after required design gates are accepted.
- Approval gates remain closed unless explicitly opened.
- Milestones must be decomposed into phases before implementation starts.
- Broad phases must be split until each has one owner, one contract boundary,
  bounded files, and clear verification.

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
