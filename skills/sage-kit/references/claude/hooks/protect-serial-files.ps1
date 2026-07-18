# SAGE-Kit serial-file guard for Claude Code on Windows (PreToolUse hook).
#
# Bind this hook to worker subagents through their frontmatter hooks with
# `shell: powershell` (see references/claude/agents/sage-coder.md), not to
# the controller session. It has no bypass by design: workers can never
# write the controller-owned serial files and must return Memory Update
# Proposals instead.
#
# Fail-closed: malformed hook input blocks the write rather than silently
# allowing it. No jq dependency; ConvertFrom-Json is built in.

$raw = [Console]::In.ReadToEnd()
try {
    $data = $raw | ConvertFrom-Json
    $file = $data.tool_input.file_path
} catch {
    [Console]::Error.WriteLine("Blocked: protect-serial-files received malformed hook input; refusing to fail open.")
    exit 2
}

if (-not $file) { exit 0 }

# Normalize Windows-style separators before matching.
$norm = $file -replace '\\', '/'

if ($norm -match '(^|/)docs/(ACTIVE_CONTEXT|DOC_ROUTING)\.md$') {
    [Console]::Error.WriteLine("Blocked: $norm is a SAGE-Kit controller-owned serial file. Workers must return a Memory Update Proposal instead of editing it.")
    exit 2
}

exit 0
