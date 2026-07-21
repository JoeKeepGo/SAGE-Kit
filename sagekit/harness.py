"""Embeddable SAGE-Kit harness entrypoints for downstream consumers."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Callable, Mapping, Sequence
import warnings

from .compatibility import ContractSelection, validate_compatible_records
from .candidate import (
    CandidateAssessment,
    CandidateFingerprint,
    CandidateFreezeResult,
    assess_candidate,
    freeze_candidate,
)
from .check import detect_root, run_check
from .change_control import ChangeClass
from .convergence import PreauthorizedConvergenceAuthority
from .continuity import (
    CheckpointResult,
    clear_checkpoint,
    create_checkpoint,
    get_checkpoint_status,
    resume_checkpoint,
)
from .execution_limits import ExecutionCounters
from .findings import Finding
from .managed_execution import (
    ManagedExecutionError,
    _run_managed_command,
    run_managed_git as _run_managed_git,
)
from .packet import (
    CompiledPacket,
    PacketConfigurationError,
    PacketError,
    _compile_packet,
    _current_packet_authority as _revalidate_current_packet_authority,
    _packet_revalidation_source,
    write_compiled_packet as _write_compiled_packet,
    _validate_packet_for_write,
)
from .process_supervisor import ProcessResult
from .resource_governor import (
    ResourceBusy,
    ResourceClass,
    ResourceManager,
    ResourceRequest,
    default_host_identity,
    host_runtime_path,
    project_runtime_path,
)
from .spec_sources import (
    NormalizedSpec,
    SourceConfig,
    SourceConfigurationError,
    load_normalized_spec,
    load_source_config,
)
from .milestone_scope import RepositoryScopeResolver
from .task_dispatch_validator import ValidationError, load_record
from .validation_scope_manifest import (
    LOCAL_SCOPE_MANIFEST,
    ScopeManifestError,
    load_validation_scope_manifest,
)
from .workspace_binding import (
    WorkspaceBinding,
    WorkspaceIdentity,
    WorkspaceVerification,
    build_workspace_binding,
    discover_workspace,
    verify_workspace as _verify_workspace,
)


@dataclass(frozen=True)
class TaskEvidenceValidationResult:
    task_path: Path
    evidence_path: Path
    errors: tuple[str, ...]
    selection: ContractSelection | None
    active_reconciliation: bool

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


@dataclass(frozen=True)
class ProjectCheckResult:
    """Stable, read-only result for a project or gate validation run."""

    project_root: Path
    findings: tuple[Finding, ...]
    gate_ready: bool
    mode: str | None
    scope: str | None
    scope_manifest_path: Path | None

    @property
    def ok(self) -> bool:
        return not any(finding.level == "FAIL" for finding in self.findings)


def check_project(
    project_root: Path,
    *,
    gate_ready: bool = False,
    mode: str | None = None,
    scope: str | None = None,
    scope_manifest_path: Path | None = None,
) -> ProjectCheckResult:
    """Run read-only project validation without command-line semantics."""

    root = detect_root(Path(project_root))
    manifest = (
        Path(scope_manifest_path).resolve(strict=False)
        if scope_manifest_path is not None
        else None
    )
    findings = run_check(
        root,
        gate_ready=gate_ready,
        mode=mode,
        scope=scope,
        scope_manifest_path=manifest,
    )
    return ProjectCheckResult(
        project_root=root,
        findings=tuple(findings),
        gate_ready=gate_ready,
        mode=mode,
        scope=scope,
        scope_manifest_path=manifest,
    )


def load_project_source_config(
    project_root: Path, *, required: bool = False
) -> SourceConfig | None:
    return load_source_config(project_root, required=required)


def load_project_normalized_spec(
    project_root: Path,
    milestone_id: str,
    *,
    source: Path | None = None,
    phase_id: str | None = None,
):
    return load_normalized_spec(
        project_root,
        milestone_id,
        source=source,
        phase_id=phase_id,
    )


def compile_ephemeral_packet(
    project_root: Path,
    milestone_id: str,
    phase_id: str | None = None,
    *,
    source: Path | None = None,
    compact: bool = False,
) -> CompiledPacket:
    return _compile_packet(
        project_root,
        milestone_id,
        phase_id,
        source=source,
        compact=compact,
    )


def write_ephemeral_packet(
    project_root: Path,
    relative_output: str | Path,
    packet: CompiledPacket,
    *,
    overwrite_generated: bool = False,
) -> Path:
    canonical = _current_packet_authority(project_root, packet)
    relative = str(relative_output).replace("\\", "/").casefold()
    if relative.startswith(".sagekit/packets/"):
        resource = canonical.payload["resolved_resource_policy"]
        allowed = resource.get("allowed_resource_classes")
        if not isinstance(allowed, list) or ResourceClass.REPO_WRITE.value not in allowed:
            raise PacketError("packet does not authorize repo-write runtime output")
    return _write_compiled_packet(
        project_root,
        relative_output,
        canonical,
        overwrite_generated=overwrite_generated,
    )


def validate_task_and_evidence_records(
    project_root: Path,
    task_path: Path,
    evidence_path: Path,
    *,
    gate_ready: bool = False,
    container_root: Path | None = None,
    scope_manifest_path: Path | None = None,
) -> TaskEvidenceValidationResult:
    root = Path(project_root).resolve(strict=True)
    task_path = Path(task_path).resolve(strict=True)
    evidence_path = Path(evidence_path).resolve(strict=True)
    if task_path.parent != evidence_path.parent:
        raise ValidationError("task and evidence records must share one record directory")
    task = load_record(task_path)
    evidence = load_record(evidence_path)
    if not isinstance(task, dict) or not isinstance(evidence, dict):
        raise ValidationError("task and evidence records must be mappings")
    container = (
        Path(container_root).resolve(strict=True)
        if container_root is not None
        else _dispatch_container_for_record(root, task_path)
    )
    manifest_path = (
        Path(scope_manifest_path).resolve(strict=True)
        if scope_manifest_path is not None
        else root / LOCAL_SCOPE_MANIFEST
    )
    manifest = None
    manifest_error = None
    if manifest_path.is_file():
        try:
            manifest = load_validation_scope_manifest(manifest_path)
        except ScopeManifestError as exc:
            manifest_error = str(exc)
    scope = RepositoryScopeResolver(
        root,
        manifest=manifest,
        manifest_source=("explicit-harness" if scope_manifest_path else "project-local"),
        manifest_error=manifest_error,
    ).resolve(container)
    result = validate_compatible_records(
        task,
        evidence,
        gate_ready=gate_ready,
        container_scope=scope,
    )
    return TaskEvidenceValidationResult(
        Path(task_path),
        Path(evidence_path),
        result.errors,
        result.selection,
        result.active_reconciliation,
    )


def _dispatch_container_for_record(root: Path, record_path: Path) -> Path:
    if root not in record_path.parents:
        raise ValidationError("Task Dispatch record resolves outside the project root")
    for parent in record_path.parents:
        if parent.name.casefold() == "dispatch":
            return parent.parent
        if parent == root:
            break
    raise ValidationError(
        "Task Dispatch record is not under a container/dispatch/<record> topology; "
        "pass container_root explicitly"
    )
def discover_project_workspace(project_root: Path) -> WorkspaceIdentity:
    return discover_workspace(project_root)


def build_project_workspace_binding(
    project_root: Path,
    *,
    permission_mode: str,
    controller: str,
    base_head: str | None,
    allowed_paths: Sequence[str],
    read_only_paths: Sequence[str] = (),
    forbidden_paths: Sequence[str] = (),
) -> WorkspaceBinding:
    identity = discover_workspace(project_root)
    return build_workspace_binding(
        identity,
        base_head=base_head,
        permission_mode=permission_mode,
        controller=controller,
        allowed_paths=allowed_paths,
        read_only_paths=read_only_paths,
        forbidden_paths=forbidden_paths,
    )


def verify_project_workspace(
    binding: WorkspaceBinding,
    *,
    current: WorkspaceIdentity | None = None,
    cwd: Path | None = None,
) -> WorkspaceVerification:
    return _verify_workspace(binding, current=current, cwd=cwd)


def run_managed_command(
    project_root: Path,
    packet: CompiledPacket,
    command: Sequence[str],
    *,
    resource_class: ResourceClass,
    stage: str,
    run_id: str,
    timeout: float,
    delegated_classes: Sequence[ResourceClass] = (),
    max_output_bytes: int = 65_536,
    environment: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    temp_root: Path | None = None,
    wait_timeout: float = 30.0,
    check: bool = True,
    on_heartbeat: Callable[[object], None] | None = None,
    on_wait: Callable[[str], None] | None = None,
    max_owned_processes: int = 32,
    source: Path | None = None,
) -> ProcessResult:
    authority = _packet_execution_authority(
        project_root,
        packet,
        resource_class=resource_class,
        delegated_classes=delegated_classes,
        source=source,
        max_output_bytes=max_output_bytes,
        wait_timeout=wait_timeout,
        max_owned_processes=max_owned_processes,
    )
    with _exclusive_packet_resources(
        project_root,
        packet,
        authority,
        wait_timeout=wait_timeout,
    ) as refresh_exclusive_lease:
        def heartbeat(event: object) -> None:
            if refresh_exclusive_lease is not None:
                refresh_exclusive_lease(event)
            if on_heartbeat is not None:
                on_heartbeat(event)

        return _run_managed_command(
            project_root,
            command,
            resource_class=resource_class,
            permission_mode=authority.binding.permission_mode,
            controller=authority.binding.controller,
            stage=stage,
            run_id=run_id,
            timeout=timeout,
            delegated_classes=delegated_classes,
            max_output_bytes=max_output_bytes,
            environment=environment,
            cwd=cwd,
            temp_root=temp_root,
            wait_timeout=wait_timeout,
            check=check,
            on_heartbeat=(heartbeat if refresh_exclusive_lease is not None else on_heartbeat),
            on_wait=on_wait,
            isolated_test_harness=False,
            max_owned_processes=max_owned_processes,
            workspace_binding=authority.binding,
            allowed_resource_classes=authority.allowed_classes,
            authority_digest=packet.digest,
        )


def run_managed_readonly_git_command(
    project_root: Path,
    packet: CompiledPacket,
    arguments: Sequence[str],
    *,
    stage: str,
    run_id: str | None = None,
    timeout: float = 30.0,
    max_output_bytes: int = 65_536,
    source: Path | None = None,
) -> ProcessResult:
    _packet_execution_authority(
        project_root,
        packet,
        resource_class=ResourceClass.REPO_READ,
        delegated_classes=(),
        source=source,
        max_output_bytes=max_output_bytes,
        wait_timeout=0.0,
        max_owned_processes=2,
    )
    return _run_managed_git(
        project_root,
        arguments,
        stage=stage,
        run_id=run_id,
        timeout=timeout,
        max_output_bytes=max_output_bytes,
    )


def run_managed_git_command(
    project_root: Path,
    packet: CompiledPacket,
    arguments: Sequence[str],
    *,
    stage: str,
    run_id: str | None = None,
    timeout: float = 30.0,
    max_output_bytes: int = 65_536,
    source: Path | None = None,
) -> ProcessResult:
    warnings.warn(
        "run_managed_git_command is deprecated; use "
        "run_managed_readonly_git_command",
        DeprecationWarning,
        stacklevel=2,
    )
    return run_managed_readonly_git_command(
        project_root,
        packet,
        arguments,
        stage=stage,
        run_id=run_id,
        timeout=timeout,
        max_output_bytes=max_output_bytes,
        source=source,
    )


@dataclass(frozen=True)
class _PacketExecutionAuthority:
    binding: WorkspaceBinding
    allowed_classes: tuple[ResourceClass, ...]
    exclusive_resources: tuple[str, ...]


def _current_packet_authority(
    project_root: Path, packet: CompiledPacket
) -> CompiledPacket:
    return _revalidate_current_packet_authority(project_root, packet)


def _packet_execution_authority(
    project_root: Path,
    packet: CompiledPacket,
    *,
    resource_class: ResourceClass,
    delegated_classes: Sequence[ResourceClass],
    source: Path | None,
    max_output_bytes: int,
    wait_timeout: float,
    max_owned_processes: int,
) -> _PacketExecutionAuthority:
    if not isinstance(packet, CompiledPacket):
        raise TypeError("managed execution requires a CompiledPacket")
    _validate_packet_for_write(packet)
    target = packet.payload.get("target")
    if not isinstance(target, dict):
        raise PacketError("packet target authority is invalid")
    canonical = _compile_packet(
        project_root,
        str(target.get("milestone_id") or ""),
        (str(target["phase_id"]) if target.get("phase_id") else None),
        source=_packet_revalidation_source(project_root, packet, source),
        compact=packet.mode == "compact",
    )
    if canonical.digest != packet.digest:
        raise ManagedExecutionError(
            "packet differs from current project-owned SPEC authority"
        )
    try:
        binding = WorkspaceBinding.from_dict(packet.payload.get("workspace_binding"))
    except ValueError as exc:
        raise PacketError(f"packet workspace binding is invalid: {exc}") from exc
    current = discover_workspace(project_root)
    verification = _verify_workspace(binding, current=current)
    if not verification.ok:
        raise ManagedExecutionError(
            "packet workspace authority differs: " + "; ".join(verification.errors)
        )
    resource = packet.payload.get("resolved_resource_policy")
    if not isinstance(resource, dict):
        raise PacketError("packet resource authority is invalid")
    raw_allowed = resource.get("allowed_resource_classes")
    if not isinstance(raw_allowed, list):
        raise PacketError("packet resource authority is invalid")
    try:
        allowed = tuple(ResourceClass(value) for value in raw_allowed)
    except (TypeError, ValueError) as exc:
        raise PacketError("packet resource authority contains an unknown class") from exc
    requested = (resource_class, *delegated_classes)
    if any(item not in allowed for item in requested):
        raise ManagedExecutionError(
            "requested or delegated resource class exceeds packet authority"
        )
    process = resource.get("process_policy")
    wait = resource.get("wait_policy")
    containment = resource.get("containment_policy")
    exclusive = resource.get("exclusive_resources")
    if (
        not isinstance(process, dict)
        or not isinstance(wait, dict)
        or not isinstance(containment, dict)
        or not isinstance(exclusive, list)
        or not all(isinstance(item, str) and item for item in exclusive)
    ):
        raise PacketError("packet resource policy is invalid")
    max_policy_output = process.get("max_output_bytes")
    max_policy_processes = process.get("max_owned_processes")
    max_policy_wait = wait.get("max_wait_seconds")
    if (
        type(max_policy_output) is not int
        or type(max_policy_processes) is not int
        or type(max_policy_wait) not in {int, float}
        or containment.get("minimum_level") != "MANAGED"
        or containment.get("soft_bypass_disclosed") is not True
    ):
        raise PacketError("packet resource policy is invalid")
    if max_output_bytes > max_policy_output:
        raise ManagedExecutionError("requested output limit exceeds packet authority")
    if max_owned_processes > max_policy_processes:
        raise ManagedExecutionError("requested process limit exceeds packet authority")
    if wait_timeout < 0 or wait_timeout > float(max_policy_wait):
        raise ManagedExecutionError("requested wait limit exceeds packet authority")
    return _PacketExecutionAuthority(
        binding,
        allowed,
        tuple(sorted(set(exclusive))),
    )


@contextmanager
def _exclusive_packet_resources(
    project_root: Path,
    packet: CompiledPacket,
    authority: _PacketExecutionAuthority,
    *,
    wait_timeout: float,
):
    if not authority.exclusive_resources:
        with nullcontext(None) as refresh:
            yield refresh
        return
    identity = discover_workspace(project_root)
    digest = lambda value: hashlib.sha256(
        os.path.normcase(str(value)).encode("utf-8")
    ).hexdigest()
    manager = ResourceManager(
        host_runtime=host_runtime_path(),
        project_runtime=project_runtime_path(
            Path(identity.project_root),
            Path(identity.git_common_dir) if identity.git_common_dir else None,
        ),
    )
    request = ResourceRequest(
        resource_class=ResourceClass.REPO_READ,
        run_id=f"packet-exclusive-{packet.digest[:16]}",
        controller=authority.binding.controller,
        stage="packet-exclusive",
        authority_digest=packet.digest,
        host_identity=default_host_identity(),
        project_identity=digest(identity.git_common_dir or identity.repository_root),
        worktree_identity=digest(identity.worktree_root),
        permission_mode=authority.binding.permission_mode,
        exclusive_resources=authority.exclusive_resources,
        allowed_classes=(ResourceClass.REPO_READ,),
    )
    try:
        lease = manager.acquire(request, wait_timeout=wait_timeout)
    except ResourceBusy as exc:
        raise ManagedExecutionError(f"{exc.state}: {exc}") from exc
    try:
        lease_box = [lease]

        def refresh(event: object) -> None:
            lease_box[0] = manager.heartbeat(
                lease_box[0], stage=getattr(event, "stage", None)
            )

        yield refresh
    finally:
        manager.release(lease_box[0])


__all__ = [
    "TaskEvidenceValidationResult",
    "ProjectCheckResult",
    "CheckpointResult",
    "CandidateAssessment",
    "CandidateFingerprint",
    "CandidateFreezeResult",
    "ChangeClass",
    "CompiledPacket",
    "ContractSelection",
    "NormalizedSpec",
    "PacketConfigurationError",
    "PacketError",
    "SourceConfigurationError",
    "ValidationError",
    "ManagedExecutionError",
    "ExecutionCounters",
    "ProcessResult",
    "PreauthorizedConvergenceAuthority",
    "ResourceClass",
    "SourceConfig",
    "WorkspaceBinding",
    "WorkspaceIdentity",
    "WorkspaceVerification",
    "build_project_workspace_binding",
    "assess_candidate",
    "check_project",
    "compile_ephemeral_packet",
    "clear_checkpoint",
    "create_checkpoint",
    "discover_project_workspace",
    "freeze_candidate",
    "load_project_normalized_spec",
    "load_project_source_config",
    "get_checkpoint_status",
    "run_managed_command",
    "run_managed_git_command",
    "run_managed_readonly_git_command",
    "resume_checkpoint",
    "validate_task_and_evidence_records",
    "verify_project_workspace",
    "write_ephemeral_packet",
]
