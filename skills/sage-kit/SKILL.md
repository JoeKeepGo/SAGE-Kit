---
name: sage-kit
description: Lightweight local task tracking for coding agents. Use when a repository is initialized with SAGE-Kit (`.sage-kit/config.json`) and the user wants a tracked task, durable evidence, a scoped task brief, or a completion gate. Do not use for uninitialized repos or non-development writing.
---

# SAGE-Kit

SAGE-Kit is a single-user, local, single-repository task tracker. Task state lives in
files under `.sage-kit/` and is written by the `sage-kit` CLI. It is not a service:
there is no daemon, no HTTP API, no database connection, and no network call.

## Project root

The CLI resolves the **project root** as the nearest ancestor directory that contains
`.git`. When no such directory exists (for example a scratch directory that is not a
git repository), it uses the current working directory. Configuration is then read from
`<project-root>/.sage-kit/config.json`; the CLI does not search parent directories for
the config file.

## When to use

Use this skill when **all** of these are true:

- `.sage-kit/config.json` exists at the resolved project root (run
  `sage-kit doctor --json` if the root or config state is unclear).
- The work is a coding task in this repository.
- The user asks to create, inspect, update, brief, or finish a tracked task.

Do not use SAGE-Kit for one-off shell commands, writing prose, or a different project.

## Commands

Run commands from anywhere inside the repository; they act on the resolved project root.
If the package is not installed locally/globally, use the tarball or `node dist/cli.js`
from a checkout — the package is not published on the npm registry yet.

```text
sage-kit task create --title "<title>" --description "<why>" --acceptance "<criterion>"
sage-kit task list
sage-kit task show <id> --json
sage-kit task status <id> running
sage-kit task status <id> review
sage-kit task status <id> done --evidence "file:line or command output"
sage-kit brief --task <id> --max-bytes 2048
sage-kit doctor --json
```

Task statuses: `imported`, `ready`, `running`, `review`, `done`, `blocked`, `failed`,
`cancelled`, `interrupted`. The CLI enforces transitions: a new task starts `ready`,
and `done` is only reachable from `review` (running/ready → done is rejected). A task
can move `running → review → done`; record evidence on the `review → done` step.

## Rules

1. Create or select one task before substantial edits. Keep one active task.
2. Read the task brief before editing; it is the bounded context, not a replacement for
   the repository's own instructions. Prefer a host-exposed brief tool if available
   (e.g. the DSH plugin's `sage_brief`); otherwise `sage-kit brief` prints the current
   brief. `SESSION_BRIEF.md` at the project root is an init-time snapshot and may be stale.
3. `done` requires at least one evidence item. If the acceptance criteria are not met,
   leave the task `running`, `review`, or `blocked` — do not claim completion.
4. Never fabricate evidence. Evidence is a pointer (file, test, exact command output),
   not a claim of success.
5. Task files under `.sage-kit/state/tasks/<id>.json` are the source of truth; events are
   appended to `.sage-kit/state/events/events.jsonl`; run records live under
   `.sage-kit/state/runs/`. Do not hand-edit a task file while the CLI may be writing.
6. This skill is stateless. It does not start a server, hold a database connection, or
   make network calls. The CLI reads/writes local files only.
7. Hooks are optional and advisory, and `init` does **not** install host hooks. When the
   host or user calls `sage-kit hook`, honor a `warn` message and never ignore a `block`
   action. Without hook wiring, generate the brief manually with `sage-kit brief`; a
   missing hook is a limitation to report, never evidence of success.

## Host notes

- **DSH:** repository instructions are `AGENTS.md`; the project skill is installed at
  `.dsh/skills/sage-kit/`. Real DSH 0.2.1-rc.2 headless sessions (mock and real model)
  discovered and loaded it; an optional native plugin (`sage-kit-dsh`) can expose
  `sage_brief` / `sage_task_*` and inject the brief at `agent/pre-step`. DSH exposes no
  installable native third-party hook config for the CLI's `hook` protocol, so
  `session.start` is not injected automatically; GUI plugin acceptance is `NOT_EXECUTED`.
- **Codex:** repository instructions are `AGENTS.md`; the file adapter installs the skill
  into the project's `.agents/skills/sage-kit/`. Real Codex session discovery is
  `NOT_VERIFIED`.
- **Claude Code:** repository instructions are `CLAUDE.md`; the file adapter installs the
  skill into `.claude/skills/sage-kit/`. Real Claude session discovery is `NOT_VERIFIED`.

If the host does not discover project skills, still use the CLI directly; the skill is
convenience, not a runtime requirement.
