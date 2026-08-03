# Engineering System Template

Use this file to bind SAGE-Kit to project-owned authority. SAGE-Kit coordinates
within granted scope and never owns product scope, threat model, permissions,
checks, or acceptance.

## Authority And Current Truth

- Active SPEC / project authority:
- Permission and acceptance owners:
- ACTIVE_CONTEXT (exclusive current objective/status/findings/blockers/next action):
- Project-required checks and approval gates:

Historical ledgers are immutable event/evidence indexes. Handoffs are bounded
transfer views. Completion reports reference authority, evidence, and current
truth instead of copying them.

## Control Level

Use the canonical matrix in `docs/agent/GOVERNANCE_LEVELS.md`:

- Light: 0-1 docs, controller may execute, no independent review by default,
  1-2 focused checks, conditional CI;
- Standard: short plan/result, useful risk-based subagents, one affected
  review, focused checks and required CI once per unchanged candidate;
- Heavy: 3-5 purposeful docs by default, one independent final review, risk
  checks and final CI only when selected by a project gate, merge/release, or
  acceptance criteria, plus explicit high-risk human gates.

Permission remains separate. Unknown model identity and delegation alone do not
enable Strict or Heavy. Shared toolchains serialize only mutable shared state;
authorized isolated lanes may commit locally while push/merge remain serial.

## Optional Profiles

Enable Graph, milestone packages, phases, waves, controller/coder split,
packets, structural gates, adapters, browser/data/redaction checks, threat-model
prompts, or legacy compatibility only when project authority or concrete risk
selects them. Planning-only defaults to one author, one bounded risk review if
warranted, and one targeted fix.

## Completion

Apply `docs/SAGE_CORE.md#sage-completion-001`. Mechanical wording, status, or
EOF fixes close with a focused check; semantic correctives receive one targeted
re-review. Continue within the same corrective authority while findings
decrease; two consecutive same-root no-progress rounds return `BLOCKED`.

Stop for product acceptance, scope/permission expansion, a new threat-model or
safety decision, destructive/production work, credentials, merge, or release.
