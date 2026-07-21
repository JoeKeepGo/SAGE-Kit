#!/bin/bash
# Negative-path tests for the Claude Code hooks shipped under
# skills/sage-kit/references/claude/hooks/.
#
# Covers the failure modes the worker-scope write guard must not get wrong.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_DIR="$ROOT/skills/sage-kit/references/claude/hooks"
GUARD="$HOOK_DIR/protect-serial-files.sh"
PASS=0; FAIL=0

check() { # name expected_exit actual_exit
  if [ "$2" -eq "$3" ]; then
    PASS=$((PASS+1)); echo "PASS $1 (exit $3)"
  else
    FAIL=$((FAIL+1)); echo "FAIL $1 (expected $2, got $3)"
  fi
}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cd "$TMP" || exit 1

# --- protect-serial-files.sh: strict, no bypass ---

printf '%s\n' '{"tool_input":{"file_path":"docs/ACTIVE_CONTEXT.md"}}' | "$GUARD" >/dev/null 2>&1
check "guard: relative serial path blocked" 2 $?

printf '%s\n' '{"tool_input":{"file_path":"/repo/docs/DOC_ROUTING.md"}}' | "$GUARD" >/dev/null 2>&1
check "guard: absolute serial path blocked" 2 $?

printf '%s\n' '{"tool_input":{"file_path":"docs\\ACTIVE_CONTEXT.md"}}' | "$GUARD" >/dev/null 2>&1
check "guard: windows relative serial path blocked" 2 $?

printf '%s\n' '{"tool_input":{"file_path":"C:\\proj\\docs\\DOC_ROUTING.md"}}' | "$GUARD" >/dev/null 2>&1
check "guard: windows absolute serial path blocked" 2 $?

printf '%s\n' '{"tool_input":{"file_path":"src/main.py"}}' | "$GUARD" >/dev/null 2>&1
check "guard: normal file allowed" 0 $?

printf '%s\n' 'not json' | "$GUARD" >/dev/null 2>&1
check "guard: malformed input fails closed" 2 $?

printf '%s\n' '{"tool_input":{}}' | "$GUARD" >/dev/null 2>&1
check "guard: missing file_path fails closed" 2 $?

printf '%s\n' '{"tool_input":{"file_path":null}}' | "$GUARD" >/dev/null 2>&1
check "guard: null file_path fails closed" 2 $?

printf '%s\n' '{"tool_input":{"file_path":123}}' | "$GUARD" >/dev/null 2>&1
check "guard: non-string file_path fails closed" 2 $?

printf '%s\n' '{"tool_input":{"file_path":"docs/sub/../ACTIVE_CONTEXT.md"}}' | "$GUARD" >/dev/null 2>&1
check "guard: dot-segment serial path blocked" 2 $?

printf '%s\n' '{"tool_input":{"file_path":"docs/ACTIVE_CONTEXT.MD"}}' | "$GUARD" >/dev/null 2>&1
check "guard: case-variant serial path blocked" 2 $?

printf '%s\n' '{"tool_input":{"command":"cat docs/ACTIVE_CONTEXT.md"}}' | "$GUARD" >/dev/null 2>&1
check "guard: bash read of serial file allowed" 0 $?

printf '%s\n' '{"tool_input":{"command":"echo x >> docs/ACTIVE_CONTEXT.md"}}' | "$GUARD" >/dev/null 2>&1
check "guard: bash append to serial file blocked" 2 $?

printf '%s\n' '{"tool_input":{"command":"sed -i s/a/b/ docs/DOC_ROUTING.md"}}' | "$GUARD" >/dev/null 2>&1
check "guard: bash in-place edit of serial file blocked" 2 $?

printf '%s\n' '{"tool_input":{"command":"npm test"}}' | "$GUARD" >/dev/null 2>&1
check "guard: unrelated bash command allowed" 0 $?

grep -q "protect-serial-files" "$ROOT/skills/sage-kit/references/claude/agents/sage-coder.md"
check "guard: bound in sage-coder frontmatter" 0 $?

echo "---"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
