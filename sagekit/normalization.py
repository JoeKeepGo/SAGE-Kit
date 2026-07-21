"""Classify and narrowly repair mechanical whitespace findings."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

from .managed_execution import ManagedExecutionError, run_managed_git


class NormalizationKind(str, Enum):
    EXTRA_BLANK_LINE_AT_EOF = "extra-blank-line-at-eof"
    MISSING_FINAL_NEWLINE = "missing-final-newline"
    TRAILING_WHITESPACE = "trailing-spaces-tabs"
    BROAD_LINE_ENDING_REWRITE = "broad-line-ending-rewrite"
    NON_WHITESPACE_CHANGE = "non-whitespace-change"


AUTO_KINDS = frozenset(
    {
        NormalizationKind.EXTRA_BLANK_LINE_AT_EOF,
        NormalizationKind.MISSING_FINAL_NEWLINE,
        NormalizationKind.TRAILING_WHITESPACE,
    }
)
PROTECTED_PARTS = frozenset(
    {"generated", "vendor", "vendored", "signed", "frozen", "accepted", "historical"}
)
KNOWN_AUTO_FIX_EXTENSIONS = frozenset(
    {
        ".bash",
        ".cfg",
        ".conf",
        ".config",
        ".cpp",
        ".cs",
        ".css",
        ".go",
        ".h",
        ".hpp",
        ".html",
        ".ini",
        ".java",
        ".js",
        ".json",
        ".jsx",
        ".kt",
        ".php",
        ".properties",
        ".py",
        ".pyi",
        ".rb",
        ".rs",
        ".sh",
        ".scss",
        ".sql",
        ".swift",
        ".toml",
        ".ts",
        ".tsx",
        ".xml",
        ".yaml",
        ".yml",
    }
)
KNOWN_AUTO_FIX_BASENAMES = frozenset({"dockerfile", "makefile", "rakefile"})
PROTECTED_MIGRATION_STATES = frozenset({"accepted", "applied", "hash-bound"})
MARKDOWN_SUFFIXES = frozenset({".md", ".mdx", ".markdown"})
PROTECTED_FORMAT_PARTS = frozenset(
    {"fixtures", "templates", "history", "migration", "migrations"}
)


@dataclass(frozen=True)
class NormalizationFinding:
    path: str
    kind: NormalizationKind
    original_sha256: str
    non_whitespace_sha256: str
    auto_eligible: bool
    reason: str


@dataclass(frozen=True)
class NormalizationReport:
    findings: tuple[NormalizationFinding, ...]

    @property
    def auto_findings(self) -> tuple[NormalizationFinding, ...]:
        return tuple(item for item in self.findings if item.auto_eligible)

    @property
    def handoff_findings(self) -> tuple[NormalizationFinding, ...]:
        return tuple(
            item
            for item in self.findings
            if item.kind in AUTO_KINDS and not item.auto_eligible
        )

    @property
    def warnings(self) -> tuple[NormalizationFinding, ...]:
        return tuple(
            item
            for item in self.findings
            if item.kind is NormalizationKind.BROAD_LINE_ENDING_REWRITE
        )


@dataclass(frozen=True)
class NormalizationReceipt:
    changed_paths: tuple[str, ...]
    before_sha256: Mapping[str, str]
    after_sha256: Mapping[str, str]
    non_whitespace_sha256: Mapping[str, str]
    successor_required: bool
    required_verification: tuple[str, ...] = (
        "git diff --check",
        "non-whitespace digest",
        "file-related focused tests",
        "targeted re-review",
    )


def classify_bytes(
    path: str,
    before: bytes,
    after: bytes,
    *,
    protected_reason: str | None = None,
    migration_state: str | None = None,
) -> tuple[NormalizationFinding, ...]:
    relative = _safe_relative(path)
    if before == after:
        return ()
    reason = protected_reason or _automatic_protection_reason(
        relative, migration_state, content=after
    )
    original = _sha256(after)
    non_whitespace = non_whitespace_digest(after)
    findings: list[NormalizationFinding] = []
    if _is_broad_line_ending_rewrite(before, after):
        findings.append(
            NormalizationFinding(
                relative,
                NormalizationKind.BROAD_LINE_ENDING_REWRITE,
                original,
                non_whitespace,
                False,
                "broad CRLF/LF rewrites are non-blocking warnings and are never auto-fixed",
            )
        )
        return tuple(findings)
    candidate_kinds: set[NormalizationKind] = set()
    if after and not after.endswith(b"\n"):
        candidate_kinds.add(NormalizationKind.MISSING_FINAL_NEWLINE)
    if after.endswith(b"\n\n") and not before.endswith(b"\n\n"):
        candidate_kinds.add(NormalizationKind.EXTRA_BLANK_LINE_AT_EOF)
    if _has_trailing_spaces_or_tabs(after):
        candidate_kinds.add(NormalizationKind.TRAILING_WHITESPACE)

    # Findings describe defects in the observed content, so reverse the selected
    # repairs and require an exact match with the baseline bytes. This prevents a
    # token-space edit from being mistaken for a mechanical whitespace change.
    has_non_whitespace_change = (
        not candidate_kinds
        or _normalize_selected(after, candidate_kinds) != before
    )
    auto_allowed = reason is None and not has_non_whitespace_change
    if has_non_whitespace_change:
        findings.append(
            NormalizationFinding(
                relative,
                NormalizationKind.NON_WHITESPACE_CHANGE,
                original,
                non_whitespace,
                False,
                "candidate content is outside the selected mechanical normalization",
            )
        )
    mechanical_reason = reason or "safe whitespace-only correction inside writable scope"
    if NormalizationKind.MISSING_FINAL_NEWLINE in candidate_kinds:
        findings.append(
            NormalizationFinding(
                relative,
                NormalizationKind.MISSING_FINAL_NEWLINE,
                original,
                non_whitespace,
                auto_allowed,
                mechanical_reason,
            )
        )
    if NormalizationKind.EXTRA_BLANK_LINE_AT_EOF in candidate_kinds:
        findings.append(
            NormalizationFinding(
                relative,
                NormalizationKind.EXTRA_BLANK_LINE_AT_EOF,
                original,
                non_whitespace,
                auto_allowed,
                mechanical_reason,
            )
        )
    if NormalizationKind.TRAILING_WHITESPACE in candidate_kinds:
        findings.append(
            NormalizationFinding(
                relative,
                NormalizationKind.TRAILING_WHITESPACE,
                original,
                non_whitespace,
                auto_allowed,
                mechanical_reason,
            )
        )

    return tuple(findings)


def whitespace_preflight(
    repository_root: Path,
    *,
    protected_paths: Sequence[str] = (),
    migration_states: Mapping[str, str] | None = None,
) -> NormalizationReport:
    root = repository_root.resolve(strict=True)
    protected = {_safe_relative(item) for item in protected_paths}
    states = dict(migration_states or {})
    paths = _changed_paths(root)
    findings: list[NormalizationFinding] = []
    for relative in paths:
        path = root.joinpath(*PurePosixPath(relative).parts)
        after = path.read_bytes() if path.is_file() and not path.is_symlink() else b""
        before = _head_bytes(root, relative)
        explicit = "explicitly protected byte-bound file" if relative in protected else None
        findings.extend(
            classify_bytes(
                relative,
                before,
                after,
                protected_reason=explicit,
                migration_state=states.get(relative),
            )
        )
    return NormalizationReport(tuple(findings))


def apply_auto_normalization(
    repository_root: Path,
    findings: Sequence[NormalizationFinding],
    *,
    writable_paths: Sequence[str],
    protected_paths: Sequence[str] = (),
    migration_states: Mapping[str, str] | None = None,
) -> NormalizationReceipt:
    root = repository_root.resolve(strict=True)
    writable = {_safe_relative(item) for item in writable_paths}
    protected = {_safe_relative(item) for item in protected_paths}
    states = dict(migration_states or {})
    grouped: dict[str, list[NormalizationFinding]] = {}
    for finding in findings:
        if not finding.auto_eligible or finding.kind not in AUTO_KINDS:
            raise PermissionError("fixer received a finding outside AUTO_NORMALIZATION_CORRECTIVE")
        if finding.path not in writable:
            raise PermissionError(f"normalization path is outside exact writable scope: {finding.path}")
        protection = (
            "explicitly protected byte-bound file"
            if finding.path in protected
            else _automatic_protection_reason(finding.path, states.get(finding.path))
        )
        if protection is not None:
            raise PermissionError(
                f"normalization target is protected: {finding.path}: {protection}"
            )
        grouped.setdefault(finding.path, []).append(finding)
    before_digests: dict[str, str] = {}
    after_digests: dict[str, str] = {}
    semantic_digests: dict[str, str] = {}
    for relative, selected in sorted(grouped.items()):
        path = root.joinpath(*PurePosixPath(relative).parts)
        _reject_unsafe_target(root, path)
        content = path.read_bytes()
        protection = (
            "explicitly protected byte-bound file"
            if relative in protected
            else _automatic_protection_reason(relative, states.get(relative), content=content)
        )
        if protection is not None:
            raise PermissionError(
                f"normalization target is protected: {relative}: {protection}"
            )
        expected = {item.original_sha256 for item in selected}
        if expected != {_sha256(content)}:
            raise RuntimeError(f"normalization finding is stale: {relative}")
        updated = _normalize_selected(content, {item.kind for item in selected})
        before_digests[relative] = _sha256(content)
        semantic_digests[relative] = non_whitespace_digest(content)
        if non_whitespace_digest(updated) != semantic_digests[relative]:
            raise RuntimeError(
                f"normalization would alter non-whitespace content: {relative}"
            )
        if updated != content:
            path.write_bytes(updated)
        after_digests[relative] = _sha256(updated)
    changed = tuple(
        path for path in sorted(grouped) if before_digests[path] != after_digests[path]
    )
    return NormalizationReceipt(
        changed,
        before_digests,
        after_digests,
        semantic_digests,
        bool(changed),
    )


def non_whitespace_digest(content: bytes) -> str:
    # Canonicalize only the three supported mechanical repairs. Do not collapse
    # arbitrary whitespace, because inline whitespace can separate content tokens.
    updated = content
    lines = updated.splitlines(keepends=True)
    cleaned: list[bytes] = []
    for line in lines:
        ending = b"\r\n" if line.endswith(b"\r\n") else b"\n" if line.endswith(b"\n") else b""
        body = line[: -len(ending)] if ending else line
        cleaned.append(body.rstrip(b" \t") + ending)
    updated = b"".join(cleaned)
    ending = b"\r\n" if b"\r\n" in updated and b"\n" not in updated.replace(b"\r\n", b"") else b"\n"
    updated = updated.rstrip(b"\r\n") + ending
    return _sha256(updated)


def _normalize_selected(content: bytes, kinds: set[NormalizationKind]) -> bytes:
    updated = content
    if NormalizationKind.TRAILING_WHITESPACE in kinds:
        lines = updated.splitlines(keepends=True)
        cleaned: list[bytes] = []
        for line in lines:
            ending = b"\r\n" if line.endswith(b"\r\n") else b"\n" if line.endswith(b"\n") else b""
            body = line[: -len(ending)] if ending else line
            cleaned.append(body.rstrip(b" \t") + ending)
        updated = b"".join(cleaned)
    if NormalizationKind.EXTRA_BLANK_LINE_AT_EOF in kinds:
        ending = b"\r\n" if b"\r\n" in updated and b"\n" not in updated.replace(b"\r\n", b"") else b"\n"
        updated = updated.rstrip(b"\r\n") + ending
    if NormalizationKind.MISSING_FINAL_NEWLINE in kinds and updated and not updated.endswith(b"\n"):
        updated += b"\n"
    return updated


def _changed_paths(root: Path) -> tuple[str, ...]:
    tracked = _git_bytes(root, "diff", "--name-only", "-z", "HEAD", "--")
    untracked = _git_bytes(root, "ls-files", "--others", "--exclude-standard", "-z")
    return tuple(
        sorted(
            {
                relative
                for item in tracked.split(b"\0") + untracked.split(b"\0")
                if item
                for relative in (
                    _safe_relative(item.decode("utf-8", errors="strict")),
                )
                if not relative.startswith(".sagekit/runtime/")
            }
        )
    )


def _head_bytes(root: Path, relative: str) -> bytes:
    try:
        return _git_bytes(root, "show", f"HEAD:{relative}")
    except ValueError:
        return b""


def _git_bytes(root: Path, *arguments: str) -> bytes:
    try:
        return run_managed_git(
            root,
            arguments,
            stage="normalization-whitespace-preflight",
            timeout=30,
        ).stdout
    except ManagedExecutionError as exc:
        raise ValueError(str(exc)) from exc


def _automatic_protection_reason(
    path: str, migration_state: str | None, content: bytes | None = None
) -> str | None:
    parts = {item.casefold() for item in PurePosixPath(path).parts}
    if parts & PROTECTED_PARTS:
        return "generated, vendored, signed, frozen, accepted, or historical files are protected"
    is_migration = bool(parts & {"migration", "migrations"})
    if is_migration:
        state = (migration_state or "unknown").casefold()
        if state in PROTECTED_MIGRATION_STATES:
            return f"migration is {state} and byte-protected"
        if state != "candidate":
            return "migration acceptance/application/hash state is not proven candidate"
    if parts & (PROTECTED_FORMAT_PARTS - {"migration", "migrations"}):
        return "fixtures/templates/history/migrations artifacts are format-sensitive"
    suffix = PurePosixPath(path).suffix.casefold()
    if suffix in MARKDOWN_SUFFIXES:
        return "markdown hard-break-sensitive formatting requires manual repair"
    if _is_unknown_format(path):
        return "unknown file format is excluded from automatic whitespace repair"
    if content is not None and _has_multiline_literal_marks(content):
        return "multiline-literal-sensitive formatting requires manual repair"
    folded = path.casefold()
    if (
        "docs/contracts/execution-documents/2026.7.19.3/" in folded
        or "resources/execution_documents/2026.7.19.3/" in folded
    ):
        return "frozen byte-checksum-bound execution contract is protected"
    return None


def _has_multiline_literal_marks(content: bytes) -> bool:
    return b'"""' in content or b"'''" in content


def _is_unknown_format(path: str) -> bool:
    name = PurePosixPath(path).name.casefold()
    suffix = PurePosixPath(path).suffix.casefold()
    if suffix and suffix in KNOWN_AUTO_FIX_EXTENSIONS:
        return False
    return suffix not in KNOWN_AUTO_FIX_EXTENSIONS and name not in KNOWN_AUTO_FIX_BASENAMES


def _reject_unsafe_target(root: Path, path: Path) -> None:
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise PermissionError(f"normalization target crosses a symlink/reparse point: {relative}")
        if os.name == "nt" and getattr(info, "st_file_attributes", 0) & 0x400:
            raise PermissionError(f"normalization target crosses a symlink/reparse point: {relative}")
    if not path.is_file():
        raise FileNotFoundError(path)


def _safe_relative(value: str) -> str:
    normalized = str(value).replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe normalization path: {value!r}")
    return path.as_posix()


def _is_broad_line_ending_rewrite(before: bytes, after: bytes) -> bool:
    if before == after or before.replace(b"\r\n", b"\n") != after.replace(b"\r\n", b"\n"):
        return False
    return max(before.count(b"\n"), after.count(b"\n")) > 1


def _has_trailing_spaces_or_tabs(content: bytes) -> bool:
    return any(
        line.rstrip(b"\r\n").endswith((b" ", b"\t"))
        for line in content.splitlines(keepends=True)
    )


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


__all__ = [
    "AUTO_KINDS",
    "NormalizationFinding",
    "NormalizationKind",
    "NormalizationReceipt",
    "NormalizationReport",
    "apply_auto_normalization",
    "classify_bytes",
    "non_whitespace_digest",
    "whitespace_preflight",
]
