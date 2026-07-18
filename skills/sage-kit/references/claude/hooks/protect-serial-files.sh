#!/bin/bash
# SAGE-Kit serial-file guard for Claude Code (PreToolUse hook).
#
# Bind this hook to worker subagents through their frontmatter hooks (see
# references/claude/agents/sage-coder.md), not to the controller session.
# It has no bypass by design: workers can never write the controller-owned
# serial files and must return Memory Update Proposals instead. The
# controller session does not load this hook, so legitimate controller
# writes are unaffected.
#
# Fail-closed: a missing jq or malformed hook input blocks the write rather
# than silently allowing it.

command -v jq >/dev/null 2>&1 || {
  echo "Blocked: protect-serial-files requires jq on PATH; refusing to fail open." >&2
  exit 2
}

INPUT=$(cat)
FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ $? -eq 0 ] || {
  echo "Blocked: protect-serial-files received malformed hook input; refusing to fail open." >&2
  exit 2
}

# Normalize Windows-style separators before matching.
NORM=$(printf '%s' "$FILE" | tr '\\' '/')

case "$NORM" in
  */docs/ACTIVE_CONTEXT.md|*/docs/DOC_ROUTING.md|docs/ACTIVE_CONTEXT.md|docs/DOC_ROUTING.md)
    echo "Blocked: $NORM is a SAGE-Kit controller-owned serial file. Workers must return a Memory Update Proposal instead of editing it." >&2
    exit 2
    ;;
esac

exit 0
