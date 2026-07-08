from __future__ import annotations


LEGACY_REQUIRED_DOCS = [
    "docs/PROJECT_PROFILE.md",
    "docs/QUALITY_GATES.md",
    "docs/ACTIVE_CONTEXT.md",
    "docs/DOC_ROUTING.md",
]

STANDARD_DOCS = [
    "docs/TECHNICAL_DESIGN.md",
    "docs/ENGINEERING_SYSTEM.md",
    "docs/APPROVAL_GATES.md",
    "docs/MILESTONE_ROADMAP.md",
]

HEAVY_CONTROL_DOCS = [
    "docs/SAGE_CORE.md",
    "docs/agent/GOVERNANCE_LEVELS.md",
    "docs/agent/SESSION_ORCHESTRATION.md",
]

MODES = ("light", "standard", "heavy")


def required_docs_for_mode(mode: str | None) -> list[str]:
    if mode is None or mode == "light":
        return list(LEGACY_REQUIRED_DOCS)
    if mode == "standard":
        return [*LEGACY_REQUIRED_DOCS, *STANDARD_DOCS]
    if mode == "heavy":
        return [*LEGACY_REQUIRED_DOCS, *STANDARD_DOCS, *HEAVY_CONTROL_DOCS]
    raise ValueError(f"unknown SAGE-Kit mode: {mode}")


def recommended_docs_for_mode(mode: str | None) -> list[str]:
    if mode is None:
        return list(STANDARD_DOCS)
    if mode in MODES:
        return []
    raise ValueError(f"unknown SAGE-Kit mode: {mode}")
