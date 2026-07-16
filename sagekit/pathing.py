from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath


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
    return candidate.resolve(strict=False)


def is_within(root: Path, candidate: Path) -> bool:
    root_resolved = root.resolve(strict=False)
    candidate_resolved = candidate.resolve(strict=False)
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError:
        return False
    return True


def relative_repo_path(root: Path, value: str | Path) -> str:
    candidate = canonical_path(root, value)
    root_resolved = root.resolve(strict=False)
    try:
        relative = candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"path resolves outside repository: {value}") from exc
    return relative.as_posix()


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
