# Technical Design Template

Use this document to describe how the project is structured and how major
components interact.

## Architecture Summary

Describe the target architecture in a few paragraphs.

## Components

| Component | Owns | Does Not Own |
|---|---|---|
| `<component>` | `<responsibilities>` | `<non-responsibilities>` |

## Data Ownership

Describe durable state, temporary state, derived state, external data, and
exports. If the project has no durable data, state that explicitly.

## Public Contracts

| Contract | Owner | Consumers | Evidence |
|---|---|---|---|
| `<contract>` | `<owner>` | `<consumers>` | `<tests or smoke>` |

## Runtime Boundaries

Describe processes, services, CLIs, jobs, workers, devices, databases, queues,
or other runtime boundaries that apply to this project.

Use `not applicable` only with a reason when the project has no runtime
boundary.

## Error Handling

Describe how failures are surfaced, logged, retried, denied, or escalated.

## Security And Privacy

Describe secrets, credentials, local data, production data, permissions, and
redaction boundaries.

## Testing Strategy

Describe unit, contract, integration, runtime, UI, security, and release checks
that apply to this project.

## Non-Goals

List architectural choices or scopes that are explicitly not part of the
current project direction.
