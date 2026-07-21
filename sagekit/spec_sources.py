"""Location-independent SPEC source selection and normalization."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from .execution_documents import (
    ExecutionDocumentError,
    ExecutionProject,
    _ensure_within,
    _reject_reparse_components,
    load_execution_project,
)


CONFIG_NAME = "SAGEKIT_CONFIG.json"
LEGACY_ACTIVE_CONTEXT = "docs/ACTIVE_CONTEXT.md"
LEGACY_DOC_ROUTING = "docs/DOC_ROUTING.md"
PUBLIC_CONTRACT_MANIFEST_VERSION = "public-contract-v1"
PUBLIC_HARNESS_API_VERSION = "harness-api-v1"
_PUBLIC_CONTRACT_RESOURCE_ROOTS = (
    "resources/contracts",
    "resources/execution_documents",
    "resources/resource_governance",
)
_CONFIG_FIELDS = {
    "schema_version",
    "project_id",
    "adoption_profile",
    "execution_scope",
    "active_context",
    "package",
    "sources",
}
_CONFIG_OPTIONAL_FIELDS = {"doc_routing", "profiles"}
_PACKAGE_FIELDS = {"name", "version", "digest"}
_SOURCE_FIELDS = {"adapter", "path"}
_MARKDOWN_BLOCK_RE = re.compile(
    r"^```sagekit-spec\s*$\n(?P<body>.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)
_CURRENT_SOURCE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:Active\s+SPEC\s+source|Current\s+SPEC\s+source|Current\s+source)\s*:\s*`?(?P<path>[^`\r\n]+?)`?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


class SourceConfigurationError(ValueError):
    """Fail-closed source selection or semantic input error."""


class DocumentClass(str, Enum):
    ACTIVE_SPEC = "ACTIVE_SPEC"
    ACTIVE_CONTEXT = "ACTIVE_CONTEXT"
    ACCEPTED_HISTORY = "ACCEPTED_HISTORY"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    RUNTIME_STATE = "RUNTIME_STATE"


@dataclass(frozen=True)
class SourceMapping:
    adapter: str
    path: str


@dataclass(frozen=True)
class SourceConfig:
    path: Path
    project_id: str
    adoption_profile: str
    execution_scope: str
    active_context: str
    doc_routing: str
    package: Mapping[str, str]
    sources: Mapping[str, SourceMapping]
    profiles: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceProvenance:
    target_root: str
    adapter: str
    configured_source: str
    canonical_path: str
    legacy_fallback: bool
    authority: str

    def to_dict(self) -> dict[str, object]:
        return {
            "target_root": self.target_root,
            "selected_adapter": self.adapter,
            "configured_source": self.configured_source,
            "resolved_canonical_path": self.canonical_path,
            "legacy_fallback_enabled": self.legacy_fallback,
            "authority": self.authority,
        }


@dataclass(frozen=True)
class NormalizedSpec:
    project: ExecutionProject
    semantic_digest: str
    provenance: SourceProvenance
    waves: Mapping[str, "WaveSpec"]
    document_class: DocumentClass
    active_context: "NormalizedActiveContext | None"


@dataclass(frozen=True)
class NormalizedActiveContext:
    """Compact handoff facts; ordinary view state is not SPEC identity."""

    current_milestone: str | None
    current_wave_phase: str | None
    current_state: str | None
    current_authority: str | None
    blockers: str | None
    next_action: str | None
    key_decisions: str | None
    evidence_pointer: str | None
    closeout_pointer: str | None
    document_class: DocumentClass = DocumentClass.ACTIVE_CONTEXT


@dataclass(frozen=True)
class WaveSpec:
    id: str
    depends_on: tuple[str, ...]
    phase_ids: tuple[str, ...]


def load_source_config(root: Path, *, required: bool = False) -> SourceConfig | None:
    project_root = root.resolve(strict=False)
    path = project_root / CONFIG_NAME
    if not path.exists():
        if required:
            raise SourceConfigurationError(f"project configuration is missing: {path}")
        return None
    _reject_reparse_components(project_root, path, "project configuration")
    _ensure_within(project_root, path, "project configuration")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SourceConfigurationError(f"project configuration JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise SourceConfigurationError("project configuration must contain one object")
    _exact_fields(
        payload,
        _CONFIG_FIELDS,
        "project configuration",
        optional=_CONFIG_OPTIONAL_FIELDS,
    )
    if payload.get("schema_version") != 1:
        raise SourceConfigurationError("project configuration schema_version must be 1")
    project_id = payload.get("project_id")
    if not isinstance(project_id, str) or re.fullmatch(
        r"[a-z0-9][a-z0-9._-]{0,127}", project_id
    ) is None:
        raise SourceConfigurationError(
            "project_id must be a lowercase machine-readable project identity"
        )
    adoption_profile = _enum(
        payload.get("adoption_profile"),
        {"package-bound", "vendored-legacy"},
        "adoption_profile",
    )
    execution_scope = _enum(
        payload.get("execution_scope"),
        {"active-only", "legacy-all"},
        "execution_scope",
    )
    active_context = _relative_path(payload.get("active_context"), "active_context")
    doc_routing = _relative_path(
        payload.get("doc_routing", LEGACY_DOC_ROUTING), "doc_routing"
    )
    package = payload.get("package")
    if not isinstance(package, dict):
        raise SourceConfigurationError("package binding must be an object")
    _exact_fields(package, _PACKAGE_FIELDS, "package binding")
    normalized_package: dict[str, str] = {}
    for key in sorted(_PACKAGE_FIELDS):
        value = package.get(key)
        if not isinstance(value, str) or not value.strip():
            raise SourceConfigurationError(f"package binding.{key} must be non-empty")
        normalized_package[key] = value.strip()
    digest = normalized_package["digest"]
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise SourceConfigurationError("package binding.digest must be lowercase SHA-256")
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, dict):
        raise SourceConfigurationError("sources must be an object")
    sources: dict[str, SourceMapping] = {}
    for milestone_id, raw in raw_sources.items():
        if not isinstance(milestone_id, str) or re.fullmatch(
            r"M[0-9]+(?:[._-][A-Za-z0-9]+)*", milestone_id
        ) is None:
            raise SourceConfigurationError(f"sources has invalid milestone ID: {milestone_id!r}")
        if not isinstance(raw, dict):
            raise SourceConfigurationError(f"sources.{milestone_id} must be an object")
        _exact_fields(raw, _SOURCE_FIELDS, f"sources.{milestone_id}")
        adapter = _enum(
            raw.get("adapter"), {"thin-v1", "markdown-v1"}, f"sources.{milestone_id}.adapter"
        )
        source_path = _relative_path(raw.get("path"), f"sources.{milestone_id}.path")
        sources[milestone_id] = SourceMapping(adapter, source_path)
    raw_profiles = payload.get("profiles", [])
    if not isinstance(raw_profiles, list) or not all(
        isinstance(item, str) and item for item in raw_profiles
    ):
        raise SourceConfigurationError("profiles must be an array of profile IDs")
    profiles = tuple(raw_profiles)
    if len(set(profiles)) != len(profiles):
        raise SourceConfigurationError("profiles must contain unique profile IDs")
    unknown_profiles = sorted(set(profiles) - {"task-dispatch-v2"})
    if unknown_profiles:
        raise SourceConfigurationError(
            "profiles contains unsupported profile(s): " + ", ".join(unknown_profiles)
        )
    return SourceConfig(
        path=path,
        project_id=project_id,
        adoption_profile=adoption_profile,
        execution_scope=execution_scope,
        active_context=active_context,
        doc_routing=doc_routing,
        package=normalized_package,
        sources=sources,
        profiles=profiles,
    )


def resolve_active_context_path(root: Path, config: SourceConfig | None = None) -> Path:
    project_root = root.resolve(strict=False)
    selected = config if config is not None else load_source_config(project_root)
    relative = selected.active_context if selected is not None else LEGACY_ACTIVE_CONTEXT
    path = project_root / Path(*PurePosixPath(relative).parts)
    _reject_reparse_components(project_root, path, "ACTIVE_CONTEXT")
    _ensure_within(project_root, path, "ACTIVE_CONTEXT")
    return path.resolve(strict=False)


def resolve_doc_routing_path(root: Path, config: SourceConfig | None = None) -> Path:
    project_root = root.resolve(strict=False)
    selected = config if config is not None else load_source_config(project_root)
    relative = selected.doc_routing if selected is not None else LEGACY_DOC_ROUTING
    path = project_root / Path(*PurePosixPath(relative).parts)
    _reject_reparse_components(project_root, path, "DOC_ROUTING")
    _ensure_within(project_root, path, "DOC_ROUTING")
    return path.resolve(strict=False)


def current_source_pointer(root: Path, config: SourceConfig | None = None) -> str | None:
    path = resolve_active_context_path(root, config)
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise SourceConfigurationError(f"ACTIVE_CONTEXT is unreadable: {exc}") from exc
    pointers = []
    for line in _active_context_authority_lines(text):
        match = _CURRENT_SOURCE_RE.match(line)
        if match is not None:
            pointers.append(
                _relative_path(match.group("path").strip(), "ACTIVE_CONTEXT current source")
            )
    if not pointers:
        return None
    distinct = tuple(dict.fromkeys(pointers))
    if len(distinct) > 1:
        raise SourceConfigurationError(
            "ACTIVE_CONTEXT has conflicting current SPEC source declarations"
        )
    return distinct[0]


def load_normalized_spec(
    root: Path,
    milestone_id: str,
    *,
    source: Path | None = None,
    _contract_root: Path | None = None,
    phase_id: str | None = None,
    scope_manifest: Any | None = None,
    **_internal: Any,
) -> NormalizedSpec:
    # Private packet compilation in older package builds used this spelling.
    if _internal:
        if set(_internal) != {"contract_root"} or _contract_root is not None:
            unexpected = ", ".join(sorted(_internal))
            raise TypeError(f"unexpected internal argument(s): {unexpected}")
        _contract_root = _internal["contract_root"]
    project_root = root.resolve(strict=False)
    config = load_source_config(project_root)
    if config is not None:
        validate_package_binding(config)
    configured_source: str
    authority: str
    legacy_fallback = False
    requested_adapter: str | None = None

    if source is not None:
        configured_source = str(source)
        authority = "explicit-source"
    else:
        mapping = config.sources.get(milestone_id) if config is not None else None
        pointer = current_source_pointer(project_root, config)
        if mapping is not None:
            if pointer is not None and pointer != mapping.path:
                raise SourceConfigurationError(
                    "ACTIVE_CONTEXT current SPEC source declaration conflicts with "
                    f"configured source mapping for {milestone_id}"
                )
            configured_source = mapping.path
            requested_adapter = mapping.adapter
            authority = "project-config"
        else:
            if pointer is not None:
                configured_source = pointer
                authority = "active-context"
            elif config is None:
                configured_source = f"docs/{milestone_id}"
                requested_adapter = "thin-v1"
                authority = "legacy-fallback"
                legacy_fallback = True
            else:
                raise _diagnostic_error(
                    project_root,
                    "unresolved",
                    "<not configured>",
                    project_root,
                    "active source authority for milestone " + milestone_id,
                    legacy_fallback=False,
                )

    candidate = Path(configured_source).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    canonical = candidate.resolve(strict=False)
    adapter = requested_adapter or _infer_adapter(canonical)
    display_adapter = (
        f"legacy-{adapter}"
        if legacy_fallback
        else f"configured-{adapter}"
        if authority == "project-config"
        else adapter
    )
    try:
        _reject_reparse_components(project_root, candidate, "SPEC source")
        _ensure_within(project_root, candidate, "SPEC source")
    except ExecutionDocumentError as exc:
        raise _diagnostic_error(
            project_root,
            display_adapter,
            configured_source,
            canonical,
            str(exc),
            legacy_fallback=legacy_fallback,
        ) from exc
    if not canonical.exists():
        raise _diagnostic_error(
            project_root,
            display_adapter,
            configured_source,
            canonical,
            "SPEC source does not exist",
            legacy_fallback=legacy_fallback,
        )
    _reject_accepted_history_source(
        project_root,
        canonical,
        scope_manifest=scope_manifest,
    )

    waves: Mapping[str, WaveSpec] = {}
    try:
        if adapter == "thin-v1":
            source_root = canonical.parent if canonical.is_file() else canonical
            if canonical.is_file() and canonical.name != "MILESTONE_MANIFEST.json":
                raise ExecutionDocumentError(
                    "thin-v1 source file must be MILESTONE_MANIFEST.json or a source directory"
                )
            project = load_execution_project(
                project_root,
                milestone_id,
                contract_root=_contract_root,
                source_root=source_root,
                required_phase_id=phase_id,
            )
            waves_path = source_root / "WAVES.json"
            if waves_path.exists():
                raw_waves = json.loads(waves_path.read_text(encoding="utf-8-sig"))
                waves = _normalize_waves(raw_waves, project)
        elif adapter == "markdown-v1":
            payload = _markdown_payload(canonical)
            raw_waves = payload.get("waves", [])
            project = load_execution_project(
                project_root,
                milestone_id,
                contract_root=_contract_root,
                source_payload={
                    "milestone": payload.get("milestone"),
                    "phases": payload.get("phases"),
                },
                source_path=canonical,
                required_phase_id=phase_id,
            )
            waves = _normalize_waves(raw_waves, project)
        else:  # defensive: config and inference are closed sets
            raise ExecutionDocumentError(f"unknown SPEC source adapter: {adapter}")
    except (ExecutionDocumentError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _diagnostic_error(
            project_root,
            display_adapter,
            configured_source,
            canonical,
            str(exc),
            legacy_fallback=legacy_fallback,
        ) from exc

    semantic = _semantic_payload(project, waves, config)
    digest = hashlib.sha256(
        json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return NormalizedSpec(
        project=project,
        semantic_digest=digest,
        provenance=SourceProvenance(
            target_root=str(project_root),
            adapter=display_adapter,
            configured_source=configured_source,
            canonical_path=str(canonical),
            legacy_fallback=legacy_fallback,
            authority=authority,
        ),
        waves=waves,
        document_class=DocumentClass.ACTIVE_SPEC,
        active_context=load_active_context_view(project_root, config),
    )


def load_active_context_view(
    root: Path, config: SourceConfig | None = None
) -> NormalizedActiveContext | None:
    """Read only the compact handoff fields without expanding referenced history."""

    path = resolve_active_context_path(root, config)
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise SourceConfigurationError(f"ACTIVE_CONTEXT is unreadable: {exc}") from exc
    combined_pointer = _context_field(text, "Evidence/closeout pointers")
    return NormalizedActiveContext(
        current_milestone=_context_field(text, "Current milestone"),
        current_wave_phase=(
            _context_field(text, "Current wave/phase")
            or _context_field(text, "Current phase")
        ),
        current_state=(
            _context_field(text, "Current state")
            or _context_field(text, "Current status")
        ),
        current_authority=_context_field(text, "Current authority"),
        blockers=(
            _context_field(text, "Current blockers")
            or _context_field(text, "Blockers")
        ),
        next_action=_context_field(text, "Next action"),
        key_decisions=_context_field(text, "Key decisions"),
        evidence_pointer=(
            _context_field(text, "Evidence pointer") or combined_pointer
        ),
        closeout_pointer=(
            _context_field(text, "Closeout pointer") or combined_pointer
        ),
    )


def _context_field(text: str, label: str) -> str | None:
    match = re.search(
        rf"^\s*(?:[-*]\s*)?{re.escape(label)}\s*:\s*`?([^`\r\n]+?)`?\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    return match.group(1).strip() if match is not None else None


def _active_context_authority_lines(text: str):
    fence: str | None = None
    in_comment = False
    for raw_line in text.splitlines():
        line, in_comment = _without_html_comments(raw_line, in_comment)
        stripped = line.lstrip()
        marker = re.match(r"(?P<fence>`{3,}|~{3,})", stripped)
        if marker is not None:
            fence_char = marker.group("fence")[0]
            if fence is None:
                fence = fence_char
            elif fence == fence_char:
                fence = None
            continue
        if fence is None and not line.startswith(("    ", "\t")):
            yield line


def _without_html_comments(line: str, in_comment: bool) -> tuple[str, bool]:
    output: list[str] = []
    cursor = 0
    while cursor < len(line):
        if in_comment:
            end = line.find("-->", cursor)
            if end < 0:
                return "".join(output), True
            in_comment = False
            cursor = end + 3
            continue
        start = line.find("<!--", cursor)
        if start < 0:
            output.append(line[cursor:])
            break
        output.append(line[cursor:start])
        in_comment = True
        cursor = start + 4
    return "".join(output), in_comment


def public_contract_manifest(package_root: Path | None = None) -> dict[str, Any]:
    """Describe only the stable public API and executable semantic contracts."""

    root = (
        Path(package_root).expanduser().resolve(strict=False)
        if package_root is not None
        else Path(__file__).resolve().parent
    )
    resources: dict[str, str] = {}
    for relative_root in _PUBLIC_CONTRACT_RESOURCE_ROOTS:
        contract_root = root / Path(*PurePosixPath(relative_root).parts)
        if not contract_root.is_dir():
            raise SourceConfigurationError(
                f"installed SAGE-Kit public contract resource is missing: {relative_root}"
            )
        for path in sorted(item for item in contract_root.rglob("*") if item.is_file()):
            if path.is_symlink():
                raise SourceConfigurationError(
                    f"installed SAGE-Kit public contract resource must not be a symlink: {path}"
                )
            relative = path.relative_to(root).as_posix()
            resources[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not resources:
        raise SourceConfigurationError("installed SAGE-Kit public contract manifest is empty")
    return {
        "manifest_version": PUBLIC_CONTRACT_MANIFEST_VERSION,
        "public_api_version": PUBLIC_HARNESS_API_VERSION,
        "resources": resources,
    }


def package_identity(package_root: Path | None = None) -> dict[str, str]:
    """Return the stable public contract identity used by project authority."""

    manifest = public_contract_manifest(package_root)
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "name": "sagekit",
        "version": PUBLIC_CONTRACT_MANIFEST_VERSION,
        "digest": hashlib.sha256(canonical).hexdigest(),
    }


def validate_package_binding(config: SourceConfig) -> None:
    actual = package_identity()
    differences = [
        key for key in ("name", "version", "digest") if config.package.get(key) != actual[key]
    ]
    if differences:
        raise SourceConfigurationError(
            "project public contract authority does not match the executing Harness: "
            + ", ".join(differences)
        )


def _reject_accepted_history_source(
    root: Path,
    source: Path,
    *,
    scope_manifest: Any | None = None,
) -> None:
    """Prevent explicitly classified accepted history from becoming execution input."""

    from .validation_scope_manifest import (
        LOCAL_SCOPE_MANIFEST,
        ScopeManifestError,
        load_validation_scope_manifest,
    )

    manifest = scope_manifest
    if manifest is None:
        manifest_path = root / LOCAL_SCOPE_MANIFEST
        if not manifest_path.exists():
            return
        try:
            manifest = load_validation_scope_manifest(manifest_path)
        except ScopeManifestError as exc:
            raise SourceConfigurationError(
                f"validation scope authority is invalid: {exc}"
            ) from exc
    source_relative = source.relative_to(root).as_posix().casefold()
    for container in manifest.accepted_legacy_containers:
        accepted = container.path.casefold()
        if source_relative == accepted or source_relative.startswith(accepted + "/"):
            raise SourceConfigurationError(
                "accepted history is non-executable and may be opened only by an explicit "
                f"history audit: {container.path}"
            )


def _markdown_payload(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise ExecutionDocumentError("markdown-v1 source must be a regular file")
    text = path.read_text(encoding="utf-8-sig")
    matches = list(_MARKDOWN_BLOCK_RE.finditer(text))
    if len(matches) != 1:
        raise ExecutionDocumentError(
            "markdown-v1 source must contain exactly one fenced sagekit-spec semantic block"
        )
    try:
        payload = json.loads(matches[0].group("body"))
    except json.JSONDecodeError as exc:
        raise ExecutionDocumentError(f"sagekit-spec JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExecutionDocumentError("sagekit-spec block must contain one JSON object")
    return payload


def _normalize_waves(value: Any, project: ExecutionProject) -> Mapping[str, WaveSpec]:
    if value in (None, []):
        return {}
    if not isinstance(value, list):
        raise ExecutionDocumentError("waves must be an array")
    waves: dict[str, WaveSpec] = {}
    assigned: dict[str, str] = {}
    for index, raw in enumerate(value):
        label = f"waves[{index}]"
        if not isinstance(raw, dict) or set(raw) != {"id", "depends_on", "phase_ids"}:
            raise ExecutionDocumentError(
                f"{label} must contain exactly id, depends_on, and phase_ids"
            )
        wave_id = raw.get("id")
        if not isinstance(wave_id, str) or re.fullmatch(
            r"W[0-9]+(?:[._-][A-Za-z0-9]+)*", wave_id
        ) is None:
            raise ExecutionDocumentError(f"{label}.id is invalid")
        if wave_id in waves:
            raise ExecutionDocumentError(f"duplicate wave ID: {wave_id}")
        depends_on = _string_array(raw.get("depends_on"), f"{label}.depends_on")
        phase_ids = _string_array(raw.get("phase_ids"), f"{label}.phase_ids", nonempty=True)
        for phase_id in phase_ids:
            if phase_id not in project.milestone.phase_ids:
                raise ExecutionDocumentError(f"{label} contains unknown phase: {phase_id}")
            if phase_id in assigned:
                raise ExecutionDocumentError(
                    f"phase {phase_id} is assigned to multiple waves: {assigned[phase_id]}, {wave_id}"
                )
            assigned[phase_id] = wave_id
        waves[wave_id] = WaveSpec(wave_id, depends_on, phase_ids)
    missing = set(project.milestone.phase_ids) - set(assigned)
    if missing:
        raise ExecutionDocumentError(
            "waves do not assign every phase: " + ", ".join(sorted(missing))
        )
    for wave in waves.values():
        unknown = set(wave.depends_on) - set(waves)
        if unknown or wave.id in wave.depends_on:
            raise ExecutionDocumentError(f"wave {wave.id} has an invalid dependency")
    _reject_wave_cycles(waves)
    for phase_id, phase in project.phases.items():
        wave_id = assigned[phase_id]
        required_waves = {assigned[dependency] for dependency in phase.depends_on}
        required_waves.discard(wave_id)
        if not required_waves.issubset(waves[wave_id].depends_on):
            raise ExecutionDocumentError(
                f"wave {wave_id} omits phase dependency wave(s): "
                + ", ".join(sorted(required_waves - set(waves[wave_id].depends_on)))
            )
    return waves


def _reject_wave_cycles(waves: Mapping[str, WaveSpec]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(wave_id: str) -> None:
        if wave_id in visiting:
            raise ExecutionDocumentError("wave dependency DAG contains a cycle")
        if wave_id in visited:
            return
        visiting.add(wave_id)
        for dependency in waves[wave_id].depends_on:
            visit(dependency)
        visiting.remove(wave_id)
        visited.add(wave_id)

    for wave_id in waves:
        visit(wave_id)


def _string_array(value: Any, label: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ExecutionDocumentError(f"{label} must be an array" + (" and non-empty" if nonempty else ""))
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or item in result:
            raise ExecutionDocumentError(f"{label} must contain unique non-empty strings")
        result.append(item)
    return tuple(result)


def _semantic_payload(
    project: ExecutionProject,
    waves: Mapping[str, WaveSpec],
    config: SourceConfig | None,
) -> dict[str, Any]:
    milestone = project.milestone
    phases = project.phases
    return {
        "project_authority": (
            {
                "schema_version": 1,
                "project_id": config.project_id,
                "adoption_profile": config.adoption_profile,
                "execution_scope": config.execution_scope,
                "package": dict(sorted(config.package.items())),
                "profiles": list(config.profiles),
            }
            if config is not None
            else None
        ),
        "project": {
            "schema_version": project.project_lock.schema_version,
            "sagekit_contract": project.project_lock.sagekit_contract,
            "execution_document_model": project.project_lock.execution_document_model,
            "effective_from": project.project_lock.effective_from,
            "legacy_documents": project.project_lock.legacy_documents,
            "profiles": list(project.project_lock.profiles),
            "overrides": project.project_lock.overrides,
            "resource_contract": project.project_lock.resource_contract,
        },
        "contract_sha256": project.contract.digest,
        "milestone": {
            "milestone_id": milestone.milestone_id,
            "objective": milestone.objective,
            "capability_outcome": milestone.capability_outcome,
            "authority_references": list(milestone.authority_references),
            "governance_profile": milestone.governance_profile,
            "dependency_dag": {
                key: list(value) for key, value in milestone.dependency_dag.items()
            },
            "approval_gates": [
                {
                    "id": gate.id,
                    "applies_to": list(gate.applies_to),
                    "status": gate.status,
                    "permission_mode": gate.permission_mode,
                    "authority_reference": gate.authority_reference,
                }
                for gate in milestone.approval_gates
            ],
            "phase_ids": list(milestone.phase_ids),
            "acceptance_criteria": list(milestone.acceptance_criteria),
            "invariants": list(milestone.invariants),
            "state": milestone.state,
            "evidence_references": list(milestone.evidence_references),
        },
        "phases": {
            phase_id: {
                "phase_id": phase.phase_id,
                "objective": phase.objective,
                "depends_on": list(phase.depends_on),
                "execution_profile": phase.execution_profile,
                "permission_mode": phase.permission_mode,
                "owner": phase.owner,
                "writable_paths": list(phase.writable_paths),
                "read_only_references": list(phase.read_only_references),
                "forbidden_paths": list(phase.forbidden_paths),
                "inherit_forbidden": phase.inherit_forbidden,
                "acceptance_criteria": list(phase.acceptance_criteria),
                "verification_commands": list(phase.verification_commands),
                "evidence_requirements": list(phase.evidence_requirements),
                "stop_conditions": list(phase.stop_conditions),
                "handoff_target": phase.handoff_target,
                "state": phase.state,
                "resource_profile": phase.resource_profile,
                "resource_overrides": phase.resource_overrides,
            }
            for phase_id, phase in sorted(phases.items())
        },
        "waves": {
            wave_id: {
                "id": wave.id,
                "depends_on": list(wave.depends_on),
                "phase_ids": list(wave.phase_ids),
            }
            for wave_id, wave in sorted(waves.items())
        },
    }


def _infer_adapter(path: Path) -> str:
    return "markdown-v1" if path.suffix.casefold() in {".md", ".markdown"} else "thin-v1"


def _diagnostic_error(
    root: Path,
    adapter: str,
    configured_source: str,
    canonical: Path,
    missing: str,
    *,
    legacy_fallback: bool,
) -> SourceConfigurationError:
    return SourceConfigurationError(
        "SPEC source resolution failed\n"
        f"target root: {root}\n"
        f"selected adapter: {adapter}\n"
        f"configured source: {configured_source}\n"
        f"resolved canonical path: {canonical}\n"
        f"missing semantic input: {missing}\n"
        f"legacy fallback enabled: {str(legacy_fallback).lower()}"
    )


def _relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceConfigurationError(f"{label} must be a non-empty relative path")
    text = value.strip()
    path = PurePosixPath(text)
    windows = PureWindowsPath(text)
    if (
        "\\" in text
        or path.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or path.as_posix() != text
        or any(part in {".", ".."} for part in path.parts)
        or any(part.endswith((".", " ")) for part in path.parts)
        or any(character in text for character in "*?[]:")
    ):
        raise SourceConfigurationError(f"{label} must be a normalized target-relative path")
    return text


def _enum(value: Any, allowed: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise SourceConfigurationError(
            f"{label} must be one of: " + ", ".join(sorted(allowed))
        )
    return value


def _exact_fields(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
    *,
    optional: set[str] | frozenset[str] = frozenset(),
) -> None:
    unknown = sorted(set(value) - expected - set(optional))
    missing = sorted(expected - set(value))
    if unknown:
        raise SourceConfigurationError(f"{label} has unknown field(s): " + ", ".join(unknown))
    if missing:
        raise SourceConfigurationError(f"{label} is missing field(s): " + ", ".join(missing))


__all__ = [
    "CONFIG_NAME",
    "DocumentClass",
    "LEGACY_ACTIVE_CONTEXT",
    "LEGACY_DOC_ROUTING",
    "PUBLIC_CONTRACT_MANIFEST_VERSION",
    "PUBLIC_HARNESS_API_VERSION",
    "NormalizedActiveContext",
    "NormalizedSpec",
    "SourceConfig",
    "SourceConfigurationError",
    "SourceMapping",
    "SourceProvenance",
    "WaveSpec",
    "current_source_pointer",
    "load_normalized_spec",
    "load_active_context_view",
    "load_source_config",
    "package_identity",
    "public_contract_manifest",
    "resolve_active_context_path",
    "resolve_doc_routing_path",
    "validate_package_binding",
]
