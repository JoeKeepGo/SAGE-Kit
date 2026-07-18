# SAGE-Kit serial-file guard for Claude Code on Windows (PreToolUse hook).
#
# Bind this hook to worker subagents through their frontmatter hooks with
# `shell: powershell` (see references/claude/agents/sage-coder.md), not to
# the controller session.
#
# Boundary honesty:
# - Structured edit tools (Edit/Write/MultiEdit): hard boundary. Paths are
#   canonicalized against CLAUDE_PROJECT_DIR before comparison, so
#   dot-segment and separator tricks resolve to their real target. The
#   comparison is lane-wide and case-insensitive: any canonical path ending
#   in docs/ACTIVE_CONTEXT.md or docs/DOC_ROUTING.md is blocked, whatever
#   its root, because a worker never owns a governance serial file.
# - Bash: best-effort heuristic. Commands that mention a serial file and
#   contain a write-shaped operator are blocked, but shell string matching
#   is evadable by design. Lanes that need a hard shell-level boundary must
#   use a worker without Bash and let the controller run verification.
#
# Fail-closed: malformed input or a missing/non-string file_path blocks the
# operation rather than silently allowing it. No jq dependency;
# ConvertFrom-Json is built in.

$raw = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($raw)) {
    [Console]::Error.WriteLine("Blocked: protect-serial-files received empty hook input; refusing to fail open.")
    exit 2
}
try {
    $data = $raw | ConvertFrom-Json
} catch {
    [Console]::Error.WriteLine("Blocked: protect-serial-files received malformed hook input; refusing to fail open.")
    exit 2
}
if ($null -eq $data -or $null -eq $data.tool_input) {
    [Console]::Error.WriteLine("Blocked: protect-serial-files received malformed hook input; refusing to fail open.")
    exit 2
}

$base = $env:CLAUDE_PROJECT_DIR
if (-not $base) { $base = (Get-Location).Path }
$base = ($base -replace '\\', '/').TrimEnd('/')

function Canon([string]$p) {
    $p = $p -replace '\\', '/'
    if (-not [System.IO.Path]::IsPathRooted($p)) { $p = "$base/$p" }
    return ([System.IO.Path]::GetFullPath($p) -replace '\\', '/')
}

# Bash layer (best-effort): mentions of serial files combined with
# write-shaped operators are blocked; reads pass.
$cmd = $data.tool_input.command
if ($cmd) {
    $ncmd = "$cmd" -replace '\\', '/'
    if (($ncmd -match 'ACTIVE_CONTEXT\.md|DOC_ROUTING\.md') -and
        ($ncmd -match '>>?|sed\s+(-i|--in-place)|perl\s+-\S*i|(^|\s)(rm|mv|cp|dd|ln|install|tee|truncate|chmod|chown)(\s|$)')) {
        [Console]::Error.WriteLine("Blocked: command appears to write a controller-owned serial file. Workers must return a Memory Update Proposal instead.")
        exit 2
    }
    exit 0
}

# Structured edit layer: file_path is mandatory and must be a string.
$fileProp = $data.tool_input.file_path
if ($null -eq $fileProp -or -not ($fileProp -is [string]) -or [string]::IsNullOrWhiteSpace($fileProp)) {
    [Console]::Error.WriteLine("Blocked: protect-serial-files: missing or non-string file_path; refusing to fail open.")
    exit 2
}

# Lane-wide policy: a worker never writes any governance serial file,
# whatever the root. Compare case-insensitively: on NTFS case variants
# resolve to the same file.
$target = Canon $fileProp
$lcTarget = $target.ToLowerInvariant()
if ($lcTarget.EndsWith('/docs/active_context.md') -or $lcTarget.EndsWith('/docs/doc_routing.md')) {
    [Console]::Error.WriteLine("Blocked: $fileProp resolves to a SAGE-Kit controller-owned serial file (canonical: $target). Workers must return a Memory Update Proposal instead of editing it.")
    exit 2
}

exit 0
