from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import ModuleType


def normalize_contract_path(value: str | Path, platform: str | None = None) -> str:
    text = str(value)
    selected = (platform or ("windows" if os.name == "nt" else "posix")).lower()
    if selected.startswith("win"):
        normalized = PureWindowsPath(text).as_posix()
        return normalized.casefold().rstrip("/")
    return PurePosixPath(text.replace("\\", "/")).as_posix().rstrip("/")


def canonical_path(root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    return Path(_canonical_filesystem_path(candidate, os.path))


def _canonical_filesystem_path(
    value: str | Path,
    path_module: ModuleType,
) -> str:
    return path_module.normpath(path_module.realpath(os.fspath(value)))


def canonical_relative_path(
    root: str | Path,
    candidate: str | Path,
    *,
    _path_module: ModuleType | None = None,
) -> str | None:
    """Return a stable relative path when both names resolve inside one root."""

    path_module = _path_module or os.path
    canonical_root = _canonical_filesystem_path(root, path_module)
    canonical_candidate = _canonical_filesystem_path(candidate, path_module)
    comparison_root = path_module.normcase(canonical_root)
    comparison_candidate = path_module.normcase(canonical_candidate)
    try:
        common = path_module.commonpath([comparison_root, comparison_candidate])
    except (OSError, TypeError, ValueError):
        return None
    if path_module.normcase(path_module.normpath(common)) != comparison_root:
        return None
    try:
        relative = path_module.relpath(canonical_candidate, canonical_root)
    except (OSError, TypeError, ValueError):
        return None
    if path_module is os.path and os.name != "nt":
        return PurePosixPath(relative).as_posix()
    if getattr(path_module, "sep", None) == "\\":
        return PureWindowsPath(relative).as_posix()
    return PurePosixPath(relative).as_posix()


def is_within(root: Path, candidate: Path) -> bool:
    return canonical_relative_path(root, candidate) is not None


def relative_repo_path(root: Path, value: str | Path) -> str:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    relative = canonical_relative_path(root, candidate)
    if relative is None:
        raise ValueError("path resolves outside repository")
    return relative


def scope_contains(root: Path, scope: str, candidate: str | Path) -> bool:
    candidate_path = canonical_path(root, candidate)
    if not is_within(root, candidate_path):
        return False
    scope_path = canonical_path(root, scope)
    if not is_within(root, scope_path):
        return False
    directory_scope = str(scope).endswith(("/", "\\"))
    if directory_scope:
        return is_within(scope_path, candidate_path)
    return normalize_contract_path(scope_path) == normalize_contract_path(candidate_path)


def paths_overlap(left: str, right: str, platform: str | None = None) -> bool:
    left_key = normalize_contract_path(left, platform)
    right_key = normalize_contract_path(right, platform)
    return (
        left_key == right_key
        or left_key.startswith(right_key + "/")
        or right_key.startswith(left_key + "/")
    )
