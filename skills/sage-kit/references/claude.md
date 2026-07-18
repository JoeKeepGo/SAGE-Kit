# Claude Code Profile

Environment profile for running sage-kit inside Claude Code. Claude Code
implements the Agent Skills open standard and adds invocation control,
subagent isolation modes, and lifecycle hooks, so several SAGE-Kit rules
that are soft guarantees elsewhere become hard enforcement here.

This file is additive environment guidance. Supporting files ship under
`references/claude/`; no Codex-facing file is changed by this profile.

## Local Information Policy

This document intentionally contains no machine-specific or owner-specific
details: no local paths, no usernames, no organization or model inventory.
Resolve concrete configuration against the installed Claude Code version at
use time.

## Skill Compatibility

| Requirement | sage-kit status |
|---|---|
| `SKILL.md` with YAML frontmatter | yes |
| Command name from directory | `sage-kit` → `/sage-kit` |
| `description` + `when_to_use` truncated at 1,536 chars in listings | passes (~500 chars) |
| Supporting files under the skill directory | `references/` ships with the skill and loads on demand |

Discovery paths (any one is sufficient):

- Project: `.claude/skills/sage-kit/SKILL.md`
- Personal: `~/.claude/skills/sage-kit/SKILL.md`
- Plugin or managed deployment for team rollout

Copy the whole `skills/sage-kit/` directory so `references/` ships with it.
Skill edits are picked up live in the running session; a newly created
top-level skills directory requires a restart.

## Invocation Mapping

| Codex | Claude Code |
|---|---|
| `$sage-kit` mention invokes the skill | `/sage-kit` slash command, or automatic selection from the description |
| `agents/openai.yaml` display metadata | Ignored; no equivalent surface |
| `allow_implicit_invocation: false` (hard config) | Native equivalent: `disable-model-invocation: true` in the SKILL.md frontmatter. This field is set in the shared SKILL.md; it is inert in runtimes that do not define it. With it, only the user can invoke the skill |
| — | Additional hard control: permission rules `Skill(sage-kit)` in settings allow/deny/ask per skill |

## Permission Mapping

Claude Code settings permissions (`allow` / `ask` / `deny` rules for `Bash`,
`Edit`, `Skill`, `Agent`, and others) enforce SAGE-Kit adapter levels:

| SAGE adapter level | Claude Code enforcement |
|---|---|
| `metadata-only` | Default; skills and agents visible by name and description |
| `read-only` | Subagent `tools: Read, Grep, Glob` allowlist, or `permissionMode: plan` |
| `write-inside-boundary` | Default tools plus `permissions.ask` rules outside the boundary |
| `environment-write` | `permissions.ask` or `deny` on package installs and config writes |
| `destructive-or-submit` | `permissions.deny` on `Bash(git push *)`, `Bash(rm -rf *)`, publish commands |

Example `.claude/settings.json` baseline for a governed project:

```json
{
  "permissions": {
    "allow": ["Bash(git status *)", "Bash(git diff *)", "Skill(sage-kit)"],
    "ask": ["Bash(pip install *)", "Bash(npm install *)"],
    "deny": ["Bash(git push *)", "Bash(rm -rf *)"]
  }
}
```

Treat these rules as enforcement of the SAGE-Kit boundary, not as the
boundary itself: allowed files, gates, and stop conditions still live in the
phase doc and execution packets.

## Orchestration Mapping

| SAGE-Kit construct | Claude Code mapping |
|---|---|
| Project Manager session | Main session running the sage-kit skill; owns routing, serial files, gates, submit authority |
| Coder Controller and workers | `sage-coder` subagent (shipped at `references/claude/agents/sage-coder.md`), dispatched with a bounded prompt naming SAGE docs, allowed files, gates, and stop conditions |
| Final Review session | `sage-final-review` subagent (shipped at `references/claude/agents/sage-final-review.md`) with a read-only tool allowlist and no shell; verification execution stays with the controller |
| Read-only exploration lanes | Built-in `Explore` and `Plan` subagents — reuse them |
| Wave Execution | Parallel subagent calls only when Wave Readiness is proven — unchanged rule |
| Worktree Isolation | Native: set `isolation: worktree` on the worker subagent |
| Serial files (`ACTIVE_CONTEXT.md`, `DOC_ROUTING.md`) | Hard-enforced inside the worker subagent through its frontmatter PreToolUse hook (below); the controller session does not load it |
| Strict Mode task cards | Run the skill or packet with `context: fork` for isolated execution |

Copy the shipped agent files into the governed project's `.claude/agents/`
to activate them. Subagent `model`, `maxTurns`, and `effort` fields make
per-role cost and step limits explicit; subagent `memory: project` gives a
version-controlled cross-session memory that complements, but never
replaces, the milestone ledger.

## Deterministic Enforcement

Claude Code hooks let SAGE-Kit rules execute as code instead of relying on
model compliance. Two hooks ship under `references/claude/hooks/`, each in a
POSIX (`.sh`) and a Windows PowerShell (`.ps1`) variant:

- `protect-serial-files` (PreToolUse, matcher `Edit|Write|MultiEdit`) is
  bound inside the `sage-coder` subagent's frontmatter hooks, not in global
  settings. Scope is what makes the authorization real: the hook has no
  bypass, so workers can never write `docs/ACTIVE_CONTEXT.md` or
  `docs/DOC_ROUTING.md`, while the controller session simply does not load
  it and can perform legitimate controller writes. Windows-style path
  separators are normalized before matching, and the hook fails closed when
  `jq` is missing or the hook input is malformed.
- `stop-sagekit-check` (Stop, opt-in via `SAGE_STOP_CHECK=1`) is wired
  globally in the governed project's `.claude/settings.json`. It runs
  `sagekit check` and reads its exit code: `0` passes, `1` blocks on
  findings, anything else blocks as an invocation/capability failure
  reported as HANDOFF. A missing validator or Python interpreter also fails
  closed with a handoff message.

Global wiring in the governed project's `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": ".claude/hooks/stop-sagekit-check.sh" }
        ]
      }
    ]
  }
}
```

On Windows, use the `.ps1` variants and declare the shell in each hook
entry (also inside the `sage-coder` frontmatter hook):

```json
{ "type": "command", "command": ".claude/hooks/stop-sagekit-check.ps1", "shell": "powershell" }
```

The PowerShell variants parse hook input with `ConvertFrom-Json` and do not
require `jq`.

Hooks are enforcement, not authority: permission mode and ownership in the
active SAGE-Kit artifact still decide whether a write is legitimate.

## Model Assurance

Claude Code runs one model family, but per-subagent `model` and `effort`
fields still make executor strength explicit. Apply
`docs/agent/MODEL_ASSURANCE_POLICY.md` per role: unproven or low-effort
executors run Strict Mode task cards, and review lanes should not run on a
weaker configuration than the implementation lane they review.

## Continuity Mapping

- `.sagekit/runtime/CURRENT_RUN.json` and the `sagekit checkpoint` /
  `sagekit resume` commands work unchanged through the Bash tool.
- `claude --continue` / `claude --resume` restore session context; the
  on-disk checkpoint remains the canonical resume contract across machines
  and agents.
- Subagent `memory: project` may mirror durable learnings; the JSON
  checkpoint remains the source of truth for run state.

## Version Requirements

Mappings were verified against current documentation. Several features are
version-gated; check `claude --version` before relying on them:

| Feature | Minimum version note |
|---|---|
| `isolation: worktree` working-directory hardening | v2.1.203+ recommended |
| Background subagents by default | v2.1.198+ |
| Subagent output scanning | v2.1.210+ |
| `Agent` tool naming (formerly `Task`) | v2.1.63+; `Task(...)` aliases still work |
| `permissionMode: manual` alias | v2.1.200+ |

## Known Deltas (vs Codex)

1. `agents/openai.yaml` is ignored by Claude Code (display metadata only).
2. Invocation is `/sage-kit`, not `$sage-kit`; prose references to
   `$sage-kit` in SAGE-Kit docs read as "invoke the sage-kit skill".
3. Bundled skills such as `/code-review` overlap SAGE-Kit review lanes;
   SAGE-Kit gates and verdict formats remain authoritative, bundled skills
   are execution tools inside a boundary.
4. Hooks and subagent fields are version-gated (see Version Requirements);
   on older versions, fall back to soft rules and record the fallback.
