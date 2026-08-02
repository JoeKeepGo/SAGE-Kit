$ErrorActionPreference = 'Stop'

$required = @(
    'README.md',
    'docs/SAGE_CORE.md',
    'docs/agent/AGENT_HARNESS.md',
    'docs/agent/GOVERNANCE_LEVELS.md',
    'contracts/graph/v1/contract.json',
    'contracts/graph/v1/graph.schema.json',
    'contracts/graph/v1/node-result.schema.json',
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
    ($_ -like '.github/workflows/*' -or $_ -like 'tests/*') -and
    $_ -match '\.(sh|ps1|ya?ml|json)$'
})
if ($executionSurfaces.Count -gt 0) {
    $stale = @(git grep -n -I -E '(python([0-9.]*)?|pip([0-9.]*)?|pytest|unittest|sagekit[[:space:]]+(run|validate|check)|npm|npx|node)[[:space:]]' -- $executionSurfaces)
    if ($LASTEXITCODE -notin 0, 1) { throw 'executable/workflow reference scan failed' }
    if ($stale.Count -ne 0) { throw "forbidden runtime invocation:`n$($stale -join "`n")" }
}

$skill = Get-Content -LiteralPath 'skills/sage-kit/SKILL.md' -Raw
if (-not $skill.StartsWith("---`n") -and -not $skill.StartsWith("---`r`n")) { throw 'invalid Skill frontmatter' }
if ($skill -notmatch '(?m)^name: sage-kit$') { throw 'missing Skill name' }
if ($skill -notmatch '(?m)^description:') { throw 'missing Skill description' }
if ($skill -notmatch 'No CLI, package runtime, daemon, or hidden validator is required') { throw 'missing model-native architecture statement' }

foreach ($path in ($tracked | Where-Object { $_ -like '*.json' })) {
    Get-Content -LiteralPath $path -Raw | ConvertFrom-Json | Out-Null
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

# Validate only the explicit canonical-authority pointer manifest.
$canonicalPointers = @(
    'docs/SAGE_CORE.md#sage-completion-001',
    'docs/agent/GOVERNANCE_LEVELS.md#sage-auth-004',
    'docs/agent/GOVERNANCE_LEVELS.md#sage-auth-005',
    'docs/agent/GOVERNANCE_LEVELS.md#sage-auth-006',
    'docs/agent/GOVERNANCE_LEVELS.md#sage-auth-008',
    'docs/agent/AGENT_HARNESS.md#sage-auth-010'
)
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
