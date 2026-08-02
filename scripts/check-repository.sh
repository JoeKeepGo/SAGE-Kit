#!/bin/sh
set -eu

for path in README.md docs/SAGE_CORE.md docs/agent/AGENT_HARNESS.md \
  docs/agent/GOVERNANCE_LEVELS.md contracts/graph/v1/contract.json \
  contracts/graph/v1/graph.schema.json contracts/graph/v1/node-result.schema.json \
  contracts/canonical-authority-pointers.txt \
  skills/sage-kit/SKILL.md; do
  test -f "$path" || { printf 'missing required path: %s\n' "$path" >&2; exit 1; }
done

forbidden_files=$(git ls-files | grep -Ei '(^|/)(pyproject\.toml|setup\.py|setup\.cfg|requirements[^/]*\.txt|tox\.ini|noxfile\.py|package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock)$|\.(py|pyi|pyc|whl)$|\.egg-info/|(^|/)(bin|src)/(sagekit|sage-kit)(/|$)' || true)
test -z "$forbidden_files" || { printf 'forbidden runtime/CLI/package surface:\n%s\n' "$forbidden_files" >&2; exit 1; }

# Scan executable, workflow, host-launch, config, and setup surfaces, not
# ordinary governance prose. Exclude these two self-describing checks.
execution_surfaces=$(git ls-files | grep -E '(^\.github/workflows/|^\.claude/|^\.codex/|^scripts/|^tests/|^skills/[^/]+/agents/|^skills/[^/]+/references/[^/]+/(agents|hooks)/|(^|/)(Makefile|Dockerfile|compose[^/]*\.ya?ml|[^/]*(launch|runner|daemon|scheduler|setup|install)[^/]*\.(sh|ps1|bat|cmd|ya?ml|json|toml))$)' | grep -E '\.(sh|ps1|bash|zsh|fish|bat|cmd|js|mjs|cjs|ts|tsx|rs|go|java|cs|rb|php|ya?ml|json|toml|md)$|(^|/)(Makefile|Dockerfile)$' | grep -Ev '^scripts/check-repository\.(sh|ps1)$' || true)
if [ -n "$execution_surfaces" ]; then
  stale=$(git grep -n -I -E '(^|[;&|()]|run:|command:|exec:|shell:)[[:space:]]*(env[[:space:]]+)?(python([0-9.]*)?|pip([0-9.]*)?|pytest|unittest|sagekit[[:space:]]+(run|validate|check|candidate|checkpoint|resource|packet)|npm|npx|node)[[:space:]]' -- $execution_surfaces || true)
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

# Explicit canonical-authority pointer manifest only; ordinary links are not
# governance contracts.
test "$(sort -u contracts/canonical-authority-pointers.txt | wc -l | tr -d ' ')" = "$(wc -l < contracts/canonical-authority-pointers.txt | tr -d ' ')" || { printf 'duplicate canonical authority pointer\n' >&2; exit 1; }
manifest_pointers=$(sort contracts/canonical-authority-pointers.txt)
declared_pointers=$(git grep -n -E '^<a id="[^"]+"></a>' -- 'docs/*.md' | sed -E 's|^([^:]+):[0-9]+:<a id="([^"]+)"></a>.*$|\1#\2|' | sort)
test "$manifest_pointers" = "$declared_pointers" || { printf 'canonical authority pointer manifest mismatch\n' >&2; exit 1; }
while IFS= read -r reference || [ -n "$reference" ]; do
  test -n "$reference" || continue
  target=${reference%%#*}
  anchor=${reference#*#}
  test -f "$target" || { printf 'broken canonical pointer: %s\n' "$reference" >&2; exit 1; }
  grep -Fq "<a id=\"$anchor\"></a>" "$target" || { printf 'missing canonical anchor: %s\n' "$reference" >&2; exit 1; }
done < contracts/canonical-authority-pointers.txt

# Validate the active Graph manifest with stock-macOS shasum fallback. Legacy
# compatibility contracts are not part of default adoption.
sha256_file=''
if command -v sha256sum >/dev/null 2>&1; then sha256_file=sha256sum
elif command -v shasum >/dev/null 2>&1; then sha256_file='shasum -a 256'
fi
test -n "$sha256_file" || { printf 'Graph manifest digest check unavailable: sha256sum/shasum not found\n' >&2; exit 1; }
graph_value() {
  key=$1
  field=$2
  if command -v jq >/dev/null 2>&1; then
    jq -r ".resources.$key.$field" contracts/graph/v1/contract.json
  elif command -v plutil >/dev/null 2>&1; then
    plutil -extract "resources.$key.$field" raw -o - contracts/graph/v1/contract.json
  else
    awk -v section="\"$key\"" -v name="\"$field\"" '
      index($0, section) { active=1; next }
      active && index($0, name) {
        value=$0
        sub(/^[^:]*:[[:space:]]*"/, "", value)
        sub(/"[,[:space:]]*$/, "", value)
        print value
        exit
      }
      active && /^[[:space:]]*}[,]?[[:space:]]*$/ { exit }
    ' contracts/graph/v1/contract.json
  fi
}
for key in graph_schema node_result_schema; do
  resource=$(graph_value "$key" resource)
  declared=$(graph_value "$key" canonical_sha256)
  test -n "$resource" && test -n "$declared" || { printf 'Graph manifest extraction failed: %s\n' "$key" >&2; exit 1; }
  printf '%s\n' "$declared" | grep -Eq '^[0-9a-fA-F]{64}$' || { printf 'invalid Graph manifest digest: %s\n' "$key" >&2; exit 1; }
  test -f "contracts/graph/v1/$resource" || { printf 'missing Graph manifest resource: %s\n' "$resource" >&2; exit 1; }
  actual=$($sha256_file "contracts/graph/v1/$resource" | awk '{print $1}')
  test "$actual" = "$declared" || { printf 'Graph manifest digest mismatch: %s\n' "$resource" >&2; exit 1; }
done

if [ -n "${SAGEKIT_DIFF_BASE:-}" ]; then
  git diff --check "$SAGEKIT_DIFF_BASE...HEAD"
else
  git diff --check || printf 'local git diff hygiene warning (non-blocking without SAGEKIT_DIFF_BASE)\n' >&2
fi

printf 'repository integrity: PASS\n'
