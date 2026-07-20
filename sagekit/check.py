from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Iterable

from .findings import Finding
from .modes import LEGACY_REQUIRED_DOCS, MODES, STANDARD_DOCS, recommended_docs_for_mode, required_docs_for_mode
from .managed_execution import ManagedExecutionError, run_managed_git
from .pathing import is_within, relative_repo_path
from .validation_scope_manifest import (
    LOCAL_SCOPE_MANIFEST,
    ScopeManifestError,
    ValidationScopeManifest,
    load_validation_scope_manifest,
)


REQUIRED_DOCS = LEGACY_REQUIRED_DOCS
RECOMMENDED_DOCS = STANDARD_DOCS

PERMISSION_MODES = [
    "READ_ONLY_REVIEW",
    "WRITE_AUTHORIZED",
    "CORRECTIVE_AUTHORIZED",
    "ENVIRONMENT_WRITE_AUTHORIZED",
    "SUBMIT_AUTHORIZED",
]

SOURCE_REPO_MARKERS = [
    "docs/SAGE_CORE.md",
    "skills/sage-kit/SKILL.md",
    "docs/PROJECT_PROFILE_TEMPLATE.md",
]

SOURCE_REQUIRED_FILES = [
    "pyproject.toml",
    "README.md",
    "README.zh-CN.md",
    "docs/SAGE_CORE.md",
    "docs/PROJECT_PROFILE_TEMPLATE.md",
    "docs/QUALITY_GATES_TEMPLATE.md",
    "docs/ACTIVE_CONTEXT_TEMPLATE.md",
    "docs/DOC_ROUTING_TEMPLATE.md",
    "docs/TECHNICAL_DESIGN_TEMPLATE.md",
    "docs/ENGINEERING_SYSTEM_TEMPLATE.md",
    "docs/APPROVAL_GATES_TEMPLATE.md",
    "docs/templates/PHASE_TEMPLATE.md",
    "docs/templates/MILESTONE_LEDGER_TEMPLATE.md",
    "docs/templates/MILESTONE_CLOSEOUT_TEMPLATE.md",
    "docs/templates/COMPLETION_REPORT_TEMPLATE.md",
    "docs/templates/SAGE_VALIDATION_SCOPE_TEMPLATE.json",
    "docs/templates/SAGE_PROJECT_TEMPLATE.json",
    "docs/templates/THIN_MILESTONE_TEMPLATE.json",
    "docs/templates/THIN_PHASE_TEMPLATE.json",
    "docs/contracts/execution-documents/2026.7.19.3/contract.json",
    "docs/contracts/execution-documents/2026.7.19.3/project.schema.json",
    "docs/contracts/execution-documents/2026.7.19.3/milestone.schema.json",
    "docs/contracts/execution-documents/2026.7.19.3/phase.schema.json",
    "docs/contracts/execution-documents/2026.7.19.3/profiles/standard-milestone-v1.json",
    "docs/contracts/execution-documents/2026.7.19.3/profiles/standard-phase-v1.json",
    "docs/contracts/execution-documents/2026.7.20.1/contract.json",
    "docs/contracts/execution-documents/2026.7.20.1/project.schema.json",
    "docs/contracts/execution-documents/2026.7.20.1/milestone.schema.json",
    "docs/contracts/execution-documents/2026.7.20.1/phase.schema.json",
    "docs/contracts/execution-documents/2026.7.20.1/profiles/standard-milestone-v1.json",
    "docs/contracts/execution-documents/2026.7.20.1/profiles/standard-phase-v1.json",
    "docs/contracts/resource-governance/conservative-host-v1.json",
    "docs/agent/GOVERNANCE_LEVELS.md",
    "docs/agent/SESSION_ORCHESTRATION.md",
    "docs/agent/CAPABILITY_ADAPTERS.md",
    "docs/agent/EXECUTION_ECONOMY.md",
    "docs/agent/CONTINUITY_PROTOCOL.md",
    "docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md",
    "docs/agent/HOST_RESOURCE_GOVERNANCE.md",
    "docs/agent/SPEC_SOURCE_CONTRACT.md",
    "docs/profiles/task-dispatch/schemas/task.schema.json",
    "docs/profiles/task-dispatch/schemas/evidence.schema.json",
    "scripts/validate_task_dispatch.py",
    "skills/sage-kit/SKILL.md",
    "sagekit/__init__.py",
    "sagekit/__main__.py",
    "sagekit/cli.py",
    "sagekit/check.py",
    "sagekit/doctor.py",
    "sagekit/init.py",
    "sagekit/modes.py",
    "sagekit/findings.py",
    "sagekit/pathing.py",
    "sagekit/candidate.py",
    "sagekit/convergence.py",
    "sagekit/change_control.py",
    "sagekit/evidence.py",
    "sagekit/execution_limits.py",
    "sagekit/review.py",
    "sagekit/continuity.py",
    "sagekit/compatibility.py",
    "sagekit/milestone_scope.py",
    "sagekit/validation_scope_manifest.py",
    "sagekit/execution_documents.py",
    "sagekit/policy_resolution.py",
    "sagekit/packet.py",
    "sagekit/spec_sources.py",
    "sagekit/managed_execution.py",
    "sagekit/process_supervisor.py",
    "sagekit/resource_cli.py",
    "sagekit/resource_governor.py",
    "sagekit/resource_policy.py",
    "sagekit/test_node.py",
    "sagekit/test_runner.py",
    "sagekit/workspace_binding.py",
    "sagekit/reporting.py",
    "sagekit/validation_contracts/__init__.py",
    "sagekit/validation_contracts/frozen_validator.py",
    "sagekit/validation_contracts/v0.py",
    "sagekit/validation_contracts/v1.py",
    "sagekit/validation_contracts/v2.py",
    "sagekit/resources/contracts/v0/policy.json",
    "sagekit/resources/contracts/v0/rules.json",
    "sagekit/resources/contracts/v0/validator.json",
    "sagekit/resources/contracts/v0/task.schema.json",
    "sagekit/resources/contracts/v0/evidence.schema.json",
    "sagekit/resources/contracts/v1/policy.json",
    "sagekit/resources/contracts/v1/rules.json",
    "sagekit/resources/contracts/v1/validator.json",
    "sagekit/resources/contracts/v1/task.schema.json",
    "sagekit/resources/contracts/v1/evidence.schema.json",
    "sagekit/resources/contracts/v2/policy.json",
    "sagekit/resources/contracts/v2/task.schema.json",
    "sagekit/resources/contracts/v2/evidence.schema.json",
    "sagekit/task_dispatch_validator.py",
    "sagekit/resources/execution_documents/2026.7.19.3/contract.json",
    "sagekit/resources/execution_documents/2026.7.19.3/project.schema.json",
    "sagekit/resources/execution_documents/2026.7.19.3/milestone.schema.json",
    "sagekit/resources/execution_documents/2026.7.19.3/phase.schema.json",
    "sagekit/resources/execution_documents/2026.7.19.3/profiles/standard-milestone-v1.json",
    "sagekit/resources/execution_documents/2026.7.19.3/profiles/standard-phase-v1.json",
    "sagekit/resources/execution_documents/2026.7.20.1/contract.json",
    "sagekit/resources/execution_documents/2026.7.20.1/project.schema.json",
    "sagekit/resources/execution_documents/2026.7.20.1/milestone.schema.json",
    "sagekit/resources/execution_documents/2026.7.20.1/phase.schema.json",
    "sagekit/resources/execution_documents/2026.7.20.1/profiles/standard-milestone-v1.json",
    "sagekit/resources/execution_documents/2026.7.20.1/profiles/standard-phase-v1.json",
    "sagekit/resources/resource_governance/conservative-host-v1.json",
    "scripts/run_tests.py",
    "scripts/wheel_smoke.py",
    "tests/test_sagekit_check.py",
    "tests/test_frozen_contracts_and_containers.py",
    "tests/test_execution_economy.py",
    "tests/test_convergence_authority.py",
    "tests/test_validation_compatibility.py",
    "tests/test_validation_scope_manifest.py",
    "tests/test_thin_execution_documents.py",
    "tests/test_packet_compile.py",
    "tests/test_thin_documentation.py",
    "tests/test_thin_routing.py",
    "tests/test_package_smoke.py",
    "tests/test_spec_sources.py",
    "tests/test_active_scope.py",
]

GITIGNORE_RUNTIME_PATTERNS = [
    ".worktrees/",
    "local/",
    ".sagekit/",
    ".runtime/",
    "docs/ACTIVE_CONTEXT.md",
    "docs/DOC_ROUTING.md",
    "docs/M[0-9]*/",
    "docs/runs/",
    "docs/task-records/",
]

FORBIDDEN_RUNTIME_STACK_PATHS = [
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "tsconfig.json",
    "*.ts",
    "*.tsx",
    "*.js",
    "*.jsx",
    "node_modules/**",
]

RESOURCE_REFERENCE_RE = re.compile(
    r"docs/(?:agent|templates|profiles|contracts)/[A-Za-z0-9_./-]+\.(?:md|yaml|json)"
)


def run_check(
    start: Path,
    gate_ready: bool = False,
    mode: str | None = None,
    scope_manifest_path: Path | None = None,
    scope: str | None = None,
) -> list[Finding]:
    if mode is not None and mode not in MODES:
        raise ValueError(f"unknown SAGE-Kit mode: {mode}")
    root = detect_root(start)
    if scope not in {None, "active", "history", "all"}:
        raise ValueError(f"unknown check scope: {scope}")
    from .spec_sources import SourceConfigurationError, load_source_config

    try:
        source_config = load_source_config(root)
    except SourceConfigurationError as exc:
        return [
            Finding("PASS", "project-root", relpath(root, root), None, f"using {root}"),
            Finding(
                "FAIL",
                "project-authority",
                "SAGEKIT_CONFIG.json",
                None,
                str(exc),
                "Correct the machine-readable project authority before current execution.",
            ),
        ]
    active_default = (
        source_config is not None and source_config.execution_scope == "active-only"
    )
    if scope == "active" or (scope is None and active_default):
        if source_config is None:
            return [
                Finding("PASS", "project-root", relpath(root, root), None, f"using {root}"),
                Finding(
                    "FAIL",
                    "active-authority",
                    None,
                    None,
                    "active-only check requires equivalent machine-readable project authority",
                ),
            ]
        return _run_active_check(root, source_config)
    if scope == "history":
        return _run_history_check(
            root,
            scope_manifest_path=scope_manifest_path,
            gate_ready=gate_ready,
        )
    findings: list[Finding] = [
        Finding("PASS", "project-root", relpath(root, root), None, f"using {root}")
    ]
    manifest, manifest_source, manifest_error = resolve_check_scope_manifest(
        root,
        scope_manifest_path,
    )
    if manifest is not None:
        findings.append(
            Finding(
                "PASS",
                "validation-scope-manifest",
                relpath(root, manifest.path),
                None,
                f"loaded {manifest_source} validation scope manifest; "
                f"digest=sha256:{manifest.digest}; "
                f"baseline_head={manifest.authority.baseline_head}; "
                f"active={len(manifest.active_containers)}; "
                f"accepted_legacy={len(manifest.accepted_legacy_containers)}",
            )
        )
    elif manifest_error is not None:
        findings.append(
            Finding(
                "FAIL",
                "validation-scope-manifest",
                relpath(
                    root,
                    scope_manifest_path
                    if scope_manifest_path is not None
                    else root / LOCAL_SCOPE_MANIFEST,
                ),
                None,
                manifest_error,
                "Correct the manifest authority; invalid manifests never authorize legacy scope.",
            )
        )
    if mode is not None:
        findings.append(Finding("PASS", "check-mode", None, None, f"mode: {mode}"))
    findings.extend(check_required_docs(root, required_docs_for_mode(mode)))
    findings.extend(check_recommended_docs(root, recommended_docs_for_mode(mode)))
    findings.extend(check_active_context(root))
    findings.extend(check_doc_routing(root))
    findings.extend(
        check_execution_documents(
            root,
            scope_manifest=manifest,
            manifest_source=manifest_source,
            manifest_error=manifest_error,
        )
    )
    findings.extend(check_completion_reports(root))
    findings.extend(
        check_task_dispatch(
            root,
            gate_ready=gate_ready,
            scope_manifest=manifest,
            manifest_source=manifest_source,
            manifest_error=manifest_error,
        )
    )
    return findings


def _run_active_check(root: Path, config) -> list[Finding]:
    """Validate only current authority and normalized ACTIVE_SPEC."""

    from .spec_sources import (
        SourceConfigurationError,
        load_normalized_spec,
        resolve_active_context_path,
        validate_package_binding,
    )

    findings: list[Finding] = [
        Finding("PASS", "project-root", relpath(root, root), None, f"using {root}")
    ]
    try:
        validate_package_binding(config)
    except SourceConfigurationError as exc:
        findings.append(
            Finding(
                "FAIL",
                "package-authority",
                relpath(root, config.path),
                None,
                str(exc),
                "Use the package version and canonical resource digest pinned by project authority.",
            )
        )
        return findings
    findings.append(
        Finding(
            "PASS",
            "package-authority",
            relpath(root, config.path),
            None,
            "installed package version and canonical resource digest match project authority",
        )
    )
    active_context = resolve_active_context_path(root, config)
    findings.extend(check_active_context(root, path=active_context))
    if not active_context.is_file():
        findings.append(
            Finding(
                "FAIL",
                "active-authority",
                relpath(root, active_context),
                None,
                "configured ACTIVE_CONTEXT is missing",
            )
        )
        return findings
    text = read_text(active_context)
    match = re.search(
        r"^\s*(?:[-*]\s*)?Current\s+milestone\s*:\s*`?([^`\r\n]+?)`?\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if match is None:
        findings.append(
            Finding(
                "FAIL",
                "active-authority",
                relpath(root, active_context),
                None,
                "ACTIVE_CONTEXT does not identify one current milestone or explicit none",
            )
        )
        return findings
    milestone_id = match.group(1).strip()
    if milestone_id.casefold() in {"none", "n/a", "idle"}:
        if config.sources:
            findings.append(
                Finding(
                    "FAIL",
                    "active-authority",
                    relpath(root, active_context),
                    None,
                    "empty-active state conflicts with configured milestone sources",
                )
            )
        else:
            findings.append(
                Finding(
                    "PASS",
                    "active-authority",
                    relpath(root, active_context),
                    None,
                    "equivalent project authority declares a legal empty-active state",
                )
            )
        return findings
    if re.fullmatch(r"M[0-9]+(?:[._-][A-Za-z0-9]+)*", milestone_id) is None:
        findings.append(
            Finding(
                "FAIL",
                "active-authority",
                relpath(root, active_context),
                None,
                f"invalid current milestone authority: {milestone_id}",
            )
        )
        return findings
    try:
        normalized = load_normalized_spec(root, milestone_id)
    except (SourceConfigurationError, ValueError) as exc:
        findings.append(
            Finding(
                "FAIL",
                "active-spec",
                None,
                None,
                str(exc),
                "Correct the selected ACTIVE_SPEC; accepted history is not a fallback.",
            )
        )
        return findings
    findings.append(
        Finding(
            "PASS",
            "active-spec",
            None,
            None,
            f"normalized ACTIVE_SPEC {milestone_id}; semantic=sha256:{normalized.semantic_digest}",
        )
    )
    return findings


def _run_history_check(
    root: Path,
    *,
    scope_manifest_path: Path | None,
    gate_ready: bool,
) -> list[Finding]:
    """Run the frozen compatibility path only when history is explicit."""

    findings: list[Finding] = [
        Finding("PASS", "project-root", relpath(root, root), None, f"using {root}"),
        Finding(
            "PASS",
            "check-scope",
            None,
            None,
            "explicit ACCEPTED_HISTORY audit; this path is not current execution authority",
        ),
    ]
    manifest, manifest_source, manifest_error = resolve_check_scope_manifest(
        root, scope_manifest_path
    )
    if manifest_error is not None:
        findings.append(
            Finding(
                "FAIL",
                "history-scope",
                None,
                None,
                manifest_error,
            )
        )
        return findings
    if manifest is None:
        findings.append(
            Finding(
                "FAIL",
                "history-scope",
                None,
                None,
                "history audit requires an explicit Validation Scope Manifest",
                "Name accepted immutable containers and their frozen v0/v1 contract versions.",
            )
        )
        return findings
    accepted = tuple(item.path.rstrip("/") for item in manifest.accepted_legacy_containers)
    findings.append(
        Finding(
            "PASS",
            "history-scope",
            relpath(root, manifest.path),
            None,
            f"loaded {len(accepted)} accepted immutable container(s)",
        )
    )
    if not accepted:
        return findings
    audited = [
        *check_phase_docs(
            root,
            scope_manifest=manifest,
            manifest_source=manifest_source,
            manifest_error=None,
        ),
        *check_task_dispatch(
            root,
            gate_ready=gate_ready,
            scope_manifest=manifest,
            manifest_source=manifest_source,
            manifest_error=None,
        ),
    ]
    for finding in audited:
        normalized = (finding.path or "").replace("\\", "/").rstrip("/")
        if any(
            normalized == prefix or normalized.startswith(prefix + "/")
            for prefix in accepted
        ):
            findings.append(finding)
    return findings


def resolve_check_scope_manifest(
    root: Path,
    explicit_path: Path | None,
) -> tuple[ValidationScopeManifest | None, str, str | None]:
    path = explicit_path if explicit_path is not None else root / LOCAL_SCOPE_MANIFEST
    source = "CLI" if explicit_path is not None else "project-local"
    if explicit_path is None and not path.exists():
        return None, source, None
    try:
        manifest = load_validation_scope_manifest(path)
    except ScopeManifestError as exc:
        return None, source, str(exc)
    from .milestone_scope import validate_manifest_repository_authority

    repository_errors = validate_manifest_repository_authority(root, manifest)
    if repository_errors:
        return (
            None,
            source,
            "scope manifest repository authority is invalid: "
            + "; ".join(repository_errors),
        )
    return manifest, source, None


def run_source_repo_check(start: Path) -> list[Finding]:
    root = detect_root(start)
    findings: list[Finding] = [
        Finding("PASS", "project-root", relpath(root, root), None, f"using {root}")
    ]
    if is_kit_source_repo(root):
        findings.append(
            Finding(
                "PASS",
                "source-repo",
                relpath(root, root / "docs/SAGE_CORE.md"),
                None,
                "SAGE-Kit source repository detected",
            )
        )
    else:
        findings.append(
            Finding(
                "FAIL",
                "source-repo",
                relpath(root, root),
                None,
                "target does not look like the SAGE-Kit source repository",
                "Use plain sagekit check for adopted projects, or run --source-repo from the SAGE-Kit repository.",
            )
        )
        return findings

    findings.extend(check_source_required_files(root))
    findings.extend(check_source_init_resources(root))
    findings.extend(check_source_resource_references(root))
    findings.extend(check_source_resource_mirrors(root))
    findings.extend(check_source_execution_document_mirrors(root))
    findings.extend(check_source_resource_governance_mirrors(root))
    findings.extend(check_source_pyproject(root))
    findings.extend(check_source_gitignore(root))
    try:
        tracked_paths = collect_source_tracked_paths(root)
    except ManagedExecutionError as exc:
        findings.append(
            Finding(
                "WARN",
                "source-tracked-snapshot",
                None,
                None,
                f"could not collect managed git ls-files snapshot: {exc}",
                "Resolve the Git capability failure before submit verification.",
            )
        )
    else:
        findings.extend(check_source_tracked_runtime_paths(tracked_paths))
        findings.extend(check_source_forbidden_runtime_paths(tracked_paths))
    return findings


def is_kit_source_repo(root: Path) -> bool:
    return all((root / marker).exists() for marker in SOURCE_REPO_MARKERS)


def check_source_execution_document_mirrors(root: Path) -> list[Finding]:
    """Require a byte-identical, bidirectional source/package contract tree."""

    source_root = root / "docs/contracts/execution-documents"
    package_root = root / "sagekit/resources/execution_documents"
    source_files = {
        path.relative_to(source_root).as_posix(): path
        for path in source_root.rglob("*")
        if path.is_file()
    } if source_root.is_dir() else {}
    package_files = {
        path.relative_to(package_root).as_posix(): path
        for path in package_root.rglob("*")
        if path.is_file()
    } if package_root.is_dir() else {}
    findings: list[Finding] = []
    for relative in sorted(set(source_files) | set(package_files)):
        source = source_files.get(relative)
        packaged = package_files.get(relative)
        display = f"docs/contracts/execution-documents/{relative}"
        if source is None:
            findings.append(
                Finding(
                    "FAIL",
                    "execution-resource-mirror",
                    display,
                    None,
                    "packaged execution contract has no source counterpart",
                )
            )
        elif packaged is None:
            findings.append(
                Finding(
                    "FAIL",
                    "execution-resource-mirror",
                    display,
                    None,
                    "source execution contract has no packaged counterpart",
                )
            )
        elif source.read_bytes() != packaged.read_bytes():
            findings.append(
                Finding(
                    "FAIL",
                    "execution-resource-mirror",
                    display,
                    None,
                    "source and packaged execution contracts differ byte-for-byte",
                )
            )
        else:
            findings.append(
                Finding(
                    "PASS",
                    "execution-resource-mirror",
                    display,
                    None,
                    "source and packaged execution contracts match",
                )
            )
    if not source_files and not package_files:
        findings.append(
            Finding(
                "FAIL",
                "execution-resource-mirror",
                "docs/contracts/execution-documents",
                None,
                "versioned execution contract resources are missing",
            )
        )
    return findings


def check_source_resource_governance_mirrors(root: Path) -> list[Finding]:
    """Require resource contract source and runtime resources to match exactly."""

    source_root = root / "docs/contracts/resource-governance"
    package_root = root / "sagekit/resources/resource_governance"
    source_files = (
        {
            path.relative_to(source_root).as_posix(): path
            for path in source_root.rglob("*")
            if path.is_file()
        }
        if source_root.is_dir()
        else {}
    )
    package_files = (
        {
            path.relative_to(package_root).as_posix(): path
            for path in package_root.rglob("*")
            if path.is_file()
        }
        if package_root.is_dir()
        else {}
    )
    findings: list[Finding] = []
    for relative in sorted(set(source_files) | set(package_files)):
        source = source_files.get(relative)
        packaged = package_files.get(relative)
        display = f"docs/contracts/resource-governance/{relative}"
        if source is None or packaged is None:
            message = (
                "packaged resource contract has no source counterpart"
                if source is None
                else "source resource contract has no packaged counterpart"
            )
            findings.append(
                Finding("FAIL", "resource-governance-mirror", display, None, message)
            )
        elif source.read_bytes() != packaged.read_bytes():
            findings.append(
                Finding(
                    "FAIL",
                    "resource-governance-mirror",
                    display,
                    None,
                    "source and packaged resource contracts differ byte-for-byte",
                )
            )
        else:
            findings.append(
                Finding(
                    "PASS",
                    "resource-governance-mirror",
                    display,
                    None,
                    "source and packaged resource contracts match",
                )
            )
    if not source_files and not package_files:
        findings.append(
            Finding(
                "FAIL",
                "resource-governance-mirror",
                "docs/contracts/resource-governance",
                None,
                "versioned resource governance contracts are missing",
            )
        )
    return findings


def detect_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
        if any((candidate / path).exists() for path in REQUIRED_DOCS):
            return candidate
    return current


def relpath(root: Path, path: Path) -> str:
    try:
        return relative_repo_path(root, path)
    except ValueError:
        return path.name


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_source_required_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for item in SOURCE_REQUIRED_FILES:
        path = root / item
        if not path.exists():
            findings.append(
                Finding("FAIL", "source-required-file", item, None, f"{item} missing")
            )
        elif path.is_file() and read_text(path).strip():
            findings.append(Finding("PASS", "source-required-file", item, None, f"{item} exists"))
        else:
            findings.append(
                Finding(
                    "FAIL",
                    "source-required-file",
                    item,
                    None,
                    f"{item} is empty or not a file",
                )
            )
    return findings


def check_source_init_resources(root: Path) -> list[Finding]:
    try:
        from .init import init_files_for_mode, package_resource_root
    except Exception as exc:
        return [
            Finding(
                "FAIL",
                "source-resource-map",
                "sagekit/init.py",
                None,
                f"could not load init resource mapping: {exc}",
            )
        ]

    source_root = package_resource_root()
    if not source_root.exists():
        return [
            Finding(
                "FAIL",
                "source-resource-map",
                relpath(root, source_root),
                None,
                "packaged resource root missing",
            )
        ]

    findings: list[Finding] = [
        Finding("PASS", "source-resource-map", relpath(root, source_root), None, "resource root exists")
    ]
    seen: set[str] = set()
    for item in init_files_for_mode("heavy", source_root, profile="vendored-legacy"):
        if not item.source or item.source in seen:
            continue
        seen.add(item.source)
        path = source_root / item.source
        display = relpath(root, path)
        if path.exists() and path.is_file() and read_text(path).strip():
            findings.append(Finding("PASS", "source-resource", display, None, f"{item.source} resolves"))
        else:
            findings.append(
                Finding(
                    "FAIL",
                    "source-resource",
                    display,
                    None,
                    f"{item.source} missing, empty, or not a file",
                )
            )
    return findings


def check_source_resource_references(root: Path) -> list[Finding]:
    try:
        from .init import package_resource_root
    except Exception as exc:
        return [
            Finding(
                "FAIL",
                "source-resource-reference",
                "sagekit/init.py",
                None,
                f"could not load packaged resource root: {exc}",
            )
        ]

    source_root = package_resource_root()
    docs_root = source_root / "docs"
    if not docs_root.exists():
        return [
            Finding(
                "FAIL",
                "source-resource-reference",
                relpath(root, docs_root),
                None,
                "packaged docs resource root missing",
            )
        ]

    references = collect_packaged_doc_references(docs_root)
    findings: list[Finding] = []
    for target, sources in sorted(references.items()):
        path = source_root / target
        display = relpath(root, path)
        source_summary = summarize_reference_sources(sources)
        if path.exists() and path.is_file() and read_text(path).strip():
            findings.append(
                Finding(
                    "PASS",
                    "source-resource-reference",
                    display,
                    None,
                    f"{target} referenced by {source_summary} resolves",
                )
            )
        else:
            findings.append(
                Finding(
                    "FAIL",
                    "source-resource-reference",
                    display,
                    None,
                    f"{target} referenced by {source_summary} is missing, empty, or not a file",
                    "Mirror the referenced SAGE-Kit doc under sagekit/resources/docs or remove the packaged reference.",
                )
            )
    return findings


def collect_packaged_doc_references(docs_root: Path) -> dict[str, set[str]]:
    references: dict[str, set[str]] = {}
    for path in sorted(docs_root.rglob("*")):
        if not path.is_file():
            continue
        text = read_text(path)
        source = path.relative_to(docs_root.parent).as_posix()
        for match in RESOURCE_REFERENCE_RE.findall(text):
            references.setdefault(match, set()).add(source)
    return references


def summarize_reference_sources(sources: set[str]) -> str:
    ordered = sorted(sources)
    if len(ordered) <= 3:
        return ", ".join(ordered)
    return ", ".join(ordered[:3]) + f", and {len(ordered) - 3} more"


def check_source_resource_mirrors(root: Path) -> list[Finding]:
    try:
        from .init import package_resource_root
    except Exception as exc:
        return [
            Finding(
                "FAIL",
                "source-resource-mirror",
                "sagekit/init.py",
                None,
                f"could not load packaged resource root: {exc}",
            )
        ]

    source_root = package_resource_root()
    docs_root = source_root / "docs"
    if not docs_root.exists():
        return [
            Finding(
                "FAIL",
                "source-resource-mirror",
                relpath(root, docs_root),
                None,
                "packaged docs resource root missing",
            )
        ]

    findings: list[Finding] = []
    for resource_path in sorted(path for path in docs_root.rglob("*") if path.is_file()):
        relative = resource_path.relative_to(source_root).as_posix()
        source_path = root / relative
        display = relpath(root, resource_path)
        if not source_path.exists() or not source_path.is_file():
            findings.append(
                Finding(
                    "FAIL",
                    "source-resource-mirror",
                    display,
                    None,
                    f"{relative} has no source document",
                    "Remove the orphan packaged resource or add the matching source document.",
                )
            )
            continue
        if read_text(resource_path) == read_text(source_path):
            findings.append(
                Finding(
                    "PASS",
                    "source-resource-mirror",
                    display,
                    None,
                    f"{relative} matches source document",
                )
            )
        else:
            findings.append(
                Finding(
                    "FAIL",
                    "source-resource-mirror",
                    display,
                    None,
                    f"{relative} differs from source document",
                    "Copy the updated source document into sagekit/resources before release.",
                )
            )
    return findings


def check_source_pyproject(root: Path) -> list[Finding]:
    path = root / "pyproject.toml"
    if not path.exists():
        return [Finding("FAIL", "source-pyproject", "pyproject.toml", None, "pyproject.toml missing")]
    text = read_text(path)
    checks = [
        (
            'requires-python = ">=3.10"',
            "source-python-policy",
            "Python >=3.10 policy is declared",
            "requires-python must declare Python >=3.10.",
        ),
        (
            "dependencies = []",
            "source-runtime-dependencies",
            "runtime dependency list is empty",
            "Keep the CLI runtime stdlib-only.",
        ),
        (
            'sagekit = "sagekit.cli:main"',
            "source-console-script",
            "console script maps sagekit to sagekit.cli:main",
            'Add [project.scripts] sagekit = "sagekit.cli:main".',
        ),
        (
            'version = {attr = "sagekit.__version__"}',
            "source-version",
            "package version is read from sagekit.__version__",
            "Keep a single version source in sagekit.__version__.",
        ),
        (
            'sagekit = ["resources/**/*"]',
            "source-package-data",
            "packaged resources are included",
            "Package sagekit/resources so init can copy bundled templates after installation.",
        ),
    ]
    findings: list[Finding] = []
    for token, rule, message, suggestion in checks:
        if token in text:
            findings.append(Finding("PASS", rule, "pyproject.toml", None, message))
        else:
            findings.append(Finding("FAIL", rule, "pyproject.toml", None, suggestion, suggestion))
    return findings


def check_source_gitignore(root: Path) -> list[Finding]:
    path = root / ".gitignore"
    if not path.exists():
        return [Finding("FAIL", "source-gitignore-runtime", ".gitignore", None, ".gitignore missing")]
    lines = {
        line.strip()
        for line in read_text(path).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    missing = [pattern for pattern in GITIGNORE_RUNTIME_PATTERNS if pattern not in lines]
    if missing:
        return [
            Finding(
                "FAIL",
                "source-gitignore-runtime",
                ".gitignore",
                None,
                "missing runtime ignore patterns: " + ", ".join(missing),
                "Ignore local worktrees and generated project runtime state without ignoring templates.",
            )
        ]
    return [
        Finding(
            "PASS",
            "source-gitignore-runtime",
            ".gitignore",
            None,
            "runtime files are ignored while templates remain trackable",
        )
    ]


def is_runtime_state_path(path: str) -> bool:
    normalized = path.replace("\\", "/").strip("/")
    runtime_prefixes = (
        "docs/runs",
        "docs/task-records",
        "local",
        ".sagekit",
        ".runtime",
    )
    if normalized in {"docs/ACTIVE_CONTEXT.md", "docs/DOC_ROUTING.md"}:
        return True
    if any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in runtime_prefixes):
        return True
    return re.match(r"^docs/M[0-9]+(/|$)", normalized) is not None


def check_source_tracked_runtime(root: Path) -> list[Finding]:
    try:
        tracked = collect_source_tracked_paths(root)
    except ManagedExecutionError as exc:
        return [
            Finding(
                "WARN",
                "source-tracked-runtime",
                None,
                None,
                f"could not run git ls-files: {exc}",
                "Run git ls-files manually before committing.",
            )
        ]
    return check_source_tracked_runtime_paths(tracked)


def check_source_tracked_runtime_paths(tracked: Iterable[str]) -> list[Finding]:
    runtime_tracked = [path for path in tracked if is_runtime_state_path(path)]
    if runtime_tracked:
        return [
            Finding(
                "FAIL",
                "source-tracked-runtime",
                None,
                None,
                ".sagekit/runtime content is tracked by Git or other runtime state is tracked: "
                + ", ".join(runtime_tracked),
                "Remove generated runtime state from version control.",
            )
        ]
    return [
        Finding(
            "PASS",
            "source-tracked-runtime",
            None,
            None,
            "no generated runtime project state is tracked",
        )
    ]


def check_source_forbidden_runtime_stack(root: Path) -> list[Finding]:
    try:
        tracked = collect_source_tracked_paths(root)
    except ManagedExecutionError as exc:
        return [
            Finding(
                "WARN",
                "source-runtime-stack",
                None,
                None,
                f"could not run git ls-files: {exc}",
                "Confirm no Node or TypeScript runtime files were introduced.",
            )
        ]
    return check_source_forbidden_runtime_paths(tracked)


def check_source_forbidden_runtime_paths(tracked: Iterable[str]) -> list[Finding]:
    forbidden = [
        path
        for path in tracked
        if any(fnmatchcase(path, pattern) for pattern in FORBIDDEN_RUNTIME_STACK_PATHS)
    ]
    if forbidden:
        return [
            Finding(
                "FAIL",
                "source-runtime-stack",
                None,
                None,
                "Node or TypeScript runtime files are tracked: " + ", ".join(forbidden),
                "Keep SAGE-Kit CLI runtime Python stdlib-only.",
            )
        ]
    return [
        Finding(
            "PASS",
            "source-runtime-stack",
            None,
            None,
            "no Node or TypeScript runtime files are tracked",
        )
    ]


def collect_source_tracked_paths(root: Path) -> tuple[str, ...]:
    result = run_managed_git(
        root,
        ("ls-files", "-z"),
        stage="source-check-git-ls-files",
        run_id="source-check-git-ls-files",
        timeout=30.0,
    )
    return tuple(
        part.decode("utf-8", errors="replace")
        for part in result.stdout.split(b"\0")
        if part
    )


def check_required_docs(root: Path, required_docs: list[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for item in REQUIRED_DOCS if required_docs is None else required_docs:
        path = root / item
        if not path.exists():
            findings.append(
                Finding(
                    "FAIL",
                    "required-docs",
                    item,
                    None,
                    f"{item} missing",
                    "Create this SAGE-Kit project document or run check from the intended project root.",
                )
            )
        elif path.is_file() and read_text(path).strip():
            findings.append(Finding("PASS", "required-docs", item, None, f"{item} exists"))
        else:
            findings.append(
                Finding(
                    "FAIL",
                    "required-docs",
                    item,
                    None,
                    f"{item} is empty or not a file",
                    "Fill the required document with current project governance facts.",
                )
            )
    return findings


def check_recommended_docs(root: Path, recommended_docs: list[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for item in RECOMMENDED_DOCS if recommended_docs is None else recommended_docs:
        path = root / item
        if path.exists():
            findings.append(Finding("PASS", "recommended-docs", item, None, f"{item} exists"))
        else:
            findings.append(
                Finding(
                    "WARN",
                    "recommended-docs",
                    item,
                    None,
                    f"{item} missing",
                    "Add it when the project needs standard SAGE-Kit governance depth.",
                )
            )
    return findings


def check_active_context(root: Path, *, path: Path | None = None) -> list[Finding]:
    path = root / "docs/ACTIVE_CONTEXT.md" if path is None else path
    if not path.exists():
        return []
    text = read_text(path)
    findings: list[Finding] = []
    if text.strip():
        findings.append(Finding("PASS", "active-context", relpath(root, path), None, "not empty"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "active-context",
                relpath(root, path),
                None,
                "ACTIVE_CONTEXT.md is empty",
                "Keep a compact current-state snapshot.",
            )
        )
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) > 200:
        findings.append(
            Finding(
                "WARN",
                "active-context",
                relpath(root, path),
                None,
                f"{len(lines)} non-empty lines; startup context may be too large",
                "Replace stale state with a compact summary instead of appending history.",
            )
        )
    else:
        findings.append(
            Finding("PASS", "active-context", relpath(root, path), None, "compact enough for startup context")
        )
    lower = text.lower()
    history_markers = ["session log", "chat transcript", "append-only", "conversation history"]
    if any(marker in lower for marker in history_markers):
        findings.append(
            Finding(
                "WARN",
                "active-context",
                relpath(root, path),
                None,
                "looks like append-only session history",
                "Keep only durable current-state facts.",
            )
        )
    return findings


def check_doc_routing(root: Path) -> list[Finding]:
    path = root / "docs/DOC_ROUTING.md"
    if not path.exists():
        return []
    text = read_text(path)
    lower = text.lower()
    findings: list[Finding] = []
    if any(token in lower for token in ["routing policy", "task routing", "read set", "read the"]):
        findings.append(Finding("PASS", "doc-routing", relpath(root, path), None, "contains routing policy"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "doc-routing",
                relpath(root, path),
                None,
                "does not name a routing policy or task-type read set",
                "Describe which docs agents should read for planning, implementation, review, and closeout.",
            )
        )
    if any(token in lower for token in ["progress log", "done:", "today i", "session transcript"]):
        findings.append(
            Finding(
                "WARN",
                "doc-routing",
                relpath(root, path),
                None,
                "looks like it may contain progress log material",
                "Keep progress in ledgers or completion reports, not DOC_ROUTING.md.",
            )
        )
    return findings


def check_phase_docs(
    root: Path,
    *,
    scope_manifest: ValidationScopeManifest | None = None,
    manifest_source: str = "project-local",
    manifest_error: str | None = None,
) -> list[Finding]:
    from .milestone_scope import MilestoneScopeKind, RepositoryScopeResolver

    findings: list[Finding] = []
    phase_paths: dict[Path, list[Path]] = {}
    for path in sorted((root / "docs").glob("M*/[0-9][0-9]-*.md")):
        if "_TEMPLATE" not in path.name:
            phase_paths.setdefault(path.parent, []).append(path)
    resolver = RepositoryScopeResolver(
        root,
        manifest=scope_manifest,
        manifest_source=manifest_source,
        manifest_error=manifest_error,
    )
    for milestone_dir, paths in sorted(phase_paths.items()):
        scope = resolver.resolve(milestone_dir)
        display = relpath(root, milestone_dir)
        if scope.kind == MilestoneScopeKind.AMBIGUOUS:
            findings.append(
                Finding(
                    "FAIL",
                    "milestone-scope",
                    display,
                    None,
                    scope.detail,
                    "Reconcile active-context and closeout authority before validating phases.",
                )
            )
            continue
        if scope.kind == MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY:
            findings.append(
                Finding(
                    "PASS",
                    "phase-scope-compatibility",
                    display,
                    None,
                    f"treated {len(paths)} phase document(s) as immutable accepted history "
                    f"using {'; '.join(scope.authorities)}",
                )
            )
            for path in paths:
                if not read_text(path).strip():
                    findings.append(
                        Finding(
                            "FAIL",
                            "phase-history-integrity",
                            relpath(root, path),
                            None,
                            "accepted historical phase document is empty",
                        )
                    )
            continue
        for path in paths:
            findings.extend(check_one_phase(root, path, read_text(path)))
    return findings


def check_execution_documents(
    root: Path,
    *,
    scope_manifest: ValidationScopeManifest | None = None,
    manifest_source: str = "project-local",
    manifest_error: str | None = None,
) -> list[Finding]:
    """Select legacy-markdown or thin-v1 independently from Task Dispatch."""

    from .execution_documents import (
        ExecutionDocumentError,
        compare_milestone_ids,
        load_execution_contract,
        load_execution_project,
        load_project_lock,
    )
    from .milestone_scope import MilestoneScopeKind, RepositoryScopeResolver
    from .policy_resolution import PolicyResolutionError, validate_project_overrides

    docs = root / "docs"
    legacy_by_milestone: dict[Path, list[Path]] = {}
    thin_by_milestone: dict[Path, list[Path]] = {}
    for path in sorted(docs.glob("M*/[0-9][0-9]-*.md")):
        if "_TEMPLATE" not in path.name:
            legacy_by_milestone.setdefault(path.parent, []).append(path)
    for path in sorted(docs.glob("M*/MILESTONE_MANIFEST.json")):
        thin_by_milestone.setdefault(path.parent, []).append(path)
    for path in sorted(docs.glob("M*/phases/*.json")):
        thin_by_milestone.setdefault(path.parent.parent, []).append(path)

    lock_path = root / "SAGE_PROJECT.json"
    alias_findings = check_reserved_execution_document_aliases(root)
    if not thin_by_milestone and not lock_path.exists() and not alias_findings:
        return check_phase_docs(
            root,
            scope_manifest=scope_manifest,
            manifest_source=manifest_source,
            manifest_error=manifest_error,
        )

    findings: list[Finding] = list(alias_findings)
    lock = None
    lock_error: str | None = None
    if lock_path.exists():
        try:
            lock = load_project_lock(root)
            contract = load_execution_contract(lock)
            validate_project_overrides(lock, contract)
            findings.append(
                Finding(
                    "PASS",
                    "project-contract",
                    "SAGE_PROJECT.json",
                    None,
                    f"loaded thin-v1 project contract; digest=sha256:{lock.digest}; "
                    f"contract=sha256:{contract.digest}",
                )
            )
        except (ExecutionDocumentError, PolicyResolutionError) as exc:
            lock_error = str(exc)
            findings.append(
                Finding(
                    "FAIL",
                    "project-contract",
                    "SAGE_PROJECT.json",
                    None,
                    lock_error,
                    "Correct the exact project lock; invalid authority never falls back to legacy.",
                )
            )

    resolver = RepositoryScopeResolver(
        root,
        manifest=scope_manifest,
        manifest_source=manifest_source,
        manifest_error=manifest_error,
    )
    milestone_set = set(legacy_by_milestone) | set(thin_by_milestone)
    if lock is not None:
        milestone_set.add(docs / lock.effective_from)
    milestones = sorted(milestone_set)
    for milestone_dir in milestones:
        legacy_paths = legacy_by_milestone.get(milestone_dir, [])
        thin_paths = thin_by_milestone.get(milestone_dir, [])
        display = relpath(root, milestone_dir)
        scope = resolver.resolve(milestone_dir)
        if scope.kind == MilestoneScopeKind.AMBIGUOUS:
            findings.append(
                Finding(
                    "FAIL",
                    "milestone-scope",
                    display,
                    None,
                    scope.detail,
                    "Reconcile active-context and closeout authority before selecting a document model.",
                )
            )
            continue
        if scope.kind == MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY:
            if lock is not None and milestone_dir.name == lock.effective_from:
                findings.append(
                    Finding(
                        "FAIL",
                        "execution-document-authority",
                        display,
                        None,
                        "project lock effective_from targets immutable accepted legacy history",
                        "Move the adoption anchor to a current milestone; do not rewrite accepted history.",
                    )
                )
            findings.append(
                Finding(
                    "PASS",
                    "phase-scope-compatibility",
                    display,
                    None,
                    f"treated {len(legacy_paths) + len(thin_paths)} execution document(s) as "
                    f"immutable accepted history using {'; '.join(scope.authorities)}",
                )
            )
            for path in legacy_paths + thin_paths:
                if not read_text(path).strip():
                    findings.append(
                        Finding(
                            "FAIL",
                            "phase-history-integrity",
                            relpath(root, path),
                            None,
                            "accepted historical execution document is empty",
                        )
                    )
            continue
        position: int | None = None
        if lock is not None:
            try:
                position = compare_milestone_ids(milestone_dir.name, lock.effective_from)
            except ExecutionDocumentError as exc:
                findings.append(
                    Finding(
                        "FAIL",
                        "execution-document-authority",
                        display,
                        None,
                        str(exc),
                    )
                )
                continue
        if legacy_paths and thin_paths:
            findings.append(
                Finding(
                    "FAIL",
                    "execution-document-mixed-format",
                    display,
                    None,
                    "active milestone contains both legacy-markdown and thin-v1 artifacts",
                    "Retain exactly one explicit document model for this active milestone.",
                )
            )
            continue
        if thin_paths:
            if not lock_path.exists():
                findings.append(
                    Finding(
                        "FAIL",
                        "execution-document-authority",
                        display,
                        None,
                        "thin-v1 artifact requires SAGE_PROJECT.json authority",
                    )
                )
                continue
            if lock is None:
                continue
            if position is not None and position < 0:
                findings.append(
                    Finding(
                        "FAIL",
                        "execution-document-authority",
                        display,
                        None,
                        f"thin-v1 milestone precedes effective_from {lock.effective_from}",
                    )
                )
                continue
            try:
                project = load_execution_project(root, milestone_dir.name)
            except (ExecutionDocumentError, PolicyResolutionError) as exc:
                findings.append(
                    Finding(
                        "FAIL",
                        "thin-document-validation",
                        display,
                        None,
                        str(exc),
                    )
                )
                continue
            findings.append(
                Finding(
                    "PASS",
                    "execution-document-model",
                    display,
                    None,
                    f"selected thin-v1 explicitly; milestone=sha256:{project.milestone.digest}; "
                    f"phases={len(project.phases)}",
                )
            )
            continue

        if lock is not None and position is not None and position >= 0:
            findings.append(
                Finding(
                    "FAIL",
                    "execution-document-authority",
                    display,
                    None,
                    f"project lock effective_from {lock.effective_from} requires an explicit "
                    "thin-v1 milestone manifest",
                )
            )
            continue
        for path in legacy_paths:
            findings.extend(check_one_phase(root, path, read_text(path)))
    return findings


def check_reserved_execution_document_aliases(root: Path) -> list[Finding]:
    """Reject non-canonical reserved names before platform glob semantics can route them."""

    findings: list[Finding] = []

    def reject(path: Path, canonical: str) -> None:
        findings.append(
            Finding(
                "FAIL",
                "execution-document-name",
                relpath(root, path),
                None,
                f"reserved execution-document name must be exactly {canonical}",
            )
        )

    try:
        root_entries = list(root.iterdir())
    except OSError:
        root_entries = []
    for path in root_entries:
        if path.name.casefold() == "sage_project.json" and path.name != "SAGE_PROJECT.json":
            reject(path, "SAGE_PROJECT.json")
    docs = root / "docs"
    if not docs.is_dir():
        return findings
    try:
        milestones = list(docs.iterdir())
    except OSError:
        return findings
    for milestone in milestones:
        if not milestone.is_dir():
            continue
        if (
            re.fullmatch(r"m[0-9]+(?:[._-][A-Za-z0-9]+)*", milestone.name, re.IGNORECASE)
            and re.fullmatch(r"M[0-9]+(?:[._-][A-Za-z0-9]+)*", milestone.name) is None
        ):
            reject(milestone, "an uppercase M milestone directory")
        try:
            entries = list(milestone.iterdir())
        except OSError:
            continue
        for entry in entries:
            if (
                entry.name.casefold() == "milestone_manifest.json"
                and entry.name != "MILESTONE_MANIFEST.json"
            ):
                reject(entry, "MILESTONE_MANIFEST.json")
            if entry.name.casefold() == "phases" and entry.name != "phases":
                reject(entry, "phases")
            if entry.is_dir() and entry.name.casefold() == "phases":
                try:
                    phase_entries = list(entry.iterdir())
                except OSError:
                    continue
                for phase in phase_entries:
                    if phase.name.casefold().endswith(".json"):
                        canonical = (
                            re.fullmatch(
                                r"P[0-9]+(?:[._-][A-Za-z0-9]+)*\.json",
                                phase.name,
                            )
                            is not None
                        )
                        if not canonical:
                            reject(phase, "an uppercase phase ID with lowercase .json suffix")
    return findings


def check_one_phase(root: Path, path: Path, text: str) -> list[Finding]:
    display = relpath(root, path)
    lower = text.lower()
    findings: list[Finding] = []
    if re.search(r"(^|\n)\s*#{1,3}\s*(goal|objective)\b", text, re.IGNORECASE) or re.search(
        r"\b(goal|objective)\s*:", text, re.IGNORECASE
    ):
        findings.append(Finding("PASS", "phase-goal", display, None, "goal or objective is named"))
    else:
        findings.append(Finding("FAIL", "phase-goal", display, None, "missing goal or objective"))

    if "governance level" in lower and re.search(r"\b(light|standard|heavy)\b", text, re.IGNORECASE):
        findings.append(Finding("PASS", "phase-governance", display, None, "governance level is named"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "phase-governance",
                display,
                None,
                "missing governance level",
                "Name Light, Standard, or Heavy for this phase.",
            )
        )

    if "permission mode" in lower and any(mode.lower() in lower for mode in PERMISSION_MODES):
        findings.append(Finding("PASS", "phase-permission", display, None, "permission mode is named"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "phase-permission",
                display,
                None,
                "missing permission mode",
                "Name the Authority Matrix permission mode for this phase.",
            )
        )

    if "allowed files" in lower:
        findings.append(Finding("PASS", "phase-boundary", display, None, "allowed files are named"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "phase-boundary",
                display,
                None,
                "missing allowed files",
                "Name allowed, read-only, and forbidden files or explain that no writes are allowed.",
            )
        )
    if "forbidden files" in lower or re.search(r"\bforbidden\s*:\s*(none|n/a)", lower):
        findings.append(Finding("PASS", "phase-boundary", display, None, "forbidden files are named or explicit"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "phase-boundary",
                display,
                None,
                "missing forbidden files",
                "Name forbidden files or state that none apply.",
            )
        )

    if has_evidence_or_na(text, "test"):
        findings.append(Finding("PASS", "phase-tests", display, None, "tests are named or explicitly N/A"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "phase-tests",
                display,
                None,
                "missing tests or non-applicability reason",
                "Name exact test commands or state N/A with a concrete reason.",
            )
        )

    if has_evidence_or_na(text, "runtime smoke"):
        findings.append(
            Finding("PASS", "phase-runtime-smoke", display, None, "runtime smoke is named or explicitly N/A")
        )
    else:
        findings.append(
            Finding(
                "FAIL",
                "phase-runtime-smoke",
                display,
                None,
                "missing runtime smoke or non-applicability reason",
                "Name exact runtime smoke or state N/A with a concrete reason.",
            )
        )

    if "stop conditions" in lower or "stop if" in lower:
        findings.append(Finding("PASS", "phase-stop-conditions", display, None, "stop conditions are named"))
    else:
        findings.append(Finding("FAIL", "phase-stop-conditions", display, None, "missing stop conditions"))

    findings.extend(check_adapter_evidence(root, path, text))
    return findings


def has_evidence_or_na(text: str, topic: str) -> bool:
    section = topic_section(text, topic)
    if not section.strip():
        return False
    lower = section.lower()
    if re.search(r"\bn/?a\b.{0,80}\b(because|reason|not applicable|planning-only|planning only)\b", lower):
        return True
    command_markers = [
        "python ",
        "python -m",
        "pytest",
        "unittest",
        "npm test",
        "pnpm test",
        "go test",
        "cargo test",
        "curl ",
        "browser",
        "cli",
        "process",
        "smoke:",
        "tests:",
    ]
    return any(marker in lower for marker in command_markers)


def topic_section(text: str, topic: str) -> str:
    if topic == "runtime smoke":
        heading_patterns = [r"\bruntime\s+smoke\b"]
        line_patterns = [r"\bruntime\s+smoke\b"]
    else:
        heading_patterns = [r"\btest\s+plan\b", r"\btests?\b"]
        line_patterns = [r"\btests?\b"]

    lines = text.splitlines()
    section: list[str] = []
    active = False
    for line in lines:
        heading = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            title = heading.group(2).strip().lower()
            if active:
                break
            if any(re.search(pattern, title) for pattern in heading_patterns):
                active = True
                section.append(line)
            continue
        if active:
            section.append(line)

    if section:
        return "\n".join(section)

    return "\n".join(
        line for line in lines if any(re.search(pattern, line, re.IGNORECASE) for pattern in line_patterns)
    )


def check_completion_reports(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    docs = root / "docs"
    if not docs.exists():
        return findings
    for path in sorted(docs.glob("M*/*COMPLETION*.md")) + sorted(docs.glob("M*/*completion*.md")):
        if "_TEMPLATE" in path.name:
            continue
        text = read_text(path)
        findings.extend(check_one_completion_report(root, path, text))
    return findings


def check_one_completion_report(root: Path, path: Path, text: str) -> list[Finding]:
    display = relpath(root, path)
    lower = text.lower()
    required = {
        "completion-files-changed": "files changed",
        "completion-tests": "tests run",
        "completion-runtime-smoke": "runtime smoke",
        "completion-skipped-checks": "skipped checks",
        "completion-approval-gates": "approval gates",
    }
    findings: list[Finding] = []
    for rule, phrase in required.items():
        if phrase in lower:
            findings.append(Finding("PASS", rule, display, None, f"{phrase} is named"))
        else:
            findings.append(Finding("FAIL", rule, display, None, f"missing {phrase}"))
    if "remaining gaps" in lower or "next action" in lower or "handoff" in lower:
        findings.append(Finding("PASS", "completion-next-action", display, None, "remaining gaps or next action named"))
    else:
        findings.append(
            Finding("FAIL", "completion-next-action", display, None, "missing remaining gaps or next action")
        )
    findings.extend(check_adapter_evidence(root, path, text))
    return findings


def check_adapter_evidence(root: Path, path: Path, text: str) -> list[Finding]:
    lower = text.lower()
    if "adapter" not in lower and "capability" not in lower:
        return []
    if "_template" in path.name.lower():
        return []
    display = relpath(root, path)
    required = [
        ("adapter-authorization", ["authorization level", "metadata-only", "read-only", "write-inside-boundary"]),
        ("adapter-boundary", ["boundary served", "sage-kit boundary", "allowed files"]),
        ("adapter-evidence", ["evidence"]),
        ("adapter-fallback", ["fallback"]),
    ]
    findings: list[Finding] = []
    for rule, tokens in required:
        if any(token in lower for token in tokens):
            findings.append(Finding("PASS", rule, display, None, f"{rule} recorded"))
        else:
            findings.append(Finding("FAIL", rule, display, None, f"missing {rule.replace('-', ' ')}"))
    return findings


def check_task_dispatch(
    root: Path,
    gate_ready: bool = False,
    *,
    scope_manifest: ValidationScopeManifest | None = None,
    manifest_source: str = "project-local",
    manifest_error: str | None = None,
) -> list[Finding]:
    from .milestone_scope import MilestoneScopeKind, RepositoryScopeResolver

    findings: list[Finding] = []
    docs = root / "docs"
    if not docs.exists():
        return findings
    discovery = discover_task_dispatch_records(root)
    findings.extend(discovery.findings)
    active_task_paths: dict[Path, Path] = {}
    active_evidence_paths: dict[Path, Path] = {}
    resolver = RepositoryScopeResolver(
        root,
        manifest=scope_manifest,
        manifest_source=manifest_source,
        manifest_error=manifest_error,
    )
    scopes: dict[Path, object] = {}
    reported_scope_failures: set[Path] = set()
    for record in discovery.records:
        directory = record.directory
        task_path = record.task_path
        evidence_path = record.evidence_path
        container_dir = record.container_dir
        if container_dir not in scopes:
            scopes[container_dir] = resolver.resolve(container_dir)
        scope = scopes[container_dir]
        if (
            scope.kind == MilestoneScopeKind.AMBIGUOUS
            and container_dir not in reported_scope_failures
        ):
            findings.append(
                Finding(
                    "FAIL",
                    "milestone-scope",
                    relpath(root, container_dir),
                    None,
                    scope.detail,
                    "Reconcile active-context and closeout authority before validating records.",
                )
            )
            reported_scope_failures.add(container_dir)
        pair_findings, active_reconciliation = validate_task_dispatch_pair_with_scope(
            root,
            task_path,
            evidence_path,
            gate_ready,
            scope,
        )
        if scope.kind == MilestoneScopeKind.AMBIGUOUS:
            pair_findings = [
                finding
                for finding in pair_findings
                if not (
                    finding.rule == "task-dispatch"
                    and finding.message == scope.detail
                )
            ]
        findings.extend(pair_findings)
        if active_reconciliation:
            active_task_paths[directory] = task_path
            active_evidence_paths[directory] = evidence_path
    findings.extend(check_duplicate_task_ids(root, list(active_task_paths.values())))
    findings.extend(check_conflicting_exclusive_locks(root, list(active_task_paths.values())))
    findings.extend(check_conflicting_exclusive_leases(root, list(active_task_paths.values())))
    findings.extend(check_dispatch_boards(root, active_task_paths, active_evidence_paths))
    return findings


@dataclass(frozen=True)
class DiscoveredTaskDispatchRecord:
    directory: Path
    container_dir: Path
    container_path: str
    task_path: Path
    evidence_path: Path


@dataclass(frozen=True)
class TaskDispatchDiscovery:
    records: tuple[DiscoveredTaskDispatchRecord, ...]
    findings: tuple[Finding, ...]


def discover_task_dispatch_records(root: Path) -> TaskDispatchDiscovery:
    docs = root / "docs"
    if not docs.is_dir():
        return TaskDispatchDiscovery((), ())
    candidates: dict[Path, dict[str, Path]] = {}
    findings: list[Finding] = []
    invalid_directories: set[Path] = set()
    for path in sorted(docs.rglob("*.yaml")):
        if path.name not in {"task.yaml", "evidence.yaml"}:
            continue
        try:
            relative = path.relative_to(docs)
        except ValueError:
            continue
        folded = tuple(part.casefold() for part in relative.parts)
        if (
            not folded
            or folded[0] in {"templates", "profiles"}
            or ".sagekit" in folded
            or any("_template" in part for part in folded)
        ):
            continue
        dispatch_indexes = [
            index for index, part in enumerate(folded) if part == "dispatch"
        ]
        if len(dispatch_indexes) != 1 or dispatch_indexes[0] == 0:
            if len(dispatch_indexes) > 1 and path.parent not in invalid_directories:
                findings.append(
                    Finding(
                        "FAIL",
                        "task-dispatch-discovery",
                        relpath(root, path),
                        None,
                        "nested dispatch path cannot determine one container",
                    )
                )
            invalid_directories.add(path.parent)
            continue
        if not is_within(root, path):
            if path.parent not in invalid_directories:
                findings.append(
                    Finding(
                        "FAIL",
                        "task-dispatch-discovery",
                        relpath(root, path),
                        None,
                        "Task Dispatch record resolves outside the target root",
                    )
                )
            invalid_directories.add(path.parent)
            continue
        directory = path.parent
        candidates.setdefault(directory, {})[path.name] = path

    records: list[DiscoveredTaskDispatchRecord] = []
    for directory, pair in sorted(candidates.items()):
        if directory in invalid_directories:
            continue
        task_path = pair.get("task.yaml")
        evidence_path = pair.get("evidence.yaml")
        if task_path is None or evidence_path is None:
            present = task_path if task_path is not None else evidence_path
            missing = "task.yaml" if task_path is None else "evidence.yaml"
            findings.append(
                Finding(
                    "FAIL",
                    "task-dispatch",
                    relpath(root, present),
                    None,
                    f"{present.name} is present but {missing} is missing",
                )
            )
            continue
        relative = task_path.relative_to(docs)
        dispatch_index = next(
            index
            for index, part in enumerate(relative.parts)
            if part.casefold() == "dispatch"
        )
        container_dir = docs.joinpath(*relative.parts[:dispatch_index])
        if not is_within(root, container_dir):
            findings.append(
                Finding(
                    "FAIL",
                    "task-dispatch-discovery",
                    relpath(root, container_dir),
                    None,
                    "Task Dispatch container resolves outside the target root",
                )
            )
            continue
        if not (
            is_within(container_dir, directory)
            and is_within(directory, task_path)
            and is_within(directory, evidence_path)
        ):
            findings.append(
                Finding(
                    "FAIL",
                    "task-dispatch-discovery",
                    relpath(root, directory),
                    None,
                    "Task Dispatch pair resolves outside its record container "
                    "or record directory",
                )
            )
            continue
        records.append(
            DiscoveredTaskDispatchRecord(
                directory=directory,
                container_dir=container_dir,
                container_path=relative_repo_path(root, container_dir),
                task_path=task_path,
                evidence_path=evidence_path,
            )
        )
    return TaskDispatchDiscovery(tuple(records), tuple(findings))


def load_task_identity(task_path: Path) -> tuple[str, dict] | None:
    try:
        from .task_dispatch_validator import load_record

        task = load_record(task_path)
    except Exception:
        return None
    if not isinstance(task, dict):
        return None
    return str(task.get("id") or task_path.parent.name).strip(), task


def check_duplicate_task_ids(root: Path, task_paths: list[Path]) -> list[Finding]:
    declarations: dict[str, list[tuple[str, Path]]] = {}
    for task_path in sorted(task_paths):
        loaded = load_task_identity(task_path)
        if loaded is not None and loaded[0]:
            declarations.setdefault(loaded[0].casefold(), []).append((loaded[0], task_path))
    findings: list[Finding] = []
    for records in declarations.values():
        if len(records) > 1:
            paths = ", ".join(relpath(root, path) for _, path in records)
            findings.append(
                Finding(
                    "FAIL",
                    "task-dispatch-duplicate-id",
                    relpath(root, records[0][1]),
                    None,
                    f"duplicate task id {records[0][0]} is declared by: {paths}",
                )
            )
    return findings


def normalized_lock_resource(resource: str) -> str:
    return " ".join(resource.replace("\\", "/").split()).strip("/").casefold()


def lock_resources_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def check_conflicting_exclusive_locks(root: Path, task_paths: list[Path]) -> list[Finding]:
    try:
        from .task_dispatch_validator import ACTIVE_LOCK_STATUSES, load_record, upper
    except Exception:
        return []

    holders: list[tuple[str, str, str, Path]] = []
    for task_path in sorted(task_paths):
        loaded = load_task_identity(task_path)
        if loaded is None:
            continue
        task_id, task = loaded
        resources = task.get("resources")
        locks = resources.get("locks") if isinstance(resources, dict) else None
        if not isinstance(locks, list):
            continue
        for lock in locks:
            if not isinstance(lock, dict):
                continue
            resource = str(lock.get("resource") or "").strip()
            if (
                not resource
                or upper(lock.get("status")) not in ACTIVE_LOCK_STATUSES
                or upper(lock.get("mode")) != "EXCLUSIVE"
            ):
                continue
            holders.append((normalized_lock_resource(resource), resource, task_id, task_path))

    findings: list[Finding] = []
    for index, left in enumerate(holders):
        for right in holders[index + 1 :]:
            if left[3] == right[3] or not lock_resources_overlap(left[0], right[0]):
                continue
            resources = left[1] if left[0] == right[0] else f"{left[1]} and {right[1]}"
            findings.append(
                Finding(
                    "FAIL",
                    "task-dispatch-lock-conflict",
                    relpath(root, left[3]),
                    None,
                    f"exclusive lock conflict for {resources} across tasks: {left[2]}, {right[2]}",
                    "Release or change one lock before dispatching concurrent work.",
                )
            )
    return findings


def task_is_explicitly_archived(dispatch_dir: Path, task_id: str) -> bool:
    for filename in ["decisions.md", "DECISIONS.md"]:
        path = dispatch_dir / filename
        if not path.exists():
            continue
        for line in read_text(path).splitlines():
            cells = [cell.strip().strip("`").upper() for cell in line.strip().strip("|").split("|")]
            words = set(re.findall(r"[A-Z]+", " ".join(cells)))
            if (
                task_id.upper() in cells
                and "ACTIVE" in cells
                and words.intersection({"ARCHIVE", "ARCHIVED"})
            ):
                return True
    return False


def active_board_task_ids(board_path: Path) -> set[str]:
    text = read_text(board_path)
    match = re.search(r"(?im)^[ \t]*##\s+Active Tasks\s*$", text)
    if match is None:
        return set()
    remainder = text[match.end() :]
    next_section = re.search(r"(?m)^[ \t]*##\s+", remainder)
    section = remainder[: next_section.start()] if next_section else remainder
    return set(re.findall(r"\bTASK-[A-Za-z0-9._-]+\b", section))


def check_dispatch_boards(
    root: Path,
    task_paths: dict[Path, Path],
    evidence_paths: dict[Path, Path],
) -> list[Finding]:
    findings: list[Finding] = []
    dispatch_dirs: set[Path] = set()
    for directory in set(task_paths) | set(evidence_paths):
        for candidate in [directory, *directory.parents]:
            if candidate.name.casefold() == "dispatch":
                dispatch_dirs.add(candidate)
                break
    for dispatch_dir in sorted(dispatch_dirs):
        board_path = dispatch_dir / "DISPATCH_BOARD.md"
        if not board_path.exists():
            findings.append(
                Finding(
                    "FAIL",
                    "task-dispatch-board",
                    relpath(root, board_path),
                    None,
                    "Task Dispatch records are present but DISPATCH_BOARD.md is missing",
                )
            )
            continue
        board_ids = active_board_task_ids(board_path)
        records: dict[str, list[tuple[Path, dict]]] = {}
        for directory, task_path in task_paths.items():
            if (
                directory != dispatch_dir
                and dispatch_dir not in directory.parents
            ) or directory not in evidence_paths:
                continue
            loaded = load_task_identity(task_path)
            if loaded is not None:
                records.setdefault(loaded[0], []).append((task_path, loaded[1]))
        for task_id in sorted(board_ids - set(records)):
            findings.append(
                Finding("FAIL", "task-dispatch-board", relpath(root, board_path), None, f"board task {task_id} has no record pair")
            )
        for task_id, task_records in sorted(records.items()):
            if task_id in board_ids:
                continue
            if task_is_explicitly_archived(dispatch_dir, task_id):
                continue
            findings.append(
                Finding(
                    "FAIL",
                    "task-dispatch-board",
                    relpath(root, task_records[0][0]),
                    None,
                    f"record pair {task_id} is absent from DISPATCH_BOARD.md",
                )
            )
    return findings


def validate_task_dispatch_pair(
    root: Path, task_path: Path, evidence_path: Path, gate_ready: bool
) -> list[Finding]:
    from .milestone_scope import RepositoryScopeResolver

    container_scope = None
    try:
        relative = task_path.relative_to(root / "docs")
        dispatch_indexes = [
            index
            for index, part in enumerate(relative.parts)
            if part.casefold() == "dispatch"
        ]
        if len(dispatch_indexes) != 1 or dispatch_indexes[0] == 0:
            raise ValueError("record path does not have one dispatch container")
        container_dir = (root / "docs").joinpath(
            *relative.parts[: dispatch_indexes[0]]
        )
        manifest, manifest_source, manifest_error = resolve_check_scope_manifest(
            root,
            None,
        )
        container_scope = RepositoryScopeResolver(
            root,
            manifest=manifest,
            manifest_source=manifest_source,
            manifest_error=manifest_error,
        ).resolve(container_dir)
    except (IndexError, ValueError):
        pass
    findings, _ = validate_task_dispatch_pair_with_scope(
        root,
        task_path,
        evidence_path,
        gate_ready,
        container_scope,
    )
    return findings


def check_conflicting_exclusive_leases(root: Path, task_paths: list[Path]) -> list[Finding]:
    try:
        from .task_dispatch_validator import ACTIVE_LOCK_STATUSES, ACTIVE_RUN_STATUSES, upper
    except Exception:
        return []
    holders: list[tuple[str, str, str, str, Path]] = []
    for task_path in sorted(task_paths):
        loaded = load_task_identity(task_path)
        if loaded is None:
            continue
        task_id, task = loaded
        runs = task.get("runs")
        if not isinstance(runs, list):
            continue
        for run in runs:
            lease = run.get("lease") if isinstance(run, dict) else None
            if (
                not isinstance(lease, dict)
                or upper(run.get("status")) not in ACTIVE_RUN_STATUSES
                or upper(lease.get("status")) not in ACTIVE_LOCK_STATUSES
                or upper(lease.get("mode")) != "EXCLUSIVE"
            ):
                continue
            resource = str(lease.get("resource") or "").strip()
            if resource:
                holders.append(
                    (
                        normalized_lock_resource(resource),
                        resource,
                        task_id,
                        str(run.get("id") or "unknown-run"),
                        task_path,
                    )
                )
    findings: list[Finding] = []
    for index, left in enumerate(holders):
        for right in holders[index + 1 :]:
            if left[4] == right[4] or not lock_resources_overlap(left[0], right[0]):
                continue
            findings.append(
                Finding(
                    "FAIL",
                    "task-dispatch-lease-conflict",
                    relpath(root, left[4]),
                    None,
                    f"exclusive active lease conflict for {left[1]} across "
                    f"{left[2]}/{left[3]} and {right[2]}/{right[3]}",
                    "Release or change one lease before running concurrent work.",
                )
            )
    return findings


def validate_task_dispatch_pair_with_scope(
    root: Path,
    task_path: Path,
    evidence_path: Path,
    gate_ready: bool,
    container_scope=None,
) -> tuple[list[Finding], bool]:
    try:
        from .compatibility import validate_compatible_records
        from .task_dispatch_validator import ValidationError, load_record
    except Exception as exc:
        return (
            [
                Finding(
                    "FAIL",
                    "task-dispatch",
                    relpath(root, task_path),
                    None,
                    f"could not load Task Dispatch validator: {exc}",
                )
            ],
            True,
        )

    try:
        task = load_record(task_path)
        evidence = load_record(evidence_path)
        if not isinstance(task, dict):
            raise ValidationError(f"task record must be a mapping: {task_path}")
        if not isinstance(evidence, dict):
            raise ValidationError(f"evidence record must be a mapping: {evidence_path}")
        result = validate_compatible_records(
            task,
            evidence,
            gate_ready=gate_ready,
            container_scope=container_scope,
        )
        errors = list(result.errors)
        active_reconciliation = result.active_reconciliation
    except ValidationError as exc:
        errors = [str(exc)]
        result = None
        active_reconciliation = True

    findings: list[Finding] = []
    if result is not None and result.selection is not None:
        selection = result.selection
        findings.append(
            Finding(
                "PASS",
                "validation-contract",
                relpath(root, task_path),
                None,
                f"selected v{selection.version} {selection.policy_id} "
                f"({selection.scope.value}); "
                f"policy_digest=sha256:{selection.policy_sha256}"
                + (" by frozen legacy rule" if selection.implicit_legacy else "")
                + "; authority: "
                + "; ".join(selection.authority_basis),
            )
        )
    if errors:
        findings.extend(
            [
                Finding(
                    "FAIL",
                    "task-dispatch",
                    relpath(root, task_path),
                    None,
                    error,
                    "Fix task.yaml/evidence.yaml or run the standalone validator for detailed context.",
                )
                for error in errors
            ]
        )
        return findings, active_reconciliation
    findings.append(
        Finding(
            "PASS",
            "task-dispatch",
            relpath(root, task_path),
            None,
            "Task Dispatch validator passed",
        )
    )
    return findings, active_reconciliation


def default_schema_dir(root: Path) -> Path | None:
    candidates = [
        root / "docs/profiles/task-dispatch/schemas",
        Path(__file__).resolve().parents[1] / "docs/profiles/task-dispatch/schemas",
        Path(__file__).resolve().parent / "resources/docs/profiles/task-dispatch/schemas",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
