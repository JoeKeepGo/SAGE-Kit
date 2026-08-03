# SPEC Source Contract

Projects explicitly identify the active SPEC and current authority. Physical
location is provenance, not semantic authority.

<a id="sage-ctx-001"></a>
<a id="sage-ctx-002"></a>
## Selection

1. Use the source explicitly named by current human/project authority.
2. Otherwise use the project's configured active source.
3. Otherwise use the current `ACTIVE_CONTEXT` routing pointer.
4. If required authority remains ambiguous, stop before mutation.

Never try multiple historical documents or schemas until one appears to pass.
Accepted history is reference-only unless an explicit historical audit selects
it. Current validation is active-only by default.

## Source Shape

The active source may be Markdown, JSON, YAML, issue/PR text, or another
project-owned format. Models normalize it conceptually into objective, scope,
acceptance, authority, dependencies, risks, checks, and stop conditions. Add
rollback owner/trigger/procedure/compatibility/post-check fields only for
durable state, public contract, migration, or release change. SAGE-Kit does not require one directory topology or compile it
through a framework runtime.

## Thin Documents

Thin documents remove repeated governance prose. They do not reduce product
design, useful decomposition, acceptance criteria, dependency analysis, or risk
controls. A project may keep detailed
milestone documents without making their layout part of execution identity.
