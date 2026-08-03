# Optional Claude Code advisory hook for exact project-authority paths.
# Preflight and installation are project-owned. SAGE_PROTECTED_PATHS is a
# newline-separated exact path list. This observes structured file_path events
# only; it does not inspect shell text or resolve symlinks/aliases.

$raw = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($env:SAGE_PROTECTED_PATHS)) { exit 0 }

try { $data = $raw | ConvertFrom-Json } catch {
    [Console]::Error.WriteLine('Advisory: malformed hook input; exact-path advisory not applied.')
    exit 0
}

$file = $data.tool_input.file_path
if (-not ($file -is [string]) -or [string]::IsNullOrWhiteSpace($file)) {
    [Console]::Error.WriteLine('Advisory: no structured file_path was available; exact-path advisory not applied.')
    exit 0
}

$base = $env:CLAUDE_PROJECT_DIR
if (-not $base) { $base = (Get-Location).Path }
function Canon([string]$path) {
    if (-not [System.IO.Path]::IsPathRooted($path)) { $path = Join-Path $base $path }
    return [System.IO.Path]::GetFullPath($path)
}

$target = Canon $file
foreach ($configured in ($env:SAGE_PROTECTED_PATHS -split "`r?`n")) {
    if ([string]::IsNullOrWhiteSpace($configured)) { continue }
    if ([string]::Equals($target, (Canon $configured), [System.StringComparison]::OrdinalIgnoreCase)) {
        [Console]::Error.WriteLine("Advisory: $file matches an exact project-authority protected path. Return an update proposal.")
        exit 2
    }
}
exit 0
