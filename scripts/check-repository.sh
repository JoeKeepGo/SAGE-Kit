#!/bin/sh
set -eu

# R-003 permits this exact optional host package, never a core Skill dependency.
unexpected_adapters=$(git ls-files adapters/ | grep -Ev '^adapters/(continuation\.mjs|dsh\.mjs|rsi\.mjs|rsi-process\.mjs|agent-host\.mjs|mcp\.mjs|hook\.mjs|package\.json|cordis\.patch\.yml|README\.md|LICENSE)$' || true)
test -z "$unexpected_adapters" || { printf 'unreviewed optional adapter: %s\n' "$unexpected_adapters" >&2; exit 1; }

for path in AGENTS.md README.md docs/SAGE_CORE.md docs/agent/AGENT_HARNESS.md \
  docs/agent/CLAIM_EVIDENCE_TRUST.md docs/agent/GOVERNANCE_LEVELS.md \
  docs/templates/AGENTS_SAGE_BOOTSTRAP_TEMPLATE.md \
  contracts/canonical-authority-pointers.txt \
  contracts/graph/v1/contract.json contracts/graph/v1/graph.schema.json \
  contracts/graph/v1/node-result.schema.json \
  contracts/release-resource-inventory.txt \
  contracts/task-dispatch-v2/policy.json \
  contracts/task-dispatch-v2/task.schema.json \
  contracts/task-dispatch-v2/evidence.schema.json \
  skills/sage-kit/SKILL.md skills/sage-kit/skill-manifest.json \
  skills/sage-kit/agents/openai.yaml; do
  test -f "$path" || { printf 'missing required path: %s\n' "$path" >&2; exit 1; }
done

entrypoints=$(git ls-files | grep -Ei '(^|/)(bin|src)/(sagekit|sage-kit)(/|$)|(^|/)(sagekit|sage-kit)(\.(sh|ps1|bash|zsh|fish|bat|cmd|exe|py|js|mjs|cjs|ts|tsx|rs|go|java|cs|rb|php))?$' || true)
test -z "$entrypoints" || { printf 'forbidden shipped runtime or entrypoint surface:\n%s\n' "$entrypoints" >&2; exit 1; }
package_manifests=$(git ls-files | grep -Ei '(^|/)(pyproject\.toml|setup\.py|setup\.cfg|requirements[^/]*\.txt|tox\.ini|noxfile\.py|Pipfile|poetry\.lock|uv\.lock|package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?|deno\.json|Cargo\.toml|Cargo\.lock|go\.mod|go\.sum|pom\.xml|build\.gradle(\.kts)?|settings\.gradle(\.kts)?|Gemfile|Gemfile\.lock|composer\.json|composer\.lock|mix\.exs|rebar\.config|pubspec\.yaml|Package\.swift|[^/]+\.(csproj|fsproj|vbproj))$' | grep -Ev '^(docs|tests|scripts|\.github)/|^adapters/package\.json$' || true)
test -z "$package_manifests" || { printf 'forbidden shipped executable dependency surface:\n%s\n' "$package_manifests" >&2; exit 1; }

# Package and interpreter tooling is permitted for docs, tests, and release
# work. This scans only shipped execution surfaces for SAGE-Kit runtime entry
# points or attempts to install/invoke SAGE-Kit as an executable dependency.
execution_surfaces=$(git ls-files | grep -E '(^\.github/workflows/|^\.claude/|^\.codex/|^scripts/|^skills/[^/]+/agents/|^skills/[^/]+/references/[^/]+/(agents|hooks)/)' | grep -E '\.(sh|ps1|bash|zsh|fish|bat|cmd|js|mjs|cjs|ts|tsx|rs|go|java|cs|rb|php|ya?ml|json|toml|md)$' | grep -Ev '^scripts/check-repository\.(sh|ps1)$' || true)
if [ -n "$execution_surfaces" ]; then
  runtime_pattern='(^|[;&|()]|run:|command:|exec:|shell:)[[:space:]]*(env[[:space:]]+)?((sagekit|sage-kit)[[:space:]]+(run|validate|check|candidate|checkpoint|resource|packet)|python([0-9.]*)?[[:space:]]+-m[[:space:]]+(sagekit|sage_kit)|pip([0-9.]*)?[[:space:]]+install.*(sagekit|sage-kit)|npm[[:space:]]+(install|exec).*(sagekit|sage-kit)|npx[[:space:]]+(sagekit|sage-kit)|cargo[[:space:]]+install.*(sagekit|sage-kit)|go[[:space:]]+install.*(sagekit|sage-kit)|dotnet[[:space:]]+tool[[:space:]]+install.*(sagekit|sage-kit)|gem[[:space:]]+install.*(sagekit|sage-kit)|composer[[:space:]]+require.*(sagekit|sage-kit))'
  stale=$(git grep -n -I -E "$runtime_pattern" -- $execution_surfaces || true)
  test -z "$stale" || { printf 'forbidden SAGE-Kit runtime invocation or executable dependency:\n%s\n' "$stale" >&2; exit 1; }
fi

skill_path=skills/sage-kit/SKILL.md
agent_manifest=skills/sage-kit/agents/openai.yaml
skill_frontmatter=$(awk '
  NR == 1 { line = $0; sub(/\r$/, "", line); if (line != "---") exit 1; next }
  { line = $0; sub(/\r$/, "", line); if (line == "---") { found = 1; exit }; print line }
  END { if (!found) exit 1 }
' "$skill_path") || { printf 'invalid Skill frontmatter\n' >&2; exit 1; }
skill_name_entries=$(printf '%s\n' "$skill_frontmatter" | grep -E '^name:' || true)
skill_name_count=$(printf '%s\n' "$skill_name_entries" | sed '/^$/d' | wc -l | tr -d ' ')
test "$skill_name_count" -eq 1 && printf '%s\n' "$skill_name_entries" | grep -Eq '^name:[[:space:]]*sage-kit[[:space:]]*$' || { printf 'Skill name must appear exactly once with value sage-kit\n' >&2; exit 1; }
skill_description_entries=$(printf '%s\n' "$skill_frontmatter" | grep -E '^description:' || true)
skill_description_count=$(printf '%s\n' "$skill_description_entries" | sed '/^$/d' | wc -l | tr -d ' ')
test "$skill_description_count" -eq 1 && printf '%s\n' "$skill_description_entries" | grep -Eq '^description:[[:space:]]*[^[:space:]]' || { printf 'Skill description must appear exactly once with a value\n' >&2; exit 1; }
model_invocation_entries=$(printf '%s\n' "$skill_frontmatter" | grep -E '^disable-model-invocation:' || true)
model_invocation_count=$(printf '%s\n' "$model_invocation_entries" | sed '/^$/d' | wc -l | tr -d ' ')
test "$model_invocation_count" -eq 1 && printf '%s\n' "$model_invocation_entries" | grep -Eq '^disable-model-invocation:[[:space:]]*false[[:space:]]*$' || { printf 'Skill disable-model-invocation must appear exactly once with value false\n' >&2; exit 1; }

implicit_invocation_entries=$(tr -d '\r' < "$agent_manifest" | grep -E '^[[:space:]]*allow_implicit_invocation:' || true)
implicit_invocation_count=$(printf '%s\n' "$implicit_invocation_entries" | sed '/^$/d' | wc -l | tr -d ' ')
test "$implicit_invocation_count" -eq 1 && printf '%s\n' "$implicit_invocation_entries" | grep -Eq '^[[:space:]]*allow_implicit_invocation:[[:space:]]*true[[:space:]]*(#.*)?$' || { printf 'SAGE-Kit allow_implicit_invocation must appear exactly once with value true\n' >&2; exit 1; }

activation_marker='SAGE_ACTIVE source=<project-entry> governance=<Light|Standard|Heavy> authority=<current-reference> profiles=<selected-or-none>'
test "$(tr -d '\r' < "$skill_path" | grep -Fxc "$activation_marker")" -eq 1 || { printf 'SAGE-Kit Skill must contain exactly one canonical activation marker\n' >&2; exit 1; }

check_bootstrap() {
  path=$1
  line_count=$(wc -l < "$path" | tr -d ' ')
  test "$line_count" -le 80 || { printf 'SAGE-Kit bootstrap exceeds 80 lines: %s\n' "$path" >&2; exit 1; }
  test "$(tr -d '\r' < "$path" | grep -Fxc "$activation_marker")" -eq 1 || { printf 'SAGE-Kit bootstrap must contain exactly one canonical activation marker: %s\n' "$path" >&2; exit 1; }
}
check_bootstrap AGENTS.md
check_bootstrap docs/templates/AGENTS_SAGE_BOOTSTRAP_TEMPLATE.md

case ${SAGEKIT_JSON_PARSER:-auto} in
  auto)
    if command -v jq >/dev/null 2>&1; then json_backend=jq
    elif command -v plutil >/dev/null 2>&1; then json_backend=plutil
    else json_backend=missing
    fi
    ;;
  jq|plutil)
    json_backend=$SAGEKIT_JSON_PARSER
    command -v "$json_backend" >/dev/null 2>&1 || { printf 'requested JSON parser is unavailable: %s\n' "$json_backend" >&2; exit 1; }
    ;;
  *) printf 'unsupported SAGEKIT_JSON_PARSER: %s\n' "$SAGEKIT_JSON_PARSER" >&2; exit 1 ;;
esac
test "$json_backend" != missing || { printf 'JSON parse check unavailable: install jq or use stock macOS plutil\n' >&2; exit 1; }

json_parse() {
  if [ "$json_backend" = jq ]; then jq . "$1" >/dev/null
  else plutil -convert json -o /dev/null -- "$1"
  fi
}
json_string() {
  file=$1
  jq_filter=$2
  plist_path=$3
  if [ "$json_backend" = jq ]; then
    output=$(jq -r "$jq_filter | if type == \"string\" then . else error(\"expected JSON string\") end" "$file") || return 1
    printf '%s\n' "$output" | tr -d '\r'
  else
    xml=$(plutil -extract "$plist_path" xml1 -o - "$file" 2>/dev/null) || return 1
    printf '%s\n' "$xml" | grep -Eq '<string>[^<]*</string>' || return 1
    plutil -extract "$plist_path" raw -o - "$file" 2>/dev/null
  fi
}
json_object_keys() {
  file=$1
  jq_filter=$2
  plist_path=$3
  if [ "$json_backend" = jq ]; then
    output=$(jq -r "$jq_filter | if type == \"object\" then keys[] else error(\"expected JSON object\") end" "$file") || return 1
    printf '%s\n' "$output" | tr -d '\r'
  else
    plutil -extract "$plist_path" xml1 -o - "$file" 2>/dev/null | awk '
      /<dict>/ { depth++; next }
      /<\/dict>/ { depth--; next }
      depth == 1 && /<key>/ { value = $0; sub(/^.*<key>/, "", value); sub(/<\/key>.*$/, "", value); print value }
    '
  fi
}
json_object_string() {
  file=$1
  jq_filter=$2
  plist_path=$3
  object_key=$4
  if [ "$json_backend" = jq ]; then
    output=$(jq -r "$jq_filter | if type == \"string\" then . else error(\"expected JSON string\") end" "$file") || return 1
    printf '%s\n' "$output" | tr -d '\r'
  else
    # plutil key paths split on dots. Extract the parent dictionary, then
    # match the literal child key so names such as task.schema.json survive.
    plutil -extract "$plist_path" xml1 -o - "$file" 2>/dev/null | awk -v expected="$object_key" '
      /<key>/ {
        key = $0
        sub(/^.*<key>/, "", key)
        sub(/<\/key>.*$/, "", key)
        matched = (key == expected)
        next
      }
      matched && /^[[:space:]]*$/ { next }
      matched && /<string>[^<]*<\/string>/ {
        value = $0
        sub(/^.*<string>/, "", value)
        sub(/<\/string>.*$/, "", value)
        print value
        found = 1
        exit
      }
      matched { exit 1 }
      END { if (!found) exit 1 }
    '
  fi
}
require_json_string() {
  label=$1
  expected=$2
  file=$3
  jq_filter=$4
  plist_path=$5
  actual=$(json_string "$file" "$jq_filter" "$plist_path") || { printf '%s is missing or not a string\n' "$label" >&2; exit 1; }
  test "$actual" = "$expected" || { printf '%s must equal %s\n' "$label" "$expected" >&2; exit 1; }
}
require_json_keys() {
  label=$1
  expected=$2
  file=$3
  jq_filter=$4
  plist_path=$5
  actual=$(json_object_keys "$file" "$jq_filter" "$plist_path" | sort) || { printf '%s is not an object\n' "$label" >&2; exit 1; }
  test "$actual" = "$expected" || { printf '%s has an unexpected key inventory\n' "$label" >&2; exit 1; }
}

for path in $(git ls-files '*.json'); do json_parse "$path" || { printf 'invalid JSON: %s\n' "$path" >&2; exit 1; }; done

# The optional host package may consume existing host peers, but cannot grow a
# CLI, installation hooks or its own mandatory dependency/runtime layer.
require_json_string 'optional adapter package name' '@sage-kit/dsh-plugin' adapters/package.json '.name' name
require_json_string 'optional adapter entry' 'dsh.mjs' adapters/package.json '.main' main
if [ "$json_backend" = jq ]; then
  jq -e '.private == true and ([keys[] | select(. == "scripts" or . == "bin" or . == "dependencies" or . == "optionalDependencies" or . == "devDependencies")] | length == 0)' adapters/package.json >/dev/null || { printf 'optional adapter must remain private with host peers only\n' >&2; exit 1; }
else
  private_xml=$(plutil -extract private xml1 -o - adapters/package.json) || exit 1
  printf '%s\n' "$private_xml" | grep -Eq '<true[[:space:]]*/>' || { printf 'optional adapter must remain private\n' >&2; exit 1; }
  adapter_xml=$(plutil -convert xml1 -o - adapters/package.json) || exit 1
  if printf '%s\n' "$adapter_xml" | grep -Eq '<key>(scripts|bin|dependencies|optionalDependencies|devDependencies)</key>'; then
    printf 'optional adapter must contain only host peers\n' >&2; exit 1
  fi
fi

sha256_file=''
if command -v sha256sum >/dev/null 2>&1; then sha256_file=sha256sum
elif command -v shasum >/dev/null 2>&1; then sha256_file='shasum -a 256'
fi
test -n "$sha256_file" || { printf 'static digest check unavailable: sha256sum/shasum not found\n' >&2; exit 1; }

dispatch_policy=contracts/task-dispatch-v2/policy.json
require_json_string 'Task Dispatch v2 selection scope' legacy-static-compatibility "$dispatch_policy" '.selection_scope' selection_scope
require_json_string 'Task Dispatch v2 selection' explicit-only "$dispatch_policy" '.selection' selection
require_json_string 'Task Dispatch v2 fallback' forbidden "$dispatch_policy" '.fallback' fallback
require_json_string 'Task Dispatch v2 record lifecycle scope field' validation_contract.record_scope "$dispatch_policy" '.record_scope_field' record_scope_field
require_json_keys 'Task Dispatch v2 schema digest inventory' 'evidence.schema.json
task.schema.json' "$dispatch_policy" '.schema_sha256' schema_sha256

if [ "$json_backend" = jq ]; then
  jq -r 'if ((.schema_files | type) == "array" and (.schema_files | length) == 2 and .schema_files[0] == "task.schema.json" and .schema_files[1] == "evidence.schema.json") then "ok" else error("invalid schema inventory") end' "$dispatch_policy" >/dev/null || { printf 'Task Dispatch v2 schema inventory is missing or malformed\n' >&2; exit 1; }
else
  schema_files_xml=$(plutil -extract schema_files xml1 -o - "$dispatch_policy" 2>/dev/null) || { printf 'Task Dispatch v2 schema inventory is missing or malformed\n' >&2; exit 1; }
  printf '%s\n' "$schema_files_xml" | grep -Eq '<array>' || { printf 'Task Dispatch v2 schema inventory is missing or malformed\n' >&2; exit 1; }
  test "$(printf '%s\n' "$schema_files_xml" | grep -c '<string>')" -eq 2 || { printf 'Task Dispatch v2 schema inventory is missing or malformed\n' >&2; exit 1; }
  test -z "$(plutil -extract schema_files.2 raw -o - "$dispatch_policy" 2>/dev/null)" || { printf 'Task Dispatch v2 schema inventory is missing or malformed\n' >&2; exit 1; }
fi
for index_schema in '0 task.schema.json' '1 evidence.schema.json'; do
  index=${index_schema%% *}
  schema=${index_schema#* }
  require_json_string "Task Dispatch v2 schema inventory entry $index" "$schema" "$dispatch_policy" ".schema_files[$index]" "schema_files.$index"
  declared=$(json_object_string "$dispatch_policy" ".schema_sha256[\"$schema\"]" schema_sha256 "$schema") || { printf 'Task Dispatch v2 digest missing or malformed: %s\n' "$schema" >&2; exit 1; }
  printf '%s\n' "$declared" | grep -Eq '^[0-9a-fA-F]{64}$' || { printf 'Task Dispatch v2 digest missing or malformed: %s\n' "$schema" >&2; exit 1; }
  schema_path="contracts/task-dispatch-v2/$schema"
  test -f "$schema_path" || { printf 'Task Dispatch v2 schema missing: %s\n' "$schema" >&2; exit 1; }
  actual=$($sha256_file "$schema_path" | awk '{print $1}')
  test "$actual" = "$declared" || { printf 'Task Dispatch v2 digest mismatch: %s\n' "$schema" >&2; exit 1; }
  require_json_string "Task Dispatch v2 record lifecycle scope $schema" active "$schema_path" '."$defs".validationContract.properties.record_scope.const' '$defs.validationContract.properties.record_scope.const'
done

graph_manifest=contracts/graph/v1/contract.json
require_json_keys 'Graph manifest resource inventory' 'graph_schema
node_result_schema' "$graph_manifest" '.resources' resources
for graph_entry in 'graph_schema graph.schema.json' 'node_result_schema node-result.schema.json'; do
  key=${graph_entry%% *}
  resource_expected=${graph_entry#* }
  resource=$(json_string "$graph_manifest" ".resources.$key.resource" "resources.$key.resource") || { printf 'Graph manifest resource is malformed: %s\n' "$key" >&2; exit 1; }
  test "$resource" = "$resource_expected" || { printf 'Graph manifest resource is malformed: %s\n' "$key" >&2; exit 1; }
  declared=$(json_string "$graph_manifest" ".resources.$key.canonical_sha256" "resources.$key.canonical_sha256") || { printf 'Graph manifest digest is malformed: %s\n' "$key" >&2; exit 1; }
  printf '%s\n' "$declared" | grep -Eq '^[0-9a-fA-F]{64}$' || { printf 'Graph manifest digest is malformed: %s\n' "$key" >&2; exit 1; }
  resource_path="contracts/graph/v1/$resource"
  test -f "$resource_path" || { printf 'missing Graph manifest resource: %s\n' "$resource_path" >&2; exit 1; }
  actual=$($sha256_file "$resource_path" | awk '{print $1}')
  test "$actual" = "$declared" || { printf 'Graph manifest digest mismatch: %s\n' "$resource_path" >&2; exit 1; }
done

release_ids='claude_agent_coder
claude_agent_final_review
host_reference_claude
host_reference_codex
host_reference_kimi
host_reference_opencode
license
migration_guide
readme_en
readme_zh_cn
release_guide
skill_manifest'
actual_release_ids=''
actual_release_paths=''
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|'#'*) continue ;; esac
  case "$line" in *'|'*) release_id=${line%%|*}; release_path=${line#*|} ;; *) printf 'invalid release resource inventory entry: %s\n' "$line" >&2; exit 1 ;; esac
  test -n "$release_id" && test -n "$release_path" && [ "$release_path" = "${release_path#../}" ] && [ "$release_path" = "${release_path#*/../}" ] || { printf 'invalid release resource inventory entry: %s\n' "$line" >&2; exit 1; }
  git ls-files --error-unmatch "$release_path" >/dev/null 2>&1 || { printf 'missing tracked release resource: %s\n' "$release_path" >&2; exit 1; }
  test -f "$release_path" || { printf 'missing release resource: %s\n' "$release_path" >&2; exit 1; }
  actual_release_ids="${actual_release_ids}${release_id}\n"
  actual_release_paths="${actual_release_paths}${release_path}\n"
done < contracts/release-resource-inventory.txt
test "$(printf '%b' "$actual_release_ids" | sort)" = "$release_ids" || { printf 'release resource inventory is incomplete or has unexpected identifiers\n' >&2; exit 1; }
test "$(printf '%b' "$actual_release_paths" | sort -u)" = "$(printf '%b' "$actual_release_paths" | sort)" || { printf 'release resource inventory contains duplicate paths\n' >&2; exit 1; }

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

if [ -n "${SAGEKIT_DIFF_BASE:-}" ]; then
  git diff --check "$SAGEKIT_DIFF_BASE...HEAD" || { printf 'PR/push-range git diff --check failed\n' >&2; exit 1; }
else
  git diff HEAD --check || { printf 'local index/worktree git diff --check failed\n' >&2; exit 1; }
fi

printf 'repository integrity: PASS\n'
