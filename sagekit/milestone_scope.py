from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


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
    def __init__(self, root: Path):
        self.root = root
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


def _read_active_milestones(
    root: Path,
) -> tuple[frozenset[str], tuple[str, ...], str | None, bool]:
    path = root / "docs/ACTIVE_CONTEXT.md"
    if not path.is_file():
        return frozenset(), (), None, False
    values: list[set[str]] = []
    authorities: list[str] = []
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
            return (
                frozenset(),
                tuple(authorities),
                f"active milestone authority is ambiguous: {raw_value}",
                True,
            )
        values.append({part.casefold() for part in parts})
    if not values:
        return frozenset(), (), None, False
    first = values[0]
    if any(value != first for value in values[1:]):
        return (
            frozenset(),
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
