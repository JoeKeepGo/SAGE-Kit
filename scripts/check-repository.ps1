$ErrorActionPreference = 'Stop'

$required = @(
    'AGENTS.md',
    'contracts/canonical-authority-pointers.txt',
    'contracts/graph/v1/contract.json',
    'contracts/graph/v1/graph.schema.json',
    'contracts/graph/v1/node-result.schema.json',
    'contracts/release-resource-inventory.txt',
    'contracts/task-dispatch-v2/policy.json',
    'contracts/task-dispatch-v2/task.schema.json',
    'contracts/task-dispatch-v2/evidence.schema.json',
    'docs/SAGE_CORE.md',
    'docs/agent/AGENT_HARNESS.md',
    'docs/agent/CLAIM_EVIDENCE_TRUST.md',
    'docs/agent/GOVERNANCE_LEVELS.md',
    'docs/templates/AGENTS_SAGE_BOOTSTRAP_TEMPLATE.md',
    'README.md',
    'skills/sage-kit/SKILL.md',
    'skills/sage-kit/skill-manifest.json',
    'skills/sage-kit/agents/openai.yaml'
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "missing required path: $path" }
}

$tracked = @(git ls-files)
# R-003 permits this optional host module, not an executable dependency of the Skill.
$unexpectedAdapters = @($tracked | Where-Object { $_ -like 'adapters/*' -and $_ -ne 'adapters/continuation.mjs' })
if ($unexpectedAdapters.Count -ne 0) { throw "unreviewed optional adapter: $($unexpectedAdapters -join ', ')" }
$packageManifest = '(^|/)(pyproject\.toml|setup\.py|setup\.cfg|requirements[^/]*\.txt|tox\.ini|noxfile\.py|Pipfile|poetry\.lock|uv\.lock|package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?|deno\.json|Cargo\.toml|Cargo\.lock|go\.mod|go\.sum|pom\.xml|build\.gradle(\.kts)?|settings\.gradle(\.kts)?|Gemfile|Gemfile\.lock|composer\.json|composer\.lock|mix\.exs|rebar\.config|pubspec\.yaml|Package\.swift|[^/]+\.(csproj|fsproj|vbproj))$'
$forbidden = @($tracked | Where-Object {
    $_ -match '(^|/)(bin|src)/(sagekit|sage-kit)(/|$)' -or
    $_ -match '(^|/)(sagekit|sage-kit)(\.(sh|ps1|bash|zsh|fish|bat|cmd|exe|py|js|mjs|cjs|ts|tsx|rs|go|java|cs|rb|php))?$' -or
    ($_ -match $packageManifest -and $_ -notmatch '^(docs|tests|scripts|\.github)/')
})
if ($forbidden.Count -ne 0) { throw "forbidden shipped runtime, entrypoint, or executable dependency surface:`n$($forbidden -join "`n")" }

# Package and interpreter tooling is permitted for docs, tests, and release
# work. This scans only shipped execution surfaces for SAGE-Kit runtime entry
# points or attempts to install/invoke SAGE-Kit as an executable dependency.
$executionSurfaces = @($tracked | Where-Object {
    $_ -notin @('scripts/check-repository.ps1', 'scripts/check-repository.sh') -and
    (
        $_ -like '.github/workflows/*' -or $_ -like '.claude/*' -or
        $_ -like '.codex/*' -or $_ -like 'scripts/*' -or
        $_ -like 'skills/*/agents/*' -or $_ -like 'skills/*/references/*/agents/*' -or
        $_ -like 'skills/*/references/*/hooks/*'
    ) -and $_ -match '\.(sh|ps1|bash|zsh|fish|bat|cmd|js|mjs|cjs|ts|tsx|rs|go|java|cs|rb|php|ya?ml|json|toml|md)$'
})
if ($executionSurfaces.Count -gt 0) {
    $runtimePattern = '(^|[;&|()]|run:|command:|exec:|shell:)[[:space:]]*(env[[:space:]]+)?((sagekit|sage-kit)[[:space:]]+(run|validate|check|candidate|checkpoint|resource|packet)|python([0-9.]*)?[[:space:]]+-m[[:space:]]+(sagekit|sage_kit)|pip([0-9.]*)?[[:space:]]+install.*(sagekit|sage-kit)|npm[[:space:]]+(install|exec).*(sagekit|sage-kit)|npx[[:space:]]+(sagekit|sage-kit)|cargo[[:space:]]+install.*(sagekit|sage-kit)|go[[:space:]]+install.*(sagekit|sage-kit)|dotnet[[:space:]]+tool[[:space:]]+install.*(sagekit|sage-kit)|gem[[:space:]]+install.*(sagekit|sage-kit)|composer[[:space:]]+require.*(sagekit|sage-kit))'
    $stale = @(git grep -n -I -E $runtimePattern -- $executionSurfaces)
    if ($LASTEXITCODE -notin 0, 1) { throw 'shipped execution-surface scan failed' }
    if ($stale.Count -ne 0) { throw "forbidden SAGE-Kit runtime invocation or executable dependency:`n$($stale -join "`n")" }
}

$skill = Get-Content -LiteralPath 'skills/sage-kit/SKILL.md' -Raw
$skillFrontmatter = [regex]::Match($skill, '(?s)\A---\r?\n(?<content>.*?)\r?\n---(?:\r?\n|\z)')
if (-not $skillFrontmatter.Success) { throw 'invalid Skill frontmatter' }
$skillFrontmatterText = $skillFrontmatter.Groups['content'].Value
$skillNameEntries = @([regex]::Matches($skillFrontmatterText, '(?m)^name:[^\r\n]*\r?$'))
if ($skillNameEntries.Count -ne 1 -or $skillNameEntries[0].Value -notmatch '\Aname:[ \t]*sage-kit[ \t]*\r?\z') { throw 'Skill name must appear exactly once with value sage-kit' }
$skillDescriptionEntries = @([regex]::Matches($skillFrontmatterText, '(?m)^description:[^\r\n]*\r?$'))
if ($skillDescriptionEntries.Count -ne 1) { throw 'Skill description must appear exactly once' }
$skillDescriptionValue = ($skillDescriptionEntries[0].Value -replace '\r$', '') -replace '^description:[ \t]*', ''
if ([string]::IsNullOrWhiteSpace($skillDescriptionValue)) { throw 'Skill description must have a value' }
$modelInvocationEntries = @([regex]::Matches($skillFrontmatterText, '(?m)^disable-model-invocation:[^\r\n]*\r?$'))
if ($modelInvocationEntries.Count -ne 1 -or $modelInvocationEntries[0].Value -notmatch '\Adisable-model-invocation:[ \t]*false[ \t]*\r?\z') { throw 'Skill disable-model-invocation must appear exactly once with value false' }

$agentManifest = Get-Content -LiteralPath 'skills/sage-kit/agents/openai.yaml' -Raw
$implicitInvocationEntries = @([regex]::Matches($agentManifest, '(?m)^[ \t]*allow_implicit_invocation:[^\r\n]*\r?$'))
if ($implicitInvocationEntries.Count -ne 1 -or $implicitInvocationEntries[0].Value -notmatch '\A[ \t]*allow_implicit_invocation:[ \t]*true[ \t]*(?:#.*)?\r?\z') { throw 'SAGE-Kit allow_implicit_invocation must appear exactly once with value true' }

$activationMarker = 'SAGE_ACTIVE source=<project-entry> governance=<Light|Standard|Heavy> authority=<current-reference> profiles=<selected-or-none>'
$skillMarkerCount = @((Get-Content -LiteralPath 'skills/sage-kit/SKILL.md') | Where-Object { $_ -ceq $activationMarker }).Count
if ($skillMarkerCount -ne 1) { throw 'SAGE-Kit Skill must contain exactly one canonical activation marker' }
foreach ($path in @('AGENTS.md', 'docs/templates/AGENTS_SAGE_BOOTSTRAP_TEMPLATE.md')) {
    $bootstrapLines = @(Get-Content -LiteralPath $path)
    if ($bootstrapLines.Count -gt 80) { throw "SAGE-Kit bootstrap exceeds 80 lines: $path" }
    $markerCount = @($bootstrapLines | Where-Object { $_ -ceq $activationMarker }).Count
    if ($markerCount -ne 1) { throw "SAGE-Kit bootstrap must contain exactly one canonical activation marker: $path" }
}

foreach ($path in ($tracked | Where-Object { $_ -like '*.json' })) {
    Get-Content -LiteralPath $path -Raw | ConvertFrom-Json -ErrorAction Stop | Out-Null
}

$dispatchRoot = 'contracts/task-dispatch-v2'
$dispatchPolicy = Get-Content -LiteralPath "$dispatchRoot/policy.json" -Raw | ConvertFrom-Json -ErrorAction Stop
if ($dispatchPolicy -isnot [pscustomobject] -or $dispatchPolicy.selection_scope -ne 'legacy-static-compatibility' -or $dispatchPolicy.selection -ne 'explicit-only' -or $dispatchPolicy.fallback -ne 'forbidden' -or $dispatchPolicy.record_scope_field -ne 'validation_contract.record_scope') { throw 'Task Dispatch v2 selection and lifecycle scopes are malformed' }
$dispatchSchemas = $dispatchPolicy.schema_files
if ($dispatchSchemas -isnot [array] -or $dispatchSchemas.Count -ne 2 -or @($dispatchSchemas | Where-Object { $_ -isnot [string] }).Count -ne 0 -or (Compare-Object @('task.schema.json', 'evidence.schema.json') $dispatchSchemas).Count -ne 0) { throw 'Task Dispatch v2 schema inventory is missing or malformed' }
$dispatchDigests = $dispatchPolicy.schema_sha256
if ($dispatchDigests -isnot [pscustomobject] -or @($dispatchDigests.PSObject.Properties).Count -ne 2) { throw 'Task Dispatch v2 digest inventory is malformed' }
foreach ($schemaName in $dispatchSchemas) {
    $digestProperty = $dispatchDigests.PSObject.Properties[$schemaName]
    if (-not $digestProperty -or $digestProperty.Value -isnot [string] -or $digestProperty.Value -notmatch '^[0-9a-fA-F]{64}$') { throw "Task Dispatch v2 digest is missing or malformed: $schemaName" }
    $schemaPath = "$dispatchRoot/$schemaName"
    if (-not (Test-Path -LiteralPath $schemaPath -PathType Leaf)) { throw "Task Dispatch v2 schema is missing: $schemaName" }
    $actual = (Get-FileHash -LiteralPath $schemaPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $digestProperty.Value.ToLowerInvariant()) { throw "Task Dispatch v2 digest mismatch: $schemaName" }
    $dispatchSchema = Get-Content -LiteralPath $schemaPath -Raw | ConvertFrom-Json -ErrorAction Stop
    if ($dispatchSchema -isnot [pscustomobject] -or $dispatchSchema.'$defs'.validationContract.properties.record_scope.const -ne 'active') { throw "Task Dispatch v2 record lifecycle scope is malformed: $schemaName" }
}

$graphManifestPath = 'contracts/graph/v1/contract.json'
$graphManifest = Get-Content -LiteralPath $graphManifestPath -Raw | ConvertFrom-Json -ErrorAction Stop
$expectedGraphResources = @{ graph_schema = 'graph.schema.json'; node_result_schema = 'node-result.schema.json' }
if ($graphManifest -isnot [pscustomobject] -or $graphManifest.resources -isnot [pscustomobject] -or @($graphManifest.resources.PSObject.Properties).Count -ne $expectedGraphResources.Count) { throw 'Graph manifest resource inventory is malformed' }
foreach ($entryName in $expectedGraphResources.Keys) {
    $entry = $graphManifest.resources.PSObject.Properties[$entryName]
    if (-not $entry -or $entry.Value -isnot [pscustomobject] -or $entry.Value.resource -isnot [string] -or $entry.Value.resource -ne $expectedGraphResources[$entryName] -or $entry.Value.canonical_sha256 -isnot [string] -or $entry.Value.canonical_sha256 -notmatch '^[0-9a-fA-F]{64}$') { throw "Graph manifest resource is malformed: $entryName" }
    $resourcePath = Join-Path (Split-Path -Parent $graphManifestPath) $entry.Value.resource
    if (-not (Test-Path -LiteralPath $resourcePath -PathType Leaf)) { throw "missing Graph manifest resource: $resourcePath" }
    $actual = (Get-FileHash -LiteralPath $resourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($entry.Value.canonical_sha256.ToLowerInvariant() -ne $actual) { throw "Graph manifest digest mismatch: $resourcePath" }
}

$releaseIds = @('license', 'readme_en', 'readme_zh_cn', 'migration_guide', 'release_guide', 'skill_manifest', 'host_reference_codex', 'host_reference_claude', 'host_reference_opencode', 'host_reference_kimi', 'claude_agent_coder', 'claude_agent_final_review')
$releaseEntries = @()
foreach ($line in (Get-Content -LiteralPath 'contracts/release-resource-inventory.txt')) {
    if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith('#')) { continue }
    $parts = $line -split '\|', 2
    if ($parts.Count -ne 2 -or [string]::IsNullOrWhiteSpace($parts[0]) -or [string]::IsNullOrWhiteSpace($parts[1]) -or $parts[1] -match '(^|/)\.\.(/|$)') { throw "invalid release resource inventory entry: $line" }
    $releaseEntries += [pscustomobject]@{ Id = $parts[0]; Path = $parts[1] }
}
if ($releaseEntries.Count -ne $releaseIds.Count -or (Compare-Object $releaseIds @($releaseEntries.Id)).Count -ne 0 -or (Compare-Object @($releaseEntries.Path | Sort-Object -Unique) @($releaseEntries.Path)).Count -ne 0) { throw 'release resource inventory is incomplete or duplicated' }
foreach ($entry in $releaseEntries) {
    if (-not (Test-Path -LiteralPath $entry.Path -PathType Leaf) -or $tracked -notcontains $entry.Path) { throw "missing tracked release resource: $($entry.Path)" }
}

$canonicalPointers = @(Get-Content -LiteralPath 'contracts/canonical-authority-pointers.txt' | Where-Object { $_.Trim() })
if (($canonicalPointers | Sort-Object -Unique).Count -ne $canonicalPointers.Count) { throw 'duplicate canonical authority pointer' }
$declaredPointers = @()
foreach ($path in ($tracked | Where-Object { $_ -like 'docs/*.md' -or $_ -like 'docs/*/*.md' -or $_ -like 'docs/*/*/*.md' })) {
    foreach ($line in (Get-Content -LiteralPath $path)) {
        if ($line -match '^<a id="([^"]+)"></a>$') { $declaredPointers += "$path#$($Matches[1])" }
    }
}
$pointerDelta = @(Compare-Object ($canonicalPointers | Sort-Object) ($declaredPointers | Sort-Object))
if ($pointerDelta.Count -ne 0) { throw "canonical authority pointer manifest mismatch:`n$($pointerDelta | Out-String)" }
foreach ($reference in $canonicalPointers) {
    $targetPath, $anchor = $reference -split '#', 2
    if (-not (Test-Path -LiteralPath $targetPath -PathType Leaf)) { throw "broken canonical pointer: $reference" }
    $targetText = Get-Content -LiteralPath $targetPath -Raw
    $anchorPattern = '<a\s+id=["'']' + [regex]::Escape($anchor) + '["'']\s*></a>'
    if ($targetText -notmatch $anchorPattern) { throw "missing canonical anchor: $reference" }
}

if ($env:SAGEKIT_DIFF_BASE) {
    git diff --check "$($env:SAGEKIT_DIFF_BASE)...HEAD"
    if ($LASTEXITCODE -ne 0) { throw 'PR/push-range git diff --check failed' }
} else {
    git diff HEAD --check
    if ($LASTEXITCODE -ne 0) { throw 'local index/worktree git diff --check failed' }
}

Write-Output 'repository integrity: PASS'
