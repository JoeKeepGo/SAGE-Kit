# Tests for the optional exact-path Claude advisory hook.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$guard = Join-Path $root 'skills/sage-kit/references/claude/hooks/protect-serial-files.ps1'
$hostExe = (Get-Process -Id $PID).Path
$script:passCount = 0
$script:failCount = 0

function Check([string]$name, [int]$expected, [int]$actual) {
    if ($expected -eq $actual) { $script:passCount++; Write-Host "PASS $name" }
    else { $script:failCount++; Write-Host "FAIL $name (expected $expected, got $actual)" }
}
function Invoke-Hook([string]$stdin, [string]$workDir) {
    $inFile = [System.IO.Path]::GetTempFileName()
    $errFile = [System.IO.Path]::GetTempFileName()
    $outFile = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText($inFile, $stdin)
    try {
        $process = Start-Process -FilePath $hostExe `
            -ArgumentList ('-NoProfile -NonInteractive -File "{0}"' -f $guard) `
            -WorkingDirectory $workDir -NoNewWindow -Wait -PassThru `
            -RedirectStandardInput $inFile -RedirectStandardError $errFile `
            -RedirectStandardOutput $outFile
        return $process.ExitCode
    } finally {
        Remove-Item $inFile, $errFile, $outFile -Force -ErrorAction SilentlyContinue
    }
}

$savedProject = $env:CLAUDE_PROJECT_DIR
$savedPaths = $env:SAGE_PROTECTED_PATHS
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('sagekit-hook-tests-' + [System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    $env:CLAUDE_PROJECT_DIR = $tmp
    $env:SAGE_PROTECTED_PATHS = "docs/ACTIVE_CONTEXT.md`ndocs/DOC_ROUTING.md"

    Check 'exact configured relative path blocked' 2 (Invoke-Hook '{"tool_input":{"file_path":"docs/ACTIVE_CONTEXT.md"}}' $tmp)
    Check 'exact configured canonical path blocked' 2 (Invoke-Hook '{"tool_input":{"file_path":"docs/sub/../DOC_ROUTING.md"}}' $tmp)
    Check 'same filename outside configured path allowed' 0 (Invoke-Hook '{"tool_input":{"file_path":"elsewhere/docs/ACTIVE_CONTEXT.md"}}' $tmp)
    Check 'shell text is not heuristically inspected' 0 (Invoke-Hook '{"tool_input":{"command":"echo x >> docs/ACTIVE_CONTEXT.md"}}' $tmp)
    Check 'unsupported event shape remains advisory' 0 (Invoke-Hook 'not json' $tmp)

    $env:SAGE_PROTECTED_PATHS = $null
    Check 'unconfigured hook allows path' 0 (Invoke-Hook '{"tool_input":{"file_path":"docs/ACTIVE_CONTEXT.md"}}' $tmp)
} finally {
    $env:CLAUDE_PROJECT_DIR = $savedProject
    $env:SAGE_PROTECTED_PATHS = $savedPaths
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "PASS=$($script:passCount) FAIL=$($script:failCount)"
if ($script:failCount -gt 0) { exit 1 }
