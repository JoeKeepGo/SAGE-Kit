from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Mapping

from .pathing import relative_repo_path, scope_contains


class ChangeClass(str, Enum):
    C0_RECORD_ONLY = "C0"
    C1_BOUNDED_CORRECTIVE = "C1"
    C2_CONTRACT_AFFECTING = "C2"
    C3_EXTERNAL_DESTRUCTIVE = "C3"


class RunState(str, Enum):
    CONTINUE = "CONTINUE"
    AUTO_CORRECT = "AUTO_CORRECT"
    HANDOFF_READY = "HANDOFF_READY"
    HUMAN_DECISION_REQUIRED = "HUMAN_DECISION_REQUIRED"
    BLOCKED = "BLOCKED"
    STOP = "STOP"


@dataclass(frozen=True)
class ChangeRequest:
    change_class: ChangeClass
    changed_paths: tuple[str, ...]
    purposes: Mapping[str, str] = field(default_factory=dict)
    authority_granted: bool = True
    immediate_destructive_risk: bool = False


@dataclass(frozen=True)
class CorrectiveEnvelope:
    acceptance_criterion: str
    acceptance_criterion_approved: bool
    adds_product_feature: bool
    changes_external_api: bool
    changes_security_policy: bool
    changes_deployment_target: bool
    allowed_paths: tuple[str, ...]
    reversible: bool
    focused_verification: tuple[str, ...]
    opens_closed_gate: bool


@dataclass(frozen=True)
class AuthorityDeltaItem:
    path: str
    purpose: str


@dataclass(frozen=True)
class ChangeDecision:
    state: RunState
    required_verification: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    authority_delta: tuple[AuthorityDeltaItem, ...] = ()
    recommended_scope: tuple[str, ...] = ()


def decide_change(
    repository_root: Path,
    request: ChangeRequest,
    envelope: CorrectiveEnvelope | None = None,
) -> ChangeDecision:
    if request.immediate_destructive_risk:
        return ChangeDecision(
            RunState.STOP,
            reasons=("immediate destructive risk",),
        )
    try:
        for value in request.changed_paths:
            relative_repo_path(repository_root, value)
    except ValueError as exc:
        return ChangeDecision(
            RunState.HUMAN_DECISION_REQUIRED,
            reasons=(f"changed path is outside repository authority: {exc}",),
        )
    if request.change_class == ChangeClass.C0_RECORD_ONLY:
        if not request.authority_granted:
            return ChangeDecision(
                RunState.HUMAN_DECISION_REQUIRED,
                ("record-consistency",),
                ("record owner write authority is missing",),
            )
        return ChangeDecision(RunState.AUTO_CORRECT, ("record-consistency",))
    if request.change_class == ChangeClass.C1_BOUNDED_CORRECTIVE:
        if not request.authority_granted:
            return ChangeDecision(
                RunState.HUMAN_DECISION_REQUIRED,
                ("focused",),
                ("bounded corrective authority is missing",),
            )
        return _decide_corrective(repository_root, request, envelope)
    if request.change_class == ChangeClass.C2_CONTRACT_AFFECTING:
        state = RunState.CONTINUE if request.authority_granted else RunState.HUMAN_DECISION_REQUIRED
        reasons = () if request.authority_granted else ("contract-affecting authority is missing",)
        return ChangeDecision(state, ("semantic-lane",), reasons)
    return ChangeDecision(
        RunState.HUMAN_DECISION_REQUIRED,
        reasons=("external or destructive work requires explicit human approval",),
    )


def _decide_corrective(
    repository_root: Path,
    request: ChangeRequest,
    envelope: CorrectiveEnvelope | None,
) -> ChangeDecision:
    if envelope is None:
        return ChangeDecision(
            RunState.HUMAN_DECISION_REQUIRED,
            ("focused",),
            ("bounded corrective envelope is missing",),
        )
    predicate_failures: list[str] = []
    if not envelope.acceptance_criterion.strip() or not envelope.acceptance_criterion_approved:
        predicate_failures.append("acceptance criterion is not approved")
    if envelope.adds_product_feature:
        predicate_failures.append("change adds product functionality")
    if envelope.changes_external_api:
        predicate_failures.append("change affects an external API")
    if envelope.changes_security_policy:
        predicate_failures.append("change affects security policy")
    if envelope.changes_deployment_target:
        predicate_failures.append("change affects deployment target")
    if not envelope.reversible:
        predicate_failures.append("change is not reversible")
    if not envelope.focused_verification:
        predicate_failures.append("focused verification is missing")
    if envelope.opens_closed_gate:
        predicate_failures.append("change would open a closed approval gate")
    if predicate_failures:
        return ChangeDecision(
            RunState.HUMAN_DECISION_REQUIRED,
            ("focused",),
            tuple(predicate_failures),
        )

    uncovered: list[AuthorityDeltaItem] = []
    for value in request.changed_paths:
        normalized = relative_repo_path(repository_root, value)
        if any(scope_contains(repository_root, scope, value) for scope in envelope.allowed_paths):
            continue
        uncovered.append(
            AuthorityDeltaItem(
                normalized,
                request.purposes.get(value, "required bounded corrective change"),
            )
        )
    if uncovered:
        top_level = sorted(
            {
                PurePosixPath(item.path).parts[0] + "/"
                if len(PurePosixPath(item.path).parts) > 1
                else item.path
                for item in uncovered
            }
        )
        return ChangeDecision(
            RunState.HUMAN_DECISION_REQUIRED,
            ("focused",),
            ("corrective file scope does not cover all required paths",),
            tuple(uncovered),
            tuple(top_level),
        )
    return ChangeDecision(RunState.AUTO_CORRECT, ("focused",))
