# Optional SAGE-Kit host adapters

This package adds governance reminders and continuation tools to DSH, Codex and
Claude Code, with separately configured manual or preauthorized automatic RSI. The original governance
Skill works without this package. There is no task CLI, polling daemon, model
call, install script, or task database. DSH runs in its existing host; Codex and
Claude own one optional stdio MCP process per connection, plus a startup-only
reminder helper. Explicit RSI tools can run fixed evaluation commands; governance
hooks never run those commands. The package keeps its original DSH package name.

The package is private while reconstruction and acceptance are in progress.
For a first local project, the source checkout includes
`examples/rebuild/minimal/README.md`: a specification, expiring bounded plan,
host mapping, actual file check and evidence-to-human-gate walkthrough. Copy it
to a disposable project and select an explicit authorization and expiry. It uses
the existing MCP tools; it does not install a host or alter default settings.
The examples live in the source repository and are not shipped in this package.
For development from a docset without any implementation, use
`examples/rebuild/from-docset/README.md`. Its three admitted tasks build a real
library, CLI and tests; initial files contain specification, mapping and fixed
acceptance only. `docs/rebuild/from-docset.md` describes the general workflow.

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

In the default manual mode, `sage_rsi_adopt()` and `sage_rsi_rollback()` each request a separate native DSH
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

### Preauthorized project-branch automation

An owner may approve one bounded automatic policy in the trusted host mapping:

```json
{
  "rsiAutomaticPolicy": {
    "branch": "workflow/project-dev",
    "baseBranch": "main",
    "planSha256": "<SHA-256 of the exact approved RSI plan bytes>",
    "maxRounds": 3,
    "improvement": { "kind": "repair" }
  }
}
```

Keep `rsiPlanPath`/`rsiStatePath`. The plan fixes targets, authority, evaluator and
expiry. Include custom host/configuration files in authority; standard root
AGENTS/CLAUDE files, `.codex/`, `.claude/`, `.dsh/`, `.mcp.json`, root Cordis patch
files and the loaded adapter files/metadata are protected automatically. These
paths are safeguards, not discovery of every custom configuration location.

`repair` requires a valid failing baseline and passing candidate. Alternatively
use `{"kind":"metric","name":"score","direction":"increase","minDelta":1}`
(`decrease` is supported). Both evaluations must succeed and stdout must be one
JSON object such as `{"metrics":{"score":42}}`; the fixed rule measures the
minimum improvement. Put diagnostics on stderr. No model-supplied approval field
or changed evaluator can authorize a candidate.

In this mode `sage_rsi_evaluate` adopts an improved candidate and reruns the same
check in the actual project directory. Failure rolls back this round's known
target files while the policy remains valid. Conflicting edits or changed
authority/branch/HEAD/expiry require reconciliation, not overwriting. The fixed
command must be approved for safe repeated execution; temporary snapshots and
postchecks are not an OS sandbox or a rollback of arbitrary external effects.

`sage_rsi_adopt` is hidden. `sage_rsi_observe` explicitly reruns the postcheck and
may roll back; at most three later observations per round. `sage_rsi_rollback`
can restore a settled adoption under the same policy. Unknown interrupted writes
cannot be blindly retried or converted to manual state. Receipts identify the
preauthorized policy, not a fresh human approval; no approval service is needed.

Propose the next immutable candidate using the same state after a settled round.
At most three rounds, with two consecutive failures/regressions stopping the
window. Normal product commits may occur between rounds on the same branch and
baseline ancestry; frozen non-target inputs and last target contents must remain
unchanged. Git queries occur only in explicit RSI operations, never in hooks or
inspect (32 commands per API, each at most 2 seconds/4 KiB). There is no polling,
automatic commit, main merge, push, deployment, release or product acceptance.
Without this optional policy, manual behavior remains unchanged.

## Codex and Claude Code

The tested Linux versions and actual evidence are recorded in the repository's
`docs/rebuild/progress.md`. Configure an isolated profile first. Do not copy these
example paths literally or merge settings into a user's default profile without
their instruction. Node 22+ runs the installed files without DSH peer imports.
Install the local tgz with `--ignore-scripts --legacy-peer-deps` when using only
the MCP adapters. No provider credentials are needed by these adapters.

Create an explicit JSON mapping (absolute filename passed to the adapter):

```json
{
  "host": "codex",
  "projectRoot": "/absolute/project",
  "planPath": "governance/continuation.json",
  "statePath": "local/continuation.json",
  "guardedTools": ["Bash", "exec_command", "Write", "Edit", "apply_patch"],
  "deadlineMs": 2000,
  "maxContextBytes": 12000
}
```

Use `"host":"claude"` for Claude. Optional `rsiPlanPath` and `rsiStatePath` have
the same meaning as DSH. Keep project instructions, active authority and any
custom hook/configuration files in the selected authority set. Standard root
AGENTS/CLAUDE instructions, Codex/Claude settings, the MCP mapping and the loaded
adapter modules are protected RSI targets automatically when inside the project.
One connection has one execution owner; do not share it across concurrent writers
or assume a parent's execution marker grants authority to subagents.

Codex MCP configuration:

```toml
[mcp_servers.sage]
command = "/absolute/node"
args = ["/absolute/installed-package/mcp.mjs", "/absolute/mapping.json"]
startup_timeout_sec = 10
tool_timeout_sec = 180
```

Claude MCP configuration:

```json
{"mcpServers":{"sage":{"command":"/absolute/node","args":["/absolute/installed-package/mcp.mjs","/absolute/mapping.json"]}}}
```

Merge these hooks into the selected host's hook settings, following its current
trust/configuration workflow. The startup helper is intentionally absent from
per-tool hooks. MCP hooks reuse the connected process; no new CLI is started.

```json
{
  "hooks": {
    "SessionStart": [{"matcher":"^(startup|resume|clear|fork)$","hooks":[{
      "type":"command",
      "command":"'/absolute/node' '/absolute/installed-package/hook.mjs' '/absolute/mapping.json'",
      "timeout":5
    }]},{"matcher":"^compact$","hooks":[{
      "type":"mcp_tool","server":"sage","tool":"sage_hook","timeout":5,
      "input":{"event":{"hook_event_name":"SessionStart","source":"${source}","session_id":"${session_id}","cwd":"${cwd}"}}
    }]}],
    "UserPromptSubmit": [{"hooks":[{
      "type":"mcp_tool","server":"sage","tool":"sage_hook","timeout":5,
      "input":{"event":{"hook_event_name":"UserPromptSubmit","session_id":"${session_id}","cwd":"${cwd}"}}
    }]}],
    "PreToolUse": [{"matcher":"Bash|exec_command|Write|Edit|apply_patch","hooks":[{
      "type":"mcp_tool","server":"sage","tool":"sage_hook","timeout":5,
      "input":{"event":{"hook_event_name":"PreToolUse","session_id":"${session_id}","cwd":"${cwd}","tool_name":"${tool_name}"}}
    }]}],
    "Stop": [{"hooks":[{
      "type":"mcp_tool","server":"sage","tool":"sage_hook","timeout":5,
      "input":{"event":{"hook_event_name":"Stop","session_id":"${session_id}","cwd":"${cwd}","stop_hook_active":"${stop_hook_active}"}}
    }]}]
  }
}
```

These are local POSIX examples, not Windows command quoting. Native hook schemas
and versions must be verified: [Codex](https://learn.chatgpt.com/docs/hooks),
[Claude](https://code.claude.com/docs/en/hooks). Startup can precede MCP readiness,
so a bounded command helper provides the initial reminder. UserPromptSubmit
refreshes it through MCP; a compact event uses the existing MCP connection to
retain its execution marker. Actual compaction/recovery support is reported per
host separately from synthetic event tests. A command helper cannot retain an
execution marker.

MCP `sage_finish.result`, RSI `feedback` and `files` are JSON objects/arrays (DSH
uses JSON strings). Missing required evidence fails. Fresh begins acquire only
an in-memory marker; replay, connection restart and errors invalidate it. Hook
success returns no permission override. Stop may request one continuation for
admitted or unreconciled work; a repeated Stop returns a handoff message. The
state remains pending until evidence and human acceptance actually exist.

Native tools outside the exact guarded list, missing/disabled hooks, connection
failures and host hook errors can bypass this mechanical check. These hooks are
not isolation. Internal hook failures return a normal denial where the event
supports it; native permissions and project authority still apply. Keep the
governance Skill/project instructions and use `sage_inspect` if reminders fail.

Manual RSI adoption/rollback request a form elicitation from the connected host. Only
its explicit `accept` plus boolean `approve:true` can approve the bound challenge;
missing capabilities, cancellation, protocol errors and rejection cannot. The
host must route this question to a human, never an automatic answerer. Unit
protocol answerers prove wiring only; native human approval is a separate check.

Input lines are capped at 1 MiB, pending requests at 16, output/backpressure at
2 MiB, mapping input at 64 KiB. Operations are serialized; cancellation and
elicitation responses are processed while an operation waits. Per continuation
read phase: 8 MiB/128 files; a changed ordinary hook may do an observe then inspect
phase (at most 16 MiB/256 reads). Lifecycle reads use one phase. Idle does no work,
no-change reads do not write state, and RSI has its separate 180-second budget.
Host timeouts should exceed adapter deadlines. A blocked kernel IO call cannot be
interrupted by the cooperative deadline. EOF cancels work and closes the process.
The byte cap belongs to this adapter; hosts have their own context limits and may
spill or truncate larger hook output. Keep the mapped round below the host's
verified limit, or reduce `maxContextBytes` (for example 2000). Read the referenced
authority through normal tools; reminder delivery is not proof that every rule
was read or understood. Native tests cover compact bounded reminders only.

## Explicit GitHub / Gitea evidence

Optional `forge` configuration enables `sage_forge_capture` in DSH and the shared
Codex/Claude MCP host. The same `openForgeEvidence` API is exported as `./forge`.
Hooks, continuation inspection and RSI evaluation never fetch platform data.
Add this object to the host mapping (or DSH plugin configuration):

```json
{
  "forge": {
    "directory": ".sage-evidence/forge",
    "sources": {
      "origin": {
        "provider": "github",
        "apiBase": "https://api.github.com",
        "repo": "OWNER/REPO",
        "tokenEnv": "SAGE_FORGE_TOKEN"
      },
      "local": {
        "provider": "gitea",
        "apiBase": "http://127.0.0.1:3000/api/v1",
        "repo": "OWNER/TEST_REPO",
        "tokenEnv": "SAGE_GITEA_TOKEN"
      }
    }
  }
}
```

Supply credentials in the selected host's environment, never in model arguments
or configuration values. `tokenEnv` may be omitted for public reads. Existing
`gh` login is not discovered or executed automatically. HTTP is allowed only for
explicit loopback instances; other endpoints require HTTPS. Redirects are refused.
The evidence directory must be separate from authority, control, evaluation and
adapter files; it and its descendants are protected against RSI modifications.

Issue request: `{"source":"origin","kind":"issue","id":26}`. A run request also
requires `expectedSha`, `workflowPath` and `requiredJobs` (an array of exact job
names). Use the exact observed API `path`: GitHub commonly returns
`.github/workflows/ci.yml`; the tested Gitea returns
`local-check.yml@refs/heads/main`. Do not infer a merge SHA from a PR number.

The result contains a relative `path`, SHA-256, assessment and resource counters.
Issue snapshots are `FEEDBACK`, not approval. Run `PASS` requires the expected
commit/path, a stable run attempt, complete job pagination, all jobs successful
and every required job present without ambiguity. Failure, skipped/queued work,
missing or unbound jobs cannot pass. Only this run at observation time is assessed;
other or later runs, branch protection, artifacts and deployments are not checked.
Recollect relevant facts at a validation/resume boundary instead of relying on
historical green runs. Workflow metadata does not prove what code its commands
actually checked out, tested or deployed.

Use the receipt `path` as a normal `sage_finish` check evidence file, with the
actual outcome, or in `sage_rsi_propose.feedback`. The existing finish API binds
bytes and caller assertions; it does not authenticate arbitrary local JSON or
override review/acceptance. Receipts retain untrusted Issue text but the tool
response does not inject that text into governance. No Issue comments or PR
reviews are collected in this version.

Captures have a separate 30-second deadline, 16 requests, 4 MiB total response
budget, 1 MiB per response/receipt and 500 jobs. There is no retry or poll loop.
Unknown/inconsistent data and incomplete pagination fail explicitly; failed
collection does not publish a partial receipt. Each observation is a create-only
content-addressed snapshot, not a mutable latest-status database. Ordinary hooks
retain their existing deadlines. The filesystem checks reject symlinks but are
not an OS sandbox against a concurrent hostile local writer.
