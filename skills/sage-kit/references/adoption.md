# SAGE-Kit Adoption

Use this reference when a project is being evaluated for SAGE-Kit or needs a
small SAGE-Kit bootstrap.

## Default Profile: Package-Bound

New adoption binds the installed SAGE-Kit package and its canonical
package version and safe runtime/resource manifest digest. The project retains only:

- its own SPEC sources and human documents;
- optional source-adapter and milestone mappings;
- the configured `ACTIVE_CONTEXT` and optional document-routing authority paths,
  when they differ from legacy defaults;
- project-specific authority, gates, exceptions, acceptance, and evidence.

Do not copy the SAGE-Kit runtime, schemas, generic docs, Skill, templates, tests,
or a framework-file allowlist into the project. Generic governance comes from
the pinned package contract. Installing the Skill for an agent runtime is a
separate operation and does not vendor the framework into the project.

Framework vendoring is an explicit compatibility profile only. Use it when an
existing legacy project intentionally depends on local Kit documents; never
select it merely because the project contains Markdown.

## Choose The SPEC Source

Milestone documents remain first-class project assets and may live at any
authorized project path. Resolve current execution authority in this order:

1. explicit source configuration;
2. project-configured active source or milestone mapping;
3. `ACTIVE_CONTEXT` Current Work Pointer;
4. legacy `docs/<M>` for an explicitly selected legacy milestone;
5. one aggregated scope error.

An explicit or configured source never silently falls back. Accepted history,
reference folders, filenames, globs, and old status fields do not become current
authority. See `docs/agent/SPEC_SOURCE_CONTRACT.md` for scope and adapter rules.

Keep an established `legacy-markdown` project working without migration.
`thin-v1` remains an execution document model, not a Task Dispatch version. Thin
documents remove repeated generic prose; they do not reduce the required
project-specific design, dependency, risk, acceptance, evidence, or stop
condition depth.

## Bootstrap Order

1. Confirm the project boundary and that adoption is explicitly requested.
2. Select package-bound adoption unless compatibility vendoring is explicitly
   requested.
3. Record the installed package version and safe runtime/resource manifest digest.
4. Record one machine-readable project identity.
5. Identify the active SPEC source and adapter. Add a mapping only when the
   legacy adapter is insufficient.
6. Keep or create a compact `ACTIVE_CONTEXT` and routing authority at configured
   paths. `docs/ACTIVE_CONTEXT.md` and `docs/DOC_ROUTING.md` remain legacy defaults.
7. Record project-specific profile, gates, authority, acceptance, and evidence
   without copying generic governance prose.
8. Run a read-only check. Do not create milestones, fixtures, checkpoints,
   package mirrors, or generated packets unless the user selected the relevant
   writing operation.

For a broad or non-technical idea, establish the capability map and architecture
boundary before promoting an executable milestone. SAGE-Kit imposes no generic
maximum number of Milestones, Waves, Phases, or changed files; use dependency,
risk, authority, and reviewability to choose the shape.

## History And Runtime State

Default checks inspect active authority only. Accepted history remains immutable
and uses frozen contracts only through an explicit history audit or scope
selection. Do not rewrite history to satisfy current schemas.

Keep leases, candidates, counters, checkpoints, and transient execution data in
`.sagekit`, normally outside Git. `ACTIVE_CONTEXT` is a compact human/agent view,
not the Harness state machine.

Bootstrap is host-owned creation of the minimal versioned project configuration;
there is no public `sagekit.init` or bootstrap API. Machine-enforced profiles
activate only through project configuration.

Synthetic adoption and compile fixtures belong in test temporary directories,
not in the inspected project. Create a temporary Git repository only when the
behavior under test needs Git/worktree binding.

## Stop Conditions

Stop and ask for direction when the project boundary, active source, package
binding, approval gates, or source authority is ambiguous; when the requested
operation would modify accepted history; or when adoption requires unrelated or
external writes.

Do not stop for a path-display, EOF, blank-line, fixture-location, or ordinary
formatting issue that can be classified and corrected safely. A zero diff is not
proof that the SPEC, authority, evidence, or gates are ready.

## Output

Summarize the selected adoption profile, package/contract binding, active source
and adapter, configured handoff path, files created or updated, unresolved
authority or approval decisions, verification, and next action.
