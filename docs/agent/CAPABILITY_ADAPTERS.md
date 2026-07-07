# Capability Adapters

Capability Adapters define how SAGE-Kit uses external skills, plugins,
connectors, MCP tools, CI systems, reviewers, and local CLIs without making
them core dependencies.

SAGE-Kit remains the governance layer. Adapters provide optional execution,
planning, context, validation, or review help inside an approved SAGE-Kit
boundary.

## Classification

| Type | Meaning | Examples |
|---|---|---|
| Built-in profile | SAGE-Kit-owned optional control that ships with the kit. | Task Dispatch Profile. |
| Reference integration | External method that SAGE-Kit knows how to route to when available, but does not require. | Superpowers. |
| External adapter | Optional provider selected by capability metadata or project policy. | Frontend skills, OpenSpec, GitNexus, browser QA, database tools. |

Built-in profiles may have SAGE-Kit schemas, templates, and validators.
Reference integrations and external adapters must not be copied into SAGE-Kit
core. They are invoked or referenced only when available and authorized.

## Adapter Lifecycle

Use this lifecycle for every optional capability:

1. Detect: inspect available capability metadata, CLI presence, MCP tools, or
   project configuration.
2. Authorize: confirm the capability is allowed for the active phase, task,
   lane, gate, or corrective packet.
3. Bound: name allowed files, forbidden files, approval gates, evidence levels,
   runtime limits, and stop conditions before use.
4. Invoke: call only the selected capability instructions or tools needed for
   the task.
5. Capture: record concise outputs as evidence, context, planning input, or
   review findings.
6. Map: write or link useful outputs into the active SAGE-Kit artifact.
7. Fallback: if the capability is missing, fails, or is unsafe, use the
   SAGE-Kit-native path or return `HANDOFF` or `BLOCKED`.

Missing optional capability is not project failure. Record it as unavailable
and continue when a safe fallback exists.

## Authorization Levels

Adapter authorization level is separate from SAGE-Kit role permission mode in
`docs/agent/GOVERNANCE_LEVELS.md#authority-matrix`. External capability use
must satisfy both: the adapter must be authorized, and the active role or packet
must allow the matching read, write, corrective, environment-write, or submit
action.

| Level | Allowed Behavior | Gate |
|---|---|---|
| `metadata-only` | Inspect names, descriptions, versions, and availability. | Default when runtime exposes metadata. |
| `read-only` | Query, search, inspect, plan, review, or analyze without changing project or user configuration. | Phase or task boundary must allow it. |
| `write-inside-boundary` | Edit files already allowed by the active SAGE-Kit boundary. | Phase, lane, or task allowed files must name the surface. |
| `environment-write` | Install packages, write MCP config, hooks, global settings, generated skills, or context files. | Explicit project owner or controller approval. |
| `destructive-or-submit` | Delete, reset, migrate, deploy, push, merge, publish, or mutate external services. | Closed approval gate until explicitly opened. |

Adapters should default to `metadata-only` or `read-only`. Higher levels require
the active SAGE-Kit artifact to name the authority and evidence required.

## Evidence Contract

Every adapter use recorded in a completion report, ledger, task evidence, or
handoff should name:

- capability name and version or source when known;
- why it was selected;
- authorization level used;
- SAGE-Kit boundary it served;
- files, routes, services, or contracts it inspected or changed;
- concise result or artifact link;
- verification, smoke, or review evidence produced;
- fallback used when unavailable, unsafe, or inconclusive;
- any gates that remain blocked.

External capability output is evidence input. It does not automatically satisfy
SAGE-Kit gates, accept milestones, or mark work `DONE`.

## Frontend Adapter Rules

Use a frontend adapter when work involves UI, styling, React, Next.js,
design-system components, browser behavior, accessibility, responsive layout,
or visual QA.

The adapter must stay inside the active SAGE-Kit boundary and should produce:

- changed UI surfaces;
- allowed files touched;
- component or route contracts affected;
- browser, console, network, or runtime smoke evidence when applicable;
- screenshot or visual evidence when visual behavior is claimed;
- responsive viewport checks when layout is in scope;
- accessibility checks or non-applicability reason when user-facing UI changes;
- skipped checks and remaining risks.

The adapter must stop before:

- adding dependencies without approval when dependency policy requires it;
- changing backend contracts outside the phase boundary;
- treating screenshots as complete evidence when runtime behavior is also in
  scope;
- using mock data silently;
- widening design scope beyond the accepted requirement.

## Superpowers Reference Integration

Superpowers may provide execution discipline when available. Treat it as a
reference integration, not a dependency.

Recommended mapping:

| Need | Superpowers capability |
|---|---|
| Clarify broad intent | brainstorming |
| Turn approved requirements into tasks | writing-plans |
| Implement behavior | test-driven-development |
| Diagnose failures | systematic-debugging |
| Coordinate bounded workers | subagent-driven-development or dispatching-parallel-agents |
| Request review | requesting-code-review |
| Prove completion | verification-before-completion |

If Superpowers is unavailable, continue with SAGE-Kit phase docs, gates,
packets, and evidence templates.

## Task Dispatch Profile

Task Dispatch is a built-in SAGE-Kit profile, not an external adapter. It may
ship with SAGE-Kit because it is a lightweight governance structure: records,
schemas, resource locks, leases, evidence levels, and a validator.

Even though it is built in, it remains opt-in per milestone, phase, task, or
gate. Do not create task-dispatch records for ordinary small work unless the
Project Manager adopted the profile.

## Installation Policy

SAGE-Kit must not silently install external skills, plugins, CLIs, MCP servers,
hooks, or global configuration.

It may recommend or request installation only when:

- the project or user asked for that capability;
- the source is allowlisted or explicitly named;
- the installation writes are disclosed;
- fallback behavior is defined;
- the relevant approval gate is open.

If installation is declined or unavailable, continue with the SAGE-Kit-native
path when safe.

## Documentation Comprehension Gate

Before requesting approval to install or initialize an external adapter in a
new environment, the controller or agent must understand the provider's current
documentation well enough to avoid stale commands and hidden writes.

Do not approve or run an installation from memory alone. First read the
current provider documentation, package metadata, or installed-tool help needed
for the requested path. Then state:

- source read, including repository, docs page, package metadata, or command
  help;
- adapter purpose and why it is needed for the active SAGE-Kit boundary;
- supported agent or editor target for this environment;
- exact install or initialization command proposed;
- files, directories, MCP config, hooks, generated skills, global settings, or
  indexes the command may write;
- runtime requirements such as Node, Python, native build tools, browser access,
  network access, or package manager;
- uninstall, rollback, or cleanup path;
- fallback if install, init, or first use fails;
- evidence destination inside SAGE-Kit.

If documentation is unavailable, contradictory, stale-looking, or unclear about
writes, return `HANDOFF` instead of installing. If a tool supports multiple
installation routes, choose one route and state why; do not install overlapping
routes that could duplicate hooks, MCP servers, or skills.

## Approved Install Candidates

The following adapters are approved candidates for "detect, explain, request
approval, then install or initialize" flows. They are not approved for silent
installation.

| Adapter | Role | Default | Approval-Install Scope | Required Caution |
|---|---|---|---|---|
| `ui-ux-pro-max` | UI/UX design intelligence, design-system generation, frontend style guidance. | `read-only` when already installed; otherwise unavailable. | CLI install or marketplace install only after approval; prefer a single Codex-targeted path such as `uipro init --ai codex`. | Confirm current CLI/package docs, package name `ui-ux-pro-max-cli`, command name `uipro`, Python requirement, generated Codex skill paths, and uninstall path. Do not use `--ai all`, global install, or multi-assistant generation unless explicitly approved. |
| `OpenSpec` | Spec/change proposal, design, task, and archive workflow support. | `read-only` or unavailable. | Package install plus project initialization or update. | Confirm Node requirement, package name, generated project files, slash-command or agent guidance writes, and how outputs map back into SAGE-Kit artifacts. |
| `GitNexus` | Codebase graph, impact, trace, context, and code-intelligence queries. | `metadata-only` or `read-only` after an existing setup. | Repo indexing, MCP setup, optional plugin or hook setup. | Treat as high-caution: indexing may write repo-local and user-level registry data; setup may write MCP config, hooks, generated skills, and context files. Pick only one install route and require explicit approval for hooks or global config. |

For these candidates, use the lowest useful level:

1. Detect existing availability.
2. Prefer read-only use when already installed.
3. Request approval before installing packages, initializing project files, or
   writing environment configuration.
4. Keep generated outputs inside allowed SAGE-Kit file boundaries when possible.
5. Record installation evidence, skipped writes, and fallback in the completion
   report or handoff.

## ui-ux-pro-max Boundary

Treat `ui-ux-pro-max` as a frontend/design adapter, not a SAGE-Kit dependency.

Default behavior:

- If already installed, use it only as `read-only` design guidance unless the
  active packet authorizes UI writes.
- If missing, record it as unavailable and continue with the SAGE-Kit-native
  frontend path unless the user approves installation.
- For Codex environments, prefer the single-target Codex route. Do not install
  for all assistants or write global skill directories unless the user
  explicitly approves that wider environment change.

Installation or initialization requires `ENVIRONMENT_WRITE_AUTHORIZED` and must
state:

- current source read, package/version, and exact command;
- generated Codex skill path or project-local files;
- Python requirement and fallback if Python is unavailable;
- uninstall or rollback command;
- evidence destination inside the active completion report or handoff.

`design-system/` outputs require `WRITE_AUTHORIZED`. They may be created or
updated only when the active phase, lane, or packet names `design-system/` in
allowed files. Generated design-system files are design evidence or guidance;
they do not replace SAGE-Kit phase docs, UI contracts, quality gates, or
completion evidence.
