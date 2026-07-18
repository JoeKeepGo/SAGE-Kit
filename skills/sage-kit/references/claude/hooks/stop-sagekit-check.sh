#!/bin/bash
# SAGE-Kit completion gate for Claude Code (Stop hook, opt-in).
#
# Runs `sagekit check` when the repository is SAGE-governed and
# SAGE_STOP_CHECK=1 is set. Blocking findings prevent the session from
# stopping so the agent must resolve or report them first.
#
# Install: copy to .claude/hooks/ and wire in .claude/settings.json (see
# references/claude.md). Off by default; enable only for governed projects.

[ "$SAGE_STOP_CHECK" = "1" ] || exit 0
[ -f docs/DOC_ROUTING.md ] || exit 0

if command -v sagekit >/dev/null 2>&1; then
  sagekit check >/dev/null 2>&1 || {
    echo "sagekit check reported blocking findings. Resolve them or report the gap before claiming DONE." >&2
    exit 2
  }
elif [ -f sagekit/__main__.py ]; then
  python3 -m sagekit check >/dev/null 2>&1 || {
    echo "sagekit check reported blocking findings. Resolve them or report the gap before claiming DONE." >&2
    exit 2
  }
fi

exit 0
