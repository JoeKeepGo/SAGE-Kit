---
name: sage-kit
description: Lightweight local task governance for coding agents. Use when a repo has a .sage-kit config and the user wants a tracked task, durable evidence, a scoped task brief, or a completion gate. Do not use for unconfigured repos or non-development writing.
---

# SAGE-Kit

SAGE-Kit is a single-user, local, single-repository task control plane. The repository's
`docs/` and `AGENTS.md` remain authoritative. This skill only helps an agent operate
SAGE-Kit tasks correctly.

## When to use

Use this skill when **all** of these are true:

- `.sage-kit/config.json` (or a parent directory) exists.
- The work is a coding task in this repository.
- The user asks to create, inspect, update, brief, or finish a tracked task.

Do not use SAGE-Kit for one-off shell commands, writing prose, or a different project.

## Commands

Run commands from the repository root. The CLI finds the nearest git root. The commands below
use `sage-kit`; if the package is not globally installed, run `npx sage-kit ...` instead.

```text
sage-kit task create --title "<title>" --description "<why>" --acceptance "<criterion>"
sage-kit task list
sage-kit task show <id> --json
sage-kit task status <id> running
sage-kit task status <id> done --evidence "file:line or command output"
sage-kit brief --task <id> --max-bytes 2048
sage-kit doctor --json
```

## Rules

1. Create or select one task before substantial edits. Keep one active task.
2. Read the task brief before editing; it is the bounded context, not a replacement for
   the repository's own instructions.
3. `done` requires at least one evidence string pointing to a file, test, or command.
   If the acceptance criteria are not met, leave the task `running` or `blocked`.
4. Never fabricate evidence. Evidence is a pointer, not a claim of success.
5. The task file under `.sage-kit/tasks/` is the source of truth; do not hand-edit it
   while the CLI is running.
6. This skill is stateless. It does not start a server, hold a database connection, or
   make network calls. The CLI reads/writes local files only.
7. Hooks are optional and advisory. If a hook returns `warn`, explain the warning;
   never ignore a `block` action.

## Host notes

- **DSH:** the repository instruction file is `AGENTS.md`. DSH discovers project skills
  under `.dsh/skills/` and `.agents/skills/` in addition to global skill roots.
- **Codex:** repository instructions are `AGENTS.md`; install the skill into the
  project's `.agents/skills/sage-kit/` when supported.
- **Claude Code:** repository instructions are `CLAUDE.md`; install the skill into
  `.claude/skills/sage-kit/`.

If the host does not discover project skills, still use the CLI directly; the skill is
convenience, not a runtime requirement.
