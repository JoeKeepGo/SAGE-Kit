# SAGE-Kit Project Bootstrap

Current rebuild authority: [decisions](docs/decisions.md), then
[active SPEC](docs/rebuild/SPEC.md) and [acceptance](docs/rebuild/acceptance.md).
Read [progress](docs/rebuild/progress.md) for evidence and the next admitted work.

This repository adopts SAGE-Kit. Apply only this lightweight kernel to project
work:

1. **Authority and scope:** The active SPEC and current project authority own
   the normative objective, acceptance, and intent; explicit human decisions
   bound every action.
2. **Claim-evidence congruence:** Support each claim only to the depth and
   fidelity its attributable evidence actually reaches.
3. **Observed-fact ownership:** Read Git, runtime, checks, reviews, and
   artifacts from their canonical observed sources; the active SPEC and current
   project authority own intent and decisions.
4. **Affected-only invalidation:** Invalidate and replace only evidence whose
   relevant inputs changed.
5. **Genuine blockers:** Block only when an authority, permission, required
   input, or required evidence gap prevents safe progress.
6. **Human risk decisions:** Within host, system, and tool boundaries, an
   explicit human risk classification constrains the agent's discretionary
   safety threshold but does not grant permission. Permission remains target-
   and action-scoped under explicit human authorization and current project
   authority. An agent may report concrete contrary evidence and propose the
   smallest safeguard, but must not replace the human risk decision with a
   stricter personal threshold, invent a gate, or silently reduce authorized
   implementation to contract-only, synthetic-only, or no-op work.

Before optional Skill routing, a confirmed Codex GPT-5.6 runtime disables the
`using-superpowers` Skill and every Superpowers workflow for the controller and
all descendants. Apply the complete package-local policy in
`skills/sage-kit/references/codex.md` and continue with model-native engineering
capabilities.

Route from these compact risk discriminators before loading the complete Skill:

- **Light:** small, reversible, low-risk, bounded work, normally touching 0-1
  short documents and no authority, safety, security, public-contract,
  migration, production, release, or acceptance boundary. Light review and a
  mechanical wording/status/EOF corrective may remain kernel-only.
- **Standard:** normal multi-file or affected-boundary work, integration or
  package behavior, or materially semantic review/corrective work.
- **Heavy:** concrete authority, safety, security, destructive, production,
  release, irreversible, or broad-integration risk.

For Light work, use only this kernel when current project instructions cover
the task; do not implicitly load the complete Skill unless the user explicitly
overrides this route. For Standard or Heavy work, materially semantic review or
corrective work, and all acceptance or release work, load
`skills/sage-kit/SKILL.md` once per controller context. Reload after compaction
or resume when the prior Skill content is no longer observable. Descendants
inherit the same or narrower boundary; handoffs carry only the compact boundary
and selected profile identity with authority references, never the activation
marker. Do not cause nested Skill reloads or duplicate reviews.

The first progress update after activation emits this non-persistent marker:

SAGE_ACTIVE source=<project-entry> governance=<Light|Standard|Heavy> authority=<current-reference> profiles=<selected-or-none>

It is routing state, not execution, safety, permission, or compliance proof,
and must not be written to project documents, memory, receipts, or ledgers.
Explicit `$sage-kit` invocation remains an override or diagnostic and is the
fallback whenever adoption, current authority, or required Skill content cannot
be observed or resolved through automatic project instructions and implicit
routing.

## Other Skills

Additional project or host Skills may be listed below this section. Invoke a
Skill only when its declared trigger matches the current task and is not
disabled by host/runtime policy, and load only the task-relevant guidance. A
Skill may contribute specialist methods, tools, and checks within the existing
controller and authority. It does not expand scope, permission, gates, or
acceptance authority, and it must not override an explicit human decision or
introduce a second generic orchestration or review workflow for the same
unchanged scope.
