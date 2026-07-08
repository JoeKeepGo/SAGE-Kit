# Boundary Template

This file is retained as a short alias for
`CONTROL_BOUNDARY_TEMPLATE.md`.

Prefer using `CONTROL_BOUNDARY_TEMPLATE.md` for new projects.

---

# Control Boundary Template

Use this document to define the boundary between a control plane and an
execution agent, worker, or runtime component.

## Components

| Component | Owns | Does Not Own |
|---|---|---|
| Control plane | Product state, user-facing API, permissions, audit, UI, orchestration. | Local execution internals or hidden side effects. |
| Execution agent | Scoped execution, local observation, capability report, execution result. | Product users, permissions, durable product state, browser-facing policy. |

## Trust Boundary

- Browser-facing clients talk only to the control plane.
- The control plane validates requests before calling the execution agent.
- The execution agent returns scoped observations and results.
- The control plane redacts and normalizes responses before exposing them.

## Forbidden Paths

- Browser-to-agent direct calls.
- Agent-owned product authorization.
- Hidden mutation without audit.
- Raw secrets in UI, logs, reports, or responses.
- Protocol fallback that treats unknown errors as success.

## Contract Owner

| Contract | Owner | Consumers | Compatibility Rule |
|---|---|---|---|
| `<contract>` | `<owner>` | `<consumers>` | `<rule>` |
