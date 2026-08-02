#!/bin/sh
# Tests for the optional exact-path Claude advisory hook.
set -u

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
GUARD="$ROOT/skills/sage-kit/references/claude/hooks/protect-serial-files.sh"
PASS=0
FAIL=0
check() {
  if [ "$2" -eq "$3" ]; then PASS=$((PASS+1)); printf 'PASS %s\n' "$1"
  else FAIL=$((FAIL+1)); printf 'FAIL %s (expected %s, got %s)\n' "$1" "$2" "$3"; fi
}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cd "$TMP" || exit 1
CLAUDE_PROJECT_DIR=$TMP
export CLAUDE_PROJECT_DIR
SAGE_PROTECTED_PATHS="docs/ACTIVE_CONTEXT.md
docs/DOC_ROUTING.md"
export SAGE_PROTECTED_PATHS

printf '%s\n' '{"tool_input":{"file_path":"docs/ACTIVE_CONTEXT.md"}}' | "$GUARD" >/dev/null 2>&1
check 'exact configured relative path blocked' 2 $?

printf '%s\n' '{"tool_input":{"file_path":"docs/sub/../DOC_ROUTING.md"}}' | "$GUARD" >/dev/null 2>&1
check 'exact configured canonical path blocked' 2 $?

printf '%s\n' '{"tool_input":{"file_path":"elsewhere/docs/ACTIVE_CONTEXT.md"}}' | "$GUARD" >/dev/null 2>&1
check 'same filename outside configured path allowed' 0 $?

printf '%s\n' '{"tool_input":{"command":"echo x >> docs/ACTIVE_CONTEXT.md"}}' | "$GUARD" >/dev/null 2>&1
check 'shell text is not heuristically inspected' 0 $?

printf '%s\n' 'not json' | "$GUARD" >/dev/null 2>&1
check 'unsupported event shape remains advisory' 0 $?

unset SAGE_PROTECTED_PATHS
printf '%s\n' '{"tool_input":{"file_path":"docs/ACTIVE_CONTEXT.md"}}' | "$GUARD" >/dev/null 2>&1
check 'unconfigured hook allows path' 0 $?

printf 'PASS=%s FAIL=%s\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
