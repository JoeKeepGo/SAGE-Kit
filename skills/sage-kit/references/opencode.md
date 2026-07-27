# OpenCode Profile

This is an OpenCode runtime adapter for `sage-kit`. It describes OpenCode
discovery, activation, configuration, and observed enforcement limits. It is
not a second governance contract.

## Canonical Contracts

- Adapter selection, authorization, bounds, evidence capture, fallback, and
  descendant inheritance: `package-doc("docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-003")`.
- Runtime/model-policy overrides: `package-doc("docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-007")`.
- Managed workspace, resource, containment, and process-tree reporting:
  `package-doc("docs/agent/HOST_RESOURCE_GOVERNANCE.md")`.

Those contracts retain authority. OpenCode configuration and tool results are
execution evidence only: they cannot widen scope, elevate authority, turn a
gate into `PASS`, or establish completion.

## Discovery And Activation

OpenCode recognizes Agent Skills-format `SKILL.md` files. Install the complete
`skills/sage-kit/` directory so its `references/` directory remains available.
Common discovery locations are:

- `.opencode/skills/sage-kit/SKILL.md` in the project;
- `~/.config/opencode/skills/sage-kit/SKILL.md` for a user installation;
- `.agents/skills/sage-kit/SKILL.md` when that compatibility location is
  enabled by the installed runtime.

The native `skill` tool loads a skill by name. OpenCode may also choose a skill
from its description when handling a task. `disable-model-invocation: true` is
shared frontmatter for runtimes that support it, not an OpenCode guarantee of
user-only activation. Restart when the installed OpenCode version requires it
to discover a newly added skill.

`agents/openai.yaml` is Codex display metadata and is not an OpenCode
activation surface.

## Configuration And Enforcement

Inspect the installed OpenCode version and its effective project/user
configuration before relying on a permission or subagent setting. Configuration
names have varied across OpenCode releases, including `agent`/`permission` and
`agents`/`permissions`; an unknown, missing, or rejected setting supplies no
enforcement claim.

When the installed runtime supports effective permission rules, use its native
`allow`, `ask`, and `deny` controls for the applicable tool or command class.
Treat `ask` as an approval interaction, not proof that a skill can only be
loaded by a user or that all equivalent routes are blocked. `edit: deny` can
make a review lane non-writing through the normal tool path. Shell rules can
ask or deny package installation, configuration changes, destructive commands,
and submit commands. A broad `edit: allow`, command glob, or subagent role does
not prove a packet-level writable-file boundary.

Report only the enforcement level demonstrated for the managed operation:

| Observed OpenCode condition | Reported boundary |
|---|---|
| Effective permission rule blocks the normal OpenCode tool path | `MANAGED` for that path, with its configured limitation |
| Permission configuration is absent, unsupported, unverifiable, or bypassable through another route | `SOFT` |

Never report `HARD` from a permission setting, an agent role, or a successful
command. Use the host-resource contract for containment terminology and
process-tree evidence.

When configuration is absent or its effect cannot be verified, use the safe
native fallback: the primary agent follows the active authority and bounded
packet, edits only named files, runs only named verification, and records the
limitation and result as evidence. For a read-only lane, use native read/search
operations and return findings to the controller. If a required bound cannot
be preserved, return the authority-defined handoff or blocker state.

## Delegation

OpenCode subagents, when present in the installed runtime, receive a bounded
prompt naming the active authority, allowed and forbidden surface, expected
evidence, and stop condition. The controller must repeat applicable adapter
bounds and runtime policy in every child launch packet. A descendant may not
use OpenCode delegation to elevate authority, resource limits, or evidence
status; it must propagate the same bound to any authorized child.

Capture whether the runtime actually inherited permissions, working directory,
and result visibility. That record is evidence of the observed boundary only,
not proof of complete containment. If inheritance is unavailable or cannot be
verified, keep executable work with the controller or use a bounded native
single-agent workflow.

## OpenCode Deltas

- The skill tool, custom-agent discovery, `@mention` routing, and subagent
  invocation behavior are version-dependent; detect them before making a
  multi-agent plan depend on them.
- Preserve the project-native workflow, approval gates, verification, and
  acceptance ownership. OpenCode is an optional execution provider, not a
  replacement authority.
