#!/bin/sh
set -eu

for path in README.md docs/SAGE_CORE.md docs/agent/AGENT_HARNESS.md \
  docs/agent/GOVERNANCE_LEVELS.md contracts/graph/v1/contract.json \
  contracts/graph/v1/graph.schema.json contracts/graph/v1/node-result.schema.json \
  skills/sage-kit/SKILL.md; do
  test -f "$path" || { printf 'missing required path: %s\n' "$path" >&2; exit 1; }
done

forbidden_files=$(git ls-files | grep -Ei '(^|/)(pyproject\.toml|setup\.py|setup\.cfg|requirements[^/]*\.txt|tox\.ini|noxfile\.py|package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock)$|\.(py|pyi|pyc|whl)$|\.egg-info/|(^|/)(bin|src)/(sagekit|sage-kit)(/|$)' || true)
test -z "$forbidden_files" || { printf 'forbidden runtime/CLI/package surface:\n%s\n' "$forbidden_files" >&2; exit 1; }

# Scan only executable/workflow surfaces, not ordinary governance prose.
execution_surfaces=$(git ls-files '.github/workflows/*' 'tests/*')
if [ -n "$execution_surfaces" ]; then
  stale=$(git grep -n -I -E '(python([0-9.]*)?|pip([0-9.]*)?|pytest|unittest|sagekit[[:space:]]+(run|validate|check)|npm|npx|node)[[:space:]]' -- $execution_surfaces || true)
  test -z "$stale" || { printf 'forbidden runtime invocation:\n%s\n' "$stale" >&2; exit 1; }
fi

head -n 1 skills/sage-kit/SKILL.md | grep -qx -- '---'
grep -q '^name: sage-kit$' skills/sage-kit/SKILL.md
grep -q '^description:' skills/sage-kit/SKILL.md
grep -q 'No CLI, package runtime, daemon, or hidden validator is required' skills/sage-kit/SKILL.md

# JSON readability uses an already available native tool. Stock macOS has
# plutil; jq remains supported but is not required.
if command -v jq >/dev/null 2>&1; then
  for path in $(git ls-files '*.json'); do jq -e . "$path" >/dev/null; done
elif command -v plutil >/dev/null 2>&1; then
  for path in $(git ls-files '*.json'); do plutil -lint "$path" >/dev/null; done
else
  printf 'JSON parse check skipped: neither jq nor plutil is available\n' >&2
fi

# Explicit canonical-authority pointer manifest only.
for reference in \
  docs/SAGE_CORE.md#sage-completion-001 \
  docs/agent/GOVERNANCE_LEVELS.md#sage-auth-004 \
  docs/agent/GOVERNANCE_LEVELS.md#sage-auth-005 \
  docs/agent/GOVERNANCE_LEVELS.md#sage-auth-006 \
  docs/agent/GOVERNANCE_LEVELS.md#sage-auth-008 \
  docs/agent/AGENT_HARNESS.md#sage-auth-010; do
  target=${reference%%#*}
  anchor=${reference#*#}
  test -f "$target" || { printf 'broken canonical pointer: %s\n' "$reference" >&2; exit 1; }
  grep -Fq "<a id=\"$anchor\"></a>" "$target" || { printf 'missing canonical anchor: %s\n' "$reference" >&2; exit 1; }
done

# Validate the active Graph manifest with stock-macOS shasum fallback. Legacy
# compatibility contracts are not part of default adoption.
sha256_file=''
if command -v sha256sum >/dev/null 2>&1; then sha256_file=sha256sum
elif command -v shasum >/dev/null 2>&1; then sha256_file='shasum -a 256'
fi
if [ -n "$sha256_file" ]; then
  for key in graph_schema node_result_schema; do
    if command -v jq >/dev/null 2>&1; then
      resource=$(jq -r ".resources.$key.resource" contracts/graph/v1/contract.json)
      declared=$(jq -r ".resources.$key.canonical_sha256" contracts/graph/v1/contract.json)
    elif command -v plutil >/dev/null 2>&1; then
      resource=$(plutil -extract "resources.$key.resource" raw -o - contracts/graph/v1/contract.json)
      declared=$(plutil -extract "resources.$key.canonical_sha256" raw -o - contracts/graph/v1/contract.json)
    else
      resource=''
      declared=''
    fi
    if [ -n "$resource" ]; then
      actual=$($sha256_file "contracts/graph/v1/$resource" | awk '{print $1}')
      test "$actual" = "$declared" || { printf 'Graph manifest digest mismatch: %s\n' "$resource" >&2; exit 1; }
    fi
  done
else
  printf 'Graph manifest digest check skipped: sha256sum/shasum not found\n' >&2
fi

if [ -n "${SAGEKIT_DIFF_BASE:-}" ]; then
  git diff --check "$SAGEKIT_DIFF_BASE...HEAD"
else
  git diff --check || printf 'local git diff hygiene warning (non-blocking without SAGEKIT_DIFF_BASE)\n' >&2
fi

printf 'repository integrity: PASS\n'
