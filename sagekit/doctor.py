from __future__ import annotations

import platform
from pathlib import Path

from .check import RECOMMENDED_DOCS, REQUIRED_DOCS, detect_root, relpath
from .findings import Finding


def run_doctor(start: Path) -> list[Finding]:
    root = detect_root(start)
    findings: list[Finding] = [
        Finding("PASS", "project-root", relpath(root, root), None, f"using {root}"),
        Finding("PASS", "python-runtime", None, None, f"Python {platform.python_version()}"),
    ]
    source_repo = is_kit_source_repo(root)
    findings.extend(check_project_mode(root, source_repo))
    findings.extend(check_adoption_docs(root, source_repo))
    findings.extend(check_package_entrypoint(root, source_repo))
    findings.extend(check_task_dispatch_runtime())
    return findings


def is_kit_source_repo(root: Path) -> bool:
    return (
        (root / "docs/SAGE_CORE.md").exists()
        and (root / "skills/sage-kit/SKILL.md").exists()
        and (root / "docs/PROJECT_PROFILE_TEMPLATE.md").exists()
    )


def check_project_mode(root: Path, source_repo: bool) -> list[Finding]:
    if source_repo:
        return [
            Finding(
                "PASS",
                "kit-source",
                relpath(root, root / "docs/SAGE_CORE.md"),
                None,
                "SAGE-Kit source repository detected",
                "Use sagekit check against adopted project repositories; use doctor for source repo diagnostics.",
            )
        ]
    missing_required = [item for item in REQUIRED_DOCS if not (root / item).exists()]
    if not missing_required:
        return [
            Finding(
                "PASS",
                "adopted-project",
                "docs/",
                None,
                "SAGE-Kit adopted project documents detected",
            )
        ]
    return [
        Finding(
            "WARN",
            "project-mode",
            relpath(root, root),
            None,
            "not a SAGE-Kit source repository and required project docs are incomplete",
            "Adopt SAGE-Kit documents or run doctor from the intended repository root.",
        )
    ]


def check_adoption_docs(root: Path, source_repo: bool) -> list[Finding]:
    missing_required = [item for item in REQUIRED_DOCS if not (root / item).exists()]
    missing_recommended = [item for item in RECOMMENDED_DOCS if not (root / item).exists()]
    findings: list[Finding] = []

    if missing_required:
        suggestion = (
            "Source repositories may keep templates without instantiated project docs."
            if source_repo
            else "Create required SAGE-Kit project docs before using sagekit check as a gate."
        )
        findings.append(
            Finding(
                "WARN",
                "adoption-required-docs",
                "docs/",
                None,
                "missing required project docs: " + ", ".join(missing_required),
                suggestion,
            )
        )
    else:
        findings.append(Finding("PASS", "adoption-required-docs", "docs/", None, "required project docs exist"))

    if missing_recommended:
        findings.append(
            Finding(
                "WARN",
                "adoption-recommended-docs",
                "docs/",
                None,
                "missing recommended project docs: " + ", ".join(missing_recommended),
                "Add them when this project needs Standard or Heavy governance depth.",
            )
        )
    else:
        findings.append(
            Finding("PASS", "adoption-recommended-docs", "docs/", None, "recommended project docs exist")
        )

    return findings


def check_package_entrypoint(root: Path, source_repo: bool) -> list[Finding]:
    if not source_repo:
        return []
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return [
            Finding(
                "WARN",
                "package-entrypoint",
                "pyproject.toml",
                None,
                "pyproject.toml missing",
                "Define a console script so macOS, Linux, and Windows share one sagekit command path.",
            )
        ]
    text = pyproject.read_text(encoding="utf-8", errors="replace")
    if 'sagekit = "sagekit.cli:main"' in text:
        return [
            Finding(
                "PASS",
                "package-entrypoint",
                "pyproject.toml",
                None,
                "console script maps sagekit to sagekit.cli:main",
            )
        ]
    return [
        Finding(
            "WARN",
            "package-entrypoint",
            "pyproject.toml",
            None,
            "console script missing or points somewhere else",
            'Add [project.scripts] sagekit = "sagekit.cli:main".',
        )
    ]


def check_task_dispatch_runtime() -> list[Finding]:
    try:
        from .task_dispatch_validator import validate_records

        if not callable(validate_records):
            raise TypeError("validate_records is not callable")
    except Exception as exc:
        return [
            Finding(
                "FAIL",
                "task-dispatch-runtime",
                None,
                None,
                f"Task Dispatch validator unavailable: {exc}",
            )
        ]
    return [Finding("PASS", "task-dispatch-runtime", None, None, "Task Dispatch validator is importable")]
