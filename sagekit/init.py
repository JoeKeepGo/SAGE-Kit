from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
import re

from .check import detect_root, is_kit_source_repo, relpath
from .findings import Finding
from .modes import HEAVY_CONTROL_DOCS, LEGACY_REQUIRED_DOCS, MODES, STANDARD_DOCS
from .spec_sources import CONFIG_NAME, package_identity


SOURCE_TEMPLATE_MAP = {
    "docs/SAGE_CORE.md": "docs/SAGE_CORE.md",
    "docs/PROJECT_PROFILE.md": "docs/PROJECT_PROFILE_TEMPLATE.md",
    "docs/QUALITY_GATES.md": "docs/QUALITY_GATES_TEMPLATE.md",
    "docs/ACTIVE_CONTEXT.md": "docs/ACTIVE_CONTEXT_TEMPLATE.md",
    "docs/DOC_ROUTING.md": "docs/DOC_ROUTING_TEMPLATE.md",
    "docs/TECHNICAL_DESIGN.md": "docs/TECHNICAL_DESIGN_TEMPLATE.md",
    "docs/ENGINEERING_SYSTEM.md": "docs/ENGINEERING_SYSTEM_TEMPLATE.md",
    "docs/APPROVAL_GATES.md": "docs/APPROVAL_GATES_TEMPLATE.md",
    "docs/MILESTONE_ROADMAP.md": "docs/templates/MILESTONE_ROADMAP_TEMPLATE.md",
}

OPTIONAL_TEMPLATE_DOCS = [
    "docs/templates/ENTRY_GATE_TEMPLATE.md",
    "docs/templates/PHASE_TEMPLATE.md",
    "docs/templates/MILESTONE_LEDGER_TEMPLATE.md",
    "docs/templates/MILESTONE_CLOSEOUT_TEMPLATE.md",
    "docs/templates/COMPLETION_REPORT_TEMPLATE.md",
]

HEAVY_TEMPLATE_DOCS = [
    "docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md",
    "docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md",
    "docs/templates/STRUCTURAL_GATE_TEMPLATE.md",
    "docs/templates/FINAL_REVIEW_PACKET_TEMPLATE.md",
    "docs/templates/CORRECTIVE_PACKET_TEMPLATE.md",
]


@dataclass(frozen=True)
class InitFile:
    destination: str
    source: str | None = None


def run_init(
    start: Path,
    mode: str,
    dry_run: bool = False,
    force: bool = False,
    exact_root: bool = False,
    profile: str = "package-bound",
) -> list[Finding]:
    if mode not in MODES:
        raise ValueError(f"unknown SAGE-Kit mode: {mode}")
    if profile not in {"package-bound", "vendored-legacy"}:
        raise ValueError(f"unknown SAGE-Kit adoption profile: {profile}")

    root = start.resolve(strict=False) if exact_root else detect_root(start)
    source_root = package_resource_root()
    findings: list[Finding] = [
        Finding("PASS", "project-root", relpath(root, root), None, f"using {root}"),
        Finding("PASS", "init-mode", None, None, f"mode: {mode}"),
        Finding("PASS", "init-profile", None, None, f"profile: {profile}"),
    ]
    detected_root = detect_root(root)
    if is_kit_source_repo(root) or is_kit_source_repo(detected_root):
        return [
            *findings,
            Finding(
                "FAIL",
                "init-source-repo",
                relpath(root, detected_root / "docs/SAGE_CORE.md"),
                None,
                "refusing to initialize inside the SAGE-Kit source repository",
                "Run init from the project that will adopt SAGE-Kit.",
            ),
        ]

    files = init_files_for_mode(mode, source_root, profile=profile)
    findings.append(
        Finding(
            "PASS",
            "init-plan",
            None,
            None,
            f"{'would create or update' if dry_run else 'create or update'} {len(files)} files",
        )
    )

    for item in files:
        findings.append(apply_init_file(root, source_root, item, dry_run=dry_run, force=force))

    findings.append(
        Finding(
            "PASS",
            "init-next-step",
            None,
            None,
            "inspect the generated project authority, then fill project-specific placeholders before executable milestone planning",
        )
    )
    return findings


def init_files_for_mode(
    mode: str, source_root: Path, *, profile: str = "package-bound"
) -> list[InitFile]:
    if profile == "package-bound":
        return [
            InitFile(CONFIG_NAME),
            InitFile("docs/ACTIVE_CONTEXT.md"),
            InitFile("docs/DOC_ROUTING.md"),
        ]
    if profile != "vendored-legacy":
        raise ValueError(f"unknown SAGE-Kit adoption profile: {profile}")
    destinations = [
        "docs/SAGE_CORE.md",
        *LEGACY_REQUIRED_DOCS,
        "docs/agent/GOVERNANCE_LEVELS.md",
    ]
    if mode in {"standard", "heavy"}:
        destinations.extend(STANDARD_DOCS)
    if mode == "heavy":
        destinations.extend(HEAVY_CONTROL_DOCS)

    files = [
        InitFile(destination=destination, source=SOURCE_TEMPLATE_MAP.get(destination, destination))
        for destination in destinations
    ]
    template_docs = list(OPTIONAL_TEMPLATE_DOCS)
    if mode == "heavy":
        template_docs.extend(HEAVY_TEMPLATE_DOCS)
    files.extend(InitFile(destination=path, source=path) for path in template_docs)
    return dedupe(files)


def package_resource_root() -> Path:
    return Path(str(resources.files("sagekit").joinpath("resources")))


def dedupe(files: list[InitFile]) -> list[InitFile]:
    seen: set[str] = set()
    result: list[InitFile] = []
    for item in files:
        if item.destination in seen:
            continue
        seen.add(item.destination)
        result.append(item)
    return result


def apply_init_file(
    root: Path,
    source_root: Path,
    item: InitFile,
    dry_run: bool,
    force: bool,
) -> Finding:
    destination = root / item.destination
    display = item.destination
    unsafe = unsafe_target_reason(root, destination)
    if unsafe:
        return Finding(
            "FAIL",
            "init-unsafe-target",
            display,
            None,
            unsafe,
            "Remove or replace the unsafe target before running init.",
        )
    exists = destination.exists()
    content, error = read_template_or_fallback(
        source_root, item, project_root=root
    )
    if error:
        return Finding("FAIL", "init-missing-resource", display, None, error)

    if exists and not force:
        return Finding(
            "WARN",
            "init-skip-existing",
            display,
            None,
            f"{display} exists; left unchanged",
            "Use --force to overwrite this file.",
        )
    if dry_run:
        action = "overwrite" if exists else "create"
        return Finding("PASS", "init-dry-run", display, None, f"would {action} {display}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return Finding("PASS", "init-write", display, None, f"{'overwrote' if exists else 'created'} {display}")


def unsafe_target_reason(root: Path, destination: Path) -> str | None:
    root_resolved = root.resolve()
    destination_resolved = destination.resolve(strict=False)
    if not destination_resolved.is_relative_to(root_resolved):
        return f"{destination} resolves outside the project root"
    if destination.is_symlink():
        return f"{destination} is a symlink or reparse target"
    if not destination.exists():
        return None
    if not destination.is_file():
        return f"{destination} exists but is not a regular file"
    return None


def read_template_or_fallback(
    source_root: Path,
    item: InitFile,
    *,
    project_root: Path | None = None,
) -> tuple[str | None, str | None]:
    if item.destination == CONFIG_NAME and item.source is None:
        payload = {
            "schema_version": 1,
            "project_id": _project_id(project_root),
            "adoption_profile": "package-bound",
            "execution_scope": "active-only",
            "active_context": "docs/ACTIVE_CONTEXT.md",
            "doc_routing": "docs/DOC_ROUTING.md",
            "package": package_identity(),
            "sources": {},
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n", None
    if item.destination == "docs/ACTIVE_CONTEXT.md" and item.source is None:
        return FALLBACK_CONTENT[item.destination].rstrip() + "\n", None
    if item.destination == "docs/DOC_ROUTING.md" and item.source is None:
        return FALLBACK_CONTENT[item.destination].rstrip() + "\n", None
    if item.source:
        source = source_root / item.source
        if source.exists() and source.is_file():
            return normalize_template(source.read_text(encoding="utf-8", errors="replace"), item.destination), None
    fallback = fallback_content(item.destination)
    if fallback:
        return fallback, None
    return None, f"missing packaged SAGE-Kit resource for {item.destination}"


def _project_id(root: Path | None) -> str:
    name = (root.name if root is not None else "project").casefold()
    normalized = re.sub(r"[^a-z0-9._-]+", "-", name).strip("-._")
    return (normalized or "project")[:128]


def normalize_template(text: str, destination: str) -> str:
    text = text.replace(" Template", "")
    if destination == "docs/ACTIVE_CONTEXT.md":
        text = text.replace("<absolute path>", "<project path>")
    return text.rstrip() + "\n"


def fallback_content(destination: str) -> str:
    fallback = FALLBACK_CONTENT.get(destination)
    if fallback:
        return fallback.rstrip() + "\n"
    return ""


FALLBACK_CONTENT = {
    "docs/PROJECT_PROFILE.md": """# Project Profile

Generated by the optional legacy adoption helper.

## Product Summary

Replace this starter content with project-specific goals, users, constraints, and non-goals.
""",
    "docs/QUALITY_GATES.md": """# Quality Gates

Generated by the optional legacy adoption helper.

Tests and runtime smoke must be recorded before work is called complete, or marked N/A with a concrete reason.
""",
    "docs/ACTIVE_CONTEXT.md": """# Active Context

Current milestone: none
Current wave/phase: none
Current state: idle
Current authority: SAGEKIT_CONFIG.json
Blockers: none
Next action: register an ACTIVE_SPEC source when work is authorized
Key decisions: package-bound SAGE-Kit runtime
Evidence/closeout pointers: none
""",
    "docs/DOC_ROUTING.md": """# Document Routing

Routing policy:

- Current execution reads ACTIVE_CONTEXT, the selected ACTIVE_SPEC, exact dependencies, and required evidence.
- ACCEPTED_HISTORY and REFERENCE_ONLY material are read only by precise pointer or explicit history audit.
- Runtime candidate, checkpoint, lease, attempt, and verification state stays under `.sagekit`.
""",
}
