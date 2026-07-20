"""Internal managed execution boundaries used by SAGE-Kit product code."""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .process_supervisor import ProcessResult, run_process
from .resource_governor import (
    DEFAULT_LEASE_TTL,
    ResourceClass,
    ResourceLease,
    ResourceManager,
    ResourceRequest,
    default_host_identity,
    host_runtime_path,
    project_runtime_path,
)
from .workspace_binding import (
    authorize_command,
    build_workspace_binding,
    discover_workspace,
    verify_workspace,
)


class ManagedExecutionError(RuntimeError):
    pass


_DELEGATION_ENVIRONMENT_KEYS = (
    "SAGEKIT_LEASE_ID",
    "SAGEKIT_DELEGATION_SECRET",
    "SAGEKIT_AUTHORITY_DIGEST",
    "SAGEKIT_PERMISSION_MODE",
    "SAGEKIT_CONTROLLER",
)


def run_managed_git(
    root: Path,
    arguments: Sequence[str],
    *,
    stage: str,
    run_id: str | None = None,
    timeout: float = 30.0,
    max_output_bytes: int = 16 * 1024 * 1024,
) -> ProcessResult:
    if not arguments:
        raise ValueError("managed Git arguments are required")
    selected_run = run_id or f"git-{os.getpid()}-{uuid.uuid4().hex[:12]}"
    return run_managed_command(
        root,
        ("git", *arguments),
        resource_class=ResourceClass.REPO_READ,
        permission_mode="READ_ONLY_REVIEW",
        controller="sagekit-root-verification-controller",
        stage=stage,
        run_id=selected_run,
        timeout=timeout,
        max_output_bytes=max_output_bytes,
    )


def run_managed_command(
    root: Path,
    command: Sequence[str],
    *,
    resource_class: ResourceClass,
    permission_mode: str,
    controller: str,
    stage: str,
    run_id: str,
    timeout: float,
    max_output_bytes: int = 65_536,
    environment: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    temp_root: Path | None = None,
    wait_timeout: float = 30.0,
    check: bool = True,
    on_heartbeat: Callable[[object], None] | None = None,
    on_wait: Callable[[str], None] | None = None,
    delegated_classes: Sequence[ResourceClass] = (),
    isolated_test_harness: bool = False,
    max_owned_processes: int = 32,
) -> ProcessResult:
    delegated_classes = tuple(dict.fromkeys(delegated_classes))
    if any(
        not isinstance(item, ResourceClass)
        or item is ResourceClass.REASONING_ONLY
        for item in delegated_classes
    ):
        raise ValueError("delegated resource classes must be executable ResourceClass values")
    identity = discover_workspace(root)
    actual_cwd = _validated_cwd(
        root,
        root if cwd is None else cwd,
        temp_root=temp_root,
        resource_class=resource_class,
    )
    binding = build_workspace_binding(
        identity,
        base_head=identity.head,
        permission_mode=permission_mode,
        controller=controller,
        allowed_paths=(),
    )
    verification = verify_workspace(binding, current=discover_workspace(root))
    if not verification.ok:
        raise ManagedExecutionError(
            "workspace binding failed: " + "; ".join(verification.errors)
        )
    manager = ResourceManager(
        host_runtime=host_runtime_path(),
        project_runtime=project_runtime_path(
            Path(identity.project_root),
            Path(identity.git_common_dir) if identity.git_common_dir else None,
        ),
    )
    project_identity = _identity_digest(
        identity.git_common_dir or identity.repository_root
    )
    worktree_identity = _identity_digest(identity.worktree_root)
    inherited_context = _inherited_context(
        manager,
        resource_class=resource_class,
        authority_digest=os.environ.get("SAGEKIT_AUTHORITY_DIGEST"),
        project_identity=project_identity,
        worktree_identity=worktree_identity,
    )
    descendant = os.environ.get("SAGEKIT_DESCENDANT") == "1"
    if descendant and inherited_context is None:
        raise ManagedExecutionError(
            "descendant has no verified root delegation for local execution"
        )
    parent_lease = inherited_context[0] if inherited_context is not None else None
    inherited_allowed = (
        inherited_context[1]
        if inherited_context is not None
        else tuple(dict.fromkeys((resource_class, *delegated_classes)))
    )
    delegated = inherited_context is not None
    if isolated_test_harness and delegated:
        raise ManagedExecutionError(
            "only the Root controller may create an authority-isolated test harness"
        )
    decision = authorize_command(
        command,
        resource_class=resource_class,
        permission_mode=permission_mode,
        allowed_classes=inherited_allowed,
        descendant=descendant,
        delegated=delegated,
    )
    if not decision.ok:
        raise ManagedExecutionError(decision.reason)
    request = ResourceRequest(
        resource_class=resource_class,
        run_id=run_id,
        controller=(
            parent_lease.record.controller if parent_lease is not None else controller
        ),
        stage=stage,
        authority_digest=(
            parent_lease.record.authority_digest
            if parent_lease is not None
            else binding.digest
        ),
        host_identity=default_host_identity(),
        project_identity=project_identity,
        worktree_identity=worktree_identity,
        permission_mode=permission_mode,
        allowed_classes=(
            (resource_class,)
            if parent_lease is not None
            else inherited_allowed
        ),
        parent_lease_id=(parent_lease.lease_id if parent_lease is not None else None),
        descendant=parent_lease is not None,
        delegation_secret=(
            parent_lease.delegation_secret if parent_lease is not None else None
        ),
    )
    inherited = (
        parent_lease
        if parent_lease is not None and manager.lease_covers(parent_lease, request)
        else None
    )
    owned_lease: ResourceLease | None = None
    lease = inherited
    if lease is None:
        owned_lease = manager.acquire(
            request,
            wait_timeout=wait_timeout,
            on_wait=on_wait,
        )
        lease = owned_lease
    lease_box = [lease]
    child_environment: dict[str, str | None] = dict(environment or {})
    for key in _DELEGATION_ENVIRONMENT_KEYS:
        child_environment[key] = None
    child_environment["SAGEKIT_DESCENDANT"] = "1"
    child_environment["SAGEKIT_ALLOWED_CLASSES"] = ResourceClass.REASONING_ONLY.value
    if isolated_test_harness:
        child_environment["SAGEKIT_DESCENDANT"] = None
        child_environment["SAGEKIT_ALLOWED_CLASSES"] = None
    if parent_lease is None and delegated_classes and not isolated_test_harness:
        if not lease.delegation_secret:
            raise ManagedExecutionError("root-managed lease has no delegation capability")
        child_environment.update(
            {
                "SAGEKIT_LEASE_ID": lease.lease_id,
                "SAGEKIT_DELEGATION_SECRET": lease.delegation_secret,
                "SAGEKIT_AUTHORITY_DIGEST": lease.record.authority_digest,
                "SAGEKIT_PERMISSION_MODE": lease.record.permission_mode,
                "SAGEKIT_ALLOWED_CLASSES": ",".join(
                    item.value for item in delegated_classes
                ),
                "SAGEKIT_CONTROLLER": lease.record.controller,
            }
        )

    def heartbeat(event) -> None:
        if owned_lease is not None:
            lease_box[0] = manager.heartbeat(
                lease_box[0], stage=event.stage, lease_ttl=DEFAULT_LEASE_TTL
            )
        if on_heartbeat is not None:
            on_heartbeat(event)

    result: ProcessResult | None = None
    try:
        launch_verification = verify_workspace(
            binding, current=discover_workspace(root)
        )
        if not launch_verification.ok:
            raise ManagedExecutionError(
                "workspace binding changed before launch: "
                + "; ".join(launch_verification.errors)
            )
        if (
            parent_lease is not None
            and binding.digest != parent_lease.record.authority_digest
        ):
            raise ManagedExecutionError(
                "descendant workspace binding differs from delegated authority"
            )
        result = run_process(
            stage=stage,
            command=command,
            cwd=actual_cwd,
            environment=child_environment,
            timeout=timeout,
            run_id=run_id,
            lease_id=lease.lease_id,
            max_output_bytes=max_output_bytes,
            heartbeat_interval=10.0,
            temp_root=temp_root,
            on_heartbeat=heartbeat,
            max_owned_processes=max_owned_processes,
        )
    finally:
        if owned_lease is not None:
            manager.release(lease_box[0])
    if result is None:
        raise ManagedExecutionError("managed command did not produce a result")
    if result.stdout_dropped_bytes or result.stderr_dropped_bytes:
        raise ManagedExecutionError(
            f"managed command output exceeded {max_output_bytes} bytes"
        )
    if check and not result.ok:
        detail = result.stderr_tail.strip() or result.stdout_tail.strip()
        raise ManagedExecutionError(
            f"managed command failed ({result.classification.value}): "
            + (detail or result.termination_reason)
        )
    return result


def _validated_cwd(
    root: Path,
    cwd: Path,
    *,
    temp_root: Path | None,
    resource_class: ResourceClass,
) -> Path:
    raw = Path(os.path.abspath(cwd))
    actual = raw.resolve(strict=True)
    project = root.resolve(strict=True)
    if actual == project:
        return actual
    if resource_class in {
        ResourceClass.REPO_READ,
        ResourceClass.REPO_WRITE,
        ResourceClass.SUBMIT_EXCLUSIVE,
    }:
        raise ManagedExecutionError("repository command cwd differs from the bound project root")
    if temp_root is None:
        raise ManagedExecutionError("external command cwd requires a controlled temp root")
    raw_temp = Path(os.path.abspath(temp_root))
    controlled = raw_temp.resolve(strict=True)
    try:
        common = Path(os.path.commonpath((str(actual), str(controlled))))
    except ValueError as exc:
        raise ManagedExecutionError("command cwd and temp root are on different volumes") from exc
    if os.path.normcase(str(common)) != os.path.normcase(str(controlled)):
        raise ManagedExecutionError("command cwd is outside the controlled temp root")
    return actual


def _inherited_lease(
    manager: ResourceManager,
    *,
    resource_class: ResourceClass,
    authority_digest: str | None,
    project_identity: str,
    worktree_identity: str,
) -> ResourceLease | None:
    context = _inherited_context(
        manager,
        resource_class=resource_class,
        authority_digest=authority_digest,
        project_identity=project_identity,
        worktree_identity=worktree_identity,
    )
    if context is None:
        return None
    lease, _ = context
    request = ResourceRequest(
        resource_class=resource_class,
        run_id="inherited-coverage-check",
        controller=lease.record.controller,
        stage="inherited-coverage-check",
        authority_digest=lease.record.authority_digest,
        host_identity=lease.record.host_identity,
        project_identity=project_identity,
        worktree_identity=worktree_identity,
        permission_mode=lease.record.permission_mode,
        allowed_classes=(resource_class,),
        parent_lease_id=lease.lease_id,
        descendant=True,
        delegation_secret=lease.delegation_secret,
    )
    return lease if manager.lease_covers(lease, request) else None


def _inherited_context(
    manager: ResourceManager,
    *,
    resource_class: ResourceClass,
    authority_digest: str | None,
    project_identity: str,
    worktree_identity: str,
) -> tuple[ResourceLease, tuple[ResourceClass, ...]] | None:
    lease_id = os.environ.get("SAGEKIT_LEASE_ID")
    if lease_id is None:
        return None
    raw_allowed = os.environ.get("SAGEKIT_ALLOWED_CLASSES", "")
    delegation_secret = os.environ.get("SAGEKIT_DELEGATION_SECRET")
    if not delegation_secret:
        raise ManagedExecutionError("inherited lease is missing its delegation secret")
    try:
        allowed = tuple(
            sorted(
                {ResourceClass(value) for value in raw_allowed.split(",") if value},
                key=lambda item: item.value,
            )
        )
    except ValueError as exc:
        raise ManagedExecutionError("inherited resource classes are invalid") from exc
    if resource_class not in allowed:
        raise ManagedExecutionError(
            f"inherited lease does not allow {resource_class.value}"
        )
    if not authority_digest:
        raise ManagedExecutionError("inherited lease is missing authority digest")
    try:
        lease = manager.load_lease(
            lease_id, delegation_secret=delegation_secret
        )
    except (OSError, ValueError) as exc:
        raise ManagedExecutionError(f"inherited lease cannot be loaded: {exc}") from exc
    record = lease.record
    if (
        record.authority_digest != authority_digest
        or record.project_identity != project_identity
        or record.worktree_identity != worktree_identity
    ):
        raise ManagedExecutionError(
            "inherited lease authority or workspace identity differs"
        )
    if not set(item.value for item in allowed).issubset(record.allowed_classes):
        raise ManagedExecutionError("inherited resource classes exceed the lease record")
    return lease, allowed


def _identity_digest(value: str) -> str:
    return hashlib.sha256(os.path.normcase(value).encode("utf-8")).hexdigest()


__all__ = [
    "ManagedExecutionError",
    "run_managed_command",
    "run_managed_git",
]
