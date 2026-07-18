#!/bin/bash
# SAGE-Kit serial-file guard for Claude Code (PreToolUse hook).
#
# Matcher: Edit|Write|MultiEdit
# Blocks writes to controller-owned serial files unless the controller set
# SAGE_SERIAL_WRITE=1 for an authorized write. Workers must return a Memory
# Update Proposal instead of editing these files.
#
# Install: copy to .claude/hooks/ and wire in .claude/settings.json (see
# references/claude.md). Requires jq on PATH.

INPUT=$(cat)
FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')

[ "$SAGE_SERIAL_WRITE" = "1" ] && exit 0

case "$FILE" in
  */docs/ACTIVE_CONTEXT.md|*/docs/DOC_ROUTING.md|docs/ACTIVE_CONTEXT.md|docs/DOC_ROUTING.md)
    echo "Blocked: $FILE is a SAGE-Kit controller-owned serial file. Return a Memory Update Proposal instead." >&2
    exit 2
    ;;
esac

exit 0
