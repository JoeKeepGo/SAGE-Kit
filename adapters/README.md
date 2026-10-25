# Optional SAGE-Kit DSH adapter

This package adds native governance reminders and continuation tools to DSH
0.2.1-rc.2. The original governance Skill works without this package. No CLI,
daemon, model call, install script, or task database is added.

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
