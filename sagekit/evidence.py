from __future__ import annotations

from dataclasses import dataclass

from .change_control import ChangeClass
from .pathing import paths_overlap


@dataclass(frozen=True)
class EvidenceFingerprint:
    evidence_id: str
    kind: str
    lane: str
    base_sha: str
    head_sha: str
    covered_paths: tuple[str, ...]
    covered_contracts: tuple[str, ...]
    command: str
    dependency_fingerprint: str
    toolchain_fingerprint: str
    platform: str
    authority_version: str
    result: str


@dataclass(frozen=True)
class ChangeEvent:
    change_class: ChangeClass
    changed_paths: tuple[str, ...] = ()
    changed_contracts: tuple[str, ...] = ()
    build_or_dependency_change: bool = False
    dependency_fingerprint: str | None = None
    toolchain_fingerprint: str | None = None
    platform: str | None = None
    authority_version: str | None = None


@dataclass(frozen=True)
class EvidenceAssessment:
    evidence_id: str
    reusable: bool
    reasons: tuple[str, ...]


def assess_evidence(
    fingerprint: EvidenceFingerprint,
    event: ChangeEvent,
) -> EvidenceAssessment:
    reasons: list[str] = []
    platform = "windows" if fingerprint.platform.lower().startswith("win") else "posix"
    path_changed = any(
        paths_overlap(covered, changed, platform)
        for covered in fingerprint.covered_paths
        for changed in event.changed_paths
    )

    if event.change_class == ChangeClass.C0_RECORD_ONLY:
        if fingerprint.kind == "record-consistency" and path_changed:
            reasons.append("covered record changed")
        return EvidenceAssessment(fingerprint.evidence_id, not reasons, tuple(reasons))

    if event.change_class == ChangeClass.C1_BOUNDED_CORRECTIVE and path_changed:
        if fingerprint.kind in {"focused", "affected-lane", "semantic", "integration"}:
            reasons.append("covered path changed")

    if event.change_class == ChangeClass.C2_CONTRACT_AFFECTING:
        if set(fingerprint.covered_contracts).intersection(event.changed_contracts):
            reasons.append("covered contract changed")
        if path_changed and fingerprint.kind in {"semantic", "affected-lane", "integration"}:
            reasons.append("covered semantic path changed")

    if event.build_or_dependency_change and fingerprint.kind in {
        "build",
        "platform",
        "package",
        "integration",
    }:
        reasons.append("build or dependency surface changed")
    if (
        event.dependency_fingerprint is not None
        and event.dependency_fingerprint != fingerprint.dependency_fingerprint
    ):
        reasons.append("dependency fingerprint changed")
    if (
        event.toolchain_fingerprint is not None
        and event.toolchain_fingerprint != fingerprint.toolchain_fingerprint
    ):
        reasons.append("toolchain fingerprint changed")
    if event.platform is not None and event.platform != fingerprint.platform:
        reasons.append("platform changed")
    if (
        event.authority_version is not None
        and event.authority_version != fingerprint.authority_version
        and fingerprint.kind in {"record-consistency", "semantic", "affected-lane", "integration"}
    ):
        reasons.append("authority version changed")

    return EvidenceAssessment(fingerprint.evidence_id, not reasons, tuple(dict.fromkeys(reasons)))
