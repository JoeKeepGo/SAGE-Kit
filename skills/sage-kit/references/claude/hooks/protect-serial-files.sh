#!/bin/bash
# SAGE-Kit serial-file guard for Claude Code (PreToolUse hook).
#
# Matcher: Edit|Write|MultiEdit
# Blocks writes to controller-owned serial files. Fail-closed: a missing jq
# or malformed hook input blocks the write rather than silently allowing it.
#
# Authorized controller writes use a one-shot token: write the normalized
# target path into .sagekit/runtime/SERIAL_WRITE_TOKEN immediately before the
# edit (for example via Bash). A matching write consumes the token once.
#
# Install: copy to .claude/hooks/ and wire in .claude/settings.json (see
# references/claude.md).

TOKEN_FILE='.sagekit/runtime/SERIAL_WRITE_TOKEN'

block() {
  echo "Blocked: $1" >&2
  exit 2
}

command -v jq >/dev/null 2>&1 || \
  block "protect-serial-files: jq is required but not on PATH; refusing to fail open."

INPUT=$(cat)
FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ $? -eq 0 ] || \
  block "protect-serial-files: malformed hook input; refusing to fail open."

# Normalize Windows-style separators before matching.
NORM=$(printf '%s' "$FILE" | tr '\\' '/')

case "$NORM" in
  */docs/ACTIVE_CONTEXT.md|*/docs/DOC_ROUTING.md|docs/ACTIVE_CONTEXT.md|docs/DOC_ROUTING.md)
    if [ -f "$TOKEN_FILE" ] && [ "$(head -n 1 "$TOKEN_FILE" | tr '\\' '/')" = "$NORM" ]; then
      rm -f "$TOKEN_FILE"
      exit 0
    fi
    block "$NORM is a SAGE-Kit controller-owned serial file. Return a Memory Update Proposal, or create a one-shot token at $TOKEN_FILE naming this path before an authorized write."
    ;;
esac

exit 0
