#!/usr/bin/env bash
# Plugin packaging smoke for SAGE-Kit and the DSH plugin package.
#
# What it proves, from a clean build:
#   1. the root `sage-kit` tarball ships the built CLI and library entry points;
#   2. the `packages/dsh-plugin` tarball ships its bundle patch and host entry;
#   3. both tarballs install together into a *fresh, isolated* DSH profile;
#   4. `dsh --profile <name> --dump-config` composes the sage-kit plugin layer.
#
# It does not boot a model run (that is task-16's real DSH E2E), so after DSH and
# pnpm are installed it is deterministic and needs no registry access: the two
# tarballs are local and the profile install resolves only them.
#
# Requirements: bash, node >=22, npm, pnpm >=10, and a DSH CLI (validated against
# @deepseek-ai/dsh 0.2.1-rc.2). pnpm 10 is required: a DSH profile keeps its
# package-manager settings in pnpm-workspace.yaml (`autoInstallPeers: false`),
# which pnpm 9 ignores; pnpm 9 then auto-installs the plugin's @deepseek-ai/*
# peers, whose internal packages are not published to npm.
#
# Environment variables:
#   DSH_BIN              dsh executable (default: `dsh` on PATH)
#   PNPM_BIN             pnpm executable (default: `pnpm` on PATH)
#   SAGE_SMOKE_WORKDIR   directory to use instead of a fresh mktemp dir
#   SAGE_SMOKE_KEEP=1    keep the work directory on success (logs, dump-config)
#   SAGE_SMOKE_TESTS=1   also run the repo's `npm test` (slow; CI runs it apart)
#   SAGE_SMOKE_TIMEOUT   seconds allowed for `dsh plugin add` (default: 300)
#   DSH_PROFILE          profile name to initialize (default: sage-kit-smoke)
#
# Usage: scripts/plugin-smoke.sh [--with-tests] [--keep] [--profile <name>]
#                                [--workdir <dir>] [-h|--help]
# Exit codes: 0 pass, 1 smoke or environment failure, 2 bad usage.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PLUGIN_DIR="$REPO_ROOT/packages/dsh-plugin"

KEEP="${SAGE_SMOKE_KEEP:-0}"
RUN_TESTS="${SAGE_SMOKE_TESTS:-0}"
PROFILE="${DSH_PROFILE:-sage-kit-smoke}"
REQUIRE_DSH_SECONDS="${SAGE_SMOKE_TIMEOUT:-300}"
WORKDIR_ARG="${SAGE_SMOKE_WORKDIR:-}"

usage() {
  cat <<'USAGE'
Usage: scripts/plugin-smoke.sh [--with-tests] [--keep] [--profile <name>]
                               [--workdir <dir>] [-h|--help]

Builds the root package, packs sage-kit and packages/dsh-plugin, installs both
into a fresh isolated DSH profile, and asserts --dump-config composes the
sage-kit plugin layer.

Requires node >=22, npm, pnpm >=10, and a DSH CLI (validated against
@deepseek-ai/dsh 0.2.1-rc.2).

Environment: DSH_BIN, PNPM_BIN, SAGE_SMOKE_WORKDIR, SAGE_SMOKE_KEEP=1,
SAGE_SMOKE_TESTS=1, SAGE_SMOKE_TIMEOUT, DSH_PROFILE.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --with-tests) RUN_TESTS=1 ;;
    --keep) KEEP=1 ;;
    --profile)
      [ "$#" -ge 2 ] || { echo "plugin-smoke: --profile needs a value" >&2; exit 2; }
      PROFILE="$2"
      shift
      ;;
    --workdir)
      [ "$#" -ge 2 ] || { echo "plugin-smoke: --workdir needs a value" >&2; exit 2; }
      WORKDIR_ARG="$2"
      shift
      ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "plugin-smoke: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

step() { printf '\n==> %s\n' "$*"; }
die() {
  printf 'plugin-smoke: ERROR: %s\n' "$*" >&2
  exit 1
}

if [ -n "$WORKDIR_ARG" ]; then
  work="$WORKDIR_ARG"
  mkdir -p "$work"
  KEEP=1
else
  work="$(mktemp -d "${TMPDIR:-/tmp}/sage-kit-plugin-smoke.XXXXXX")"
fi
logs="$work/logs"
mkdir -p "$logs" "$work/pack"

# A failed run always keeps its logs; a passing run cleans up unless asked.
cleanup() {
  local rc=$?
  trap - EXIT
  if [ "$KEEP" = "1" ] || [ "$rc" -ne 0 ]; then
    printf 'plugin-smoke: work directory kept: %s\n' "$work"
  else
    rm -rf "$work"
  fi
  exit "$rc"
}
trap cleanup EXIT

run_bounded() {
  local seconds="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$seconds" "$@"
  else
    "$@"
  fi
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

# Read a dotted string field from a package.json (empty when absent).
pkg_field() {
  node -e '
    const fs = require("fs");
    const [file, dotted] = process.argv.slice(1);
    let value = JSON.parse(fs.readFileSync(file, "utf8"));
    for (const key of dotted.split(".")) value = value == null ? undefined : value[key];
    process.stdout.write(typeof value === "string" ? value : "");
  ' "$1" "$2"
}

step "checking prerequisites"
command -v node >/dev/null 2>&1 || die "node is required"
command -v npm >/dev/null 2>&1 || die "npm is required"
[ -f "$REPO_ROOT/package.json" ] || die "run from a SAGE-Kit checkout (missing $REPO_ROOT/package.json)"
[ -f "$PLUGIN_DIR/package.json" ] || die "missing plugin package at $PLUGIN_DIR"

node_major="$(node -p 'process.versions.node.split(".")[0]')"
[ "$node_major" -ge 22 ] || die "node >=22 required (found $(node --version))"

dsh_bin="${DSH_BIN:-}"
if [ -z "$dsh_bin" ]; then
  dsh_bin="$(command -v dsh || true)"
fi
[ -n "$dsh_bin" ] || die "dsh not found: set DSH_BIN or put dsh on PATH (CI installs @deepseek-ai/dsh@0.2.1-rc.2)"
case "$dsh_bin" in
  /mnt/*) die "dsh resolves to a Windows binary ($dsh_bin); run this smoke in WSL/Linux with a Linux DSH install" ;;
esac
dsh_version="$("$dsh_bin" --version 2>/dev/null | head -1 || true)"
[ -n "$dsh_version" ] || die "failed to run '$dsh_bin --version'"

pnpm_bin="${PNPM_BIN:-}"
if [ -z "$pnpm_bin" ]; then
  pnpm_bin="$(command -v pnpm || true)"
fi
[ -n "$pnpm_bin" ] || die "pnpm not found: set PNPM_BIN or put pnpm on PATH (dsh plugin forwards to pnpm)"
case "$pnpm_bin" in
  /*) ;;
  *) pnpm_bin="$(command -v "$pnpm_bin" || true)" ;;
esac
[ -n "$pnpm_bin" ] || die "cannot resolve the pnpm executable (PNPM_BIN=$pnpm_bin)"
case "$pnpm_bin" in
  /mnt/*) die "pnpm resolves to a Windows binary ($pnpm_bin); install a Linux pnpm (npm i --prefix <dir> pnpm@10) and set PNPM_BIN" ;;
esac
# `dsh plugin` runs pnpm itself (execa resolves the bare name from PATH), so the
# validated binary must also be the one its child process finds. Without this a
# WSL host with a Windows pnpm later on PATH panics inside pnpm.
pnpm_dir="$(cd -- "$(dirname -- "$pnpm_bin")" && pwd)"
export PATH="$pnpm_dir:$PATH"
resolved_pnpm="$(command -v pnpm || true)"
case "$resolved_pnpm" in
  /mnt/*) die "PATH resolves pnpm to a Windows binary ($resolved_pnpm) ahead of $pnpm_bin; put the Linux pnpm first or set PNPM_BIN" ;;
esac
pnpm_version="$("$pnpm_bin" --version 2>/dev/null | tail -1 || true)"
pnpm_major="${pnpm_version%%.*}"
case "$pnpm_major" in
  ''|*[!0-9]*) die "could not read pnpm version from '$pnpm_bin --version' (output: $pnpm_version)" ;;
esac
if [ "$pnpm_major" -lt 10 ]; then
  die "pnpm >=10 required (found $pnpm_version): DSH profiles configure pnpm in pnpm-workspace.yaml, which pnpm 9 ignores; pnpm 9 auto-installs unpublished @deepseek-ai/* peers and fails"
fi

printf 'node: %s\nnpm:  %s\ndsh:  %s (%s)\npnpm: %s (%s)\nrepo: %s\nwork: %s\n' \
  "$(node --version)" "$(npm --version)" "$dsh_version" "$dsh_bin" "$pnpm_version" "$pnpm_bin" "$REPO_ROOT" "$work"

if [ ! -d "$REPO_ROOT/node_modules/typescript" ]; then
  step "installing dev dependencies"
  ( cd "$REPO_ROOT" && npm ci --no-audit --no-fund ) || die "npm ci failed"
fi

step "building root package"
( cd "$REPO_ROOT" && npm run build ) || die "npm run build failed"
[ -f "$REPO_ROOT/dist/index.js" ] || die "build did not produce dist/index.js (library export)"
[ -f "$REPO_ROOT/dist/cli.js" ] || die "build did not produce dist/cli.js (bin entry)"

root_name="$(pkg_field "$REPO_ROOT/package.json" name)"
root_version="$(pkg_field "$REPO_ROOT/package.json" version)"
plugin_name="$(pkg_field "$PLUGIN_DIR/package.json" name)"
plugin_version="$(pkg_field "$PLUGIN_DIR/package.json" version)"
[ -n "$root_name" ] && [ -n "$root_version" ] || die "cannot read name/version from root package.json"
[ -n "$plugin_name" ] && [ -n "$plugin_version" ] || die "cannot read name/version from $PLUGIN_DIR/package.json"

plugin_patch="$(pkg_field "$PLUGIN_DIR/package.json" dsh.bundle.patch)"
plugin_patch="${plugin_patch#./}"
[ -n "$plugin_patch" ] || die "$plugin_name does not declare dsh.bundle.patch; a DSH plugin must declare its bundle layer"
plugin_dsh_range="$(pkg_field "$PLUGIN_DIR/package.json" engines.dsh)"
[ -n "$plugin_dsh_range" ] || die "$plugin_name does not declare engines.dsh; compatibility with the host cannot be enforced"
plugin_root_requirement="$(node -e '
  const fs = require("fs");
  const manifest = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
  const requirements = { ...(manifest.dependencies ?? {}), ...(manifest.peerDependencies ?? {}) };
  process.stdout.write(requirements[process.argv[2]] ?? "");
' "$PLUGIN_DIR/package.json" "$root_name")"
[ -n "$plugin_root_requirement" ] || die "$plugin_name does not declare a dependency/peer on $root_name; the plugin would not receive the core library"

step "packing $root_name@$root_version"
( cd "$REPO_ROOT" && npm pack --pack-destination "$work/pack" ) >"$logs/pack-root.log" 2>&1 \
  || { cat "$logs/pack-root.log" >&2; die "npm pack failed for the root package"; }
root_tarball="$work/pack/${root_name}-${root_version}.tgz"
[ -f "$root_tarball" ] || die "expected tarball not found: $root_tarball"

step "packing $plugin_name@$plugin_version"
( cd "$PLUGIN_DIR" && npm pack --pack-destination "$work/pack" ) >"$logs/pack-plugin.log" 2>&1 \
  || { cat "$logs/pack-plugin.log" >&2; die "npm pack failed for $PLUGIN_DIR"; }
plugin_tarball="$work/pack/${plugin_name}-${plugin_version}.tgz"
[ -f "$plugin_tarball" ] || die "expected tarball not found: $plugin_tarball"

tar -tzf "$root_tarball" | sed 's:^package/::' | sort >"$logs/root-tarball-files.txt"
for required in package.json dist/cli.js dist/index.js "skills/sage-kit/SKILL.md"; do
  grep -qxF "$required" "$logs/root-tarball-files.txt" \
    || die "root tarball is missing $required"
done
forbidden_root='^(tests|reports|work|src|node_modules|scripts|\.github|\.git|\.sage-kit|packages)/'
if grep -qE "$forbidden_root" "$logs/root-tarball-files.txt"; then
  grep -E "$forbidden_root" "$logs/root-tarball-files.txt" >&2
  die "root tarball contains non-shipped paths (see list above)"
fi

tar -tzf "$plugin_tarball" | sed 's:^package/::' | sort >"$logs/plugin-tarball-files.txt"
for required in package.json index.js "$plugin_patch"; do
  grep -qxF "$required" "$logs/plugin-tarball-files.txt" \
    || die "plugin tarball is missing $required"
done
forbidden_plugin='^(tests|reports|work|src|node_modules|\.github|\.git|\.sage-kit)/'
if grep -qE "$forbidden_plugin" "$logs/plugin-tarball-files.txt"; then
  grep -E "$forbidden_plugin" "$logs/plugin-tarball-files.txt" >&2
  die "plugin tarball contains non-shipped paths (see list above)"
fi

root_sha256="$(sha256_of "$root_tarball")"
plugin_sha256="$(sha256_of "$plugin_tarball")"

export DSH_HOME="$work/dsh-home"
profile_dir="$DSH_HOME/profiles/$PROFILE"

step "installing root tarball into fresh DSH profile '$PROFILE'"
root_add_log="$logs/dsh-add-root.log"
# A DSH profile is a pnpm workspace root. pnpm 10 accepts a root add directly;
# pnpm 9 needed -w but is rejected above for ignoring the profile's workspace
# settings. Adding the two tarballs one at a time is the documented install path.
if ! run_bounded "$REQUIRE_DSH_SECONDS" "$dsh_bin" plugin --profile "$PROFILE" add \
  "$root_tarball" >"$root_add_log" 2>&1; then
  cat "$root_add_log" >&2
  die "dsh plugin add failed for $root_name (log: $root_add_log)"
fi
printf 'dsh plugin add %s: OK\n' "$root_name"

step "installing plugin tarball into profile '$PROFILE'"
plugin_add_log="$logs/dsh-add-plugin.log"
if ! run_bounded "$REQUIRE_DSH_SECONDS" "$dsh_bin" plugin --profile "$PROFILE" add \
  "$plugin_tarball" >"$plugin_add_log" 2>&1; then
  cat "$plugin_add_log" >&2
  die "dsh plugin add failed for $plugin_name (log: $plugin_add_log)"
fi
# Peer warnings are expected: the DSH host supplies @deepseek-ai/* peers, and the
# profile deliberately keeps autoInstallPeers=false. The same applies to the
# "sage-kit declares no dsh.bundle" notice from the first add: the core package is
# a plain library dependency of the plugin, not itself a profile layer.
printf 'dsh plugin add %s: OK\n' "$plugin_name"

step "checking the installed profile manifest"
[ -f "$profile_dir/package.json" ] || die "profile manifest missing: $profile_dir/package.json"
node -e '
  const fs = require("fs");
  const [file, rootName, pluginName] = process.argv.slice(1);
  const manifest = JSON.parse(fs.readFileSync(file, "utf8"));
  const dependencies = manifest.dependencies ?? {};
  for (const name of [rootName, pluginName]) {
    if (!dependencies[name]) throw new Error(`profile dependencies are missing ${name}`);
  }
  const bundles = manifest?.dsh?.profile?.bundles ?? [];
  if (!bundles.includes(pluginName)) {
    throw new Error(`profile dsh.profile.bundles is missing ${pluginName}: ${bundles.join(", ") || "none"}`);
  }
  console.log(`profile dependencies: ${rootName}, ${pluginName}`);
  console.log(`profile bundles: ${bundles.join(", ")}`);
' "$profile_dir/package.json" "$root_name" "$plugin_name" || die "installed profile manifest failed validation"

[ -f "$profile_dir/node_modules/$root_name/dist/index.js" ] \
  || die "installed profile is missing $root_name/dist/index.js"
[ -f "$profile_dir/node_modules/$plugin_name/index.js" ] \
  || die "installed profile is missing $plugin_name/index.js"

installed_version="$(node "$profile_dir/node_modules/$root_name/dist/cli.js" version)" \
  || die "the installed root tarball's CLI does not run"
[ "$installed_version" = "$root_version" ] \
  || die "installed CLI reports version '$installed_version', expected '$root_version'"

step "asserting the sage-kit layer in the composed profile config"
dump="$logs/dump-config.yml"
"$dsh_bin" --profile "$PROFILE" --dump-config >"$dump" 2>"$logs/dump-config.err" \
  || { cat "$logs/dump-config.err" >&2; die "dsh --dump-config failed for profile '$PROFILE'"; }
grep -qxF -- "# == $plugin_name" "$dump" \
  || die "--dump-config does not show the '# == $plugin_name' bundle layer"
grep -A2 -F -- "- id: $plugin_name" "$dump" | grep -qF -- "name: $plugin_name" \
  || die "--dump-config layer '$plugin_name' does not resolve its entry name"
layer_line="$(grep -n -F -- "# == $plugin_name" "$dump" | head -1 | cut -d: -f1)"
{
  printf '%s\n' '--- composed layer (from dump-config) ---'
  sed -n "${layer_line},$((layer_line + 7))p" "$dump"
} | tee "$logs/sage-kit-layer.txt"

if [ "$RUN_TESTS" = "1" ]; then
  step "running npm test"
  ( cd "$REPO_ROOT" && npm test ) || die "npm test failed"
fi

step "summary"
printf 'dsh             %s (%s)\n' "$dsh_version" "$dsh_bin"
printf 'pnpm            %s (%s)\n' "$pnpm_version" "$pnpm_bin"
printf 'plugin engine   %s\n' "$plugin_dsh_range"
printf 'profile         %s\n' "$profile_dir"
printf 'root tarball    %s\n  sha256 %s\n' "$root_tarball" "$root_sha256"
printf 'plugin tarball  %s\n  sha256 %s\n' "$plugin_tarball" "$plugin_sha256"
printf '\nPLUGIN SMOKE PASSED\n'
