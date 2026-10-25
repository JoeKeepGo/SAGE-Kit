# SAGE-Kit quickstart for DSH (Linux/WSL2)

`scripts/quickstart-dsh.sh` is a self-contained, deterministic smoke test of the whole
self-use path: it builds this checkout, packs it, installs into a **fresh isolated DSH
profile**, initializes a **fresh demo project**, and drives one task through
`create -> brief -> running -> review -> done` with evidence. It prints every command and
its output, and ends with a single marker:

```
QUICKSTART PASS
```

Nothing is committed, published, or written to the user's DSH profile. The script is
idempotent: re-running it recreates only its own marked work directory.

## Prerequisites

- Linux or WSL2 (Windows-native, macOS: **not supported/tested**; the script refuses `/mnt/*` binaries).
- Node.js >= 22 and npm (used for `npm run build` / `npm pack` in the checkout).
- A Linux DSH CLI. Validated with **DSH 0.2.1-rc.2**; other versions are untested.
- A Linux pnpm >= 10, required by `dsh plugin add` for bundle installs.

WSL note: the default Windows `pnpm` panics with `current dir is an absolute path with
drive letter`. If that happens, install a Linux pnpm and point the script at it:

```sh
npm install --prefix ~/.local pnpm@10
export PNPM_BIN="$HOME/.local/node_modules/.bin/pnpm"
```

## Run it

From the repository root (Linux path, e.g. under WSL):

```sh
cd /path/to/SAGE-Kit
DSH_BIN=/path/to/dsh PNPM_BIN=/path/to/pnpm scripts/quickstart-dsh.sh
```

`DSH_BIN` / `PNPM_BIN` are only needed when the right binaries are not on `PATH`.
Options:

| Flag / env | Default | Meaning |
| --- | --- | --- |
| `--workdir <dir>` / `SAGE_QUICKSTART_WORKDIR` | `$HOME/.sage-kit-quickstart` | All scratch state, logs, profile and demo project |
| `--profile <name>` / `SAGE_QUICKSTART_PROFILE` | `sage-kit-quickstart` | DSH profile created inside the isolated `DSH_HOME` |
| `--cleanup` | keep | Remove the work directory after a successful run |
| `--keep` | default | Keep the work directory (logs, profile, demo project) for inspection |
| `SAGE_QUICKSTART_TIMEOUT` | `300` | Per-step timeout in seconds |

The script refuses work directories it cannot safely own and never touches
`$HOME/.dsh` (or any Windows user's `.dsh`). It also refuses a work directory below an
already initialized SAGE-Kit project.

## Expected output

Abridged from a real WSL2 run (Node 22.22.1, npm 9.2.0, DSH 0.2.1-rc.2, pnpm 12.15.0):

```
==> checking prerequisites
    node:  v22.22.1
    dsh:   0.2.1-rc.2 (.../node_modules/.bin/dsh)
    work:  /home/<user>/.sage-kit-quickstart
    DSH_HOME: /home/<user>/.sage-kit-quickstart/dsh-home (isolated; user DSH profile untouched)
==> building SAGE-Kit
==> packing sage-kit@<version> and sage-kit-dsh@<version>
==> creating fresh isolated DSH profile 'sage-kit-quickstart'
==> installing sage-kit (core CLI/library) into the profile
==> installing sage-kit-dsh (DSH bundle) into the profile
profile bundles: @deepseek-ai/dsh-base, @deepseek-ai/dsh-headless, sage-kit-dsh
==> asserting the plugin layer in the composed profile config
==> initializing fresh demo project: /home/<user>/.sage-kit-quickstart/demo-project
==> task create
    task id: task-<timestamp>-<rand>
==> brief
==> status ready -> running
task-<id>: running
==> status running -> review
task-<id>: review
==> status review -> done (requires evidence)
task-<id>: done
==> task show --json
verified: status=done, evidence items=2
==> task list
==> quickstart summary
QUICKSTART PASS
```

Any failed step exits non-zero with `quickstart: ERROR: ...` or
`QUICKSTART FAILED at step: <step>`; logs remain under `<workdir>/logs/`.

## What it writes

| Path | Content |
| --- | --- |
| `<workdir>/pack/` | `npm pack` tarballs of the core CLI and the DSH plugin |
| `<workdir>/dsh-home/profiles/<profile>/` | Isolated DSH profile (`DSH_HOME` is redirected here) |
| `<workdir>/demo-project/` | Fresh demo project initialized with `--host dsh --scope project` |
| `<workdir>/logs/` | Per-command transcripts, verification scripts/results, doctor JSON |
| `$HOME/.dsh` | **Never touched** (all DSH state goes to the isolated `DSH_HOME`; the script refuses workdirs inside it) |

## Cleanup

```sh
scripts/quickstart-dsh.sh --cleanup   # remove workdir after a PASS
rm -rf "$HOME/.sage-kit-quickstart"   # or remove it manually
```

To start fully fresh without running: delete the work directory; it only ever wipes a
directory carrying its own `.sage-quickstart-workdir` marker.

## Failure handling

| Symptom | Fix |
| --- | --- |
| `ERROR: pnpm resolves to a Windows binary` | Install a Linux pnpm and set `PNPM_BIN` (see above) |
| `ERROR: dsh is not executable` / dsh not found | Set `DSH_BIN` to the Linux DSH CLI binary |
| `ERROR: node >= 22 is required` | Upgrade Node.js in WSL/Linux |
| `ERROR: refusing to touch the user's DSH profile` | Choose another `--workdir` |
| `ERROR: ancestor is already a SAGE-Kit project` | Pick a workdir outside any SAGE-Kit project |
| `ERROR: refusing to wipe existing directory without our marker` | Use a new `--workdir` or remove that directory yourself |
| `QUICKSTART FAILED at step: ...` | Read `<workdir>/logs/*.log`; the work directory is kept |

`pnpm` may print peer-dependency warnings for `@deepseek-ai/*` packages missing from the
plugin tarball; DSH resolves those at runtime, so they are expected noise and not a
failure. The script still succeeds only after asserting the profile, project, task file,
task list and doctor output.

## Untested boundaries

- Windows-native and macOS execution; only Linux/WSL2 was run.
- DSH versions other than 0.2.1-rc.2.
- `dsh web` / GUI sessions and real-model prompts: this quickstart is deliberately
  deterministic and model-free (plugin headless E2E with a real model is covered
  separately in `reports/plugin/dsh-plugin-e2e.md`).
- Installs from a package registry (the script packs and installs local tarballs only).

Validated on 2026-10-25 in WSL2 Ubuntu 26.04.1 against this checkout; PASS runs used both
the default work directory and `--cleanup`, plus a repeated idempotency run.
