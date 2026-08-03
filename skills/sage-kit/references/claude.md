# Claude Code

Use Claude Code agents, tool permissions, and optional hooks as host adapters
to the same project authority. The generic agents do not bind hooks by default.

The shipped coder and final-review examples preserve role separation. A project
may explicitly install the path hook only after preflight confirms the host
emits a structured `file_path`, the matching Shell/PowerShell implementation is
available, and project authority supplies exact protected paths through the
newline-separated `SAGE_PROTECTED_PATHS` setting.

The hook is `MANAGED` advisory defense for observed structured edit events. It
does not parse Bash command text, resolve symlinks/aliases, cover unobserved
tools, or grant authority. Same-named files outside the exact configured paths
are allowed. A hard boundary requires host-enforced path permissions or a
worker with no shell/write escape path. Run the matching hook test after
installation and report unsupported event shapes as a limitation.

Claude session continuation is not project truth. Reconcile the project-owned
active context, repository state, and evidence on resume. Unsupported host
features are limitations, not inferred enforcement.
