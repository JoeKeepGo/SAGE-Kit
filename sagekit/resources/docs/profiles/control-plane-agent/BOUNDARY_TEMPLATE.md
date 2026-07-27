# Boundary Template (Compatibility Alias)

`BOUNDARY_TEMPLATE.md` remains a stable compatibility pointer to the canonical
`docs/profiles/control-plane-agent/CONTROL_BOUNDARY_TEMPLATE.md`. Use the
canonical template for its components,
trust boundary, forbidden paths, and contract-owner fields; this alias creates
no second boundary authority.

The canonical template records only this profile's project-specific capability
and authority delta. Core authority is canonical at
`docs/SAGE_CORE.md#sage-auth-001`, adapter authority at
`docs/agent/CAPABILITY_ADAPTERS.md#sage-adp-003`, Graph semantics at
`docs/SAGE_CORE.md#sage-grf-001`, and execution-loop semantics at
`docs/agent/PHASE_EXECUTION.md#execution-loop`.

This file's presence does not activate the control-plane-agent profile; project
authority must activate any optional profile explicitly.
