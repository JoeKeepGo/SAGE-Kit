# Runtime Smoke Template

Use this document to prove that the control plane and execution boundary work
in a live environment.

## Smoke Scope

Describe the runtime path being verified:

```text
user-facing client -> control plane -> execution boundary -> result -> visible state
```

## Preconditions

- Environment:
- Required config:
- Safe fixture or target:
- Approval gate status:

## Commands

```bash
<start control plane>
<start or verify execution boundary>
<call health route>
<call contract route>
```

## Expected Evidence

- control plane process is reachable;
- execution boundary reports health or capability;
- request IDs or correlation IDs match where applicable;
- errors are explicit;
- browser-facing response is redacted;
- logs contain enough information to diagnose failure without exposing secrets.

## Completion Report Snippet

```markdown
Runtime Smoke:
- command:
- result:
- evidence:
- skipped checks:
- approval gates:
```

