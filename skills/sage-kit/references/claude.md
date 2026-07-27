# Claude Code Profile

This is a Claude Code runtime adapter. It supplies only Claude-specific
discovery, tool-surface, and enforcement facts. It does not define SAGE-Kit
authority, role permissions, evidence, verification, acceptance, or workflow.

## Canonical Pointers

Use the named canonical owner rather than duplicating its rules here.

| Concern | Canonical owner | Claude Code delta |
|---|---|---|
| Authority, approval, and completion | `sagekit/resources/docs/SAGE_CORE.md#sage-auth-001` and `sagekit/resources/docs/SAGE_CORE.md#sage-auth-009` | Claude permissions do not grant project authority. |
| Packet, source, file boundary, and controller duties | `sagekit/resources/docs/agent/AGENT_HARNESS.md#sage-auth-010` | Dispatch the resolved authority and named launch-only delta; Coder packet file and command limits remain `SOFT` instructions unless a separate control covers a specific operation. |
| Permission modes and separated Coder/Final Review authority | `sagekit/resources/docs/agent/GOVERNANCE_LEVELS.md#sage-auth-004`, `sagekit/resources/docs/agent/GOVERNANCE_LEVELS.md#sage-auth-005`, and `sagekit/resources/docs/agent/GOVERNANCE_LEVELS.md#sage-auth-006` | Agent frontmatter narrows available tools; it cannot broaden a packet. |
| Adapter lifecycle, evidence-only results, native fallback, and descendant inheritance | `sagekit/resources/docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-003` | Propagate the bound and applicable runtime/model policy in every child prompt. |
| Managed-operation containment and reporting | `sagekit/resources/docs/agent/HOST_RESOURCE_GOVERNANCE.md` | Claude hooks and tool declarations are not host-process containment. |
| Session roles, verification ownership, and review/corrective flow | `sagekit/resources/docs/agent/SESSION_ORCHESTRATION.md` | The controller owns required command execution and its evidence. |

An adapter result is evidence only. It cannot create permission, widen scope,
open a gate, establish `PASS`, accept work, or claim `DONE`.

## Claude Code Discovery

Claude Code discovers a skill from a project, personal, plugin, or managed
deployment location. Deploy the whole `skills/sage-kit/` directory so the
`references/` files remain available on demand. Resolve concrete locations and
supported frontmatter against the installed Claude Code version; this profile
intentionally contains no machine-specific paths or inventories.

`SKILL.md` uses `disable-model-invocation: true`. Where the installed runtime
supports that field, it is a `HARD` invocation control for model-initiated skill
loading. Settings rules such as `Skill(sage-kit)` can further allow, ask, or
deny use. Neither control replaces explicit packet authority.

## Tool And Role Mapping

Copy the shipped agent files into a governed project's `.claude/agents/`
directory when their bounded roles are authorized.

| SAGE-Kit role | Claude Code agent | Runtime restriction | Controller responsibility |
|---|---|---|---|
| Coder worker | `sage-coder` | `Edit`, `Write`, and `Bash` are exposed. Packet-authorized file and command limits are `SOFT` worker instructions, not frontmatter-enforced restrictions. | Issue the writable boundary and run any controller-owned verification. |
| Final Review | `sage-final-review` | `Read`, `Grep`, and `Glob` only; no edit, write, or shell tool. | Run required verification and provide its output as review evidence. |
| Exploration | Built-in read-only exploration/planning agent when available | No writable or shell surface unless separately authorized. | Keep it inside the same inherited bound. |

The reviewer tool set is a `HARD` restriction on the declared agent surface:
it cannot modify files or execute verification commands through those tools.
The review verdict remains evidence only and never replaces controller-owned
verification, corrective authorization, or acceptance.

## Hook And Containment Limits

The shipped `protect-serial-files` PreToolUse hook may be bound to the Coder
agent for the named structured edit and Bash events. Its serial-file control is
`MANAGED` only when Claude Code invokes the configured hook for the event and
the deployment has the matching hook command available. It does not make a
worker's packet file or command boundary `HARD`.

For structured edit events, the hook can reject its configured controller-owned
serial-file targets before that tool operation. Only that matching serial-file
control is `MANAGED`; other packet allowed/read-only/forbidden paths remain
`SOFT` instructions. Bash inspection is command-text heuristic and therefore
`SOFT`: shell indirection or another unobserved write path can bypass it, so it
does not enforce the packet command boundary. A controller that needs stronger
isolation must select a worker without `Bash` or use an environment-enforced
boundary, then report the actual containment level under
`sagekit/resources/docs/agent/HOST_RESOURCE_GOVERNANCE.md`.

Windows and Unix deployments select a runtime-supported hook command for the
available shell. The paired hook implementations do not imply equivalent host
containment, and neither platform is presumed `HARD` merely because a hook is
configured. Do not edit hook scripts as part of this adapter profile.

## Dispatch And Continuity

Dispatch the normalized `ACTIVE_SPEC` or execution packet, allowed/read-only/
forbidden files, commands, gates, expected evidence, and stop conditions. Read
legacy documents only when the packet names them. Every descendant inherits the
same adapter bound and applicable runtime/model policy; a descendant that cannot
repeat them in its child packet must return the authority-defined handoff.

For a Coder with the shipped frontmatter, the packet file and command boundary
is a `SOFT` instruction boundary. It remains mandatory governance, but it is
not a runtime-enforced tool restriction except for a matching managed
serial-file structured-edit control.

Use native model workflows for planning, implementation, debugging, review,
and verification whenever the packet requires them. Runtime helpers are optional
methods inside the canonical adapter lifecycle, not new authority or a fallback
for missing evidence.

Claude session continuation can restore conversation context, but the
project-owned checkpoint and evidence records remain canonical. Version-gated
features, agent frontmatter, isolation modes, and hook behavior must be
detected from the installed runtime before reliance; unsupported or unverified
behavior is reported as a limitation, not inferred as enforcement.
