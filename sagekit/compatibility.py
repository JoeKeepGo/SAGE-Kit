from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .validation_contracts import v1, v2


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
) -> ContractSelection:
    task_metadata = task.get("validation_contract")
    evidence_metadata = evidence.get("validation_contract")
    if task_metadata is None and evidence_metadata is None:
        if _is_closed_legacy_pair(task, evidence):
            metadata = v1.contract_metadata()
            return ContractSelection(
                version=1,
                policy_id=metadata["policy_id"],
                policy_sha256=metadata["policy_sha256"],
                scope=ContractScope.CLOSED_LEGACY,
                implicit_legacy=True,
            )
        raise ContractSelectionError(
            "unversioned active or non-terminal records are ambiguous and fail closed"
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
    if task_version == 1:
        if (
            task_metadata.get("scope") == ContractScope.ACTIVE.value
            or evidence_metadata.get("scope") == ContractScope.ACTIVE.value
        ):
            raise ContractSelectionError("frozen v1 must not be used for active work")
        if not _is_closed_legacy_pair(task, evidence):
            raise ContractSelectionError(
                "frozen v1 requires a closed/verified terminal record pair"
            )
        expected = v1.contract_metadata()
        return ContractSelection(
            1,
            str(task_metadata.get("policy_id") or expected["policy_id"]),
            str(task_metadata.get("policy_sha256") or expected["policy_sha256"]),
            ContractScope.CLOSED_LEGACY,
            False,
        )
    if task_version == 2:
        return ContractSelection(
            2,
            str(task_metadata.get("policy_id") or ""),
            str(task_metadata.get("policy_sha256") or ""),
            ContractScope.ACTIVE,
            False,
        )
    raise ContractSelectionError(f"unsupported validation contract version: {task_version}")


def validate_compatible_records(
    task: dict[str, Any],
    evidence: dict[str, Any],
    *,
    gate_ready: bool = False,
) -> CompatibilityResult:
    active = not _is_terminal_pair(task, evidence)
    try:
        selection = select_validation_contract(task, evidence)
    except ContractSelectionError as exc:
        return CompatibilityResult(None, (str(exc),), active)
    if selection.version == 1:
        errors = v1.validate_records(task, evidence, gate_ready=gate_ready)
    else:
        errors = v2.validate_records(task, evidence, gate_ready=gate_ready)
    return CompatibilityResult(selection, tuple(errors), active)


def _is_closed_legacy_pair(task: dict[str, Any], evidence: dict[str, Any]) -> bool:
    return (
        str(task.get("status") or "").upper() == "CLOSED"
        and _evidence_status(evidence) == "VERIFIED"
    )


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
