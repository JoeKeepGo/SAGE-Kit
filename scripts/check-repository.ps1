$ErrorActionPreference = 'Stop'

$required = @(
    'README.md',
    'docs/SAGE_CORE.md',
    'docs/agent/AGENT_HARNESS.md',
    'docs/agent/EXECUTION_ECONOMY.md',
    'contracts/graph/v1/graph.schema.json',
    'contracts/graph/v1/node-result.schema.json',
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

git diff --check
if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }
Write-Output 'repository integrity: PASS'
