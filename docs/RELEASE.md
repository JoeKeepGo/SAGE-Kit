# Releases

The rebuilt release line ships the portable governance Skill plus optional
host execution adapters. Governance alone needs no runtime. The adapters use
Node.js 22+ inside DSH or a host-owned MCP connection; there is no SAGE-Kit task
CLI, polling daemon, database service or separate model executor.

## Version and delivery identity

The first rebuilt preview targets **v0.3.0-alpha.1**. It is a GitHub prerelease,
not a stable or npm release. The earlier **v0.2.0-alpha.1** describes the archived
CLI/database architecture and must not be used as an installation guide for this
line. Existing releases and tags remain immutable.

| Delivered surface | Identity and use |
|---|---|
| GitHub source archive | The new release tag; contains current docs, examples, tests, adapters and the complete Skill |
| `skills/sage-kit/` within the archive | Unchanged governance component `v2026.8.13.1`; its manifest binds its own package identity and canonical-LF resource digests, not the whole rebuilt release |
| `sage-kit-dsh-plugin-0.3.0-alpha.1.tgz` | Optional private `@sage-kit/dsh-plugin` package; includes DSH and Codex/Claude MCP adapters, but not the Skill or examples |
| `SHA256SUMS` | SHA-256 of the attached adapter tgz; verify before installation |

Download the source archive for the complete Skill, docs and from-docset example.
Install the entire Skill directory through the host's Skill mechanism. For
execution support, follow [adapter installation](../adapters/README.md) using the
release tgz, or package the selected source checkout locally. `private: true`
deliberately prevents npm publication; it does not prevent local tgz installation.
Use an isolated profile first and retain the previous installed package/config
until the new version has passed its project-specific checks.

## Candidate verification and publication

1. Select an immutable candidate and version. Run repository integrity, portable
   Skill references, affected native-host and optional-adapter checks. Preserve
   the original governance component and required resources. Run the real-model
   trial against the installed candidate when that trial is part of the release
   claim; exact scope, interventions and remaining limits belong in
   [progress](rebuild/progress.md).
2. Pack the adapter with lifecycle scripts disabled, inspect the payload and
   install it offline into a fresh directory. Compare installed bytes with the
   candidate, including metadata, then verify MCP startup and the selected native
   host path. Freeze that tgz and calculate its digest. A changed payload needs
   affected revalidation; documentation-only evidence updates do not change it.
3. Obtain the required independent review and use the human-authorized submit
   scope. Merge to `main` and verify CI for that exact commit. Create a new tag
   reachable from `main`; the `v*` workflow also checks reachability and runs the
   five repository/adapter jobs. Do not move a published tag to fix a failure.
4. After the tag's required checks succeed, publish a GitHub **prerelease** with
   the frozen adapter tgz and `SHA256SUMS`. Record support versions, experiment
   limits, migration guidance and the tag/CI references. Verify the published
   asset digest against the locally verified candidate. No npm publication or
   production deployment is part of this procedure.

CI verifies continuation/RSI and installed DSH integration on Linux, plus static
repository/Skill checks on Linux, Windows and macOS. It does not establish native
agent operation on all three systems. A supported Hook denial is a guardrail for
the tested event path, not operating-system containment or universal tool coverage.
Product acceptance in projects using SAGE-Kit remains owned by those projects.
