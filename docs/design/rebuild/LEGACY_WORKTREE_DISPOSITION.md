# Legacy Worktree Disposition

Baseline: `f19ed5ce7af4a62f053ba11fd55c7dda5b21e34e`.

This integration preserves selected behavior from legacy worktrees without
directly merging any legacy branch.

## Port

- `LEG-TD-001` (`7f1926b`): reject duplicate mapping keys in JSON, PyYAML,
  and fallback YAML Task Dispatch inputs.
- `LEG-CP-002` (`c67be52`): require external checkpoint authority ID and
  version as a pair while retaining unanchored legacy resume.
- `LEG-CAND-001` (`1f32089`): close each candidate repository snapshot with
  one `rev-parse HEAD` sentinel and fail on drift without a second full scan.
- `LEG-HIST-001` (`27c15b1`): recheck the validation-scope manifest semantic
  digest at the end of explicit `history` or `all` audits.
- `LEG-SRC-001` (`27c15b1`): make tracked-file Git collection failures fail
  closed and skip runtime-path classification.
- `LEG-EE-001` (`5cdf4b8`): align C2 verification expectations with the
  canonical `contract-scoped` mode.

## Drop

- The legacy transition resolver in full.
- Legacy process runner, wheel changes, product CLI paths, and serial test
  graph.
- Mutable validation policy, contracts facade, full documentation discovery,
  CLI freeze, and dynamic fallback.
- Path-only C2 authority, global resume-authority requirements, CPU-test
  resource downgrade, old normalization, and full snapshot double scans.

## Defer

- C2 authority-record semantics and waiver provenance/output contracts.
- A public manifest-integrity field or full historical-byte scan.
- Compatibility aggregation, process-supervisor hardening, and Git fixture
  timeouts.
- Host apply-time stale-result revalidation.

This disposition does not resurrect a product CLI and does not modify any
consumer repository or Installed Skill.
