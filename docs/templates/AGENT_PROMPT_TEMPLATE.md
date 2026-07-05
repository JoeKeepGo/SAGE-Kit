# Agent Prompt Template

Use this template to start a focused AI agent task.

```markdown
You are working inside a SPEC-Kit governed project.

Strict Mode:
- The controller or human decides whether this task uses Strict Mode according
  to `docs/agent/MODEL_ASSURANCE_POLICY.md`.
- In Strict Mode, read only listed files, modify only allowed files, run exact
  commands, and stop on ambiguity or failed verification.

Read first:
- docs/ACTIVE_CONTEXT.md
- docs/DOC_ROUTING.md
- docs/QUALITY_GATES.md
- docs/agent/MODEL_ASSURANCE_POLICY.md
- docs/agent/STRICT_MODE.md
- docs/agent/WAVE_EXECUTION.md
- docs/agent/MILESTONE_PLANNING.md
- <active milestone ledger>
- <active phase doc>

Objective:
- <one objective>

Allowed files:
- <files>

Read-only files:
- <files>

Forbidden files:
- <files>

Contracts:
- <contract owner and consumer>

Tests:
- <commands>

Runtime smoke:
- <commands or not applicable reason>

Wave / lane assignment:
- <lane name, allowed files, expected output, or serial-only>

Approval gates:
- <closed gates>

Return format:
- Use `docs/templates/LANE_PACKET_TEMPLATE.md` for lane work.
- Use `docs/agent/HANDOFF_TEMPLATE.md` for phase or session handoff.
```
