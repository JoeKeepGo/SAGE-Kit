#!/bin/bash
# Negative-path tests for the Claude Code hooks shipped under
# skills/sage-kit/references/claude/hooks/.
#
# Covers the failure modes a governance hook must not get wrong:
# Windows path separators, malformed hook input, missing validator,
# one-shot token consumption, and validator finding propagation.

set -u

HOOK_DIR="$(cd "$(dirname "$0")/../skills/sage-kit/references/claude/hooks" && pwd)"
GUARD="$HOOK_DIR/protect-serial-files.sh"
STOP="$HOOK_DIR/stop-sagekit-check.sh"
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

# --- protect-serial-files.sh ---

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

mkdir -p .sagekit/runtime
echo "docs/ACTIVE_CONTEXT.md" > .sagekit/runtime/SERIAL_WRITE_TOKEN
printf '%s\n' '{"tool_input":{"file_path":"docs/ACTIVE_CONTEXT.md"}}' | "$GUARD" >/dev/null 2>&1
check "guard: one-shot token allows matching write" 0 $?

[ ! -f .sagekit/runtime/SERIAL_WRITE_TOKEN ]
check "guard: token consumed after use" 0 $?

printf '%s\n' '{"tool_input":{"file_path":"docs/ACTIVE_CONTEXT.md"}}' | "$GUARD" >/dev/null 2>&1
check "guard: write blocked after token consumed" 2 $?

# --- stop-sagekit-check.sh ---

mkdir -p "$TMP/plain" && cd "$TMP/plain" || exit 1
"$STOP" >/dev/null 2>&1
check "stop: opt-out passes" 0 $?

mkdir -p "$TMP/gov-no-validator/docs" && cd "$TMP/gov-no-validator" || exit 1
touch docs/DOC_ROUTING.md
SAGE_STOP_CHECK=1 "$STOP" >/dev/null 2>&1
check "stop: opted-in without validator fails closed" 2 $?

mkdir -p "$TMP/gov-ok/docs" "$TMP/gov-ok/bin" && cd "$TMP/gov-ok" || exit 1
touch docs/DOC_ROUTING.md
printf '#!/bin/bash\nexit 0\n' > bin/sagekit && chmod +x bin/sagekit
SAGE_STOP_CHECK=1 PATH="$TMP/gov-ok/bin:/usr/bin:/bin" "$STOP" >/dev/null 2>&1
check "stop: validator pass allows stop" 0 $?

printf '#!/bin/bash\nexit 1\n' > bin/sagekit
SAGE_STOP_CHECK=1 PATH="$TMP/gov-ok/bin:/usr/bin:/bin" "$STOP" >/dev/null 2>&1
check "stop: validator findings block stop" 2 $?

echo "---"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
