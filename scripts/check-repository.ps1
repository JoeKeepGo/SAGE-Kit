$ErrorActionPreference = 'Stop'

$required = @(
    'README.md',
    'docs/SAGE_CORE.md',
    'docs/agent/AGENT_HARNESS.md',
    'docs/agent/EXECUTION_ECONOMY.md',
    'contracts/graph/v1/contract.json',
    'contracts/graph/v1/graph.schema.json',
    'contracts/graph/v1/node-result.schema.json',
    'contracts/task-dispatch-v2/policy.json',
    'skills/sage-kit/SKILL.md'
)

foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "missing required path: $path"
    }
}

$tracked = @(git ls-files)
$forbidden = @($tracked | Where-Object {
    $_ -match '(^|/)(pyproject\.toml|setup\.py|setup\.cfg|requirements[^/]*\.txt|tox\.ini|noxfile\.py)$' -or
    $_ -match '\.(py|pyi|pyc|whl)$' -or
    $_ -match '\.egg-info/'
})
if ($forbidden.Count -ne 0) {
    throw "forbidden Python surface:`n$($forbidden -join "`n")"
}

$stale = @(git grep -n -I -E '(-m[[:space:]]+(sagekit|scripts\.run_tests)|pip([0-9.]*)?[[:space:]]+install|pytest|unittest|\.venv|sagekit/resources)' -- . ':(exclude)docs/MIGRATION_MODEL_NATIVE.md' ':(exclude)scripts/check-repository.sh' ':(exclude)scripts/check-repository.ps1')
if ($LASTEXITCODE -notin 0, 1) { throw 'stale-reference scan failed' }
if ($stale.Count -ne 0) {
    throw "stale executable/runtime reference:`n$($stale -join "`n")"
}

$skill = Get-Content -LiteralPath 'skills/sage-kit/SKILL.md' -Raw
if (-not $skill.StartsWith("---`n") -and -not $skill.StartsWith("---`r`n")) { throw 'invalid Skill frontmatter' }
if ($skill -notmatch '(?m)^name: sage-kit$') { throw 'missing Skill name' }
if ($skill -notmatch '(?m)^description:') { throw 'missing Skill description' }
if ($skill -notmatch 'No CLI, package runtime, daemon, or hidden validator is required') { throw 'missing model-native architecture statement' }

foreach ($path in ($tracked | Where-Object { $_ -like '*.json' })) {
    Get-Content -LiteralPath $path -Raw | ConvertFrom-Json | Out-Null
}

function Assert-CanonicalDigest {
    param(
        [string]$ManifestPath,
        [string]$Resource,
        [string]$DeclaredDigest
    )

    if ($DeclaredDigest -notmatch '^[0-9a-f]{64}$') {
        throw "invalid declared SHA-256 in ${ManifestPath}: $Resource"
    }
    $resourcePath = Join-Path (Split-Path -Parent $ManifestPath) $Resource
    if (-not (Test-Path -LiteralPath $resourcePath -PathType Leaf)) {
        throw "missing manifest resource in ${ManifestPath}: $Resource"
    }
    $actual = (Get-FileHash -LiteralPath $resourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $DeclaredDigest) {
        throw "manifest digest mismatch in ${ManifestPath}: $Resource declared=$DeclaredDigest actual=$actual"
    }
}

$taskPolicyPath = 'contracts/task-dispatch-v2/policy.json'
$taskPolicy = Get-Content -LiteralPath $taskPolicyPath -Raw | ConvertFrom-Json
foreach ($resource in $taskPolicy.schema_files) {
    $digestProperty = $taskPolicy.schema_sha256.PSObject.Properties[$resource]
    if ($null -eq $digestProperty) {
        throw "missing declared SHA-256 in ${taskPolicyPath}: $resource"
    }
    Assert-CanonicalDigest $taskPolicyPath $resource $digestProperty.Value
}

$graphManifestPath = 'contracts/graph/v1/contract.json'
$graphManifest = Get-Content -LiteralPath $graphManifestPath -Raw | ConvertFrom-Json
foreach ($entry in $graphManifest.resources.PSObject.Properties) {
    Assert-CanonicalDigest $graphManifestPath $entry.Value.resource $entry.Value.canonical_sha256
}

# Canonical authority references use explicit local anchors. Check only the
# narrow docs/<path>.md#<anchor> form rather than crawling general links.
$authorityReferencePattern = 'docs/[A-Za-z0-9_./-]+\.md#[A-Za-z0-9_.:-]+'
foreach ($source in ($tracked | Where-Object { $_ -match '\.(md|ya?ml)$' })) {
    $sourceText = Get-Content -LiteralPath $source -Raw
    foreach ($referenceMatch in [regex]::Matches($sourceText, $authorityReferencePattern)) {
        $reference = $referenceMatch.Value
        $parts = $reference -split '#', 2
        $targetPath = $parts[0]
        $anchor = $parts[1]
        if (-not (Test-Path -LiteralPath $targetPath -PathType Leaf)) {
            throw "broken canonical authority reference in ${source}: $reference"
        }
        $targetText = Get-Content -LiteralPath $targetPath -Raw
        $anchorPattern = '<a\s+id=["'']' + [regex]::Escape($anchor) + '["'']\s*></a>'
        if ($targetText -notmatch $anchorPattern) {
            throw "missing canonical authority anchor in ${source}: $reference"
        }
    }
}

git diff --check
if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }
Write-Output 'repository integrity: PASS'
