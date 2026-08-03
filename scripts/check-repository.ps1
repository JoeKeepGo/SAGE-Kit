$ErrorActionPreference = 'Stop'

$required = @(
    'README.md',
    'docs/SAGE_CORE.md',
    'docs/agent/AGENT_HARNESS.md',
    'docs/agent/GOVERNANCE_LEVELS.md',
    'contracts/graph/v1/contract.json',
    'contracts/graph/v1/graph.schema.json',
    'contracts/graph/v1/node-result.schema.json',
    'contracts/task-dispatch-v2/policy.json',
    'contracts/task-dispatch-v2/task.schema.json',
    'contracts/task-dispatch-v2/evidence.schema.json',
    'contracts/canonical-authority-pointers.txt',
    'skills/sage-kit/SKILL.md'
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "missing required path: $path" }
}

$tracked = @(git ls-files)
$forbidden = @($tracked | Where-Object {
    $_ -match '(^|/)(pyproject\.toml|setup\.py|setup\.cfg|requirements[^/]*\.txt|tox\.ini|noxfile\.py|package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock)$' -or
    $_ -match '\.(py|pyi|pyc|whl)$' -or $_ -match '\.egg-info/' -or
    $_ -match '(^|/)(bin|src)/(sagekit|sage-kit)(/|$)'
})
if ($forbidden.Count -ne 0) { throw "forbidden runtime/CLI/package surface:`n$($forbidden -join "`n")" }

# Scan executable/workflow surfaces only. Ordinary governance prose may discuss
# runtimes and tests without becoming an executable dependency.
$executionSurfaces = @($tracked | Where-Object {
    $_ -notin @('scripts/check-repository.ps1', 'scripts/check-repository.sh') -and
    (
        $_ -like '.github/workflows/*' -or $_ -like '.claude/*' -or
        $_ -like '.codex/*' -or $_ -like 'scripts/*' -or $_ -like 'tests/*' -or
        $_ -like 'skills/*/agents/*' -or $_ -like 'skills/*/references/*/agents/*' -or
        $_ -like 'skills/*/references/*/hooks/*' -or
        $_ -match '(^|/)(Makefile|Dockerfile|compose[^/]*\.ya?ml|[^/]*(launch|runner|daemon|scheduler|setup|install)[^/]*\.(sh|ps1|bat|cmd|ya?ml|json|toml))$'
    ) -and $_ -match '\.(sh|ps1|bash|zsh|fish|bat|cmd|js|mjs|cjs|ts|tsx|rs|go|java|cs|rb|php|ya?ml|json|toml|md)$|(^|/)(Makefile|Dockerfile)$'
})
if ($executionSurfaces.Count -gt 0) {
    $stale = @(git grep -n -I -E '(^|[;&|()]|run:|command:|exec:|shell:)[[:space:]]*(env[[:space:]]+)?(python([0-9.]*)?|pip([0-9.]*)?|pytest|unittest|sagekit[[:space:]]+(run|validate|check|candidate|checkpoint|resource|packet)|npm|npx|node)[[:space:]]' -- $executionSurfaces)
    if ($LASTEXITCODE -notin 0, 1) { throw 'executable/workflow reference scan failed' }
    if ($stale.Count -ne 0) { throw "forbidden runtime invocation:`n$($stale -join "`n")" }
}

$skill = Get-Content -LiteralPath 'skills/sage-kit/SKILL.md' -Raw
if (-not $skill.StartsWith("---`n") -and -not $skill.StartsWith("---`r`n")) { throw 'invalid Skill frontmatter' }
if ($skill -notmatch '(?m)^name: sage-kit\r?$') { throw 'missing Skill name' }
if ($skill -notmatch '(?m)^description:') { throw 'missing Skill description' }
if ($skill -notmatch 'No CLI, package runtime, daemon, or hidden validator is required') { throw 'missing model-native architecture statement' }

foreach ($path in ($tracked | Where-Object { $_ -like '*.json' })) {
    Get-Content -LiteralPath $path -Raw | ConvertFrom-Json | Out-Null
}

# Task Dispatch v2 is legacy static compatibility, not default routing. Verify
# only that its policy binds the exact schema bytes it declares.
$dispatchRoot = 'contracts/task-dispatch-v2'
$dispatchPolicy = Get-Content -LiteralPath "$dispatchRoot/policy.json" -Raw | ConvertFrom-Json
if ($dispatchPolicy.scope -ne 'legacy-static-compatibility' -or $dispatchPolicy.selection -ne 'explicit-only') { throw 'Task Dispatch v2 must remain explicit legacy compatibility' }
$dispatchSchemas = @($dispatchPolicy.schema_files)
if ($dispatchSchemas.Count -ne 2 -or $dispatchSchemas -notcontains 'task.schema.json' -or $dispatchSchemas -notcontains 'evidence.schema.json') { throw 'Task Dispatch v2 schema inventory is missing or malformed' }
foreach ($schemaName in $dispatchSchemas) {
    $schemaPath = "$dispatchRoot/$schemaName"
    $digestProperty = $dispatchPolicy.schema_sha256.PSObject.Properties[$schemaName]
    if (-not $digestProperty -or $digestProperty.Value -notmatch '^[0-9a-fA-F]{64}$') { throw "Task Dispatch v2 digest is missing or malformed: $schemaName" }
    if (-not (Test-Path -LiteralPath $schemaPath -PathType Leaf)) { throw "Task Dispatch v2 schema is missing: $schemaName" }
    $actual = (Get-FileHash -LiteralPath $schemaPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $digestProperty.Value.ToLowerInvariant()) { throw "Task Dispatch v2 digest mismatch: $schemaName" }
}

# Validate the active Graph manifest only. Legacy compatibility contracts are
# readable inventory but are not part of default adoption.
$graphManifestPath = 'contracts/graph/v1/contract.json'
$graphManifest = Get-Content -LiteralPath $graphManifestPath -Raw | ConvertFrom-Json
foreach ($entry in $graphManifest.resources.PSObject.Properties) {
    $resourcePath = Join-Path (Split-Path -Parent $graphManifestPath) $entry.Value.resource
    if (-not (Test-Path -LiteralPath $resourcePath -PathType Leaf)) { throw "missing Graph manifest resource: $resourcePath" }
    $declared = $entry.Value.canonical_sha256
    $actual = (Get-FileHash -LiteralPath $resourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($declared -ne $actual) { throw "Graph manifest digest mismatch: $resourcePath" }
}

# Validate only the small explicit canonical-authority pointer manifest, not
# ordinary Markdown links.
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
    if ($LASTEXITCODE -ne 0) { throw 'PR-range git diff --check failed' }
} else {
    git diff --check
    if ($LASTEXITCODE -ne 0) { Write-Warning 'local git diff --check reported hygiene issues (non-blocking without SAGEKIT_DIFF_BASE)' }
}

Write-Output 'repository integrity: PASS'
