# Migrating To The Governed Rebuild

The rebuilt release preserves the governance component from **v2026.8.13.1**
and adds optional continuation, hooks, RSI and platform-evidence adapters.
The new **v0.3.0-alpha.1** preview is distinct from the archived runtime in
**v0.2.0-alpha.1**. Existing tags keep their historical meaning. Do not rewrite
accepted project history or treat old runtime state as proof for the new adapter.

## From The Governance-Only Baseline

Existing governance-only use can continue without an additional runtime. Install
the complete `skills/sage-kit` directory; its retained `v2026.8.13.1` manifest
identifies that component, while the new source tag identifies the whole rebuild.
Keep project authority, risk-based review, evidence ownership and human acceptance.

For continuous execution, select the project's current documents and a bounded
round using the [from-docset guide](rebuild/from-docset.md). Install the optional
release tgz into an isolated location and explicitly configure the selected host
using the [adapter guide](../adapters/README.md). Preserve the user's existing
configuration; merge only the intended MCP/plugin and Hook entries. Test the real
tool names, refusal before `begin`, valid execution and recovery before relying
on the configuration. Manual RSI remains the default; automatic RSI requires a
separate trusted project-branch policy and fixed evaluation inputs.

## From The Archived Runtime Alpha

Stop only the old SAGE-Kit jobs/services you own, retain their configuration and
data for rollback, and remove their invocations from the selected project profile.
The following are **old-runtime** surfaces, not a ban on the new optional adapters:

## Remove From Consumer Automation

- old package installation and imports;
- old task CLI wrappers and command-specific configuration;
- candidate freezing, repository-wide artifact hashing, and framework
  checkpoints;
- framework process/resource management and leases;
- wheel build, install, and package smoke jobs;
- old runtime store, recovery, and resolver calls.

There is no automatic SQLite/task-store conversion. Reconcile unfinished effects
against Git, project files and real checks, then create a fresh bounded plan and
new continuation/RSI state paths. Do not copy old completed flags into new state.
Keep the archived data until its owner no longer needs it; migration does not
require deleting user data or uninstalling other projects' tools.

## Keep Or Adopt

- project-owned current authority and active SPEC;
- compact `ACTIVE_CONTEXT` handoff truth;
- milestone, wave, phase, and lane planning at the depth the product needs;
- project-native focused checks and CI;
- static contracts from `contracts/` where they add value;
- the optional Skill for model routing and host-specific guidance.

Replace former runtime calls with a direct model workflow: read authority and
SPEC, plan, edit, run project checks, review by risk, run required final CI once
per unchanged candidate, and
return evidence to the human acceptance owner.

Legacy runtime compatibility belongs to the old immutable release tag. The new
line ships no old-CLI compatibility executable. To roll back the installation,
close the new host connection and restore the previous package/profile. Reconcile
project changes separately; switching packages does not undo product work. For an
adopted RSI candidate, use its recorded rollback under the applicable approval or
preauthorization while the target still matches; do not overwrite third-party edits.

## Migrate From Explicit-Only Activation

The model-native line no longer requires `$sage-kit` in every prompt:

1. Install or reference the Skill once through the host's normal Skill
   mechanism.
2. Preflight the host version and configuration against its documented
   automatic instruction and Skill-discovery behavior. Then add the lightweight
   project entry from
   [`AGENTS_SAGE_BOOTSTRAP_TEMPLATE.md`](templates/AGENTS_SAGE_BOOTSTRAP_TEMPLATE.md)
   using the host's documented automatic instruction file. Claude Code uses a
   `CLAUDE.md` project instruction and may import the `AGENTS.md` bootstrap.
3. Let the project entry carry Light work, including Light review and
   mechanical corrective work. Load the complete Skill for materially semantic
   review or corrective work, Standard or Heavy work, and all acceptance or
   release work.
4. Keep explicit invocation as an override and diagnostic. Require it as the
   fallback whenever adoption, current authority, or required Skill content
   cannot be observed or resolved after preflight.

After activation, the first progress update reports the non-persistent
`SAGE_ACTIVE` routing marker. It is not execution, safety, permission, or
compliance proof and is not written to project documents, memory, receipts, or
ledgers. Governance activation alone adds no executable dependency. Optional
execution support is installed and configured separately; it does not change
project authority or authorize background scheduling, main merges or deployment.
