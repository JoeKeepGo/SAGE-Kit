from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

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
        (
            self._active_milestones,
            self._active_authorities,
            self._active_error,
            self._active_authority_available,
        ) = _read_active_milestones(root)

    def resolve(self, milestone_dir: Path) -> MilestoneScope:
        milestone_id = milestone_dir.name
        normalized_id = milestone_id.casefold()
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
                milestone_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "validation scope manifest is invalid; legacy scope selection is "
                f"blocked: {self.manifest_error}",
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
                milestone_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "validation scope manifest repository authority is invalid; "
                "legacy scope selection is blocked for every milestone: "
                + "; ".join(self._manifest_repository_errors),
            )
        if self.manifest is not None:
            authorities = [
                *self.manifest.authority_details(self.manifest_source),
                *authorities,
            ]
            return self._resolve_with_manifest(
                milestone_id=milestone_id,
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
                milestone_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "active milestone authority uses an alternate identifier for this "
                f"container: {', '.join(sorted(aliases))}",
            )
        if uncertain:
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "closeout authority is ambiguous: "
                + "; ".join(item.detail for item in uncertain),
            )
        if accepted and nonaccepted:
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "closeout authority conflict: accepted and non-accepted structured outcomes coexist",
            )
        if accepted and self._active_error:
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                self._active_error,
            )
        if accepted and not self._active_authority_available:
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "active milestone authority is unavailable; accepted closeout alone "
                "cannot prove immutable inactive history",
            )
        if active and accepted:
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "authority conflict: milestone is both explicitly active and accepted history",
            )
        if accepted:
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY,
                tuple(authorities),
                "trusted accepted closeout authority and no active milestone authority",
            )
        if self._active_error:
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.CURRENT,
                tuple(authorities),
                f"{self._active_error}; no trusted accepted historical scope, "
                "so current checks remain required",
            )
        if active:
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.CURRENT,
                tuple(authorities),
                "explicit active milestone authority requires the current contract",
            )
        if nonaccepted:
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.CURRENT,
                tuple(authorities),
                "structured closeout outcome is not accepted; current checks remain required",
            )
        return MilestoneScope(
            milestone_id,
            MilestoneScopeKind.CURRENT,
            (),
            "no trusted accepted closeout authority; current checks remain required",
        )

    def _resolve_with_manifest(
        self,
        *,
        milestone_id: str,
        normalized_id: str,
        active: bool,
        aliases: list[str],
        accepted: list[CloseoutAuthority],
        uncertain: list[CloseoutAuthority],
        nonaccepted: list[CloseoutAuthority],
        authorities: list[str],
    ) -> MilestoneScope:
        assert self.manifest is not None
        manifest_active = {
            item.casefold(): item for item in self.manifest.active_milestones
        }
        manifest_accepted = {
            item.casefold(): item
            for item in self.manifest.accepted_legacy_milestones
        }
        canonical = _canonical_milestone_id(normalized_id)
        manifest_aliases = [
            item
            for item in (*self.manifest.active_milestones, *self.manifest.accepted_legacy_milestones)
            if item.casefold() != normalized_id
            and _canonical_milestone_id(item) == canonical
        ]
        if aliases or manifest_aliases:
            rendered = sorted({*aliases, *manifest_aliases})
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "milestone authority uses an alternate separator alias for this "
                f"container: {', '.join(rendered)}",
            )

        listed_active = normalized_id in manifest_active
        listed_accepted = normalized_id in manifest_accepted
        if listed_active:
            if accepted:
                return MilestoneScope(
                    milestone_id,
                    MilestoneScopeKind.AMBIGUOUS,
                    tuple(authorities),
                    "authority conflict: validation scope manifest marks milestone "
                    "active while structured closeout authority marks it accepted",
                )
            if uncertain:
                return MilestoneScope(
                    milestone_id,
                    MilestoneScopeKind.AMBIGUOUS,
                    tuple(authorities),
                    "authority conflict: validation scope manifest marks milestone "
                    "active while closeout authority is ambiguous",
                )
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.CURRENT,
                tuple(authorities),
                "validation scope manifest explicitly requires the current contract",
            )

        if listed_accepted:
            if active:
                return MilestoneScope(
                    milestone_id,
                    MilestoneScopeKind.AMBIGUOUS,
                    tuple(authorities),
                    "authority conflict: validation scope manifest marks milestone "
                    "accepted legacy while ACTIVE_CONTEXT marks it active",
                )
            invalid_supersedes = self._invalid_manifest_supersedes(
                milestone_id,
                closeouts=(*accepted, *uncertain, *nonaccepted),
            )
            if invalid_supersedes:
                return MilestoneScope(
                    milestone_id,
                    MilestoneScopeKind.AMBIGUOUS,
                    tuple(authorities),
                    "validation scope manifest has unrelated or inaccurate "
                    "supersedes authority: "
                    + "; ".join(invalid_supersedes),
                )
            unsuperseded = [
                item
                for item in nonaccepted
                if not self._manifest_supersedes(milestone_id, item.path)
            ]
            if unsuperseded:
                return MilestoneScope(
                    milestone_id,
                    MilestoneScopeKind.AMBIGUOUS,
                    tuple(authorities),
                    "validation scope manifest accepted legacy authority conflicts "
                    "with explicit non-accepted closeout authority that is not "
                    "precisely superseded: "
                    + "; ".join(item.detail for item in unsuperseded),
                )
            if nonaccepted:
                authorities.extend(
                    f"manifest supersedes {item.path.relative_to(self.root).as_posix()}"
                    for item in nonaccepted
                )
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY,
                tuple(authorities),
                "validation scope manifest explicitly accepts immutable legacy "
                "history and no conflicting current authority remains",
            )

        if active and accepted:
            return MilestoneScope(
                milestone_id,
                MilestoneScopeKind.AMBIGUOUS,
                tuple(authorities),
                "authority conflict: unlisted milestone is both explicitly active "
                "and accepted by structured closeout authority",
            )
        return MilestoneScope(
            milestone_id,
            MilestoneScopeKind.CURRENT,
            tuple(authorities),
            "milestone is not listed in the validation scope manifest; current "
            "checks remain required and lower-precedence authority cannot grant "
            "implicit legacy scope",
        )

    def _manifest_supersedes(self, milestone_id: str, closeout_path: Path) -> bool:
        assert self.manifest is not None
        declared = {
            value.casefold()
            for value in self.manifest.superseded_paths(milestone_id)
        }
        actual = closeout_path.relative_to(self.root).as_posix().casefold()
        return actual in declared

    def _invalid_manifest_supersedes(
        self,
        milestone_id: str,
        *,
        closeouts: tuple[CloseoutAuthority, ...],
    ) -> tuple[str, ...]:
        assert self.manifest is not None
        declared = self.manifest.superseded_paths(milestone_id)
        if not declared:
            return ()
        by_path = {
            item.path.relative_to(self.root).as_posix().casefold(): item
            for item in closeouts
        }
        errors: list[str] = []
        expected_container = (self.root / "docs" / milestone_id).resolve(strict=False)
        for value in declared:
            path = (self.root / Path(value)).resolve(strict=False)
            try:
                path.relative_to(expected_container)
            except ValueError:
                errors.append(f"{value} is outside docs/{milestone_id}")
                continue
            authority = by_path.get(value.casefold())
            if authority is None:
                errors.append(f"{value} does not identify an existing closeout")
            elif authority.disposition != CloseoutDisposition.NOT_ACCEPTED:
                errors.append(
                    f"{value} is not an explicit non-accepted closeout"
                )
        return tuple(errors)


def validate_manifest_repository_authority(
    root: Path,
    manifest: ValidationScopeManifest,
) -> tuple[str, ...]:
    errors: list[str] = []
    for milestone_id, declared_paths in manifest.supersedes:
        expected_container = (root / "docs" / milestone_id).resolve(strict=False)
        for value in declared_paths:
            path = (root / Path(value)).resolve(strict=False)
            try:
                relative = path.relative_to(expected_container)
            except ValueError:
                errors.append(f"{value} is outside docs/{milestone_id}")
                continue
            if len(relative.parts) != 1:
                errors.append(
                    f"{value} is not a direct closeout for docs/{milestone_id}"
                )
                continue
            if not path.is_file():
                errors.append(f"{value} does not identify an existing closeout")
                continue
            authority = _classify_closeout(root, path)
            if authority.disposition != CloseoutDisposition.NOT_ACCEPTED:
                errors.append(
                    f"{value} is not an explicit non-accepted closeout"
                )
    return tuple(errors)


def _read_active_milestones(
    root: Path,
) -> tuple[frozenset[str], tuple[str, ...], str | None, bool]:
    path = root / "docs/ACTIVE_CONTEXT.md"
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
        authorities.append(f"docs/ACTIVE_CONTEXT.md active milestone field: {raw_value}")
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
    if any(value != first for value in values[1:]):
        return (
            declared,
            tuple(authorities),
            "active milestone authority is conflicting across structured fields",
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
        and path.name.casefold() in _CLOSEOUT_NAMES
        and "_template" not in path.name.casefold()
    )
    return [_classify_closeout(root, path) for path in paths]


def _classify_closeout(root: Path, path: Path) -> CloseoutAuthority:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    values = _structured_closeout_values(text)
    display = path.relative_to(root).as_posix()
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
