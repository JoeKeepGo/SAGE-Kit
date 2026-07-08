# Approval Gates Template

Approval gates define actions that require explicit human approval before an AI
agent or automation performs them.

## Default Closed Gates

| Gate | Opens Only When | Required Evidence |
|---|---|---|
| Production credentials | User approves a scoped credential use. | Secret handling plan, redacted logs, no staged secrets. |
| Production data | User approves named inputs and objective. | Data minimization plan, read/write scope, cleanup plan. |
| Destructive action | User approves exact target and rollback. | Backup or rollback evidence and target confirmation. |
| External mutation | User approves service, environment, and action. | Dry-run or fake-provider evidence where possible. |
| Environment capability install | User approves tool, source, files/config it will write, and fallback. | Documentation source read, version/source, write list, assistant target, rollback or uninstall path, no silent hooks, no multi-assistant or global install unless explicitly approved. |
| Release or publish | User approves version and destination. | Build checks, changelog, artifact scan, rollback note. |
| Merge to protected branch | User approves merge after review, when Git or protected branches are used. | Clean branch, fresh checks, no forbidden files staged. |

## Approval Request Format

When approval is required, ask for:

- exact action;
- exact target;
- expected effect;
- rollback or recovery plan;
- verification after completion.

## Agent Rules

- Do not infer approval from prior unrelated messages.
- Do not broaden approval scope.
- Do not run real mutations when the phase says fake, dry, or simulation only.
- Record approval evidence in the completion report.
