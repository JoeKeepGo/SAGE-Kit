# Minimal local project specification

This is a disposable SAGE-Kit adoption example. The project owner decides its
scope and acceptance. Running its check demonstrates this example only.

- **MIN-REQ-01:** Create `output/greeting.txt` containing exactly
  `Hello, SAGE-Kit!` followed by one newline (UTF-8).
- **MIN-ACC-01:** `node check.mjs` must exit zero after reading that actual file.
  Save its actual stdout, stderr and exit status as evidence for `greeting`.
- **MIN-GATE-01:** After the checked task, stop at `human_acceptance`. A check
  result is not human acceptance and does not authorize another task.

The owner may authorize one round in a separate disposable copy: prepare its
local plan/configuration, create the greeting, run the fixed check, and save
local evidence/state. The round has at most three attempts and a chosen expiry
within one hour. Only `output/`, `evidence/`, `plan.json`, `host.json` and
`state.json` (including its temporary coordination files) may be generated.
Do not change this specification, the check or
templates to get a pass. No network, dependencies, credentials, external writes,
release or RSI adoption are part of this example. Host permissions still apply;
plan scope and hooks do not provide filesystem isolation.
