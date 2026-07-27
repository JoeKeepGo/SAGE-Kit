# SAGE-Kit

[English](README.md) | [中文](README.zh-CN.md)

[![SAGE-Kit self-check](https://github.com/JoeKeepGo/SAGE-Kit/actions/workflows/sagekit-self-check.yml/badge.svg)](https://github.com/JoeKeepGo/SAGE-Kit/actions/workflows/sagekit-self-check.yml)
[![Latest release](https://img.shields.io/github/v/release/JoeKeepGo/SAGE-Kit)](https://github.com/JoeKeepGo/SAGE-Kit/releases)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)](https://www.python.org/)
[![MIT license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

SAGE-Kit is a project-governance and evidence runtime for long-running,
agent-assisted software work.

It combines project-owned SPEC contracts, an embeddable Python Harness, frozen
validation contracts, resource-aware execution, and an optional multi-runtime
Skill. The project remains authoritative for product requirements, scope,
permissions, approval gates, and acceptance. SAGE-Kit supplies the mechanisms
used to execute and verify those decisions without turning framework defaults
into product policy.

Project-owned SPEC and configuration are authoritative. The Harness interprets
and enforces their boundaries; it does not own project policy.

## Core Model

- Project-owned SPEC and configuration define the work.
- Source adapters normalize Markdown or machine-readable inputs without making
  their physical location part of execution identity.
- The embedded Harness compiles packets, validates contracts, manages bounded
  execution, and returns structured evidence.
- A compact active context carries current handoff facts; accepted history
  remains immutable reference material.
- Implementation, review, corrective work, verification, and acceptance keep
  distinct authority boundaries.
- Canonical framework resources ship with the package under
  [`sagekit/resources`](sagekit/resources).

## Architecture

```mermaid
flowchart LR
  A["Project authority and SPEC"] --> B["Source adapter"]
  B --> C["Normalized SPEC"]
  C --> D["Execution packet or direct Harness call"]
  D --> E["Controller and bounded workers"]
  E --> F["Focused verification and evidence"]
  F --> G["Independent review"]
  G --> H["PM acceptance or handoff"]
```

Paths provide provenance. Semantic identity is bound to project authority,
contracts, normalized inputs, workspace state, and candidate evidence rather
than one mandatory `docs/<milestone>` layout.

## Install

Install the latest tagged release directly from GitHub:

```bash
python -m pip install \
  "git+https://github.com/JoeKeepGo/SAGE-Kit.git@v2026.7.28.4"
```

For local development:

```bash
git clone https://github.com/JoeKeepGo/SAGE-Kit.git
cd SAGE-Kit
python -m pip install -e .
```

The package has no third-party runtime dependencies.

## Minimal Harness Use

The public API is exported from `sagekit`:

```python
from pathlib import Path

from sagekit import check_project

result = check_project(Path("."))
for finding in result.findings:
    print(finding.to_text())

if not result.ok:
    raise SystemExit(1)
```

Project tools can also:

- load configured, normalized SPEC sources;
- compile ephemeral execution packets;
- discover and verify workspace bindings;
- freeze and assess candidate fingerprints;
- create and resume checkpoints;
- validate versioned Task/Evidence records;
- run resource-managed commands and Git operations.

These APIs provide evidence and enforcement primitives. Their return values do
not grant PM acceptance or redefine project completion.

## Project Binding

New integrations should prefer:

- `SAGEKIT_CONFIG.json` for package binding, source mapping, active context, and
  active-only versus legacy scope;
- `SAGE_PROJECT.json` when using Thin documents (machine contract ID:
  `thin-v1`);
- project-owned milestone/phase manifests or an explicit Markdown source
  adapter;
- a compact, configurable `ACTIVE_CONTEXT` for current handoff facts.

Supported adoption profiles:

- `package-bound`: use installed package contracts and resources;
- `vendored-legacy`: retain an explicitly authorized legacy framework layout.

Supported execution scopes:

- `active-only`: evaluate the active authority without rescanning accepted
  history;
- `legacy-all`: preserve explicitly selected legacy behavior.

Explicit source mappings fail closed. SAGE-Kit does not silently fall back to a
different authority source.

## Optional Legacy Layout

Legacy Markdown layouts remain available when a project explicitly selects
`legacy-markdown`. They are compatibility inputs, not a second framework copy
and not the default for a new package-bound project.

## Controller Workflow

A normal milestone uses three logical controllers:

1. **PM Controller** defines the milestone, DAG, scope, acceptance criteria,
   resource policy, and approval boundaries.
2. **Coder Controller** delegates bounded implementation and focused testing,
   reconciles evidence, and freezes a candidate.
3. **Final Review Controller** runs independent review lanes, routes authorized
   correctives, and returns a verdict to the PM.

Subagents inherit the caller's allowed, read-only, and forbidden boundaries.
They do not gain product authority and do not recursively launch executable
descendants unless explicitly authorized.

## Verification Economy

SAGE-Kit uses an affected-evidence model:

```text
worker change        -> focused verification
lane closure         -> affected-lane verification
frozen candidate     -> one serial final verification graph
unchanged inputs     -> reuse bound evidence
```

`WAIVED`, `SKIPPED`, `HOST_UNAVAILABLE`, and incomplete verification are never
reported as `PASS`. Timeout or resource exhaustion produces a truthful handoff,
not a fabricated engineering failure or success.

## Compatibility

SAGE-Kit preserves:

- Thin documents and explicitly selected `legacy-markdown` documents;
- frozen validation contracts and versioned compatibility;
- existing `SAGE_PROJECT.json` projects;
- configurable legacy `docs/...` consumer layouts;
- immutable accepted-history provenance.

Consumer projects may still use `docs/...`. This source repository does not
duplicate package resources into a second top-level `docs` mirror.

## Optional Skill

The public Skill is located at [`skills/sage-kit`](skills/sage-kit). An
Installed Skill provides activation, routing, authority, delegation, review,
and completion guidance for Codex, Claude Code, OpenCode, Kimi Work, and
compatible hosts.

The Python package and the host Skill are deliberately separate installs. The
package provides the Embedded Harness and canonical resources. To add agent
routing, download the matching `sage-kit-skill-2026.7.28.4.zip`, its manifest,
and `.sha256` asset from the [release](https://github.com/JoeKeepGo/SAGE-Kit/releases/tag/v2026.7.28.4),
verify the checksum, then explicitly extract or sync the bundle through your
host's Skill mechanism. Installing the Python package does not change a host
Skill automatically.

The Skill is optional. It is not project authority and cannot create missing
requirements, threat models, migrations, gates, or acceptance criteria.

## Repository Layout

```text
sagekit/                    Embeddable Harness and runtime modules
sagekit/resources/docs/     Canonical governance docs and templates
sagekit/resources/contracts Frozen machine-readable contracts
skills/sage-kit/            Optional multi-runtime assistant Skill
scripts/                    Serial test and package helpers
tests/                      Unit, integration, compatibility, and smoke tests
```

Start with:

- [`SAGE_CORE.md`](sagekit/resources/docs/SAGE_CORE.md)
- [`AGENT_HARNESS.md`](sagekit/resources/docs/agent/AGENT_HARNESS.md)
- [`EXECUTION_ECONOMY.md`](sagekit/resources/docs/agent/EXECUTION_ECONOMY.md)
- [`SPEC_SOURCE_CONTRACT.md`](sagekit/resources/docs/agent/SPEC_SOURCE_CONTRACT.md)

## Contributing

Start with the focused checks for the surface you changed:

```bash
python -B -m scripts.run_tests focused --repository .
```

Additional unit, integration, source-repository, and package lanes are available
under `scripts.run_tests` when the change reaches those surfaces.

## Fit

SAGE-Kit is useful when:

- work spans many sessions, milestones, people, or agents;
- authority, scope, evidence, and completion must remain distinguishable;
- verification is expensive enough to require evidence reuse and resource
  coordination;
- accepted history must remain auditable without becoming current authority.

It is intentionally more structure than a short script or disposable prototype
usually needs.
