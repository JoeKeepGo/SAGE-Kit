from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


LOCAL_SCOPE_MANIFEST = "docs/SAGE_VALIDATION_SCOPE.json"
SUPPORTED_SCHEMA_VERSION = 1
SUPPORTED_LEGACY_CONTRACT_VERSION = 1

_MILESTONE_ID_RE = re.compile(r"M[0-9]+(?:[._-][A-Za-z0-9]+)*")
_MILESTONE_RANGE_RE = re.compile(r"M[0-9]+-M[0-9]+", re.IGNORECASE)
_BASELINE_HEAD_RE = re.compile(r"[0-9a-f]{40}")
_UTC_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "legacy_contract_version",
    "active_milestones",
    "accepted_legacy_milestones",
    "authority",
    "supersedes",
}
_AUTHORITY_FIELDS = {
    "source",
    "approved_by",
    "approved_at",
    "baseline_head",
}


class ScopeManifestError(ValueError):
    pass


class _DuplicateJsonKey(ValueError):
    pass


@dataclass(frozen=True)
class ScopeManifestAuthority:
    source: str
    approved_by: str
    approved_at: str
    baseline_head: str


@dataclass(frozen=True)
class ValidationScopeManifest:
    path: Path
    schema_version: int
    legacy_contract_version: int
    active_milestones: tuple[str, ...]
    accepted_legacy_milestones: tuple[str, ...]
    authority: ScopeManifestAuthority
    supersedes: tuple[tuple[str, tuple[str, ...]], ...]
    digest: str

    def superseded_paths(self, milestone_id: str) -> tuple[str, ...]:
        normalized = milestone_id.casefold()
        for declared_id, paths in self.supersedes:
            if declared_id.casefold() == normalized:
                return paths
        return ()

    def authority_details(self, source_kind: str) -> tuple[str, ...]:
        return (
            f"validation scope manifest ({source_kind}): {self.path}",
            f"manifest digest sha256:{self.digest}",
            f"manifest authority source: {self.authority.source}",
            f"manifest approved_by: {self.authority.approved_by}",
            f"manifest approved_at: {self.authority.approved_at}",
            f"manifest baseline_head: {self.authority.baseline_head}",
        )


def load_validation_scope_manifest(path: Path) -> ValidationScopeManifest:
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.exists():
        raise ScopeManifestError(f"scope manifest does not exist: {resolved}")
    if not resolved.is_file():
        raise ScopeManifestError(f"scope manifest must be a file: {resolved}")
    try:
        payload = json.loads(
            resolved.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_unique_object,
        )
    except _DuplicateJsonKey as exc:
        raise ScopeManifestError(str(exc)) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ScopeManifestError(f"scope manifest JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ScopeManifestError("scope manifest JSON must contain one object")

    unknown = sorted(set(payload) - _TOP_LEVEL_FIELDS)
    if unknown:
        raise ScopeManifestError(
            "scope manifest has unknown field(s): " + ", ".join(unknown)
        )
    missing = sorted((_TOP_LEVEL_FIELDS - {"supersedes"}) - set(payload))
    if missing:
        raise ScopeManifestError(
            "scope manifest is missing field(s): " + ", ".join(missing)
        )

    schema_version = payload.get("schema_version")
    if (
        type(schema_version) is not int
        or schema_version != SUPPORTED_SCHEMA_VERSION
    ):
        raise ScopeManifestError(
            f"unsupported scope manifest schema_version: {schema_version}"
        )
    legacy_contract_version = payload.get("legacy_contract_version")
    if (
        type(legacy_contract_version) is not int
        or legacy_contract_version != SUPPORTED_LEGACY_CONTRACT_VERSION
    ):
        raise ScopeManifestError(
            "unsupported scope manifest legacy_contract_version: "
            f"{legacy_contract_version}"
        )

    active = _milestone_list(payload.get("active_milestones"), "active_milestones")
    accepted = _milestone_list(
        payload.get("accepted_legacy_milestones"),
        "accepted_legacy_milestones",
    )
    _validate_milestone_relationships(active, accepted)
    authority = _authority(payload.get("authority"))
    supersedes = _supersedes(payload.get("supersedes", {}), accepted)

    canonical_payload = {
        "schema_version": schema_version,
        "legacy_contract_version": legacy_contract_version,
        "active_milestones": list(active),
        "accepted_legacy_milestones": list(accepted),
        "authority": {
            "source": authority.source,
            "approved_by": authority.approved_by,
            "approved_at": authority.approved_at,
            "baseline_head": authority.baseline_head,
        },
    }
    if supersedes:
        canonical_payload["supersedes"] = {
            milestone_id: list(paths) for milestone_id, paths in supersedes
        }
    canonical = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return ValidationScopeManifest(
        path=resolved,
        schema_version=schema_version,
        legacy_contract_version=legacy_contract_version,
        active_milestones=active,
        accepted_legacy_milestones=accepted,
        authority=authority,
        supersedes=supersedes,
        digest=hashlib.sha256(canonical).hexdigest(),
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(f"scope manifest has duplicate JSON key: {key}")
        result[key] = value
    return result


def _milestone_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ScopeManifestError(f"{field} must be an array of explicit milestone IDs")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if (
            not isinstance(item, str)
            or _MILESTONE_ID_RE.fullmatch(item) is None
            or _MILESTONE_RANGE_RE.fullmatch(item) is not None
        ):
            raise ScopeManifestError(
                f"{field} contains invalid milestone ID: {item!r}"
            )
        normalized = item.casefold()
        if normalized in seen:
            raise ScopeManifestError(f"{field} contains duplicate milestone ID: {item}")
        seen.add(normalized)
        result.append(item)
    return tuple(result)


def _validate_milestone_relationships(
    active: tuple[str, ...],
    accepted: tuple[str, ...],
) -> None:
    active_ids = {item.casefold(): item for item in active}
    accepted_ids = {item.casefold(): item for item in accepted}
    overlap = sorted(set(active_ids) & set(accepted_ids))
    if overlap:
        rendered = ", ".join(active_ids[item] for item in overlap)
        raise ScopeManifestError(
            "milestone cannot be both active and accepted legacy: " + rendered
        )

    aliases: dict[str, str] = {}
    for item in (*active, *accepted):
        canonical = _canonical_milestone_id(item)
        previous = aliases.get(canonical)
        if previous is not None and previous.casefold() != item.casefold():
            raise ScopeManifestError(
                f"milestone separator alias collision: {previous} and {item}"
            )
        aliases[canonical] = item


def _authority(value: Any) -> ScopeManifestAuthority:
    if not isinstance(value, dict):
        raise ScopeManifestError("scope manifest authority must be an object")
    unknown = sorted(set(value) - _AUTHORITY_FIELDS)
    missing = sorted(_AUTHORITY_FIELDS - set(value))
    if unknown:
        raise ScopeManifestError(
            "scope manifest authority has unknown field(s): " + ", ".join(unknown)
        )
    if missing:
        raise ScopeManifestError(
            "scope manifest authority is missing field(s): " + ", ".join(missing)
        )
    strings: dict[str, str] = {}
    for field in ("source", "approved_by", "approved_at", "baseline_head"):
        item = value.get(field)
        if not isinstance(item, str) or not item.strip():
            raise ScopeManifestError(
                f"scope manifest authority.{field} must be a non-empty string"
            )
        strings[field] = item.strip()
    if _UTC_TIMESTAMP_RE.fullmatch(strings["approved_at"]) is None:
        raise ScopeManifestError(
            "scope manifest authority.approved_at must be an RFC 3339 UTC timestamp"
        )
    try:
        datetime.strptime(strings["approved_at"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ScopeManifestError(
            "scope manifest authority.approved_at is not a valid UTC timestamp"
        ) from exc
    if _BASELINE_HEAD_RE.fullmatch(strings["baseline_head"]) is None:
        raise ScopeManifestError(
            "scope manifest authority.baseline_head must be a full 40-character "
            "lowercase hexadecimal Git SHA"
        )
    return ScopeManifestAuthority(**strings)


def _supersedes(
    value: Any,
    accepted: tuple[str, ...],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if not isinstance(value, dict):
        raise ScopeManifestError("scope manifest supersedes must be an object")
    accepted_ids = {item.casefold(): item for item in accepted}
    result: list[tuple[str, tuple[str, ...]]] = []
    seen_milestones: set[str] = set()
    for milestone_id, raw_paths in value.items():
        if (
            not isinstance(milestone_id, str)
            or milestone_id.casefold() not in accepted_ids
        ):
            raise ScopeManifestError(
                "supersedes milestone must appear in accepted_legacy_milestones: "
                f"{milestone_id}"
            )
        declared_id = accepted_ids[milestone_id.casefold()]
        if milestone_id != declared_id:
            raise ScopeManifestError(
                "supersedes milestone key must exactly match its "
                f"accepted_legacy_milestones ID: {milestone_id}"
            )
        if milestone_id.casefold() in seen_milestones:
            raise ScopeManifestError(
                f"supersedes contains duplicate milestone key: {milestone_id}"
            )
        seen_milestones.add(milestone_id.casefold())
        if not isinstance(raw_paths, list) or not raw_paths:
            raise ScopeManifestError(
                f"supersedes.{milestone_id} must be a non-empty array of exact paths"
            )
        paths: list[str] = []
        seen: set[str] = set()
        for raw_path in raw_paths:
            if not isinstance(raw_path, str):
                raise ScopeManifestError(
                    f"supersedes.{milestone_id} contains a non-string path"
                )
            path = PurePosixPath(raw_path)
            if (
                "\\" in raw_path
                or path.is_absolute()
                or ".." in path.parts
                or "*" in raw_path
                or "?" in raw_path
                or len(path.parts) < 3
                or path.parts[0] != "docs"
                or path.name.casefold()
                not in {"milestone_closeout.md", "closeout.md"}
            ):
                raise ScopeManifestError(
                    f"supersedes.{milestone_id} contains invalid exact closeout path: "
                    f"{raw_path}"
                )
            normalized = path.as_posix().casefold()
            if normalized in seen:
                raise ScopeManifestError(
                    f"supersedes.{milestone_id} contains duplicate path: {raw_path}"
                )
            seen.add(normalized)
            paths.append(path.as_posix())
        result.append((declared_id, tuple(paths)))
    return tuple(result)


def _canonical_milestone_id(value: str) -> str:
    return re.sub(r"[._-]+", ".", value.casefold())
