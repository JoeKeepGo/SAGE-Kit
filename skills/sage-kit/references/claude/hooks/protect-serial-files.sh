#!/bin/sh
# Optional Claude Code advisory hook for exact project-authority paths.
# Preflight and installation are project-owned. Set SAGE_PROTECTED_PATHS to a
# newline-separated list of exact relative or absolute paths. This hook observes
# structured file_path events only. It does not inspect shell text or resolve
# symlinks/aliases and is never a hard containment boundary.

warn() { printf 'Advisory: %s\n' "$1" >&2; }

[ -n "${SAGE_PROTECTED_PATHS:-}" ] || exit 0
input=$(cat)
file=$(printf '%s' "$input" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | sed -n '1p')
if [ -z "$file" ]; then
  warn 'no structured file_path was available; exact-path advisory not applied.'
  exit 0
fi

base=${CLAUDE_PROJECT_DIR:-$PWD}
canon() {
  printf '%s\n' "$1" | tr '\\' '/' | awk -v base="$base" '
    {
      p = $0; gsub(/\\/, "/", base)
      if (substr(p, 1, 1) != "/" && p !~ /^[A-Za-z]:\//) p = base "/" p
      n = split(p, seg, "/"); delete st; j = 0
      for (i = 1; i <= n; i++) {
        s = seg[i]; if (s == "" || s == ".") continue
        if (s == "..") { if (j > 0) j--; continue }
        st[++j] = s
      }
      out = (p ~ /^[A-Za-z]:\// ? st[1] : "")
      start = (p ~ /^[A-Za-z]:\// ? 2 : 1)
      for (i = start; i <= j; i++) out = out "/" st[i]
      print (out == "" ? "/" : out)
    }'
}

target=$(canon "$file")
old_ifs=$IFS
IFS='
'
for configured in $SAGE_PROTECTED_PATHS; do
  [ -n "$configured" ] || continue
  if [ "$target" = "$(canon "$configured")" ]; then
    warn "$file matches an exact project-authority protected path. Return an update proposal."
    exit 2
  fi
done
IFS=$old_ifs
exit 0
