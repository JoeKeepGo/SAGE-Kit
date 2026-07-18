#!/bin/bash
# SAGE-Kit completion gate for Claude Code (Stop hook, opt-in).
#
# Runs `sagekit check` when the repository is SAGE-governed and
# SAGE_STOP_CHECK=1 is set. Blocking findings prevent the session from
# stopping so the agent must resolve or report them first.
#
# Fail-closed: when the owner opted in but no validator is available (no
# sagekit command, no source module, no Python interpreter), the hook blocks
# and reports the capability gap. A missing validator is never a pass, and a
# capability failure is never reported as a validator finding.
#
# Install: copy to .claude/hooks/ and wire in .claude/settings.json (see
# references/claude.md).

[ "$SAGE_STOP_CHECK" = "1" ] || exit 0
[ -f docs/DOC_ROUTING.md ] || exit 0

RUN=""
if command -v sagekit >/dev/null 2>&1; then
  RUN="sagekit check"
elif [ -f sagekit/__main__.py ]; then
  if command -v python3 >/dev/null 2>&1; then
    RUN="python3 -m sagekit check"
  elif command -v python >/dev/null 2>&1; then
    RUN="python -m sagekit check"
  else
    echo "SAGE_STOP_CHECK is set but no Python interpreter is available to run the validator. Report the capability gap (HANDOFF); do not claim DONE." >&2
    exit 2
  fi
else
  echo "SAGE_STOP_CHECK is set but no sagekit validator was found (no command on PATH, no source module). Report the capability gap (HANDOFF); do not claim DONE." >&2
  exit 2
fi

$RUN >/dev/null 2>&1 || {
  echo "sagekit check reported blocking findings. Resolve them or report the gap before claiming DONE." >&2
  exit 2
}

exit 0
