# Optional SAGE-Kit DSH adapter

This package adds native governance reminders and continuation tools to DSH
0.2.1-rc.2, with separately configured controlled RSI. The original governance
Skill works without this package. No CLI, daemon, model call, install script,
or task database is added. Explicit RSI tools can run fixed evaluation commands;
governance hooks never run those commands.

The package is private while reconstruction and acceptance are in progress.
Pack it locally with `npm pack ./adapters --ignore-scripts --pack-destination <directory>`
from the repository, then install that artifact into an isolated DSH environment
with the declared host peers. Do not change a user's default profile merely to
run tests. The package declares a DSH bundle which inserts a disabled
`sage-kit-dsh` entry. Select it in the profile's `dsh.profile.bundles`, then
enable it with an explicit project mapping in the profile's `cordis.patch.yml`:

```yaml
- id: sage-kit-dsh
  disabled: false
  config:
    projectRoot: /absolute/path/to/project
    planPath: planning/continuation.json
    statePath: local/continuation.json
    guardedTools: [write_file, shell]
    deadlineMs: 2000
    maxContextBytes: 16384
    remindEverySteps: 8
```

Use the actual tool names and configuration format of your installed profile.
The guarded list is exact: it does not inspect arbitrary shell paths or protect
unnamed tools. Existing DSH permissions and other plugin refusals remain in force.
The project controller selects the existing normative documents, admitted steps,
scope, evidence requirements, attempt limit and expiry in the continuation plan.
The repository protocol is `docs/rebuild/continuation.md`; the DSH contract and
acceptance scenarios are `docs/rebuild/dsh.md` (these docs are not part of this
optional package).

Native tools are `sage_inspect()`, `sage_begin({stepId, attemptId})`, and
`sage_finish({attemptId, result})`, where `result` is a JSON string containing the
outcome, check evidence and any required review. Only a new successful begin
establishes an in-memory execution marker for the current session. Replaying a
begin clears that marker. Recovery requires checking actual effects and recording
the result, not rerunning the old task. Check references and hashes do not prove
that a test ran, that a review was independent, or that a human accepted delivery.

Each model step refreshes bounded authority/state inputs. Full historical proof
checks occur at lifecycle boundaries and new admission; ordinary tool calls use
the current step's memory and do not scan disk. Reminders are deduplicated and
renewed after actual surface replacement. Governance failure rejects the step;
oversized context is never silently truncated. Cancellation is cooperative between
filesystem operations and cannot interrupt a single blocked kernel call.

The optional in-memory `sage/diagnostic` event reports operation, elapsed time,
logical input reads, injection bytes or error code. It contains no document text
and does not write metrics to disk. R1 limits apply per operation: 8 MiB/128 input
files and 4 MiB persisted state. There is no background polling or synchronous RSI.

From the source checkout, set `SAGE_DSH_NODE_MODULES` to an already installed DSH
0.2.1-rc.2 `node_modules`, then run `node --test tests/dsh.test.mjs`. These tests use
real host components and an in-process deterministic model double. They do not
call a provider, read credentials, or prove real-model development quality.

## Controlled RSI

To enable RSI, add `rsiPlanPath` and `rsiStatePath` to the explicit project config.
They must be distinct from the continuation plan and state. The project controller
prepares a plan like this; paths and the command must match the actual project:

```json
{
  "version": 1,
  "authority": ["docs/current-spec.md"],
  "inputs": ["drafts/strategy.txt", "eval/check.mjs"],
  "targets": ["drafts/strategy.txt"],
  "command": ["/absolute/path/to/node", "eval/check.mjs"],
  "expiresAt": "<explicit ISO expiry for this authorized round>",
  "revoked": false,
  "maxEvaluations": 2,
  "timeoutMs": 10000,
  "maxOutputBytes": 16384
}
```

`sage_rsi_propose({hypothesis, feedback, files})` takes JSON strings for evidence
references (`[{"path":"checks/failure.txt","kind":"failure"}]`) and candidate
replacements (`[{"path":"drafts/strategy.txt","content":"..."}]`). Feedback is
data. Only configured targets can change; fixed evaluation inputs, the evaluator
entry, and current continuation authority/plan/state are protected.

`sage_rsi_evaluate()` runs the same fixed command in two fresh bounded snapshots.
Both sides must preserve evaluation assets; the candidate must pass. Every round
has one immutable candidate and at most three evaluations. No dependency install,
provider call, automatic retry, or recurring job occurs. Environment credentials
are not inherited. The temporary directories are not an operating-system sandbox;
the configured command must already be authorized for local execution.

`sage_rsi_adopt()` and `sage_rsi_rollback()` each request a separate native DSH
one-time approval for the exact differences and evaluation. A working
`dsh-user-approval` service with a human answerer is required. Missing/rejected/
cancelled/unavailable approval never changes the targets. The tool rechecks all
bindings after the answer; there is no model-supplied approval parameter.

`sage_rsi_inspect()` reads the result; `sage_rsi_recover()` settles an interrupted
evaluation without rerunning it. Interrupted adoption requires inspecting actual
files and approving rollback; third-party edits are never overwritten. Preserve
old round state and choose new explicit paths for a revised candidate. Do not
delete a stale lock before confirming its writer is no longer active.

Each API call reads at most 8 MiB/128 file operations, including both evaluation
snapshots and rechecks. Candidate and recovery text are each limited to 256 KiB;
logs and command duration are bounded separately. RSI tools have a 180-second
host budget, separate from the short governance hook deadline. Windows evaluation
is explicitly unavailable until process-tree termination is verified. Full protocol
and evidence boundaries are in `docs/rebuild/rsi.md` in the source repository.
