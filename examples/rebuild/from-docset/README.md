# Develop from an empty implementation

This example supplies a [docset](SPEC.md), [task mapping](plan.template.json),
[host mapping](host.template.json) and [fixed acceptance check](check.mjs).
It deliberately contains **no Task Lens implementation**. The existing Agent
must build the actual library, CLI, tests and product README from the docset.

1. Authorize a bounded local round in a new disposable directory. Copy `SPEC.md`,
   `check.mjs` and both JSON templates there. Do **not** copy this README as the
   product README. Initialize Git with `main`, commit these input files, then
   create `workflow/docset-demo`. This is setup in the disposable project only.
2. In that directory run Node 22+ with the absolute path to the existing
   [prepare helper](../minimal/prepare.mjs) and an explicit ISO expiry in the next
   hour. It creates `plan.json` and `host.json` without overwriting. No external
   dependencies are needed. Select `claude` in the host template when applicable.
3. Point an isolated existing host's MCP entry to the installed adapter and the
   absolute `host.json`; use the hooks and actual-tool-name preflight described
   in the [adapter guide](../../../adapters/README.md). Preserve native tool
   permissions. Read the [from-docset workflow](../../../docs/rebuild/from-docset.md)
   for authority selection, evidence, RSI and known host limits.
4. Ask the model to inspect, begin the admitted task, read SPEC.md, build the
   project, execute its fixed checks, save real immutable logs and finish. It
   should continue the three dependent tasks and stop at `human_acceptance`.
   Missing implementation must fail the check; do not weaken it to get a pass.
5. Independently run `node check.mjs all` and `node --test tests/*.test.mjs`, inspect
   the delivered CLI and README, and review evidence before human acceptance.
   Cleanup may remove only the disposable copy after evidence is retained.

The example does not enable automatic RSI itself: that is a separate optional
trusted project policy with its own targets, evaluator and budget. Tests of the
example's mapping are not real-model development evidence; actual R7 trial
results and limits are recorded in the source repository's progress document.
