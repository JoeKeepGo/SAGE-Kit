---
name: sage-kit
description: 'Use only when SAGE-Kit is explicitly invoked, requested for adoption, or selected by current project authority. Routes model-native SPEC, planning, execution, review, handoff, and closeout without imposing SAGE-Kit on unrelated work.'
disable-model-invocation: true
---

# SAGE-Kit

SAGE-Kit is an activation and routing Skill. It does not replace project SPEC,
scope, permissions, gates, tests, evidence owners, or acceptance authority.
No CLI, package runtime, daemon, or hidden validator is required.

## Activate Narrowly

Activate only when the user invokes SAGE-Kit, asks to adopt it, or the current
project explicitly routes work through it. Do not impose it on generic coding,
planning, review, or debugging.

Project-owned current authority wins over framework guidance. Resolve, in
order:

1. host/system safety and tool boundaries;
2. explicit human decisions for this task;
3. project authority, active SPEC, and approval gates;
4. SAGE-Kit defaults;
5. adapter and agent suggestions.

Missing or contradictory required authority fails closed before mutation.
Historical documents are references unless current authority explicitly
selects them. `ACTIVE_CONTEXT` is compact current truth, not a second SPEC.

## Route Only What Is Needed

| Work | Read |
|---|---|
| Adoption | `references/adoption.md` |
| Roadmap, milestone, wave, or phase planning | `references/planning.md` |
| Implementation, debugging, or delegated work | relevant sections of `references/execution.md` |
| Review, corrective, handoff, acceptance, closeout | `references/review-completion.md` |
| Core authority and lifecycle | `docs/SAGE_CORE.md` when the framework checkout or static bundle is available |
| Graph and Node Result | `contracts/graph/v1/` only when Graph adds decision value |

Host references are loaded only for the active host: `references/codex.md`,
`references/claude.md`, `references/opencode.md`, or
`references/kimi-runtime.md`.

`framework-doc("path[#anchor]")` is a static locator into the matching SAGE-Kit
source archive or static release bundle. Resolving it reads text only; it does
not import a package, execute a validator, or change project authority. When
the referenced bundle is unavailable, use the self-contained guidance in this
Skill and report any missing project authority directly.

## Model-Native Workflow

1. Read current authority, active SPEC, and only task-relevant context.
2. Select Light, Standard, or Heavy from actual risk; select permission
   independently.
3. Create a bounded plan. Add a Graph only for meaningful dependencies, joins,
   gates, or parallel work.
4. Edit only allowed surfaces and run project-native focused checks.
5. Request independent review when risk or project authority requires it.
6. Correct the affected boundary and use targeted re-review.
7. Run the project's CI once for the final candidate.
8. Return evidence to the named human acceptance owner.

Models may use their native brainstorming, planning, TDD, debugging,
subagent, and review capabilities. Specialist Skills, plugins, MCP tools, and
project automation coexist with SAGE-Kit. Loading one never expands authority.

## Governance And Delegation

- **Light:** small, low-risk, bounded, usually one loop.
- **Standard:** normal multi-file work with affected-surface review.
- **Heavy:** delegation, security, authority, release, environment, or broad
  integration risk.

Delegated work names objective, allowed/read-only/forbidden surfaces,
permissions, expected evidence, and stop conditions. Descendants inherit the
same or narrower boundary. Parallel writers need disjoint ownership and one
integration owner. A subagent never gains product, submit, waiver, or
acceptance authority by delegation.

Cross-milestone unattended work is allowed only inside an explicit human
preauthorization that names the milestone range, allowed operations, path and
authority limits, stop conditions, and human-only decisions. Scope expansion,
authority change, security decisions, credentials, destructive operations,
acceptance, merge, and release remain human gates unless individually granted.

## Verification Economy

Use focused checks for each change, affected-only verification at a boundary,
and one project CI run for the final candidate. Reuse evidence only when its
inputs and scope are unchanged. A corrective receives targeted re-review; it
does not replay unrelated review lanes.

Continue while findings converge and scope remains fixed. Two consecutive
approved rounds with no progress on the same root cause stop the loop. Ordinary
owned wording, EOF, and non-semantic consistency fixes do not require a full
review cycle.

## Completion

Report authority used, changed surfaces, checks and review evidence, skipped or
unavailable checks, unresolved concerns, deferred work, and next action.
External tool output is evidence input only: it cannot declare `DONE`, pass a
gate, grant approval, or create human acceptance.
