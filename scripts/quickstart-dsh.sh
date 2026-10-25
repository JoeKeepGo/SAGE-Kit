#!/usr/bin/env bash
# SAGE-Kit self-use DSH quickstart (Linux/WSL2).
#
# End to end, on a clean machine with Node >=22, a DSH CLI, and a Linux pnpm >=10:
#   1. builds and packs this checkout (root `sage-kit` + `packages/dsh-plugin`);
#   2. creates a fresh, isolated DSH_HOME and profile, and installs both tarballs
#      with `dsh plugin --profile ... add` (peer warnings are expected: DSH
#      supplies its own @deepseek-ai/* packages at runtime);
#   3. asserts the composed profile config contains the sage-kit plugin layer;
#   4. initializes a fresh demo project with the *installed* CLI and runs
#      task create -> brief -> running -> review -> done (with evidence);
#   5. verifies the task JSON on disk and prints QUICKSTART PASS.
#
# Safety: the script only writes inside its own work directory
# (default: $HOME/.sage-kit-quickstart). It refuses to touch the default user
# DSH home ($HOME/.dsh / Windows %USERPROFILE%\.dsh), and it refuses to wipe a
# work directory it did not create (marker file `.sage-quickstart-workdir`).
#
# It does not call a model and needs no API key: the DSH profile install and the
# task lifecycle are both deterministic.
#
# Usage: scripts/quickstart-dsh.sh [--workdir <dir>] [--profile <name>]
#                                  [--keep] [--cleanup] [-h|--help]
# Environment: DSH_BIN, PNPM_BIN, SAGE_QUICKSTART_WORKDIR,
#              SAGE_QUICKSTART_PROFILE, SAGE_QUICKSTART_TIMEOUT (seconds, default 300)
# Exit codes: 0 pass, 1 step or environment failure, 2 bad usage.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
PLUGIN_DIR="$REPO_ROOT/packages/dsh-plugin"

PROFILE="${SAGE_QUICKSTART_PROFILE:-sage-kit-quickstart}"
WORKDIR="${SAGE_QUICKSTART_WORKDIR:-$HOME/.sage-kit-quickstart}"
CLEANUP=0
KEEP=0
STEP_TIMEOUT="${SAGE_QUICKSTART_TIMEOUT:-300}"

usage() {
  cat <<'USAGE'
Usage: scripts/quickstart-dsh.sh [--workdir <dir>] [--profile <name>]
                                 [--keep] [--cleanup] [-h|--help]

Builds and packs SAGE-Kit, installs root+plugin tarballs into a fresh isolated
DSH profile, initializes a demo project, and runs the task lifecycle
(create -> brief -> running -> review -> done with evidence).

  --workdir <dir>  work directory (default: $HOME/.sage-kit-quickstart)
  --profile <name> DSH profile name (default: sage-kit-quickstart)
  --keep           keep the work directory on success (default behaviour)
  --cleanup        remove the work directory after a successful run
  -h, --help       show this help

Requires: bash, node >=22, npm, a Linux/WSL DSH CLI (0.2.1-rc.2 validated),
and a Linux pnpm >=10. On WSL, a Windows pnpm on PATH makes `dsh plugin` panic;
set PNPM_BIN to a Linux pnpm (e.g. npm i --prefix ~/.local pnpm@10).
Environment: DSH_BIN, PNPM_BIN, SAGE_QUICKSTART_WORKDIR,
SAGE_QUICKSTART_PROFILE, SAGE_QUICKSTART_TIMEOUT.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --workdir)
      [ "$#" -ge 2 ] || { echo "quickstart: --workdir needs a value" >&2; exit 2; }
      WORKDIR="$2"; shift ;;
    --profile)
      [ "$#" -ge 2 ] || { echo "quickstart: --profile needs a value" >&2; exit 2; }
      PROFILE="$2"; shift ;;
    --keep) KEEP=1 ;;
    --cleanup) CLEANUP=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "quickstart: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done
[ "$KEEP" = "1" ] && CLEANUP=0

say()  { printf '\n==> %s\n' "$*"; }
note() { printf '    %s\n' "$*"; }
die()  { printf 'quickstart: ERROR: %s\n' "$*" >&2; exit 1; }

CURRENT_STEP="setup"
on_err() {
  local rc=$?
  printf '\nQUICKSTART FAILED at step: %s (exit %s)\n' "$CURRENT_STEP" "$rc" >&2
  printf 'quickstart: logs and partial state kept at: %s\n' "$WORKDIR" >&2
  exit "$rc"
}
trap on_err ERR

# A safe, idempotent work directory: wipe only our own marked directory.
prepare_workdir() {
  local real_home
  real_home="$(cd -- "$HOME" && pwd -P)"
  [ -n "$WORKDIR" ] || die "--workdir is empty"
  # Resolve `.`/`..` and existing symlink ancestors BEFORE any refusal check or
  # deletion. Otherwise `$HOME/./.dsh/x` or a symlinked parent could bypass the
  # raw-string checks and delete the real profile directory.
  if command -v realpath >/dev/null 2>&1; then
    WORKDIR="$(realpath -m -- "$WORKDIR")"
  else
    die "realpath is required to canonicalize --workdir before refusal/cleanup checks"
  fi
  # Canonicalize the protected profile location too; `.dsh` itself may be a
  # symlink to a directory with a different canonical path.
  local real_dsh
  real_dsh="$(realpath -m -- "$real_home/.dsh")"
  case "$WORKDIR" in
    "$real_dsh"|"$real_dsh/"*) die "refusing to touch the user's DSH profile: $WORKDIR" ;;
  esac
  case "$WORKDIR" in
    "/"|"$real_home"|"$real_home/"|"$REPO_ROOT"|"$REPO_ROOT/")
      die "refusing to use the filesystem root or the checkout itself as --workdir" ;;
    "$real_home/.dsh"|"$real_home/.dsh/"*|/mnt/c/Users/*/.dsh|/mnt/c/Users/*/.dsh/*|/mnt/[a-z]/Users/*/.dsh*)
      die "refusing to touch the user's DSH profile: $WORKDIR" ;;
  esac
  if [ -e "$WORKDIR" ]; then
    [ -f "$WORKDIR/.sage-quickstart-workdir" ] \
      || die "refusing to wipe existing directory without our marker: $WORKDIR (use a new --workdir)"
  fi
  rm -rf -- "$WORKDIR"
  mkdir -p -- "$WORKDIR/logs" "$WORKDIR/pack"
  : > "$WORKDIR/.sage-quickstart-workdir"
  WORKDIR="$(cd -- "$WORKDIR" && pwd -P)" || die "cannot resolve workdir"
  # The demo project lives under WORKDIR; an initialized ancestor would swallow it.
  probe="$(dirname -- "$WORKDIR")"
  while :; do
    [ -e "$probe/.sage-kit/config.json" ] \
      && die "ancestor is already a SAGE-Kit project: $probe; choose a clean --workdir"
    parent="$(dirname -- "$probe")"; [ "$parent" = "$probe" ] && break; probe="$parent"
  done
  export DSH_HOME="$WORKDIR/dsh-home"
  export SAGE_QUICKSTART_STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

show_log() { sed 's/^/    /' "$1"; }

run_logged() { # <logfile> <description> <command...>
  local log="$1" desc="$2"; shift 2
  printf '\n$ %s\n' "$*"
  if ! "$@" >"$log" 2>&1; then
    show_log "$log" >&2
    die "$desc failed (see $log)"
  fi
  show_log "$log"
}

run_bounded() { # <seconds> <logfile> <description> <command...>
  local seconds="$1" log="$2" desc="$3"; shift 3
  printf '\n$ %s\n' "$*"
  local rc=0
  if command -v timeout >/dev/null 2>&1; then
    timeout "$seconds" "$@" >"$log" 2>&1 || rc=$?
  else
    "$@" >"$log" 2>&1 || rc=$?
  fi
  show_log "$log"
  [ "$rc" -eq 0 ] || die "$desc failed (exit $rc; see $log)"
}

run_quiet() { # <seconds> <logfile> <description> <command...>; only prints the tail
  local seconds="$1" log="$2" desc="$3"; shift 3
  printf '\n$ %s\n' "$*"
  local rc=0
  if command -v timeout >/dev/null 2>&1; then
    timeout "$seconds" "$@" >"$log" 2>&1 || rc=$?
  else
    "$@" >"$log" 2>&1 || rc=$?
  fi
  if [ "$rc" -ne 0 ]; then show_log "$log" >&2; die "$desc failed (exit $rc; see $log)"; fi
  note "ok ($(wc -l < "$log") output lines, log: $log)"
  tail -3 "$log" | sed 's/^/    /'
}

# ---------------------------------------------------------------- prerequisites
CURRENT_STEP="prerequisites"
say "checking prerequisites"
command -v node >/dev/null 2>&1 || die "node not found"
command -v npm  >/dev/null 2>&1 || die "npm not found"
[ -f "$REPO_ROOT/package.json" ] || die "not a SAGE-Kit checkout: $REPO_ROOT"
[ -f "$PLUGIN_DIR/package.json" ] || die "missing plugin package: $PLUGIN_DIR"

node_major="$(node -p 'process.versions.node.split(".")[0]')"
[ "$node_major" -ge 22 ] || die "node >=22 required (found $(node --version))"

dsh_bin="${DSH_BIN:-$(command -v dsh || true)}"
[ -n "$dsh_bin" ] || die "dsh not found; set DSH_BIN or put dsh on PATH (validated: @deepseek-ai/dsh 0.2.1-rc.2)"
case "$dsh_bin" in /mnt/*) die "dsh resolves to a Windows binary ($dsh_bin); run this quickstart in WSL/Linux with a Linux DSH" ;; esac
case "$dsh_bin" in */*) [ -x "$dsh_bin" ] || die "dsh is not executable: $dsh_bin" ;; esac
dsh_version="$("$dsh_bin" --version 2>/dev/null | head -1 || true)"
[ -n "$dsh_version" ] || die "cannot run '$dsh_bin --version'"

pnpm_bin="${PNPM_BIN:-$(command -v pnpm || true)}"
[ -n "$pnpm_bin" ] || die "pnpm not found; set PNPM_BIN or install pnpm >=10 (dsh plugin forwards to pnpm)"
case "$pnpm_bin" in /mnt/*) die "pnpm resolves to a Windows binary ($pnpm_bin); install/point PNPM_BIN at a Linux pnpm >=10" ;; esac
pnpm_bin="$(readlink -f "$pnpm_bin" 2>/dev/null || printf '%s' "$pnpm_bin")"
case "$pnpm_bin" in /mnt/*) die "pnpm resolves to a Windows binary ($pnpm_bin)" ;; esac
pnpm_version="$("$pnpm_bin" --version 2>/dev/null | tail -1 || true)"
pnpm_major="${pnpm_version%%.*}"
case "$pnpm_major" in ''|*[!0-9]*) die "cannot read pnpm version (output: $pnpm_version)" ;; esac
[ "$pnpm_major" -ge 10 ] || die "pnpm >=10 required (found $pnpm_version)"

# `dsh plugin` spawns `pnpm` by name, so a PNPM_BIN that is not already on PATH
# needs a shim. Keep the shim inside the owned workdir and prepend it after the
# workdir exists.
prepare_workdir
mkdir -p -- "$WORKDIR/bin"
cat >"$WORKDIR/bin/pnpm" <<EOF
#!/bin/sh
exec "$pnpm_bin" "\$@"
EOF
chmod +x "$WORKDIR/bin/pnpm"
export PATH="$WORKDIR/bin:$PATH"
resolved_pnpm="$(command -v pnpm 2>/dev/null || true)"
case "$resolved_pnpm" in "$WORKDIR/bin/pnpm") ;; *) die "pnpm shim did not resolve first on PATH: ${resolved_pnpm:-<none>}" ;; esac
note "node:  $(node --version)"
note "npm:   $(npm --version)"
note "dsh:   $dsh_version ($dsh_bin)"
note "pnpm:  $pnpm_version ($pnpm_bin)"
note "repo:  $REPO_ROOT"
note "work:  $WORKDIR"
note "DSH_HOME: $DSH_HOME (isolated; user DSH profile untouched)"

# ------------------------------------------------------------------- build+pack
CURRENT_STEP="build"
say "building SAGE-Kit"
if [ ! -d "$REPO_ROOT/node_modules/typescript" ]; then
  note "dev dependencies missing; running npm ci"
  ( cd "$REPO_ROOT" && npm ci --no-audit --no-fund ) >"$WORKDIR/logs/npm-ci.log" 2>&1 \
    || { show_log "$WORKDIR/logs/npm-ci.log" >&2; die "npm ci failed"; }
fi
run_logged "$WORKDIR/logs/build.log" "npm run build" npm --prefix "$REPO_ROOT" run build
[ -f "$REPO_ROOT/dist/cli.js" ] || die "build did not produce dist/cli.js"
[ -f "$REPO_ROOT/dist/index.js" ] || die "build did not produce dist/index.js"

root_name="$(node -p 'require(process.argv[1]).name' "$REPO_ROOT/package.json")"
root_version="$(node -p 'require(process.argv[1]).version' "$REPO_ROOT/package.json")"
plugin_name="$(node -p 'require(process.argv[1]).name' "$PLUGIN_DIR/package.json")"
plugin_version="$(node -p 'require(process.argv[1]).version' "$PLUGIN_DIR/package.json")"

CURRENT_STEP="pack"
say "packing $root_name@$root_version and $plugin_name@$plugin_version"
( cd "$REPO_ROOT" && npm pack --pack-destination "$WORKDIR/pack" ) >"$WORKDIR/logs/pack-root.log" 2>&1 \
  || { show_log "$WORKDIR/logs/pack-root.log" >&2; die "npm pack failed for the root package"; }
( cd "$PLUGIN_DIR" && npm pack --pack-destination "$WORKDIR/pack" ) >"$WORKDIR/logs/pack-plugin.log" 2>&1 \
  || { show_log "$WORKDIR/logs/pack-plugin.log" >&2; die "npm pack failed for $plugin_name"; }
root_tgz="$WORKDIR/pack/${root_name}-${root_version}.tgz"
plugin_tgz="$WORKDIR/pack/${plugin_name}-${plugin_version}.tgz"
[ -f "$root_tgz" ] || die "expected tarball not found: $root_tgz"
[ -f "$plugin_tgz" ] || die "expected tarball not found: $plugin_tgz"
tar -tzf "$root_tgz" >"$WORKDIR/logs/root-tarball-files.txt"
grep -qxF 'package/dist/cli.js' "$WORKDIR/logs/root-tarball-files.txt" || die "root tarball is missing dist/cli.js"
tar -tzf "$plugin_tgz" >"$WORKDIR/logs/plugin-tarball-files.txt"
grep -qxF 'package/index.js' "$WORKDIR/logs/plugin-tarball-files.txt" || die "plugin tarball is missing index.js"
note "tarballs: $root_tgz"
note "          $plugin_tgz"
sha256sum "$root_tgz" "$plugin_tgz" | sed 's/^/    /'

# ------------------------------------------------------------- profile install
CURRENT_STEP="profile"
say "creating fresh isolated DSH profile '$PROFILE' (DSH_HOME=$DSH_HOME)"
profile_dir="$DSH_HOME/profiles/$PROFILE"
run_quiet 120 "$WORKDIR/logs/profile-init.log" "dsh --from-default-profile headless" \
  "$dsh_bin" --profile "$PROFILE" --from-default-profile headless --dump-config

say "installing $root_name (core CLI/library) into the profile"
run_bounded "$STEP_TIMEOUT" "$WORKDIR/logs/dsh-add-root.log" "dsh plugin add (root)" \
  "$dsh_bin" plugin --profile "$PROFILE" add "$root_tgz"
say "installing $plugin_name (DSH bundle) into the profile"
note "peer warnings are expected: DSH supplies @deepseek-ai/* at runtime"
run_bounded "$STEP_TIMEOUT" "$WORKDIR/logs/dsh-add-plugin.log" "dsh plugin add (plugin)" \
  "$dsh_bin" plugin --profile "$PROFILE" add "$plugin_tgz"

[ -f "$profile_dir/package.json" ] || die "profile manifest missing: $profile_dir/package.json"
cat >"$WORKDIR/logs/verify-profile.cjs" <<'NODE'
const fs = require("fs");
const [file, rootName, pluginName] = process.argv.slice(2);
const manifest = JSON.parse(fs.readFileSync(file, "utf8"));
const deps = manifest.dependencies ?? {};
for (const name of [rootName, pluginName]) {
  if (!deps[name]) throw new Error(`profile dependencies are missing ${name}`);
}
const bundles = manifest?.dsh?.profile?.bundles ?? [];
if (!bundles.includes(pluginName)) throw new Error(`profile bundles are missing ${pluginName}: ${bundles.join(", ")}`);
console.log(`profile dependencies include: ${rootName}, ${pluginName}`);
console.log(`profile bundles: ${bundles.join(", ")}`);
NODE
node "$WORKDIR/logs/verify-profile.cjs" "$profile_dir/package.json" "$root_name" "$plugin_name" \
  || die "installed profile manifest validation failed"

CURRENT_STEP="profile-config"
say "asserting the plugin layer in the composed profile config"
dump="$WORKDIR/logs/dump-config.yml"
"$dsh_bin" --profile "$PROFILE" --dump-config >"$dump" 2>"$WORKDIR/logs/dump-config.err" \
  || { show_log "$WORKDIR/logs/dump-config.err" >&2; die "dsh --dump-config failed"; }
grep -qxF -- "# == $plugin_name" "$dump" || die "--dump-config does not show the '# == $plugin_name' layer"
layer_block="$(grep -m1 -A4 -F -- "- id: $plugin_name" "$dump" || true)"
case "$layer_block" in
  *"name: $plugin_name"*) ;;
  *) die "--dump-config does not resolve the $plugin_name entry" ;;
esac
grep -m1 -A4 -F -- "# == $plugin_name" "$dump" | sed 's/^/    /'
installed_cli="$profile_dir/node_modules/$root_name/dist/cli.js"
[ -f "$installed_cli" ] || die "installed profile is missing $installed_cli"
installed_version="$(node "$installed_cli" version)" || die "installed CLI does not run"
[ "$installed_version" = "$root_version" ] || die "installed CLI reports $installed_version, expected $root_version"
note "installed CLI: $installed_cli ($installed_version)"

# --------------------------------------------------------------- demo project
CURRENT_STEP="demo-project"
DEMO="$WORKDIR/demo-project"
say "initializing fresh demo project: $DEMO"
# Refuse to init under an ancestor that is already a SAGE-Kit project.
probe="$DEMO"
while :; do
  [ -e "$probe/.sage-kit/config.json" ] && die "ancestor is already a SAGE-Kit project: $probe; use a clean --workdir"
  parent="$(dirname -- "$probe")"; [ "$parent" = "$probe" ] && break; probe="$parent"
done
rm -rf -- "$DEMO"; mkdir -p -- "$DEMO"
cd "$DEMO" || die "cannot enter $DEMO"
run_logged "$WORKDIR/logs/init.log" "sage-kit init" node "$installed_cli" init --host dsh --scope project --project-root "$DEMO"
cat >"$WORKDIR/logs/verify-project.cjs" <<'NODE'
const fs = require("fs");
const root = fs.realpathSync(process.argv[2]);
const config = JSON.parse(fs.readFileSync(`${root}/.sage-kit/config.json`, "utf8"));
if (config.projectRoot !== root) throw new Error(`config projectRoot ${config.projectRoot} != ${root}`);
console.log(`project root: ${config.projectRoot} (host=${config.host}, mode=${config.mode})`);
NODE
node "$WORKDIR/logs/verify-project.cjs" "$DEMO" || die "demo project was not initialized where expected"
run_quiet 120 "$WORKDIR/logs/doctor.json" "sage-kit doctor --json" node "$installed_cli" doctor --json
node -e 'const o=JSON.parse(require("fs").readFileSync(process.argv[1],"utf8")); if(!o.ok){console.error(JSON.stringify(o,null,2)); process.exit(1)}' \
  "$WORKDIR/logs/doctor.json" || die "doctor reported ok:false"
note "doctor ok:true"

# ------------------------------------------------------------- task lifecycle
CURRENT_STEP="task"
say "task create"
create_log="$WORKDIR/logs/task-create.log"
node "$installed_cli" task create \
  --title "Quickstart demo task" \
  --description "Created by scripts/quickstart-dsh.sh to prove the task lifecycle." \
  --acceptance "brief shows the task and acceptance criteria" \
  --acceptance "done records at least one evidence item" | tee "$create_log"
task_id="$(sed -n 's/^Created \([^:]*\):.*/\1/p' "$create_log")"
task_id="${task_id%%$'\n'*}"
[ -n "$task_id" ] || die "could not parse the task id from task create output"
[ -f "$DEMO/.sage-kit/state/tasks/$task_id.json" ] || die "task JSON not found: .sage-kit/state/tasks/$task_id.json"
note "task id: $task_id"

say "brief"
node "$installed_cli" brief --task "$task_id" --max-bytes 2048 | tee "$WORKDIR/logs/brief.txt"

say "status ready -> running"
node "$installed_cli" task status "$task_id" running --note "quickstart: work started" | tee "$WORKDIR/logs/status-running.txt"

say "status running -> review"
node "$installed_cli" task status "$task_id" review --note "quickstart: ready for review" | tee "$WORKDIR/logs/status-review.txt"

say "status review -> done (requires evidence)"
node "$installed_cli" task status "$task_id" done \
  --evidence "quickstart: create -> brief -> running -> review -> done executed by scripts/quickstart-dsh.sh" \
  --evidence "task show --json reports status=done with 2 evidence items" | tee "$WORKDIR/logs/status-done.txt"

CURRENT_STEP="verify"
say "task show --json"
node "$installed_cli" task show "$task_id" --json >"$WORKDIR/logs/task-show.json" 2>&1 \
  || { show_log "$WORKDIR/logs/task-show.json" >&2; die "task show failed"; }
show_log "$WORKDIR/logs/task-show.json"
cat >"$WORKDIR/logs/verify-task.cjs" <<'NODE'
const fs = require("fs");
const payload = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const task = payload.task ?? payload;
if (task.status !== "done") throw new Error(`expected status done, found ${task.status}`);
if (!Array.isArray(task.evidence) || task.evidence.length < 2) throw new Error("expected >=2 evidence items");
console.log(`verified: status=${task.status}, evidence items=${task.evidence.length}`);
NODE
node "$WORKDIR/logs/verify-task.cjs" "$WORKDIR/logs/task-show.json" \
  || die "task JSON did not reach status=done with evidence"

say "task list"
node "$installed_cli" task list | tee "$WORKDIR/logs/task-list.txt"

# --------------------------------------------------------------------- verdict
CURRENT_STEP="done"
say "quickstart summary"
note "profile:   $PROFILE (bundles include $plugin_name)"
note "demo:      $DEMO"
note "task file: $DEMO/.sage-kit/state/tasks/$task_id.json"
note "logs:      $WORKDIR/logs"
if [ "$CLEANUP" = "1" ]; then
  rm -rf -- "$WORKDIR"
  note "work directory removed (--cleanup)"
else
  note "work directory kept; remove later with: rm -rf -- '$WORKDIR'"
fi
printf '\nQUICKSTART PASS\n'
