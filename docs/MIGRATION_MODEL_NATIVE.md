# Migrating To The Model-Native Release Line

This release line removes the former executable package and command surface.
Existing tags remain immutable and continue to document their historical
behavior. Do not rewrite accepted project history to imitate the new model.

## Remove From Consumer Automation

- package installation and imports;
- command wrappers and command-specific configuration;
- candidate freezing, repository-wide artifact hashing, and framework
  checkpoints;
- framework process/resource management and leases;
- wheel build, install, and package smoke jobs;
- framework runtime store, recovery, and resolver calls.

## Keep Or Adopt

- project-owned current authority and active SPEC;
- compact `ACTIVE_CONTEXT` handoff truth;
- milestone, wave, phase, and lane planning at the depth the product needs;
- project-native focused checks and CI;
- static contracts from `contracts/` where they add value;
- the optional Skill for model routing and host-specific guidance.

Replace former runtime calls with a direct model workflow: read authority and
SPEC, plan, edit, run project checks, review by risk, run final CI once, and
return evidence to the human acceptance owner.

Legacy runtime compatibility belongs to the old immutable release tag. The new
line intentionally ships no compatibility executable.
