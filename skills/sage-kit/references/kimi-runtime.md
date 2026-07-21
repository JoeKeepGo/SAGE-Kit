# Kimi Runtime Profile

Environment profile for running sage-kit in the explicitly supported Kimi Work
and Kimi Code runtimes. Other clients that describe themselves as compatible
are not covered by these guarantees: detect their skill invocation,
permissions, delegation, persistence, and resume capabilities before use, and
treat unknown behavior as a soft capability.

The governance model is platform-neutral, but process containment is not
identical across operating systems. The embedded Harness reports its selected
platform adapter, containment level, and limitations; do not infer equal
Windows, macOS, and Linux guarantees. No public SAGE-Kit command entrypoint is
required.

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
- This environment does not require a public command entrypoint install. A local package
  checkout is sufficient for standard operation. A toolchain install is an
  `environment-write` and requires approval first.
- No other runtime dependencies.

## Invocation Mapping

| Codex | Kimi Work | Kimi Code |
|---|---|---|
| `$sage-kit` mention invokes the skill | Invoke the skill by exact name through the runtime Skill surface; explicit-only behavior is a soft guarantee | Invoke explicitly with `/skill:sage-kit` |
| `agents/openai.yaml` (`display_name`, `default_prompt`) | Ignored; display metadata only | Ignored; display metadata only |
| `allow_implicit_invocation: false` (hard config) | No hard equivalent; the description carries a soft explicit-trigger policy | `disable-model-invocation: true` is the supported hard equivalent |

For any other client, probe these capabilities instead of inheriting the Kimi
Code column. Missing or unverifiable controls remain soft and must not be
recorded as enforced.

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

- The Codex-targeted `ui-ux-pro-max` adapter install path
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
| Coder Controller and workers | `coder` subagents dispatched by the main session with bounded prompts that reference the normalized active SPEC or ephemeral packet, allowed files, gates, and stop conditions |
| Final Review session | Read-only `explore` review lane returning an ephemeral verdict packet to the controller; persistence occurs only when project-owned SPEC/configuration requires it |
| Wave Execution | Parallel subagent calls only when Wave Readiness is proven (disjoint writable files, serial shared files, frozen contracts) — unchanged rule |
| Worktree Isolation | Pure git; unchanged |
| Serial files (`ACTIVE_CONTEXT.md`, `DOC_ROUTING.md`) | Controller-owned; workers return Memory Update Proposals — unchanged rule |

Subagent constraints to record in execution packets:

- Detect timeout, resume-by-id, result visibility, persistence, and delegation
  support before relying on them. Do not infer those properties from a generic
  compatibility label.
- Subagents return an ephemeral structured result to the controller. Persist a
  lane packet, result packet, or evidence record only when project-owned
  SPEC/configuration requires repository persistence.
- When a supported runtime exposes no durable subagent state, long work may use
  `.sagekit/runtime/CURRENT_RUN.json` as runtime state without turning it into
  project authority.
- Nested delegation is reasoning-only. A subagent may delegate bounded
  analysis when a named, detected runtime supports it, but it may not assign
  executable work to that child. Any executable grandchild must be launched
  by the root/main session with its own bounded packet. Unknown permission
  inheritance is a soft limitation, not a hard guarantee.

## Authorization Level Mapping

| SAGE adapter level | Kimi runtime surface |
|---|---|
| `metadata-only` | Skills index and tool-list inspection (default) |
| `read-only` | `explore` subagent, Read/Grep, plugin queries |
| `write-inside-boundary` | `coder` subagent or main-session Edit/Write within named allowed files |
| `environment-write` | Installing skills, plugins, runtime adapters, MCP servers, or config; requires explicit owner approval |
| `destructive-or-submit` | Push, merge, publish, delete, deploy; closed approval gate, confirm before calling |

## Continuity Mapping

- `.sagekit/runtime/CURRENT_RUN.json` and checkpoint/resume contracts are
  available when the named runtime exposes the required filesystem and embedded
  package APIs.
- The on-disk checkpoint is runtime state, not project authority. Capability
  detection must confirm that a client can read and resume it.
- Kimi Work only: long-term memory may mirror `next_action` and checkpoint
  pointers across process restarts, and a scheduled Blueprint job may report
  checkpoint drift. Both are optional enhancements; their output is evidence
  input, not gate completion.

## Runtime Deltas

| Feature | Kimi Work | Kimi Code |
|---|---|---|
| Skill invocation (Skill tool, skills index) | yes | yes |
| Subagent orchestration (`coder` / `explore` / `plan`) | yes | yes |
| Checkpoint / resume via on-disk JSON | yes | yes |
| Scheduled Blueprint jobs, widgets, dashboards | yes | no |
| Long-term memory mirror for continuity | yes | no; rely on the checkpoint file |

## Known Deltas (vs Codex)

1. `agents/openai.yaml` is ignored by the Kimi runtime (display metadata
   only).
2. Explicit-only invocation is split: Kimi Code honors
   `disable-model-invocation: true`; Kimi Work has no hard equivalent, so the
   skill description carries a soft explicit-trigger policy.
3. Codex-targeted adapter install commands are not applicable; use the
   Kimi-native capability table above.
4. Subagent timeout, result visibility, persistence, and nested delegation are
   runtime capabilities that must be detected. Unknown clients receive no hard
   guarantee from this profile.
