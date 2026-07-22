# SPEC Source Contract

`SAGEKIT_CONFIG.json` schema v1 may set `active_context` and optional
`doc_routing`. Resolve both configured in-project paths before reading startup
authority. When `doc_routing` is absent, use legacy `docs/DOC_ROUTING.md`; when
`active_context` is absent there is no schema-v1 project authority. Fixed
`docs/ACTIVE_CONTEXT.md` and `docs/DOC_ROUTING.md` references are legacy
defaults, not mandatory topology. Machine-enforced profiles are activated only
by project configuration, never by prose or agent selection.

This contract defines how SAGE-Kit finds project facts, assigns execution
authority, and presents them to the Harness. SAGE-Kit governs SPEC semantics
and execution contracts; it does not require project documents to live in one
framework-owned directory.

## Architecture

The execution data flow is:

```text
Markdown, explicit path, configured adapter, or legacy docs/<M>
-> SPEC Source Adapter
-> Normalized SPEC Model
-> Execution Packet
-> Harness Runtime
```

The normalized model represents Project, Milestone, Phase, Gate, Evidence, and
Active Context without using a source path as business identity. Source paths,
adapter names, and canonical resolved paths are provenance. Moving unchanged
content must not change its semantic digest or create a different execution
packet merely because the directory changed.

An execution packet carries the selected scope and authority, dependency DAG,
allowed and forbidden boundaries, evidence requirements, stop conditions, and
resource policy. Project documents do not need to repeat generic Kit or Skill
rules already supplied by the pinned package contract.

<a id="sage-ctx-002"></a>

## Scope Classes

- `ACTIVE_SPEC`: the project facts authorized for current execution.
- `ACTIVE_CONTEXT`: a compact current-truth and handoff view for the active
  milestone and phase.
- `ACCEPTED_HISTORY`: immutable accepted evidence and closeout material.
- `REFERENCE_ONLY`: background or decision context with no execution authority.
- `RUNTIME_STATE`: leases, candidates, counters, checkpoints, and transient
  execution state under `.sagekit`.

Directory location, filename pattern, glob membership, or an old status field
does not promote a document into `ACTIVE_SPEC`. A container explicitly
classified as `ACCEPTED_HISTORY` is non-executable and may be opened only by an
explicit history audit. Accepted history and reference material never
participate in current duplicate, lock, lease, board, gate, candidate, or
fingerprint reconciliation. An exact content-digest reference may use history
as evidence, but never promotes it into execution authority.

When candidate lifecycle must remain independent of unrelated repository
history, use the versioned `active-spec` candidate snapshot. It binds the
normalized current Milestone semantic digest; legacy clean-head and
working-tree candidate formats retain their existing whole-repository
semantics.

<a id="sage-ctx-001"></a>

## Authority Resolution

Resolve one current source in this order:

1. an explicit source selected by the user;
2. the active source or milestone mapping in project configuration;
3. the `ACTIVE_CONTEXT` Current Work Pointer;
4. the legacy `docs/<M>` adapter for a legacy project and an explicitly selected
   milestone when legacy fallback is enabled;
5. one aggregated scope error.

An explicit or configured source fails closed. It must never silently fall back
to legacy discovery when it is missing, malformed, unsafe, or semantically
incomplete. Multiple plausible current sources are ambiguity, not permission to
scan all of them.

Legacy projects remain supported without migration. New configuration fields
are optional, versioned, and additive. Frozen validation contracts and accepted
history remain unchanged.

## ACTIVE_CONTEXT

`ACTIVE_CONTEXT` remains a first-class handoff interface. Its path is
configurable; `docs/ACTIVE_CONTEXT.md` remains the legacy default. The compact
view contains only:

- current milestone and phase;
- current status and authority;
- blockers and next action;
- a small set of key decisions;
- evidence and closeout pointers.

It is not a complete execution specification and cannot replace the selected
`ACTIVE_SPEC` or execution packet.

Full history, leases, candidate counters, and the Harness state machine belong
outside this view. Ordinary status, next-action, evidence-pointer, layout,
blank-line, path-display, and wording synchronization is C0/C1 and receives
targeted verification only. Authority, scope, approval, security boundary, or
source-of-truth changes require semantic review. Check and compile are read-only
and must not rewrite this view.

## Active And Historical Validation

For projects adopting this scope contract, embedded source loading, normalized
SPEC validation, and ephemeral packet compilation operate on `ACTIVE_SPEC`
only. Frozen contracts are invoked only by a separately authorized history
audit host workflow. SAGE-Kit does not expose accepted history as an executable
source and this contract does not invent a public history-audit API.

Required semantic input inside the selected active source fails closed when it
is missing or malformed. An EOF, obsolete field, or old schema in an
out-of-scope historical or reference file is not an active-execution failure.
Unclassified or ambiguous authority produces one aggregated scope finding, not
a per-file failure storm.

Thin documents reduce repeated governance prose, not planning depth. Every
active plan must still contain the project-specific objective, design and key
decisions, dependency DAG, boundaries, risks, acceptance, evidence, and stop
conditions needed for safe execution. SAGE-Kit defines no universal maximum for
Milestones, Waves, Phases, or changed files; readiness follows dependency,
authority, risk, and reviewability. A zero-diff candidate proves only that no
tracked content changed. It does not prove readiness, acceptance, evidence, or
gate closure.

## Adoption And Synthetic Fixtures

Default adoption is package-bound. `SAGEKIT_CONFIG.json` records the stable
public contract manifest version and digest, a machine-readable project
identity, source mappings, and the configured ACTIVE_CONTEXT path.
Its optional `profiles` array is the only project-config activation source for
machine-enforced optional profiles such as `task-dispatch-v2`; artifact presence
or prose does not activate a profile.
`SAGE_PROJECT.json` remains the compatible execution-document lock for
`thin-v1`: it selects the execution document model and pinned policy contracts
after source resolution. Source authority resolves first, then the selected
content is validated by the execution-document lock. Neither file silently
overrides the other. A future contract version may unify them; current projects
must not duplicate facts beyond these separate ownership boundaries.

The public contract digest includes the explicit Harness API version and
versioned executable contract resources only. Package release metadata, generic
docs, Skill text, and unrelated implementation files do not change this
identity. Projects created with the former whole-package digest require one
explicit authority migration; accepted history is never rewritten for it. A
project does not copy the framework runtime, schemas, generic docs,
Skill, templates, or tests, and it does not maintain a consumer-side allowlist
for package files. Public-contract compatibility is checked through the
manifest version and canonical executable-contract digest.

Framework vendoring remains an explicit compatibility profile. It is never the
default and does not authorize rewriting existing project or historical files.

Synthetic compile, adoption, and package-smoke fixtures live in test temporary
directories. They create a temporary Git repository only when a Git/worktree
binding is part of the behavior under test. Embedded validation and compile must not create a
fixture, checkpoint, output file, cache, bytecode, or `.sagekit` runtime state in
the inspected project unless the user explicitly selected a write operation.

## Resource Admission

| Admission | Normal operations |
|---|---|
| Direct read-only | file reads, deterministic config parsing, in-process normalized SPEC compilation, and repository snapshot reads |
| Light managed | Focused validators, focused unit tests, and bounded short Git subprocesses |
| Strict governance | Full suites, wheel/package builds, fresh environments and installs, browser/runtime smoke, long-lived services, high CPU or memory work, and tools likely to create descendants |

Direct read-only work acquires no heavy lease, starts no Windows Job Object, and
runs no adoption self-test. Consumer adoption performs at most one lightweight
capability detection; containment probes and platform product self-tests belong
to SAGE-Kit CI and release evidence. Every external process still requires a
bounded timeout, bounded output, stage reporting, and cleanup limited to its
owned process tree. Capability claims remain honest: Windows may report `HARD`,
POSIX may report `MANAGED`, and neither implies that arbitrary bypassed commands
are intercepted.

## Review Economy

Each planning candidate receives at most one full planning review. The reviewer
returns findings in one batch. P0/P1 always block. P2 blocks only for authority,
false-green, approval, security, validator/gate readiness, source authority, or
evidence integrity; ordinary documentation-consistency P2 does not block.

C0/C1 corrections receive targeted verification and targeted closure only.
Ledger-, evidence-, status-, and pointer-only changes run only the affected
record or Lane D/E equivalent review. Full lanes run again only when semantics,
permissions, source authority, or the information-architecture contract changed.
Continue automatically while findings fall and scope stays stable. Return
`BLOCKED` only after two consecutive rounds for the same root cause make no
material progress, not because a fixed corrective count was reached.
