# Host Resource Governance

This document defines the reusable execution boundary for adopted SAGE-Kit
projects. Milestone and phase manifests reference the versioned
`conservative-host-v1` profile instead of copying these rules.

## Runtime and leases

Host records use the current user's runtime location:

- Windows: `%LOCALAPPDATA%\SAGE-Kit\runtime`.
- macOS and Linux: `XDG_RUNTIME_DIR/sage-kit` when available; otherwise the
  current user's platform cache directory.

Git projects store claim records below the Git common directory at
`.git/sagekit/runtime`. Claim names keep `repo-write` scoped to the canonical
worktree identity, while `submit-exclusive` and Git index/commit/push mutation
remain scoped to the Git common directory. Non-Git projects use
`.sagekit/runtime`. These records are runtime state and must not be committed.

Each schema-v2 atomic lease record binds its ID, class,
host/project/worktree identities, run, controller, owner PID and
process-creation identity, nonce, timestamps, stage, authority digest,
permission mode, allowed classes, exclusive resources, claims, optional parent
lease, and only the SHA-256 of a delegation secret. The secret itself is held
by the Root controller and passed only to an explicitly delegated direct child.
Heartbeat and release verify the owner. Expired leases are reclaimed only when
the process probe proves the recorded instance dead or reused; an unknown probe
result remains occupied instead of being reclaimed.

The profile permits one host `cpu-heavy` claim, one host `package-build`
claim, one writer per worktree, and one Git-common-dir submit/index mutation.
Named runtime resources cover values such as a database or port. A
reasoning-only authority cannot start a local command. A normal descendant
cannot acquire a lease or start another managed command. Product-internal
delegation additionally verifies the private secret, direct parent PID,
reliable process-creation identity, workspace, authority, permission, and class
ceiling. On first use, the capability is atomically bound to that direct
child's PID and creation identity; unknown creation identity fails closed. A
delegated lease cannot delegate again, and delegation credentials are scrubbed
before it launches a managed child. Root-managed children receive no lease ID
or secret unless the Root explicitly names executable delegated classes.

On Windows, the trusted gated Job bootstrap is the physical direct child. It
verifies the parent lease and pre-binds the real target's PID and creation
identity before delegated reuse is accepted. Only that exact target identity is
accepted; its children cannot reuse or transfer the delegation capability.

## Workspace binding

Execution packet schema v2 binds the canonical repository, worktree and project
roots, Git common directory, branch, HEAD/base HEAD, permission, controller,
allowed/read-only/forbidden paths, and a SHA-256 binding digest.
`base_head` is signed compile-time provenance. Runtime verification rejects a
different bound `head`; it does not infer or enforce an ancestor relationship
from `base_head`.

Check the binding before execution:

```text
sagekit workspace verify --target <project> --packet <packet.json>
```

A different repository, worktree, branch, HEAD, Git common directory, or an
allowed path crossing a symlink/reparse point fails verification. Binding is
verified again after any lease wait and immediately before process launch, so
the lease and Workspace Binding must be valid together. `repo-write` supplies
the worktree writer claim; `submit-exclusive` also supplies the Git-common-dir
index/commit/push claim.

## Profiles and concurrency

- Light: Root only, one writer, and one local managed command.
- Standard: Root plus at most two active reasoning-only subagents, one writer,
  and one host CPU-heavy/package node.
- Heavy: Root plus at most four active reasoning-only/review subagents. At most
  two writers are allowed only in different worktrees with disjoint writable
  paths, an explicit integration owner, and no concurrent edits to main or
  shared integration files. Host CPU-heavy and package-build leases remain one.

Agents may analyze or edit independent files concurrently when their authority
allows it. Conflicting test/build nodes enter `WAITING_FOR_RESOURCE` and
continue automatically after lease release. Total historical subagent
invocations are not a blocking limit; active concurrency is. Do not dispatch
duplicate readers, duplicate tests, or unbounded descendant trees.

## Managed commands

The CLI exposes the lease lifecycle and one supervised command boundary:

```text
sagekit resource status --target <project>
sagekit resource acquire --target <project> --packet <packet.json> --class <class> --run-id <id>
sagekit resource heartbeat --target <project> --lease <lease-id>
sagekit resource release --target <project> --lease <lease-id>
sagekit resource run --target <project> --packet <packet.json> --class <class> --run-id <id> --timeout <seconds> -- <argv>
```

When a claim is occupied, the default bounded wait is 300 seconds. The runtime
emits `WAITING_FOR_RESOURCE` immediately and every 30 seconds, polls once per
second, continues automatically after release, and returns `HANDOFF_READY`
when the wait bound expires. Waiting is recorded separately from verification
and is not a test failure.

Commands use argv with `shell=False`. Child environments set the supported
thread hints to one and disable interactive Git prompts. Output pipes are
drained concurrently while only a bounded tail is retained.
The conservative policy stops a node when low-frequency sampling observes more
than 32 owned processes. This sampled guard is not a cgroup/PID hard limit.

Containment levels are explicit. `HARD` means the OS constrains the complete
launched process tree, including intentional or accidental descendants.
`MANAGED` means SAGE-Kit manages the normal process group/job and descendants
but cannot prove malicious escape impossible. `SOFT` means only command/agent
cooperation with `resource run` supplies the boundary. The conservative
profile requires at least `MANAGED`; a request for `HARD` is rejected before
target launch when the selected adapter cannot supply it.

On Windows, `windows-job-object-gated-v1` starts a trusted bootstrap that waits
for `GO`. The parent binds that bootstrap to a kill-on-close Job Object before
releasing it to launch the target argv. Binding failure never starts the target.
Descendants inherit the Job, and timeout terminates the Job and waits for zero
active processes. A successful gated run reports `HARD`.

On macOS and Linux, `posix-session-process-group-v1` starts the child in a new
session/process group. Cleanup
uses SIGTERM, a bounded grace period, SIGKILL when needed, and reap/wait. Linux
also enables subreaper behavior when the kernel call is available. A child can
deliberately call `setsid`, so the adapter reports `MANAGED`, not `HARD`.
Linux cgroup v2 and stronger macOS sandbox adapters are optional future `HARD`
adapters, not missing v1 gates. The current implementation does not impose
cgroup memory/PID limits or an FD hard limit.

Every `resource run` process result reports `containment_level`,
`containment_complete`, `cleanup_complete`, `orphan_check`, `platform_adapter`,
and `limitations`.

## Serial verification

The root verification controller is the only launcher for expensive local
nodes:

```text
python -B -m scripts.run_tests unit
python -B -m scripts.run_tests integration
python -B -m scripts.run_tests package
python -B -m scripts.run_tests final
```

`final` plans `focused -> unit -> integration -> source-repo -> package`.
Each node has one lease, one temp root, a stage, current-test heartbeat, timeout,
bounded output, metrics, process-tree cleanup, and release. The
`--waive-high-load` option records source-repo and package nodes as
`WAIVED`; it does not record them as passing.

## Enforcement boundary

Commands routed through the Windows gated adapter may receive `HARD` process
tree containment and POSIX process-group runs receive `MANAGED`. The broader
runtime interception guarantee remains `SOFT`: SAGE-Kit checks commands routed
through packet/workspace verification and `sagekit resource run`. It does not
intercept an agent, plugin, shell, or arbitrary child that bypasses that
boundary. Known mutation argv is rejected for read-only authority, but
arbitrary program behavior remains a soft guarantee and must also be controlled
by the host runtime and the root controller.
