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
SUPPORTED_LEGACY_CONTRACT_VERSIONS = {0, 1}

_CONTAINER_ID_RE = re.compile(r"[A-Z][A-Z0-9]*(?:[._-][A-Z0-9]+)*")
_RANGE_ID_RE = re.compile(r"[A-Z]+[0-9]+-[A-Z]+[0-9]+")
_BASELINE_HEAD_RE = re.compile(r"[0-9a-f]{40}")
_UTC_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "active_containers",
    "accepted_legacy_containers",
    "authority",
}
_AUTHORITY_FIELDS = {
    "source",
    "approved_by",
    "approved_at",
    "baseline_head",
}
_ACTIVE_FIELDS = {"id", "path"}
_LEGACY_FIELDS = {"id", "path", "contract_version", "supersedes"}
_LEGACY_REQUIRED_FIELDS = {"id", "path", "contract_version"}
_DISCOVERY_EXCLUDED_ROOTS = {"profiles", "templates"}


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
class ActiveContainer:
    id: str
    path: str


@dataclass(frozen=True)
class LegacyContainer:
    id: str
    path: str
    contract_version: int
    supersedes: tuple[str, ...]


@dataclass(frozen=True)
class ValidationScopeManifest:
    path: Path
    schema_version: int
    active_containers: tuple[ActiveContainer, ...]
    accepted_legacy_containers: tuple[LegacyContainer, ...]
    authority: ScopeManifestAuthority
    digest: str

    def active_for_path(self, container_path: str) -> ActiveContainer | None:
        normalized = container_path.casefold()
        return next(
            (
                container
                for container in self.active_containers
                if container.path.casefold() == normalized
            ),
            None,
        )

    def legacy_for_path(self, container_path: str) -> LegacyContainer | None:
        normalized = container_path.casefold()
        return next(
            (
                container
                for container in self.accepted_legacy_containers
                if container.path.casefold() == normalized
            ),
            None,
        )

    def containers_with_alias_id(self, container_id: str) -> tuple[str, ...]:
        normalized = container_id.casefold()
        canonical = _canonical_container_id(container_id)
        return tuple(
            container.id
            for container in (*self.active_containers, *self.accepted_legacy_containers)
            if container.id.casefold() != normalized
            and _canonical_container_id(container.id) == canonical
        )

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
    _exact_fields(payload, _TOP_LEVEL_FIELDS, "scope manifest")

    schema_version = payload.get("schema_version")
    if type(schema_version) is not int or schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ScopeManifestError(
            f"unsupported scope manifest schema_version: {schema_version}"
        )
    active = _active_containers(payload.get("active_containers"))
    legacy = _legacy_containers(payload.get("accepted_legacy_containers"))
    _validate_container_relationships(active, legacy)
    authority = _authority(payload.get("authority"))

    canonical_payload = {
        "schema_version": schema_version,
        "active_containers": [
            {"id": container.id, "path": container.path}
            for container in active
        ],
        "accepted_legacy_containers": [
            {
                "id": container.id,
                "path": container.path,
                "contract_version": container.contract_version,
                "supersedes": list(container.supersedes),
            }
            for container in legacy
        ],
        "authority": {
            "source": authority.source,
            "approved_by": authority.approved_by,
            "approved_at": authority.approved_at,
            "baseline_head": authority.baseline_head,
        },
    }
    canonical = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return ValidationScopeManifest(
        path=resolved,
        schema_version=schema_version,
        active_containers=active,
        accepted_legacy_containers=legacy,
        authority=authority,
        digest=hashlib.sha256(canonical).hexdigest(),
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(f"scope manifest has duplicate JSON key: {key}")
        result[key] = value
    return result


def _exact_fields(
    value: dict[str, Any],
    expected: set[str],
    label: str,
) -> None:
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown:
        raise ScopeManifestError(
            f"{label} has unknown field(s): " + ", ".join(unknown)
        )
    if missing:
        raise ScopeManifestError(
            f"{label} is missing field(s): " + ", ".join(missing)
        )


def _active_containers(value: Any) -> tuple[ActiveContainer, ...]:
    if not isinstance(value, list):
        raise ScopeManifestError("active_containers must be an array")
    result: list[ActiveContainer] = []
    for index, raw in enumerate(value):
        label = f"active_containers[{index}]"
        if not isinstance(raw, dict):
            raise ScopeManifestError(f"{label} must be an object")
        _exact_fields(raw, _ACTIVE_FIELDS, label)
        result.append(
            ActiveContainer(
                id=_container_id(raw.get("id"), f"{label}.id"),
                path=_container_path(raw.get("path"), f"{label}.path"),
            )
        )
    return tuple(result)


def _legacy_containers(value: Any) -> tuple[LegacyContainer, ...]:
    if not isinstance(value, list):
        raise ScopeManifestError("accepted_legacy_containers must be an array")
    result: list[LegacyContainer] = []
    for index, raw in enumerate(value):
        label = f"accepted_legacy_containers[{index}]"
        if not isinstance(raw, dict):
            raise ScopeManifestError(f"{label} must be an object")
        unknown = sorted(set(raw) - _LEGACY_FIELDS)
        missing = sorted(_LEGACY_REQUIRED_FIELDS - set(raw))
        if unknown:
            raise ScopeManifestError(
                f"{label} has unknown field(s): " + ", ".join(unknown)
            )
        if missing:
            raise ScopeManifestError(
                f"{label} is missing field(s): " + ", ".join(missing)
            )
        contract_version = raw.get("contract_version")
        if (
            type(contract_version) is not int
            or contract_version not in SUPPORTED_LEGACY_CONTRACT_VERSIONS
        ):
            raise ScopeManifestError(
                f"{label}.contract_version is unsupported: {contract_version}"
            )
        supersedes = _supersedes(raw.get("supersedes", []), label)
        result.append(
            LegacyContainer(
                id=_container_id(raw.get("id"), f"{label}.id"),
                path=_container_path(raw.get("path"), f"{label}.path"),
                contract_version=contract_version,
                supersedes=supersedes,
            )
        )
    return tuple(result)


def _container_id(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or _CONTAINER_ID_RE.fullmatch(value) is None
        or _RANGE_ID_RE.fullmatch(value) is not None
    ):
        raise ScopeManifestError(f"{label} contains invalid container ID: {value!r}")
    return value


def _container_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ScopeManifestError(f"{label} must be a non-empty relative path")
    path = PurePosixPath(value)
    if (
        "\\" in value
        or path.is_absolute()
        or value != path.as_posix()
        or ".." in path.parts
        or "." in path.parts
        or "*" in value
        or "?" in value
        or "[" in value
        or "]" in value
        or any(_RANGE_ID_RE.fullmatch(part.upper()) for part in path.parts)
        or len(path.parts) < 2
        or path.parts[0] != "docs"
        or path.parts[1].casefold() in _DISCOVERY_EXCLUDED_ROOTS
        or any(part.casefold() == "dispatch" for part in path.parts)
        or any("_template" in part.casefold() for part in path.parts)
    ):
        raise ScopeManifestError(
            f"{label} must be a normalized target-relative docs container path: {value}"
        )
    return path.as_posix()


def _supersedes(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ScopeManifestError(f"{label}.supersedes must be an array")
    result: list[str] = []
    seen: set[str] = set()
    for index, raw_path in enumerate(value):
        item_label = f"{label}.supersedes[{index}]"
        if not isinstance(raw_path, str) or not raw_path:
            raise ScopeManifestError(f"{item_label} must be a non-empty path")
        path = PurePosixPath(raw_path)
        if (
            "\\" in raw_path
            or path.is_absolute()
            or raw_path != path.as_posix()
            or ".." in path.parts
            or "." in path.parts
            or "*" in raw_path
            or "?" in raw_path
            or "[" in raw_path
            or "]" in raw_path
            or len(path.parts) < 2
            or path.parts[0] != "docs"
        ):
            raise ScopeManifestError(
                f"{item_label} must be a normalized target-relative docs path"
            )
        normalized = path.as_posix().casefold()
        if normalized in seen:
            raise ScopeManifestError(
                f"{label}.supersedes contains duplicate path: {raw_path}"
            )
        seen.add(normalized)
        result.append(path.as_posix())
    return tuple(result)


def _validate_container_relationships(
    active: tuple[ActiveContainer, ...],
    legacy: tuple[LegacyContainer, ...],
) -> None:
    ids: dict[str, tuple[str, str]] = {}
    paths: dict[str, tuple[str, str]] = {}
    aliases: dict[str, str] = {}
    for kind, containers in (("active", active), ("accepted legacy", legacy)):
        for container in containers:
            normalized_id = container.id.casefold()
            previous_id = ids.get(normalized_id)
            if previous_id is not None:
                raise ScopeManifestError(
                    f"duplicate or overlapping container ID {container.id}: "
                    f"{previous_id[0]} and {kind}"
                )
            ids[normalized_id] = (kind, container.id)
            canonical = _canonical_container_id(container.id)
            previous_alias = aliases.get(canonical)
            if (
                previous_alias is not None
                and previous_alias.casefold() != normalized_id
            ):
                raise ScopeManifestError(
                    f"container ID alias collision: {previous_alias} and {container.id}"
                )
            aliases[canonical] = container.id

            normalized_path = container.path.casefold()
            previous_path = paths.get(normalized_path)
            if previous_path is not None:
                raise ScopeManifestError(
                    f"duplicate or overlapping container path {container.path}: "
                    f"{previous_path[0]} and {kind}"
                )
            paths[normalized_path] = (kind, container.path)


def _authority(value: Any) -> ScopeManifestAuthority:
    if not isinstance(value, dict):
        raise ScopeManifestError("scope manifest authority must be an object")
    _exact_fields(value, _AUTHORITY_FIELDS, "scope manifest authority")
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


def _canonical_container_id(value: str) -> str:
    return re.sub(r"[._-]+", ".", value.casefold())
