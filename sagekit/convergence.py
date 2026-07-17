from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable

from .change_control import RunState
from .pathing import scope_contains


AUTHORITY_FIELDS = frozenset(
    {
        "authority_id",
        "mode",
        "execution_scope",
        "root_cause_family",
        "allowed_paths",
        "invariant",
        "semantic_change_policy",
        "targeted_review_required",
        "stop_conditions",
        "approved_by",
        "authority_ref",
    }
)
SEMANTIC_CHANGE_POLICIES = frozenset({"implementation-preserving-only"})
SEMANTIC_CHANGES = frozenset({"implementation-preserving", "policy-changing"})


def _required_text(value: object, field: str, maximum: int = 2_000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"convergence authority {field} must not be empty")
    text = value.strip()
    if len(text) > maximum:
        raise ValueError(f"convergence authority {field} exceeds {maximum} characters")
    return text


def _normalize_allowed_path(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("convergence authority allowed path must not be empty")
    text = value.strip().replace("\\", "/")
    if any(character in text for character in "*?[]{}"):
        raise ValueError(f"convergence authority allowed path must not contain glob syntax: {value}")
    posix = PurePosixPath(text)
    windows = PureWindowsPath(text)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or windows.root:
        raise ValueError(f"convergence authority allowed path must be relative: {value}")
    if any(part in {"..", ""} for part in posix.parts) or not posix.parts:
        raise ValueError(f"convergence authority allowed path escapes its target: {value}")
    if any(part == "." for part in posix.parts):
        raise ValueError(f"convergence authority allowed path is not canonical: {value}")
    normalized = posix.as_posix()
    if text.endswith("/"):
        normalized += "/"
    return normalized


def _required_text_tuple(values: object, field: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError(f"convergence authority {field} must not be empty")
    if len(values) > 100:
        raise ValueError(f"convergence authority {field} exceeds 100 items")
    return tuple(_required_text(value, field) for value in values)


@dataclass(frozen=True)
class PreauthorizedConvergenceAuthority:
    authority_id: str
    mode: str
    execution_scope: str
    root_cause_family: str
    allowed_paths: tuple[str, ...]
    invariant: str
    semantic_change_policy: str
    targeted_review_required: bool
    stop_conditions: tuple[str, ...]
    approved_by: str
    authority_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "authority_id", _required_text(self.authority_id, "id"))
        object.__setattr__(
            self,
            "execution_scope",
            _required_text(self.execution_scope, "execution scope"),
        )
        object.__setattr__(
            self,
            "root_cause_family",
            _required_text(self.root_cause_family, "root-cause family"),
        )
        object.__setattr__(self, "invariant", _required_text(self.invariant, "invariant"))
        object.__setattr__(self, "approved_by", _required_text(self.approved_by, "approved by"))
        object.__setattr__(
            self,
            "authority_ref",
            _required_text(self.authority_ref, "authority reference"),
        )
        if not isinstance(self.mode, str) or self.mode != "preauthorized":
            raise ValueError("convergence authority mode must be preauthorized")
        if (
            not isinstance(self.semantic_change_policy, str)
            or self.semantic_change_policy not in SEMANTIC_CHANGE_POLICIES
        ):
            raise ValueError("convergence authority semantic change policy is invalid")
        if not isinstance(self.targeted_review_required, bool):
            raise ValueError("convergence authority targeted review requirement must be boolean")
        if not isinstance(self.allowed_paths, (list, tuple)) or not self.allowed_paths:
            raise ValueError("convergence authority allowed paths must not be empty")
        normalized_paths = tuple(_normalize_allowed_path(path) for path in self.allowed_paths)
        if len(normalized_paths) != len(set(normalized_paths)):
            raise ValueError("convergence authority allowed paths must be unique")
        object.__setattr__(self, "allowed_paths", normalized_paths)
        object.__setattr__(
            self,
            "stop_conditions",
            _required_text_tuple(self.stop_conditions, "stop conditions"),
        )

    def _payload(self) -> dict[str, object]:
        return {
            "authority_id": self.authority_id,
            "mode": self.mode,
            "execution_scope": self.execution_scope,
            "root_cause_family": self.root_cause_family,
            "allowed_paths": list(self.allowed_paths),
            "invariant": self.invariant,
            "semantic_change_policy": self.semantic_change_policy,
            "targeted_review_required": self.targeted_review_required,
            "stop_conditions": list(self.stop_conditions),
            "approved_by": self.approved_by,
            "authority_ref": self.authority_ref,
        }

    @property
    def canonical_json(self) -> str:
        return json.dumps(self._payload(), sort_keys=True, separators=(",", ":"))

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return self._payload()

    @classmethod
    def from_dict(cls, value: object) -> "PreauthorizedConvergenceAuthority":
        if not isinstance(value, dict) or set(value) != AUTHORITY_FIELDS:
            raise ValueError("convergence authority fields are invalid")
        return cls(
            authority_id=value["authority_id"],
            mode=value["mode"],
            execution_scope=value["execution_scope"],
            root_cause_family=value["root_cause_family"],
            allowed_paths=value["allowed_paths"],
            invariant=value["invariant"],
            semantic_change_policy=value["semantic_change_policy"],
            targeted_review_required=value["targeted_review_required"],
            stop_conditions=value["stop_conditions"],
            approved_by=value["approved_by"],
            authority_ref=value["authority_ref"],
        )


def load_convergence_authority(path: Path) -> PreauthorizedConvergenceAuthority:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load convergence authority: {exc}") from exc
    if isinstance(payload, dict) and set(payload) == {"convergence_authority"}:
        payload = payload["convergence_authority"]
    return PreauthorizedConvergenceAuthority.from_dict(payload)


@dataclass(frozen=True)
class ConvergenceEvidence:
    execution_scope: str
    root_cause_family: str
    root_cause_id: str
    finding_count: int
    finding_severity: int | None
    semantic_change: str
    targeted_review_closed: bool
    next_layer_exposed: bool = False
    product_scope_expanded: bool = False
    approval_gate_opened: bool = False
    permissions_increased: bool = False
    test_or_gate_weakened: bool = False
    security_or_evidence_weakened: bool = False
    contract_or_public_behavior_changed: bool = False
    consumer_mutation: bool = False
    authority_precedence_changed: bool = False
    required_evidence_unavailable: bool = False

    def __post_init__(self) -> None:
        for field in ("execution_scope", "root_cause_family", "root_cause_id"):
            object.__setattr__(self, field, _required_text(getattr(self, field), field))
        if (
            not isinstance(self.finding_count, int)
            or isinstance(self.finding_count, bool)
            or self.finding_count < 0
        ):
            raise ValueError("convergence finding count must be a non-negative integer")
        if self.finding_severity is not None and (
            not isinstance(self.finding_severity, int)
            or isinstance(self.finding_severity, bool)
            or self.finding_severity < 0
        ):
            raise ValueError("convergence finding severity must be a non-negative integer")
        if (
            not isinstance(self.semantic_change, str)
            or self.semantic_change not in SEMANTIC_CHANGES
        ):
            raise ValueError("convergence semantic change classification is invalid")
        for field in (
            "targeted_review_closed",
            "next_layer_exposed",
            "product_scope_expanded",
            "approval_gate_opened",
            "permissions_increased",
            "test_or_gate_weakened",
            "security_or_evidence_weakened",
            "contract_or_public_behavior_changed",
            "consumer_mutation",
            "authority_precedence_changed",
            "required_evidence_unavailable",
        ):
            if not isinstance(getattr(self, field), bool):
                raise ValueError(f"convergence evidence {field} must be boolean")


@dataclass(frozen=True)
class ConvergenceDecision:
    state: RunState
    trend: str
    no_progress_rounds: int
    reason: str


def paths_outside_authority(
    repository_root: Path,
    authority: PreauthorizedConvergenceAuthority,
    changed_paths: Iterable[str],
) -> tuple[str, ...]:
    root = repository_root.resolve(strict=False)
    outside: list[str] = []
    for raw in changed_paths:
        try:
            normalized = _normalize_allowed_path(str(raw))
        except ValueError:
            outside.append(str(raw))
            continue
        candidate = normalized.rstrip("/")
        if not any(
            scope_contains(root, allowed, candidate)
            for allowed in authority.allowed_paths
        ):
            outside.append(candidate)
    return tuple(outside)


def evaluate_convergence(
    authority: PreauthorizedConvergenceAuthority,
    evidence: ConvergenceEvidence,
    *,
    previous_root_cause_id: str | None,
    previous_finding_count: int | None,
    previous_finding_severity: int | None,
    previous_no_progress_rounds: int,
) -> ConvergenceDecision:
    stopped = evaluate_convergence_stops(
        authority,
        evidence,
        previous_no_progress_rounds=previous_no_progress_rounds,
    )
    if stopped is not None:
        return stopped
    if previous_finding_count is None:
        return ConvergenceDecision(RunState.CONTINUE, "initial", 0, "window initialized")
    count_increased = evidence.finding_count > previous_finding_count
    severity_increased = (
        previous_finding_severity is not None
        and evidence.finding_severity is not None
        and evidence.finding_severity > previous_finding_severity
    )
    if count_increased or severity_increased:
        if evidence.next_layer_exposed:
            if not evidence.targeted_review_closed:
                return ConvergenceDecision(
                    RunState.HANDOFF_READY,
                    "stopped",
                    previous_no_progress_rounds,
                    "next-layer evidence requires targeted review",
                )
            return ConvergenceDecision(
                RunState.CONTINUE,
                "next-layer-exposed",
                0,
                "previous corrective exposed the next deterministic layer",
            )
        dimensions = []
        if count_increased:
            dimensions.append("finding count")
        if severity_increased:
            dimensions.append("finding severity")
        return ConvergenceDecision(
            RunState.HANDOFF_READY,
            "findings-increased",
            previous_no_progress_rounds,
            " and ".join(dimensions) + " increased without next-layer evidence",
        )
    if evidence.finding_count < previous_finding_count:
        return ConvergenceDecision(
            RunState.CONTINUE,
            "finding-count-decreased",
            0,
            "finding count decreased",
        )
    if (
        previous_finding_severity is not None
        and evidence.finding_severity is not None
        and evidence.finding_severity < previous_finding_severity
    ):
        return ConvergenceDecision(
            RunState.CONTINUE,
            "severity-decreased",
            0,
            "finding severity decreased",
        )
    if evidence.next_layer_exposed:
        if not evidence.targeted_review_closed:
            return ConvergenceDecision(
                RunState.HANDOFF_READY,
                "stopped",
                previous_no_progress_rounds,
                "next-layer evidence requires targeted review",
            )
        return ConvergenceDecision(
            RunState.CONTINUE,
            "next-layer-exposed",
            0,
            "previous corrective exposed the next deterministic layer",
        )
    if evidence.root_cause_id != previous_root_cause_id:
        return ConvergenceDecision(
            RunState.HANDOFF_READY,
            "stopped",
            previous_no_progress_rounds,
            "root-cause id changed without convergence or next-layer evidence",
        )
    rounds = previous_no_progress_rounds + 1
    if rounds >= 2:
        return ConvergenceDecision(
            RunState.BLOCKED,
            "no-progress",
            rounds,
            "same root cause made no progress for two consecutive rounds",
        )
    return ConvergenceDecision(
        RunState.CONTINUE,
        "no-progress",
        rounds,
        "first no-progress round recorded",
    )


def evaluate_convergence_stops(
    authority: PreauthorizedConvergenceAuthority,
    evidence: ConvergenceEvidence,
    *,
    previous_no_progress_rounds: int,
) -> ConvergenceDecision | None:
    if evidence.required_evidence_unavailable:
        return ConvergenceDecision(
            RunState.BLOCKED,
            "evidence-unavailable",
            previous_no_progress_rounds,
            "required convergence evidence cannot be produced",
        )
    handoff_reasons: list[str] = []
    if evidence.execution_scope != authority.execution_scope:
        handoff_reasons.append("execution scope changed")
    if evidence.root_cause_family != authority.root_cause_family:
        handoff_reasons.append("root-cause family changed")
    if evidence.semantic_change != "implementation-preserving":
        handoff_reasons.append("policy-changing semantic change")
    stop_flags = {
        "product scope expanded": evidence.product_scope_expanded,
        "approval gate opened": evidence.approval_gate_opened,
        "permissions increased": evidence.permissions_increased,
        "test or gate weakening": evidence.test_or_gate_weakened,
        "security or evidence weakening": evidence.security_or_evidence_weakened,
        "contract or public behavior changed": evidence.contract_or_public_behavior_changed,
        "consumer mutation": evidence.consumer_mutation,
        "authority precedence changed": evidence.authority_precedence_changed,
    }
    handoff_reasons.extend(reason for reason, active in stop_flags.items() if active)
    if authority.targeted_review_required and not evidence.targeted_review_closed:
        handoff_reasons.append("targeted review is not closed")
    if handoff_reasons:
        return ConvergenceDecision(
            RunState.HANDOFF_READY,
            "stopped",
            previous_no_progress_rounds,
            "; ".join(handoff_reasons),
        )
    return None
