# Negative-path tests for the Windows PowerShell Claude Code hooks shipped
# under skills/sage-kit/references/claude/hooks/.
#
# Mirrors tests/test_claude_hooks.sh for the .ps1 variants: Windows path
# separators, dot segments, case variants, malformed or missing hook input,
# Bash-shaped commands, and validator exit-code semantics.
#
# Hooks are exercised as real child processes of the current host, so the
# same file runs under both PowerShell 7 (pwsh) and Windows PowerShell 5.1
# (powershell.exe); CI invokes it with both.

$root = Split-Path -Parent $PSScriptRoot
$hookDir = Join-Path $root 'skills/sage-kit/references/claude/hooks'
$guard = Join-Path $hookDir 'protect-serial-files.ps1'
$stop = Join-Path $hookDir 'stop-sagekit-check.ps1'
$hostExe = (Get-Process -Id $PID).Path

$script:passCount = 0
$script:failCount = 0
$script:lastStderr = ''

function Check([string]$name, [int]$expected, [int]$actual) {
    if ($expected -eq $actual) {
        $script:passCount++
        Write-Host "PASS $name (exit $actual)"
    } else {
        $script:failCount++
        Write-Host "FAIL $name (expected $expected, got $actual)"
    }
}

function Check-Match([string]$name, [string]$pattern) {
    if ($script:lastStderr -match $pattern) { Check $name 0 0 } else { Check $name 0 1 }
}

function Invoke-Hook([string]$hook, [string]$stdin, [string]$workDir) {
    $inFile = [System.IO.Path]::GetTempFileName()
    $errFile = [System.IO.Path]::GetTempFileName()
    $outFile = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText($inFile, $stdin)
    try {
        $p = Start-Process -FilePath $hostExe `
            -ArgumentList ('-NoProfile -NonInteractive -File "{0}"' -f $hook) `
            -WorkingDirectory $workDir -NoNewWindow -Wait -PassThru `
            -RedirectStandardInput $inFile `
            -RedirectStandardError $errFile `
            -RedirectStandardOutput $outFile
        $script:lastStderr = [System.IO.File]::ReadAllText($errFile)
        return $p.ExitCode
    } finally {
        Remove-Item $inFile, $errFile, $outFile -Force -ErrorAction SilentlyContinue
    }
}

$savedStop = $env:SAGE_STOP_CHECK
$savedFake = $env:SAGE_FAKE_RC
$savedPath = $env:PATH
$savedProj = $env:CLAUDE_PROJECT_DIR

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('sagekit-hook-tests-' + [System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $tmp | Out-Null

try {
    # Guard tests rely on the CLAUDE_PROJECT_DIR fallback to the working dir.
    $env:CLAUDE_PROJECT_DIR = $null
    $env:SAGE_STOP_CHECK = $null

    # --- protect-serial-files.ps1: strict, no bypass ---

    $rc = Invoke-Hook $guard '{"tool_input":{"file_path":"docs/ACTIVE_CONTEXT.md"}}' $tmp
    Check 'guard: relative serial path blocked' 2 $rc

    $rc = Invoke-Hook $guard '{"tool_input":{"file_path":"docs\\ACTIVE_CONTEXT.md"}}' $tmp
    Check 'guard: windows separator serial path blocked' 2 $rc

    $rc = Invoke-Hook $guard '{"tool_input":{"file_path":"C:\\proj\\docs\\DOC_ROUTING.md"}}' $tmp
    Check 'guard: absolute serial path blocked' 2 $rc

    $rc = Invoke-Hook $guard '{"tool_input":{"file_path":"docs/sub/../ACTIVE_CONTEXT.md"}}' $tmp
    Check 'guard: dot-segment serial path blocked' 2 $rc

    $rc = Invoke-Hook $guard '{"tool_input":{"file_path":"docs/ACTIVE_CONTEXT.MD"}}' $tmp
    Check 'guard: case-variant serial path blocked' 2 $rc

    $rc = Invoke-Hook $guard '{"tool_input":{"file_path":"src/main.py"}}' $tmp
    Check 'guard: normal file allowed' 0 $rc

    $rc = Invoke-Hook $guard 'not json' $tmp
    Check 'guard: malformed input fails closed' 2 $rc

    $rc = Invoke-Hook $guard '' $tmp
    Check 'guard: empty input fails closed' 2 $rc

    $rc = Invoke-Hook $guard '{"tool_input":{}}' $tmp
    Check 'guard: missing file_path fails closed' 2 $rc

    $rc = Invoke-Hook $guard '{"tool_input":{"file_path":null}}' $tmp
    Check 'guard: null file_path fails closed' 2 $rc

    $rc = Invoke-Hook $guard '{"tool_input":{"file_path":123}}' $tmp
    Check 'guard: non-string file_path fails closed' 2 $rc

    $rc = Invoke-Hook $guard '{"tool_input":{"command":"cat docs/ACTIVE_CONTEXT.md"}}' $tmp
    Check 'guard: bash read of serial file allowed' 0 $rc

    $rc = Invoke-Hook $guard '{"tool_input":{"command":"echo x >> docs/ACTIVE_CONTEXT.md"}}' $tmp
    Check 'guard: bash append to serial file blocked' 2 $rc

    $rc = Invoke-Hook $guard '{"tool_input":{"command":"npm test"}}' $tmp
    Check 'guard: unrelated bash command allowed' 0 $rc

    # --- stop-sagekit-check.ps1 ---

    $gov = Join-Path $tmp 'gov'
    New-Item -ItemType Directory -Path (Join-Path $gov 'docs') -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $gov 'docs/DOC_ROUTING.md') -Force | Out-Null

    $rc = Invoke-Hook $stop '' $gov
    Check 'stop: opt-out passes' 0 $rc

    $env:SAGE_STOP_CHECK = '1'
    $rc = Invoke-Hook $stop '' $gov
    Check 'stop: opted-in without validator fails closed' 2 $rc
    Check-Match 'stop: missing validator reported as handoff' 'HANDOFF'

    $fakeBin = Join-Path $tmp 'bin'
    New-Item -ItemType Directory -Path $fakeBin | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $fakeBin 'sagekit.cmd'), "@echo off`r`nexit /b %SAGE_FAKE_RC%`r`n")
    $env:PATH = $fakeBin + [System.IO.Path]::PathSeparator + $savedPath

    $env:SAGE_FAKE_RC = '0'
    $rc = Invoke-Hook $stop '' $gov
    Check 'stop: validator pass allows stop' 0 $rc

    $env:SAGE_FAKE_RC = '1'
    $rc = Invoke-Hook $stop '' $gov
    Check 'stop: validator findings block stop' 2 $rc
    Check-Match 'stop: exit 1 reported as findings' 'blocking findings'

    $env:SAGE_FAKE_RC = '2'
    $rc = Invoke-Hook $stop '' $gov
    Check 'stop: validator invocation error blocks stop' 2 $rc
    Check-Match 'stop: exit 2 reported as handoff not findings' 'HANDOFF'

    $env:SAGE_FAKE_RC = '3'
    $rc = Invoke-Hook $stop '' $gov
    Check 'stop: validator internal error blocks stop' 2 $rc
    Check-Match 'stop: exit 3 reported as handoff not findings' 'HANDOFF'
} finally {
    $env:SAGE_STOP_CHECK = $savedStop
    $env:SAGE_FAKE_RC = $savedFake
    $env:PATH = $savedPath
    $env:CLAUDE_PROJECT_DIR = $savedProj
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host '---'
Write-Host "PASS=$($script:passCount) FAIL=$($script:failCount)"
if ($script:failCount -gt 0) { exit 1 }
exit 0
