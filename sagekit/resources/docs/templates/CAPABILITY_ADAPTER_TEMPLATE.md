# Capability Adapter: `<name>`

## Purpose

- Capability:
- Provider type: `<skill / plugin / MCP / CLI / CI / reviewer / other>`
- SAGE-Kit role: `<planning / execution / context / validation / review>`
- Default authorization level: `<metadata-only / read-only / write-inside-boundary>`
- Required SAGE-Kit permission mode: `<READ_ONLY_REVIEW / WRITE_AUTHORIZED /
  CORRECTIVE_AUTHORIZED / ENVIRONMENT_WRITE_AUTHORIZED / SUBMIT_AUTHORIZED>`

## Trigger

Use this adapter when:

- `<condition>`

Do not use this adapter when:

- `<condition>`

## Detection

- Metadata source:
- CLI or MCP check:
- Required project config:
- Missing-capability fallback:

## Documentation Preflight

Required before install, init, or environment writes:

- current documentation source read:
- package or version source:
- supported agent/editor target:
- exact command proposed:
- files/config/hooks/indexes generated or modified:
- runtime requirements:
- uninstall or rollback path:
- fallback if unavailable or install fails:

## Authorization

- Allowed SAGE-Kit boundary:
- Required permission mode:
- Allowed files:
- Read-only files:
- Forbidden files:
- Approval gates:
- Environment writes allowed: `<yes / no / only with approval>`
- Destructive or submit actions allowed: `<no unless explicitly opened>`

## Invocation

- Instructions or tools to load:
- Commands or tool calls:
- Inputs:
- Stop conditions:

## Evidence Mapping

Record these fields in the active completion report, ledger, task evidence, or
handoff:

- capability name and version/source;
- selected reason;
- authorization level;
- SAGE-Kit boundary served;
- files, contracts, or runtime surfaces inspected or changed;
- output summary or artifact link;
- tests, smoke, screenshots, logs, or review findings;
- skipped checks and fallback;
- remaining gates or blockers.

## Fallback

If unavailable, unsafe, or inconclusive:

- SAGE-Kit-native path:
- Evidence limitation:
- Handoff or blocker rule:
