# SAGE-Kit completion gate for Claude Code on Windows (Stop hook, opt-in).
#
# Runs `sagekit check` when the repository is SAGE-governed and
# SAGE_STOP_CHECK=1 is set. Blocks the stop so the agent must resolve or
# report before claiming DONE.
#
# Exit-code contract of the validator: 0 = pass, 1 = blocking findings,
# anything else = invocation or internal error. The hook fails closed on
# capability gaps and reports them as HANDOFF, never as a pass and never
# mislabeled as findings.

if ($env:SAGE_STOP_CHECK -ne "1") { exit 0 }
if (-not (Test-Path "docs/DOC_ROUTING.md")) { exit 0 }

$rc = $null
if (Get-Command sagekit -ErrorAction SilentlyContinue) {
    sagekit check | Out-Null
    $rc = $LASTEXITCODE
} elseif (Test-Path "sagekit/__main__.py") {
    $py = $null
    if (Get-Command python -ErrorAction SilentlyContinue) { $py = "python" }
    elseif (Get-Command python3 -ErrorAction SilentlyContinue) { $py = "python3" }
    if (-not $py) {
        [Console]::Error.WriteLine("SAGE_STOP_CHECK is set but no Python interpreter is available to run the validator. Report the capability gap (HANDOFF); do not claim DONE.")
        exit 2
    }
    & $py -m sagekit check | Out-Null
    $rc = $LASTEXITCODE
} else {
    [Console]::Error.WriteLine("SAGE_STOP_CHECK is set but no sagekit validator was found (no command on PATH, no source module). Report the capability gap (HANDOFF); do not claim DONE.")
    exit 2
}

switch ($rc) {
    0 { exit 0 }
    1 {
        [Console]::Error.WriteLine("sagekit check reported blocking findings. Resolve them or report the gap before claiming DONE.")
        exit 2
    }
    default {
        [Console]::Error.WriteLine("sagekit check exited $rc`: invocation or internal error, not validation findings. Report HANDOFF; do not claim DONE.")
        exit 2
    }
}
