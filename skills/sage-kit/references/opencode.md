# OpenCode Profile

Environment profile for running sage-kit inside OpenCode, the open-source,
model-agnostic terminal coding agent. OpenCode implements the Agent Skills
open standard, so the `sage-kit` skill drops in without format changes.

This file is additive environment guidance. It does not modify the skill's
governance rules, and no Codex-facing file is changed by its presence.

## Local Information Policy

This document intentionally contains no machine-specific or owner-specific
details: no local paths, no usernames, no provider or model inventory beyond
what SAGE-Kit governance requires. Resolve concrete capability names from
the active environment at use time.

## Skill Compatibility

| Requirement | sage-kit status |
|---|---|
| `SKILL.md` with YAML frontmatter | yes |
| `name` 1–64 chars, lowercase kebab-case, matches directory | `sage-kit` passes |
| `description` 1–1024 chars | passes (~500 chars) |
| Unknown frontmatter fields | none used; `agents/openai.yaml` is outside the scanned surface and is ignored |

Discovery paths (any one is sufficient):

- Project: `.opencode/skills/sage-kit/SKILL.md`
- Global: `~/.config/opencode/skills/sage-kit/SKILL.md`
- Universal fallback also scanned: `.agents/skills/sage-kit/SKILL.md`

Copy the whole `skills/sage-kit/` directory so `references/` ships with it.
Restart the session after installing. OpenCode loads skills on demand
through its native `skill` tool: the agent sees only name and description
until it selects the skill, which matches this skill's narrow-read design.

## Invocation Mapping

| Codex | OpenCode |
|---|---|
| `$sage-kit` mention invokes the skill | The `skill` tool loads it by exact name; the agent auto-selects from the description when the task matches, and the user can request it by name |
| `agents/openai.yaml` display metadata | Ignored; no equivalent surface |
| `allow_implicit_invocation: false` (hard config) | Hard enforcement is available: set `"permission": { "skill": { "sage-kit": "ask" } }` in `opencode.json` so every load requires user approval. Without it, explicit-only behavior rests on the description wording (soft guarantee). Prefer the hard rule for governed projects |

## Permission Mapping

OpenCode permissions (`allow` / `ask` / `deny`, glob resources, per-agent
overrides, last match wins) can enforce SAGE-Kit authority modes natively.
Map them as follows:

| SAGE adapter level | OpenCode enforcement |
|---|---|
| `metadata-only` | Default; skills and agents visible by name and description |
| `read-only` | Agent frontmatter `permission: { edit: deny }` |
| `write-inside-boundary` | `edit: allow` plus bash globs limiting verification commands |
| `environment-write` | bash rules: package installs, global config writes → `ask` or `deny` |
| `destructive-or-submit` | bash rules: `git push*`, `rm -rf*`, publish commands → `deny` or `ask` |

Example `opencode.json` baseline for a governed project:

```json
{
  "permission": {
    "skill": { "sage-kit": "ask" },
    "bash": {
      "*": "ask",
      "git status*": "allow",
      "git diff*": "allow",
      "git push*": "deny",
      "rm -rf*": "deny"
    }
  }
}
```

Treat these rules as enforcement of the SAGE-Kit boundary, not as the
boundary itself: allowed files, gates, and stop conditions still live in the
phase doc and execution packets.

## Orchestration Mapping

| SAGE-Kit construct | OpenCode mapping |
|---|---|
| Project Manager session | Primary agent (`build`) running the sage-kit skill; owns routing, serial files, gates, submit authority |
| Coder Controller and workers | Custom `sage-coder` subagent (template below), dispatched via the Task tool with a bounded prompt naming SAGE docs, allowed files, gates, and stop conditions |
| Final Review session | Custom `sage-final-review` subagent with `edit: deny`; returns a verdict packet to the primary agent |
| Read-only exploration lanes | Built-in `explore` subagent (read-only) — reuse it instead of defining a new one |
| Wave Execution | Parallel Task calls only when Wave Readiness is proven (disjoint writable files, serial shared files, frozen contracts) — unchanged rule |
| Worktree Isolation | Pure git; unchanged |
| Serial files (`ACTIVE_CONTEXT.md`, `DOC_ROUTING.md`) | Controller-owned; workers return Memory Update Proposals — unchanged rule |

Worker template `.opencode/agents/sage-coder.md`:

```markdown
---
description: SAGE-Kit bounded implementation worker. Executes one approved
  packet inside named file boundaries and returns evidence.
mode: subagent
permission:
  edit: allow
  bash: ask
---

You are a SAGE-Kit Coder worker. Execute only the dispatched packet:
1. Read the SAGE-Kit docs named in the dispatch prompt before editing.
2. Edit only the allowed files named there; never touch serial files
   (docs/ACTIVE_CONTEXT.md, docs/DOC_ROUTING.md).
3. Run only the verification commands named in the packet.
4. Return: changes made, verification evidence, findings, and a Memory
   Update Proposal. Do not claim DONE; acceptance is the controller's call.
```

Review template `.opencode/agents/sage-final-review.md`:

```markdown
---
description: SAGE-Kit read-only final review lane. Returns a verdict packet
  with severity-classified findings; never edits files.
mode: subagent
permission:
  edit: deny
  bash: ask
---

You are a SAGE-Kit Final Reviewer. Review against the phase doc, contracts,
and quality gates named in the dispatch prompt.
1. Classify findings by severity (P0-P3) with file and line references.
2. Classify required corrections as AUTO_CORRECTIVE, PM_DECISION, BLOCKED,
   or DEFER.
3. Return the verdict packet to the controller. You may not edit files,
   accept milestones, or record closure receipts.
```

## Model Assurance

OpenCode is model-agnostic, so executor quality varies by configured model
per agent. Apply `docs/agent/MODEL_ASSURANCE_POLICY.md` per agent rather
than globally: stronger models may run the standard contract; weaker or
unproven executors should run Strict Mode task cards. The `model` field in
agent frontmatter makes the executor choice explicit and reviewable.

## Continuity Mapping

- `.sagekit/runtime/CURRENT_RUN.json` and the `sagekit checkpoint` /
  `sagekit resume` commands work unchanged through OpenCode's bash tool; no
  install is required beyond the CLI itself.
- OpenCode has no cross-session memory or scheduled jobs; the on-disk
  checkpoint is the only continuity mechanism. Keep it current before any
  handoff.

## Known Deltas (vs Codex)

1. `agents/openai.yaml` is ignored by OpenCode (display metadata only).
2. No `$skill` syntax; the `skill` tool loads by exact name.
3. Custom subagents have had upstream invocation bugs in some releases
   (Task tool not listing markdown-defined agents, `@mention` routing not
   firing). Verify against your installed version before relying on
   multi-agent flows; fall back to primary-agent serial execution when
   affected.
4. Configuration keys differ across OpenCode generations (`agent` /
   `permission` vs newer `agents` / `permissions`). Check the docs matching
   your installed version before writing config.
5. No scheduled jobs, notifications, or dashboard surfaces; continuity is
   checkpoint-only.
