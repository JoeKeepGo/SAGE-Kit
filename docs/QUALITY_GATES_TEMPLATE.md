# Quality Gates Template

This document defines the evidence required before project work can be called
complete.

## Gate Levels

| Level | Use When | Evidence Examples |
|---|---|---|
| Unit | Pure behavior in one module. | Focused test cases. |
| Contract | API, event, CLI, worker, UI, or config boundary. | Schema tests, fixture tests, consumer tests. |
| Integration | Multiple components interact. | Service-to-worker, API-to-database, backend-to-external adapter checks. |
| Runtime | Behavior depends on a running process. | Curl, CLI invocation, process health, logs. |
| UI | User-visible behavior changes, if the project has a UI. | Browser or component smoke with visible states. |
| Security | Secrets, auth, permissions, sensitive data. | Redaction checks, deny-path tests, scans. |
| Release | Build, package, deploy, or publish. | Artifact checks, rollback notes, release smoke. |

## Gate Status Values

Every phase completion report must classify applicable gates with these values.

| Status | Meaning |
|---|---|
| `PASS` | Required evidence exists and was checked. |
| `FAIL` | Evidence was produced and shows the gate failed. |
| `BLOCKED` | Evidence cannot be produced without a blocker, missing input, or approval. |
| `WAIVED` | Project owner explicitly accepted the risk for this phase. |
| `N/A` | Gate does not apply, with a concrete reason. |

Blocking gates marked `FAIL`, `BLOCKED`, or missing cannot be accepted.
Blocking gates marked `WAIVED` require owner, reason, and scope.

## Universal Required Gates

| Gate | Required Evidence |
|---|---|
| Read gate | Completion report names docs read, phase doc, files, and verification plan. |
| Project owner entry gate | Broad, non-technical, or coarse-roadmap projects produce intake and a capability map before executable roadmap planning. |
| Phase documentation gate | Non-trivial work uses a retained phase document. |
| Milestone granularity gate | Milestone candidate maps to one primary capability and has reviewable phases with contracts, file boundaries, tests, and smoke plans. |
| Contract gate | Request, response, event, config, UI, CLI, or data contract is named before implementation. |
| Test gate | Focused tests exist and run, or a manual-only exception is justified. |
| Runtime gate | Runtime claims are proven by live evidence. |
| UI visibility gate | UI claims are proven by visible state checks when UI is in scope. |
| Wave safety gate | When Wave Execution is used, parallel lanes have exclusive file ownership and controller integration evidence. |
| Wave readiness gate | Wave or parallel phase execution names independent lanes, exclusive writable files, serial shared files, frozen contracts, runtime ownership, validation lanes, integration owner, and conflict stop conditions. |
| Coder separation gate | In Session Orchestration, Coder Controller self-execution is absent or explicitly allowed, narrow, recorded, and independently reviewed. |
| Authority gate | Every active packet names both governance level and permission mode; write, corrective, environment-write, and submit authority are explicit. |
| Corrective closure gate | When review returns required corrections, it provides a corrective packet, Project Manager decision request, blocker, or waiver path. |
| Security gate | Secrets and sensitive data are not exposed or staged. |
| No fallback gate | No guessed fields, hidden success, speculative aliases, or silent downgrade paths. |
| Completion report gate | Final report lists files, tests, smoke, skipped checks, and remaining gaps. |
| Capability adapter gate | External capability use records adapter name, authorization level, boundary served, evidence produced, and fallback when relevant. |
| Structured dispatch gate | When Task Dispatch Profile is active, task and evidence records exist, required L0-L4 levels are present, resource locks and leases are recorded, and the validator passes in gate-ready mode before acceptance. |

## Universal Blockers

- behavior changed but no test or smoke path exists;
- implementation started without the required retained phase document;
- a broad, non-technical, or coarse-roadmap project generated an executable roadmap directly
  from intake without a capability map and granularity audit;
- milestone implementation started before phases were decomposed into
  reviewable slices;
- a milestone candidate spans multiple primary capabilities without being
  split;
- a phase mixes unrelated ownership domains without a wave plan and integration
  owner;
- parallel lanes edit the same file without controller-owned serialization;
- a runtime behavior was claimed from static checks only;
- UI behavior was claimed without opening or smoke-checking the UI surface;
- Wave Execution or parallel phases are used without Wave Readiness Gate
  evidence;
- Coder Controller self-executes broad milestone work without explicit
  self-execution policy and independent review;
- a packet or handoff names governance level but omits permission mode;
- a read-only review returns `NEEDS_CORRECTION`, `BLOCKED`, or
  `Corrective Packet Required: yes` without a corrective packet, Project
  Manager decision request, blocker, or waiver path;
- write, corrective, environment-write, submit, merge, publish, release, or
  cleanup work occurs without the matching permission mode;
- a hidden fallback path masks failure as success;
- an external capability writes files, installs tools, changes environment
  configuration, or claims completion without adapter authorization and
  evidence mapping;
- a shared contract changed without updating both owner and consumer evidence;
- secrets, credentials, tokens, private keys, account data, or production data
  are staged or committed.
- a blocking gate is skipped without an explicit `WAIVED` status from the
  project owner.
- Task Dispatch Profile is active and a task, phase, or milestone is accepted
  without a passing gate-ready dispatch validator result.

## Required Gate Status Table

Every phase completion report must include:

| Gate | Status | Evidence | Blocking | Owner | Notes |
|---|---|---|---|---|---|
| `<gate>` | `PASS`, `FAIL`, `BLOCKED`, `WAIVED`, or `N/A` | `<evidence>` | `<yes/no>` | `<owner>` | `<notes>` |

## Baseline Commands

Replace with project-specific commands:

```bash
<unit test command>
<typecheck command>
<build command>
<runtime smoke command>
```

## Completion Language Rule

Allowed:

```text
Unit tests passed. Runtime smoke was not applicable because this phase changed
only static documentation.
```

Not allowed:

```text
This should work.
```

Evidence beats confidence.

## Optional Structured Evidence Levels

Use these levels when a project adopts the Task Dispatch Profile:

| Level | Meaning |
|---|---|
| `L0` | Static and structural evidence. |
| `L1` | Focused behavior evidence. |
| `L2` | Contract or integration evidence. |
| `L3` | Runtime evidence. |
| `L4` | Release or production-path evidence. |

These levels complement the gate table above. They do not replace normal
quality gates, owner waivers, or Final Review judgment.
