# Minimal local adoption example

Use this disposable project to map a small specification to an existing host.
Its [specification](SPEC.md), [bounded plan template](plan.template.json),
[host mapping template](host.template.json) and [fixed check](check.mjs) use the
existing SAGE-Kit APIs. This is example execution evidence, not a delivered
application or accepted product.

1. Copy this directory to a separate temporary project. Have the project owner
   explicitly authorize the bounded local round described in SPEC.md. Use Node
   22+ and an already installed adapter package; no dependency fetch is needed.
2. In that copy, choose a concrete ISO expiry within one hour, including
   milliseconds and `Z`. Run `node prepare.mjs <chosen-ISO-expiry>`, replacing the
   placeholder. The [setup script](prepare.mjs) creates `plan.json` and `host.json`
   without overwriting them. It resolves the current project directory, so no
   machine path or indefinite expiry is built into the templates. Use a new
   disposable copy for a new round; retain prior evidence until reviewed.
3. In an isolated host profile, point the existing MCP configuration at the
   installed `mcp.mjs` and the absolute filename of this copy's `host.json`.
   Configure the hooks from the adapter README's Codex/Claude section, matching
   the actual native tool names in `guardedTools`. Keep native permissions and
   the project's instructions. Do not change user defaults. Claude users choose
   `"host": "claude"` in their mapping before starting the round. The source
   repository's [adapter README](../../../adapters/README.md) contains the host
   configuration; examples are not included in the optional npm package.
4. Call `sage_inspect({})` and read its authority references. Only a fresh
   `sage_begin({"stepId":"greeting","attemptId":"greeting-1"})` with
   `replayed:false` permits starting these task effects. If resuming an existing
   attempt, inspect actual output and logs before recording its result.
5. Create `output/greeting.txt` as specified, then run the actual check and save
   its exit status. In a POSIX shell in this copy:

   ```sh
   mkdir -p evidence
   set -o noclobber
   node check.mjs > evidence/greeting-1.log 2>&1
   check_status=$?
   printf '%s\n' "$check_status" > evidence/greeting-1.exit
   cat evidence/greeting-1.log
   ```

   Do not pipe away the status or replace failed output with a passing assertion.
   Use a new evidence filename for each attempt. If the status is zero, call:

   ```json
   {"attemptId":"greeting-1","result":{"outcome":"passed","checks":[{"id":"greeting","passed":true,"evidence":"evidence/greeting-1.log"}]}}
   ```

   This is the argument to MCP `sage_finish`. On failure, report `outcome:failed`
   and `passed:false` with the actual log. Diagnose before a new admitted attempt;
   never edit the fixed check or overwrite evidence bound to a finished attempt.
6. Call `sage_inspect({})` again. The expected action is `human_gate` for
   `human_acceptance`. Stop and give the output, command status and evidence to
   the owner. Do not begin or pass that gate. After review, delete only this
   disposable copy to clean up the example's generated files.

`tests/project-mapping.test.mjs` in the source repository copies these files to a
temporary directory, prepares a short round, writes the actual greeting, runs
`node check.mjs`, binds its log via the shared host API and checks the human stop.
It cleans up the copy. That component test does not prove native host hook setup,
model understanding or human acceptance. Checks and hashes establish only their
observed scope; host/tool permissions and project authority remain necessary.
