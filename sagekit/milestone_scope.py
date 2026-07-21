from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from .pathing import is_within, relative_repo_path

if TYPE_CHECKING:
    from .validation_scope_manifest import ValidationScopeManifest


class MilestoneScopeKind(str, Enum):
    CURRENT = "current"
    IMMUTABLE_ACCEPTED_HISTORY = "immutable-accepted-history"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class MilestoneScope:
    milestone_id: str
    kind: MilestoneScopeKind
    authorities: tuple[str, ...]
    detail: str
    contract_version: int | None = None
    container_path: str | None = None


class CloseoutDisposition(str, Enum):
    ACCEPTED = "accepted"
    NOT_ACCEPTED = "not-accepted"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class CloseoutAuthority:
    disposition: CloseoutDisposition
    path: Path
    values: tuple[str, ...]
    detail: str


_ACTIVE_FIELD_RE = re.compile(
    r"^\s*[-*]\s*(?:current|active)\s+milestones?\s*:\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)
_MILESTONE_ID_RE = re.compile(r"M[0-9]+(?:[._-][A-Za-z0-9]+)*", re.IGNORECASE)
_CLOSEOUT_FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:milestone\s+)?(?:status|outcome)\s*:\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)
_CLOSEOUT_NAMES = {"milestone_closeout.md", "closeout.md"}
_ACCEPTED_VALUES = {
    "ACCEPTED",
    "ACCEPTED_WITH_CONCERNS",
    "DONE",
    "DONE_WITH_CONCERNS",
    "PM_ACCEPTED",
}
_NOT_ACCEPTED_VALUES = {
    "ABANDONED",
    "BLOCKED",
    "CLOSED_BLOCKED",
    "CORRECTIVE_READY_FOR_INDEPENDENT_RE_REVIEW",
    "DEFERRED",
    "DRAFT",
    "HANDOFF",
    "NEEDS_CORRECTION",
    "NOT_ACCEPTED",
    "PENDING",
    "PENDING_ACCEPTANCE",
    "REJECTED",
    "SUPERSEDED",
}
_ACCEPTED_COMPOSITES = {
    ("PM_ACCEPTED", "ACCEPTED", "CLOSED"),
}


class RepositoryScopeResolver:
    def __init__(
        self,
        root: Path,
        *,
        manifest: ValidationScopeManifest | None = None,
        manifest_source: str = "project-local",
        manifest_error: str | None = None,
    ):
        self.root = root
        self.manifest = manifest
        self.manifest_source = manifest_source
        self.manifest_error = manifest_error
        self._manifest_repository_errors = (
            validate_manifest_repository_authority(root, manifest)
            if manifest is not None
            else ()
        )
        try:
            from .spec_sources import resolve_active_context_path

            active_context_path = resolve_active_context_path(root)
        except ValueError as exc:
            self._active_milestones = frozenset()
            self._active_authorities = ()
            self._active_error = f"configured active context cannot be resolved: {exc}"
            self._active_authority_available = False
            return
        (
            self._active_milestones,
            self._active_authorities,
            self._active_error,
            self._active_authority_available,
        ) = read_active_milestones(root, active_context_path)

    def resolve(self, milestone_dir: Path) -> MilestoneScope:
        container_id = milestone_dir.name
        normalized_id = container_id.casefold()
        if milestone_dir.is_symlink():
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.AMBIGUOUS,
                (),
                "container symlink identity is not trusted scope authority",
                container_path=milestone_dir.as_posix(),
            )
        container_path = _container_relative_path(self.root, milestone_dir)
        if container_path is None:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.AMBIGUOUS,
                (),
                "container path resolves outside the target root",
                container_path=milestone_dir.as_posix(),
            )
        active = normalized_id in self._active_milestones
        aliases = [
            active_id
            for active_id in self._active_milestones
            if active_id != normalized_id
            and _canonical_milestone_id(active_id)
            == _canonical_milestone_id(normalized_id)
        ]
        closeouts = tuple(_read_closeout_authorities(self.root, milestone_dir))
        accepted = [item for item in closeouts if item.disposition == CloseoutDisposition.ACCEPTED]
        uncertain = [item for item in closeouts if item.disposition == CloseoutDisposition.AMBIGUOUS]
        nonaccepted = [
            item for item in closeouts if item.disposition == CloseoutDisposition.NOT_ACCEPTED
        ]
        authorities = list(self._active_authorities)
        authorities.extend(item.detail for item in closeouts)
        if self.manifest_error is not None:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "validation scope manifest is invalid; legacy scope selection is "
                f"blocked: {self.manifest_error}",
                container_path=container_path,
            )
        if self._manifest_repository_errors:
            authorities = [
                *(
                    self.manifest.authority_details(self.manifest_source)
                    if self.manifest is not None
                    else ()
                ),
                *authorities,
            ]
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "validation scope manifest repository authority is invalid; "
                "legacy scope selection is blocked for every container: "
                + "; ".join(self._manifest_repository_errors),
                container_path=container_path,
            )
        if self.manifest is not None:
            authorities = [
                *self.manifest.authority_details(self.manifest_source),
                *authorities,
            ]
            return self._resolve_with_manifest(
                container_id=container_id,
                container_path=container_path,
                normalized_id=normalized_id,
                active=active,
                aliases=aliases,
                accepted=accepted,
                uncertain=uncertain,
                nonaccepted=nonaccepted,
                authorities=authorities,
            )

        if aliases:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "active milestone authority uses an alternate identifier for this "
                f"container: {', '.join(sorted(aliases))}",
                container_path=container_path,
            )
        if uncertain:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "closeout authority is ambiguous: "
                + "; ".join(item.detail for item in uncertain),
                container_path=container_path,
            )
        if accepted and nonaccepted:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "closeout authority conflict: accepted and non-accepted structured outcomes coexist",
                container_path=container_path,
            )
        if accepted and self._active_error:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                self._active_error,
                container_path=container_path,
            )
        if accepted and not self._active_authority_available:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "active milestone authority is unavailable; accepted closeout alone "
                "cannot prove immutable inactive history",
                container_path=container_path,
            )
        if active and accepted:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "authority conflict: milestone is both explicitly active and accepted history",
                container_path=container_path,
            )
        if accepted:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.CURRENT,
                tuple(authorities),
                "accepted closeout is audit evidence only; an explicit Validation "
                "Scope Manifest is required to authorize immutable history",
                container_path=container_path,
            )
        if self._active_error:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.CURRENT,
                tuple(authorities),
                f"{self._active_error}; no trusted accepted historical scope, "
                "so current checks remain required",
                container_path=container_path,
            )
        if active:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.CURRENT,
                tuple(authorities),
                "explicit active milestone authority requires the current contract",
                container_path=container_path,
            )
        if nonaccepted:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.CURRENT,
                tuple(authorities),
                "structured closeout outcome is not accepted; current checks remain required",
                container_path=container_path,
            )
        return MilestoneScope(
            container_id,
            MilestoneScopeKind.CURRENT,
            (),
            "no trusted accepted closeout authority; current checks remain required",
            container_path=container_path,
        )

    def _resolve_with_manifest(
        self,
        *,
        container_id: str,
        container_path: str,
        normalized_id: str,
        active: bool,
        aliases: list[str],
        accepted: list[CloseoutAuthority],
        uncertain: list[CloseoutAuthority],
        nonaccepted: list[CloseoutAuthority],
        authorities: list[str],
    ) -> MilestoneScope:
        assert self.manifest is not None
        listed_active = self.manifest.active_for_path(container_path)
        listed_accepted = self.manifest.legacy_for_path(container_path)
        manifest_id = (
            listed_active.id
            if listed_active is not None
            else listed_accepted.id
            if listed_accepted is not None
            else container_id
        )
        manifest_aliases = list(
            self.manifest.containers_with_alias_id(manifest_id)
        )
        if aliases or manifest_aliases:
            rendered = sorted({*aliases, *manifest_aliases})
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "container authority uses an alternate separator alias for this "
                f"container: {', '.join(rendered)}",
                container_path=container_path,
            )

        if listed_active is not None:
            if accepted:
                return MilestoneScope(
                    container_id,
                    MilestoneScopeKind.AMBIGUOUS,
                    tuple(authorities),
                    "authority conflict: validation scope manifest marks milestone "
                    "active while structured closeout authority marks it accepted",
                    container_path=container_path,
                )
            if uncertain:
                return MilestoneScope(
                    container_id,
                    MilestoneScopeKind.AMBIGUOUS,
                    tuple(authorities),
                    "authority conflict: validation scope manifest marks milestone "
                    "active while closeout authority is ambiguous",
                    container_path=container_path,
                )
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.CURRENT,
                tuple(authorities),
                "validation scope manifest explicitly requires the current contract "
                f"for {container_path}",
                container_path=container_path,
            )

        if listed_accepted is not None:
            manifest_active_by_id = (
                listed_accepted.id.casefold() in self._active_milestones
            )
            if active or manifest_active_by_id:
                return MilestoneScope(
                    container_id,
                    MilestoneScopeKind.AMBIGUOUS,
                    tuple(authorities),
                    "authority conflict: validation scope manifest marks milestone "
                    "accepted legacy while ACTIVE_CONTEXT marks it active",
                    container_path=container_path,
                )
            declared_supersedes = {
                value.casefold() for value in listed_accepted.supersedes
            }
            unsuperseded = [
                item
                for item in nonaccepted
                if relative_repo_path(self.root, item.path).casefold()
                not in declared_supersedes
            ]
            if unsuperseded:
                return MilestoneScope(
                    container_id,
                    MilestoneScopeKind.AMBIGUOUS,
                    tuple(authorities),
                    "validation scope manifest accepted legacy authority conflicts "
                    "with explicit non-accepted closeout authority that is not "
                    "precisely superseded: "
                    + "; ".join(item.detail for item in unsuperseded),
                    container_path=container_path,
                )
            if nonaccepted:
                authorities.extend(
                    f"manifest supersedes {relative_repo_path(self.root, item.path)}"
                    for item in nonaccepted
                )
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY,
                tuple(authorities),
                "validation scope manifest explicitly accepts immutable legacy "
                f"history at {container_path} using frozen v"
                f"{listed_accepted.contract_version}; no conflicting current "
                "authority remains",
                contract_version=listed_accepted.contract_version,
                container_path=container_path,
            )

        if active and accepted:
            return MilestoneScope(
                container_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "authority conflict: unlisted milestone is both explicitly active "
                "and accepted by structured closeout authority",
                container_path=container_path,
            )
        return MilestoneScope(
            container_id,
            MilestoneScopeKind.CURRENT,
            tuple(authorities),
            f"container {container_path} is not listed in the validation scope "
            "manifest; current "
            "checks remain required and lower-precedence authority cannot grant "
            "implicit legacy scope",
            container_path=container_path,
        )


def validate_manifest_repository_authority(
    root: Path,
    manifest: ValidationScopeManifest,
) -> tuple[str, ...]:
    errors: list[str] = []
    containers = (
        *manifest.active_containers,
        *manifest.accepted_legacy_containers,
    )
    for container in containers:
        container_path = root / Path(container.path)
        if not is_within(root, container_path):
            errors.append(f"{container.path} resolves outside the target root")
            continue
        if not container_path.is_dir():
            errors.append(
                f"{container.path} does not identify an existing container directory"
            )

    for container in manifest.accepted_legacy_containers:
        expected_container = root / Path(container.path)
        for value in container.supersedes:
            declared_path = root / Path(value)
            if declared_path.is_symlink():
                errors.append(f"{value} must not be a symlink authority")
                continue
            if not is_within(root, declared_path):
                errors.append(f"{value} resolves outside the target root")
                continue
            if not is_within(expected_container, declared_path):
                errors.append(f"{value} is outside {container.path}")
                continue
            if not declared_path.is_file():
                errors.append(f"{value} does not identify an existing closeout")
                continue
            authority = _classify_closeout(root, declared_path)
            if authority.disposition != CloseoutDisposition.NOT_ACCEPTED:
                errors.append(
                    f"{value} is not an explicit non-accepted closeout"
                )
    return tuple(errors)


def read_active_milestones(
    root: Path,
    path: Path,
) -> tuple[frozenset[str], tuple[str, ...], str | None, bool]:
    if not path.is_file():
        return frozenset(), (), None, False
    values: list[set[str]] = []
    authorities: list[str] = []
    invalid_values: list[str] = []
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    for line in _authority_lines(text):
        match = _ACTIVE_FIELD_RE.match(line)
        if match is None:
            continue
        raw_value = _strip_markdown_value(match.group("value"))
        authorities.append(
            f"{relative_repo_path(root, path)} active milestone field: {raw_value}"
        )
        if raw_value.casefold() in {"none", "n/a", "na", "no active milestone"}:
            values.append(set())
            continue
        parts = [part.strip().strip("`") for part in raw_value.split(",")]
        if not parts or any(_MILESTONE_ID_RE.fullmatch(part) is None for part in parts):
            invalid_values.append(raw_value)
            continue
        values.append({part.casefold() for part in parts})
    declared = frozenset().union(*values) if values else frozenset()
    if invalid_values:
        return (
            declared,
            tuple(authorities),
            "active milestone authority is ambiguous: "
            + ", ".join(invalid_values),
            True,
        )
    if not values:
        return frozenset(), (), None, False
    first = values[0]
    if len(values) > 1:
        if any(value != first for value in values[1:]):
            detail = "active milestone authority is conflicting across structured fields"
        else:
            detail = "active milestone authority has duplicate structured declarations"
        return (
            declared,
            tuple(authorities),
            detail,
            True,
        )
    return frozenset(first), tuple(authorities), None, True


def _read_closeout_authorities(
    root: Path,
    milestone_dir: Path,
) -> list[CloseoutAuthority]:
    if not milestone_dir.is_dir():
        return []
    paths = sorted(
        path
        for path in milestone_dir.iterdir()
        if path.is_file()
        and (
            path.name.casefold() in _CLOSEOUT_NAMES
            or path.name.casefold().endswith("_closeout.md")
        )
        and "_template" not in path.name.casefold()
    )
    authorities: list[CloseoutAuthority] = []
    container_display = _container_relative_path(root, milestone_dir)
    for path in paths:
        display = (
            f"{container_display}/{path.name}"
            if container_display is not None
            else path.name
        )
        if path.is_symlink():
            authorities.append(
                CloseoutAuthority(
                    CloseoutDisposition.AMBIGUOUS,
                    path,
                    (),
                    f"{display} is a symlink and is not trusted closeout authority",
                )
            )
            continue
        if not is_within(milestone_dir, path):
            authorities.append(
                CloseoutAuthority(
                    CloseoutDisposition.AMBIGUOUS,
                    path,
                    (),
                    f"{display} resolves outside its container",
                )
            )
            continue
        authorities.append(_classify_closeout(root, path))
    return authorities


def _container_relative_path(root: Path, container_dir: Path) -> str | None:
    try:
        relative_text = relative_repo_path(root, container_dir)
    except ValueError:
        return None
    relative = Path(relative_text)
    if len(relative.parts) < 2 or relative.parts[0].casefold() != "docs":
        return None
    return relative.as_posix()


def _classify_closeout(root: Path, path: Path) -> CloseoutAuthority:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    values = _structured_closeout_values(text)
    display = relative_repo_path(root, path)
    if not values:
        return CloseoutAuthority(
            CloseoutDisposition.AMBIGUOUS,
            path,
            (),
            f"{display} has no structured Status or Outcome value",
        )
    dispositions = {_closeout_value_disposition(value) for value in values}
    rendered = ", ".join(values)
    if dispositions == {CloseoutDisposition.ACCEPTED}:
        return CloseoutAuthority(
            CloseoutDisposition.ACCEPTED,
            path,
            values,
            f"{display} accepted outcome: {rendered}",
        )
    if dispositions == {CloseoutDisposition.NOT_ACCEPTED}:
        return CloseoutAuthority(
            CloseoutDisposition.NOT_ACCEPTED,
            path,
            values,
            f"{display} non-accepted outcome: {rendered}",
        )
    return CloseoutAuthority(
        CloseoutDisposition.AMBIGUOUS,
        path,
        values,
        f"{display} has conflicting or unrecognized structured outcome: {rendered}",
    )


def _structured_closeout_values(text: str) -> tuple[str, ...]:
    values: list[str] = []
    for line in _authority_lines(text):
        match = _CLOSEOUT_FIELD_RE.match(line)
        if match is not None:
            values.append(_strip_markdown_value(match.group("value")))
            continue
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) >= 2 and cells[0].casefold() in {
            "status",
            "milestone status",
            "outcome",
        }:
            values.append(_strip_markdown_value(cells[1]))
    return tuple(value for value in values if value)


def _authority_lines(text: str):
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
        if fence is not None or line.startswith(("    ", "\t")):
            continue
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


def _strip_markdown_value(value: str) -> str:
    result = value.strip().rstrip(".").strip()
    if len(result) >= 2 and result.startswith("`") and result.endswith("`"):
        result = result[1:-1].strip()
    return result


def _normalize_status(value: str) -> str:
    return re.sub(r"[\s-]+", "_", value.strip().upper())


def _canonical_milestone_id(value: str) -> str:
    return re.sub(r"[._-]+", ".", value.casefold())


def _closeout_value_disposition(value: str) -> CloseoutDisposition:
    parts = tuple(_normalize_status(part) for part in value.split("/"))
    if len(parts) > 1:
        if parts in _ACCEPTED_COMPOSITES:
            return CloseoutDisposition.ACCEPTED
        return CloseoutDisposition.AMBIGUOUS
    normalized = parts[0]
    if normalized in _ACCEPTED_VALUES:
        return CloseoutDisposition.ACCEPTED
    if normalized in _NOT_ACCEPTED_VALUES:
        return CloseoutDisposition.NOT_ACCEPTED
    return CloseoutDisposition.AMBIGUOUS
