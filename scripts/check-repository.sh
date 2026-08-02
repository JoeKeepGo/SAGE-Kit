#!/usr/bin/env bash
set -euo pipefail

required=(
  README.md
  docs/SAGE_CORE.md
  docs/agent/AGENT_HARNESS.md
  docs/agent/EXECUTION_ECONOMY.md
  contracts/graph/v1/contract.json
  contracts/graph/v1/graph.schema.json
  contracts/graph/v1/node-result.schema.json
  contracts/task-dispatch-v2/policy.json
  skills/sage-kit/SKILL.md
)

for path in "${required[@]}"; do
  test -f "$path" || { printf 'missing required path: %s\n' "$path" >&2; exit 1; }
done

forbidden_files="$(git ls-files | grep -Ei '(^|/)(pyproject\.toml|setup\.py|setup\.cfg|requirements[^/]*\.txt|tox\.ini|noxfile\.py)$|\.(py|pyi|pyc|whl)$|\.egg-info/' || true)"
test -z "$forbidden_files" || { printf 'forbidden Python surface:\n%s\n' "$forbidden_files" >&2; exit 1; }

forbidden_invocations="$(git grep -n -Ei '(^|[^[:alnum:]_])(-m[[:space:]]+(sagekit|scripts\.run_tests)|pip([0-9.]*)?[[:space:]]+install|pytest|unittest|\.venv|sagekit/resources)' -- ':!docs/MIGRATION_MODEL_NATIVE.md' ':!scripts/check-repository.sh' ':!scripts/check-repository.ps1' || true)"
test -z "$forbidden_invocations" || { printf 'stale executable/runtime reference:\n%s\n' "$forbidden_invocations" >&2; exit 1; }

head -n 1 skills/sage-kit/SKILL.md | grep -qx -- '---'
grep -q '^name: sage-kit$' skills/sage-kit/SKILL.md
grep -q '^description:' skills/sage-kit/SKILL.md
grep -q 'No CLI, package runtime, daemon, or hidden validator is required' skills/sage-kit/SKILL.md

command -v jq >/dev/null 2>&1 || { printf 'jq is required for repository integrity\n' >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { printf 'sha256sum is required for repository integrity\n' >&2; exit 1; }

while IFS= read -r path; do jq -e . "$path" >/dev/null; done < <(git ls-files '*.json')

assert_canonical_digest() {
  local manifest="$1" resource="$2" declared="$3" base actual
  resource="${resource%$'\r'}"
  declared="${declared%$'\r'}"
  [[ "$declared" =~ ^[0-9a-f]{64}$ ]] || {
    printf 'invalid declared SHA-256 in %s: %s\n' "$manifest" "$resource" >&2
    exit 1
  }
  base="$(dirname "$manifest")"
  test -f "$base/$resource" || {
    printf 'missing manifest resource in %s: %s\n' "$manifest" "$resource" >&2
    exit 1
  }
  actual="$(sha256sum "$base/$resource" | awk '{print $1}')"
  test "$actual" = "$declared" || {
    printf 'manifest digest mismatch in %s: %s declared=%s actual=%s\n' \
      "$manifest" "$resource" "$declared" "$actual" >&2
    exit 1
  }
}

task_policy='contracts/task-dispatch-v2/policy.json'
while IFS=$'\t' read -r resource digest; do
  assert_canonical_digest "$task_policy" "$resource" "$digest"
done < <(jq -r '.schema_files[] as $resource | [$resource, .schema_sha256[$resource]] | @tsv' "$task_policy")

graph_manifest='contracts/graph/v1/contract.json'
while IFS=$'\t' read -r resource digest; do
  assert_canonical_digest "$graph_manifest" "$resource" "$digest"
done < <(jq -r '.resources[] | [.resource, .canonical_sha256] | @tsv' "$graph_manifest")

# Canonical authority references use explicit local anchors. Check only the
# narrow docs/<path>.md#<anchor> form rather than crawling general links.
while IFS= read -r source; do
  while IFS= read -r reference; do
    test -n "$reference" || continue
    target="${reference%%#*}"
    anchor="${reference#*#}"
    test -f "$target" || {
      printf 'broken canonical authority reference in %s: %s\n' "$source" "$reference" >&2
      exit 1
    }
    grep -Fq "<a id=\"$anchor\"></a>" "$target" || {
      printf 'missing canonical authority anchor in %s: %s\n' "$source" "$reference" >&2
      exit 1
    }
  done < <(grep -Eo 'docs/[A-Za-z0-9_./-]+\.md#[A-Za-z0-9_.:-]+' "$source" | sort -u || true)
done < <(git ls-files '*.md' '*.yaml' '*.yml')

git diff --check
printf 'repository integrity: PASS\n'
