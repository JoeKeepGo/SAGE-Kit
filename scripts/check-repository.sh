#!/usr/bin/env bash
set -euo pipefail

required=(
  README.md
  docs/SAGE_CORE.md
  docs/agent/AGENT_HARNESS.md
  docs/agent/EXECUTION_ECONOMY.md
  contracts/graph/v1/graph.schema.json
  contracts/graph/v1/node-result.schema.json
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

if command -v jq >/dev/null 2>&1; then
  while IFS= read -r path; do jq -e . "$path" >/dev/null; done < <(git ls-files '*.json')
fi

git diff --check
printf 'repository integrity: PASS\n'
