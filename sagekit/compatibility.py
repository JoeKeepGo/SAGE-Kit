from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .milestone_scope import MilestoneScope, MilestoneScopeKind
from .validation_contracts import v0, v1, v2


class ContractScope(str, Enum):
    ACTIVE = "active"
    CLOSED_LEGACY = "closed-legacy"


@dataclass(frozen=True)
class ContractSelection:
    version: int
    policy_id: str
    policy_sha256: str
    scope: ContractScope
    implicit_legacy: bool
    authority_basis: tuple[str, ...]


@dataclass(frozen=True)
class CompatibilityResult:
    selection: ContractSelection | None
    errors: tuple[str, ...]
    active_reconciliation: bool


class ContractSelectionError(ValueError):
    pass


def select_validation_contract(
    task: dict[str, Any],
    evidence: dict[str, Any],
    *,
    container_scope: MilestoneScope | None = None,
) -> ContractSelection:
    task_metadata = task.get("validation_contract")
    evidence_metadata = evidence.get("validation_contract")
    if task_metadata is None and evidence_metadata is None:
        if (
            container_scope is not None
            and container_scope.kind == MilestoneScopeKind.AMBIGUOUS
        ):
            raise ContractSelectionError(container_scope.detail)
        if (
            _is_terminal_pair(task, evidence)
            and container_scope is not None
            and container_scope.kind
            == MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY
        ):
            version = (
                container_scope.contract_version
                if container_scope.contract_version is not None
                else 1
            )
            contract = {0: v0, 1: v1}.get(version)
            if contract is None:
                raise ContractSelectionError(
                    f"accepted legacy container selects unsupported frozen v{version}"
                )
            metadata = contract.contract_metadata()
            return ContractSelection(
                version=version,
                policy_id=metadata["policy_id"],
                policy_sha256=metadata["policy_sha256"],
                scope=ContractScope.CLOSED_LEGACY,
                implicit_legacy=True,
                authority_basis=(
                    container_scope.detail,
                    *container_scope.authorities,
                ),
            )
        if (
            container_scope is not None
            and container_scope.kind == MilestoneScopeKind.CURRENT
            and "explicit active milestone authority" in container_scope.detail
        ):
            raise ContractSelectionError(
                "unversioned terminal records in an active milestone fail closed; "
                "current v2 metadata is required"
            )
        raise ContractSelectionError(
            "unversioned records require terminal task/evidence and trusted accepted "
            "immutable milestone scope; inferred terminal state alone is insufficient"
        )
    if task_metadata is None or evidence_metadata is None:
        raise ContractSelectionError(
            "mixed validation contract records fail closed: both task and evidence must declare metadata"
        )
    if not isinstance(task_metadata, dict) or not isinstance(evidence_metadata, dict):
        raise ContractSelectionError("validation contract metadata must be a mapping")

    task_version = task_metadata.get("version")
    evidence_version = evidence_metadata.get("version")
    if task_version != evidence_version:
        raise ContractSelectionError(
            f"mixed validation contract versions fail closed: task={task_version}, evidence={evidence_version}"
        )
    if type(task_version) is not int or task_version not in {0, 1, 2}:
        raise ContractSelectionError(
            f"unsupported validation contract version: {task_version}"
        )
    if task_version == 2:
        return ContractSelection(
            2,
            str(task_metadata.get("policy_id") or ""),
            str(task_metadata.get("policy_sha256") or ""),
            ContractScope.ACTIVE,
            False,
            (
                "explicit matching validation_contract version 2 metadata",
                *(container_scope.authorities if container_scope is not None else ()),
            ),
        )
    if (
        container_scope is not None
        and container_scope.kind == MilestoneScopeKind.AMBIGUOUS
    ):
        raise ContractSelectionError(container_scope.detail)
    if task_version in {0, 1}:
        if (
            task_metadata.get("scope") == ContractScope.ACTIVE.value
            or evidence_metadata.get("scope") == ContractScope.ACTIVE.value
        ):
            raise ContractSelectionError(
                f"frozen v{task_version} must not be used for active work"
            )
        if (
            container_scope is None
            or container_scope.kind
            != MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY
        ):
            raise ContractSelectionError(
                f"frozen v{task_version} requires immutable accepted historical "
                "container scope"
            )
        if not _is_terminal_pair(task, evidence):
            raise ContractSelectionError(
                f"frozen v{task_version} requires a terminal task/evidence record pair"
            )
        contract = v0 if task_version == 0 else v1
        expected = contract.contract_metadata()
        return ContractSelection(
            task_version,
            str(task_metadata.get("policy_id") or expected["policy_id"]),
            str(task_metadata.get("policy_sha256") or expected["policy_sha256"]),
            ContractScope.CLOSED_LEGACY,
            False,
            (
                f"explicit matching validation_contract version {task_version} metadata",
                container_scope.detail,
                *container_scope.authorities,
            ),
        )
    raise ContractSelectionError(f"unsupported validation contract version: {task_version}")


def validate_compatible_records(
    task: dict[str, Any],
    evidence: dict[str, Any],
    *,
    gate_ready: bool = False,
    container_scope: MilestoneScope | None = None,
) -> CompatibilityResult:
    try:
        selection = select_validation_contract(
            task,
            evidence,
            container_scope=container_scope,
        )
    except ContractSelectionError as exc:
        return CompatibilityResult(None, (str(exc),), True)
    if selection.version == 0:
        errors = v0.validate_records(task, evidence, gate_ready=gate_ready)
    elif selection.version == 1:
        errors = v1.validate_records(task, evidence, gate_ready=gate_ready)
    else:
        errors = v2.validate_records(task, evidence, gate_ready=gate_ready)
    active_reconciliation = not (
        selection.version in {0, 1}
        and selection.scope == ContractScope.CLOSED_LEGACY
        and _is_terminal_pair(task, evidence)
    )
    return CompatibilityResult(selection, tuple(errors), active_reconciliation)


def _is_terminal_pair(task: dict[str, Any], evidence: dict[str, Any]) -> bool:
    return (
        str(task.get("status") or "").upper() in {"VERIFIED", "CLOSED"}
        and _evidence_status(evidence) == "VERIFIED"
    )


def _evidence_status(evidence: dict[str, Any]) -> str:
    conclusion = evidence.get("conclusion")
    if not isinstance(conclusion, dict):
        return ""
    return str(conclusion.get("status") or "").upper()
