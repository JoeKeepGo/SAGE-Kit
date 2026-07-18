#!/bin/bash
# SAGE-Kit serial-file guard for Claude Code (PreToolUse hook).
#
# Bind this hook to worker subagents through their frontmatter hooks (see
# references/claude/agents/sage-coder.md), not to the controller session.
#
# Boundary honesty:
# - Structured edit tools (Edit/Write/MultiEdit): hard boundary. Paths are
#   canonicalized against CLAUDE_PROJECT_DIR before comparison, so
#   dot segments and separator variants collapse lexically (symlinks are
#   not resolved). The
#   comparison is lane-wide and case-insensitive: any canonical path ending
#   in docs/ACTIVE_CONTEXT.md or docs/DOC_ROUTING.md is blocked, whatever
#   its root, because a worker never owns a governance serial file.
# - Bash: best-effort heuristic. Commands that mention a serial file and
#   contain a write-shaped operator are blocked, but shell string matching
#   is evadable by design. Lanes that need a hard shell-level boundary must
#   use a worker without Bash and let the controller run verification.
#
# Fail-closed: missing jq, malformed input, or a missing/non-string
# file_path blocks the operation rather than silently allowing it.

block() {
  echo "Blocked: $1" >&2
  exit 2
}

command -v jq >/dev/null 2>&1 || \
  block "protect-serial-files requires jq on PATH; refusing to fail open."

INPUT=$(cat)
printf '%s' "$INPUT" | jq -e . >/dev/null 2>&1 || \
  block "protect-serial-files received malformed hook input; refusing to fail open."

BASE="${CLAUDE_PROJECT_DIR:-$PWD}"

# Lexically canonicalize a path: normalize separators, resolve against BASE
# when relative, and collapse dot segments. No filesystem access required.
canon() {
  printf '%s\n' "$1" | tr '\\' '/' | awk -v base="$BASE" '
    {
      p = $0
      gsub(/\\/, "/", base)
      if (substr(p, 1, 1) != "/") p = base "/" p
      n = split(p, seg, "/")
      delete st; j = 0
      for (i = 1; i <= n; i++) {
        s = seg[i]
        if (s == "" || s == ".") continue
        if (s == "..") { if (j > 0) j--; continue }
        st[++j] = s
      }
      out = ""
      for (i = 1; i <= j; i++) out = out "/" st[i]
      print (out == "" ? "/" : out)
    }'
}

# Bash layer (best-effort): the command is a free-form string. Mentions of
# serial files combined with write-shaped operators are blocked; reads pass.
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
if [ -n "$COMMAND" ]; then
  NCMD=$(printf '%s' "$COMMAND" | tr '\\' '/')
  if printf '%s' "$NCMD" | grep -qiE 'ACTIVE_CONTEXT\.md|DOC_ROUTING\.md' \
    && printf '%s' "$NCMD" | grep -qE '>>?|sed[[:space:]]+(-i|--in-place)|perl[[:space:]]+-[^[:space:]]*i|(^|[[:space:]])(rm|mv|cp|dd|ln|install|tee|truncate|chmod|chown)([[:space:]]|$)'; then
    block "command appears to write a controller-owned serial file. Workers must return a Memory Update Proposal instead."
  fi
  exit 0
fi

# Structured edit layer: file_path is mandatory and must be a string.
FTYPE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path | type')
[ "$FTYPE" = "string" ] || \
  block "protect-serial-files: missing or non-string file_path; refusing to fail open."

FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path')
TARGET=$(canon "$FILE")

# Lane-wide policy: a worker never writes any governance serial file,
# whatever the root. Compare case-insensitively: on case-insensitive
# filesystems (default APFS, NTFS) case variants resolve to the same file.
LC_TARGET=$(printf '%s' "$TARGET" | tr 'A-Z' 'a-z')
case "$LC_TARGET" in
  */docs/active_context.md|*/docs/doc_routing.md)
    block "$FILE resolves to a SAGE-Kit controller-owned serial file (canonical: $TARGET). Workers must return a Memory Update Proposal instead of editing it."
    ;;
esac

exit 0
