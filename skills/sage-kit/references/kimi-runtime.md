# Kimi Runtime Profile

Environment profile for running sage-kit inside the Kimi runtime, which
covers both Kimi Work (desktop agent) and Kimi Code CLI. Both share the same
skill system — `SKILL.md` format, a skills index as the source of truth, and
a plugin/MCP surface — so one profile covers both. The few feature deltas
are called out in Runtime Deltas below.

This profile is platform-neutral. The SAGE-Kit Python package contains no
OS-specific assumptions (`sagekit.cmd` is a Windows shim; POSIX shells use
`python -m sagekit`), and nothing in this profile depends on a particular
operating system.

This file is additive environment guidance. It does not modify the skill's
governance rules, and no Codex-facing file is changed by its presence.

## Local Information Policy

This document intentionally contains no machine-specific or owner-specific
details: no local paths, no usernames, no exact runtime patch versions, and
no inventory of locally installed skills or plugins. Concrete capability
names must be resolved from the runtime skills index at use time, never
hard-coded from one machine's setup.

## Environment Requirements

- Python ≥ 3.10 available to the agent shell; a runtime-managed Python is
  fine.
- The CLI works directly from a checkout (`python -m sagekit ...`). A
  persistent install (`pipx install ...`) is an `environment-write` and
  requires approval first.
- No other runtime dependencies.

## Invocation Mapping

| Codex | Kimi runtime (Work and Code CLI) |
|---|---|
| `$sage-kit` mention invokes the skill | The runtime invokes skills through its Skill tool by exact name; the skills index is the source of truth |
| `agents/openai.yaml` (`display_name`, `default_prompt`) | Ignored; display metadata only, no behavior loss |
| `allow_implicit_invocation: false` (hard config) | No hard equivalent. The `SKILL.md` description carries the policy through explicit trigger and negative-trigger wording ("Use when SAGE-Kit is explicit...", "Do not use for generic milestones..."). Preserve that wording in any Kimi runtime install |

## Runtime Capability Mapping

The Superpowers reference-integration table in
`docs/agent/CAPABILITY_ADAPTERS.md` maps as follows in this environment.
All Kimi runtime capabilities follow the standard adapter lifecycle
(detect, authorize, bound, invoke, capture, map, fallback) and default to
`metadata-only` or `read-only`.

Capability routes below are named by category. The controller resolves the
concrete skill or plugin name from the runtime skills index at use time and
records the resolved name, version, and source in the adapter evidence. The
installed inventory differs per machine; never assume a specific plugin is
present.

| SAGE-Kit need | Codex reference | Kimi runtime route |
|---|---|---|
| Clarify broad intent | superpowers: brainstorming | Main-session dialogue; `plan` subagent for structured ideation |
| Turn requirements into plans | superpowers: writing-plans | `plan` subagent (read-only) plus SAGE planning templates |
| Implement behavior | superpowers: test-driven-development | `coder` subagent inside the approved file boundary |
| Diagnose failures | superpowers: systematic-debugging | `coder` or `explore` subagent with bounded reproduction |
| Coordinate bounded workers | subagent-driven-development | Parallel subagent calls only with disjoint file ownership |
| Request review | requesting-code-review | Read-only `explore` review lane returning findings to the controller |
| Prove completion | verification-before-completion | Shell-run verification with evidence capture (unchanged) |
| Frontend / UI build | `ui-ux-pro-max` | Kimi-native webapp / design skill |
| Browser QA | browser tools | Kimi-native browser-automation skill (drives the owner's real browser) |
| Charts / data visualization | — | Managed-Python charting skill |
| Documents (docx/xlsx/pptx/pdf) | — | Document-generation skills, when installed |
| Academic research | — | Academic-search plugin, when installed |
| Market / enterprise data | — | Finance or enterprise-data plugins, when installed |
| PRC legal data | — | Legal-database plugin, when installed |
| Image / audio generation | — | Media-generation plugins, when installed |

Notes:

- The Codex-targeted `ui-ux-pro-max` install path (`uipro init --ai codex`)
  is not applicable here. Prefer the Kimi-native frontend skills at
  `read-only` default; request approval before any install.
- Kimi runtime skills and plugins live under runtime-managed directories.
  Treat any write to them as `environment-write` (see below).
- "When installed" routes fall back to the SAGE-Kit-native path when the
  plugin is unavailable; record the fallback in the adapter evidence.

## Orchestration Mapping

| SAGE-Kit construct | Kimi runtime mapping |
|---|---|
| Project Manager session | Main session; owns routing, serial files, gates, and submit authority |
| Coder Controller and workers | `coder` subagents dispatched by the main session with bounded prompts that name SAGE docs, allowed files, gates, and stop conditions |
| Final Review session | Read-only `explore` review lane returning a verdict packet to the controller; the controller records it |
| Wave Execution | Parallel subagent calls only when Wave Readiness is proven (disjoint writable files, serial shared files, frozen contracts) — unchanged rule |
| Worktree Isolation | Pure git; unchanged |
| Serial files (`ACTIVE_CONTEXT.md`, `DOC_ROUTING.md`) | Controller-owned; workers return Memory Update Proposals — unchanged rule |

Subagent constraints to record in execution packets:

- Subagents run as bounded same-process loops with a fixed timeout; on
  timeout, resume the same subagent by id rather than starting fresh.
- Subagent results are visible only to the controller. The controller must
  write lane packets, result packets, and evidence into the repository.
- Subagents have no independent cross-process persistence. Long milestone
  work must checkpoint through `.sagekit/runtime/CURRENT_RUN.json`.

## Authorization Level Mapping

| SAGE adapter level | Kimi runtime surface |
|---|---|
| `metadata-only` | Skills index and tool-list inspection (default) |
| `read-only` | `explore` subagent, Read/Grep, plugin queries |
| `write-inside-boundary` | `coder` subagent or main-session Edit/Write within named allowed files |
| `environment-write` | Installing skills, plugins, CLIs, MCP servers, or config; requires explicit owner approval |
| `destructive-or-submit` | Push, merge, publish, delete, deploy; closed approval gate, confirm before calling |

## Continuity Mapping

- `.sagekit/runtime/CURRENT_RUN.json` and the `sagekit checkpoint create`,
  `checkpoint status`, and `resume` commands work unchanged from a checkout;
  no install is required.
- The on-disk checkpoint is the canonical source of truth in both Kimi Work
  and Kimi Code CLI.
- Kimi Work only: long-term memory may mirror `next_action` and checkpoint
  pointers across process restarts, and a scheduled Blueprint job may run
  `sagekit checkpoint status` and report drift. Both are optional
  enhancements; their output is evidence input, not gate completion.

## Runtime Deltas

| Feature | Kimi Work | Kimi Code CLI |
|---|---|---|
| Skill invocation (Skill tool, skills index) | yes | yes |
| Subagent orchestration (`coder` / `explore` / `plan`) | yes | yes |
| Checkpoint / resume via on-disk JSON | yes | yes |
| Scheduled Blueprint jobs, widgets, dashboards | yes | no |
| Long-term memory mirror for continuity | yes | no; rely on the checkpoint file |

## Known Deltas (vs Codex)

1. `agents/openai.yaml` is ignored by the Kimi runtime (display metadata
   only).
2. Hard `allow_implicit_invocation: false` has no Kimi equivalent; it is
   enforced through the skill description wording as a soft guarantee.
3. Codex-targeted adapter install commands are not applicable; use the
   Kimi-native capability table above.
4. Subagents differ from Codex sessions (bounded runs, controller-visible
   results, no independent persistence); mitigated by checkpoint/resume and
   packet-on-disk conventions.
