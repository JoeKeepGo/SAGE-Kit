# Control-Plane And Execution-Agent Profile

Use this profile when a project has a browser or API control plane that
coordinates work performed by a separate execution agent, worker, service, or
runtime boundary.

## Adds To Core

- Trust boundary documentation.
- Control-plane to execution-agent protocol.
- Capability and version checks.
- Redacted, browser-safe responses.
- Runtime smoke for the execution boundary.
- Mutation gates for actions with external effects.
- Cross-component contract owner and consumer tracking.

## Boundary Rules

- The control plane owns product state, users, permissions, audit, UI, and
  browser-facing APIs.
- The execution agent owns only scoped execution and local observation.
- The browser calls the control plane, not the execution agent.
- Execution-agent responses must be redacted before reaching user-facing
  surfaces.
- Mutating actions require authorization, audit, dry-run or preview where
  possible, and explicit approval gates for high-risk environments.

## Required Documents

| File | Purpose |
|---|---|
| `docs/CONTROL_BOUNDARY.md` | Ownership and trust boundary. |
| `docs/EXECUTION_PROTOCOL.md` | Request, response, error, version, and capability contract. |
| `docs/RUNTIME_SMOKE.md` | Commands and evidence for live boundary checks. |
| `docs/CROSS_COMPONENT_CONTRACTS.md` | Contract owner, consumers, and compatibility notes. |

Template sources:

- `docs/profiles/control-plane-agent/CONTROL_BOUNDARY_TEMPLATE.md`
- `docs/profiles/control-plane-agent/EXECUTION_PROTOCOL_TEMPLATE.md`
- `docs/profiles/control-plane-agent/RUNTIME_SMOKE_TEMPLATE.md`
- `docs/profiles/control-plane-agent/CROSS_COMPONENT_CONTRACTS_TEMPLATE.md`

## Acceptance Rules

- No user-facing surface exposes execution secrets.
- No browser path bypasses the control plane.
- Protocol errors are explicit.
- Capability mismatch fails visibly.
- Mutations are audited and bounded.
- Runtime claims include live boundary evidence.
