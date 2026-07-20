"""Machine-verifiable binding between execution authority and one workspace."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Sequence

from .resource_governor import ResourceClass


WORKSPACE_BINDING_SCHEMA_VERSION = 1
_WRITE_PERMISSIONS = {
    "WRITE_AUTHORIZED",
    "CORRECTIVE_AUTHORIZED",
    "ENVIRONMENT_WRITE_AUTHORIZED",
    "SUBMIT_AUTHORIZED",
}
_KNOWN_GIT_MUTATIONS = {
    "add",
    "am",
    "apply",
    "bisect",
    "branch",
    "checkout",
    "cherry-pick",
    "clean",
    "commit",
    "fetch",
    "gc",
    "merge",
    "mv",
    "pull",
    "push",
    "rebase",
    "reset",
    "restore",
    "revert",
    "rm",
    "stash",
    "switch",
    "tag",
    "update-index",
    "worktree",
}


@dataclass(frozen=True)
class WorkspaceIdentity:
    repository_root: str
    worktree_root: str
    project_root: str
    git_common_dir: str | None
    branch: str | None
    head: str | None


@dataclass(frozen=True)
class WorkspaceBinding:
    schema_version: int
    repository_root: str
    worktree_root: str
    project_root: str
    git_common_dir: str | None
    branch: str | None
    head: str | None
    base_head: str | None
    permission_mode: str
    controller: str
    allowed_paths: tuple[str, ...]
    read_only_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    digest: str

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "repository_root": self.repository_root,
            "worktree_root": self.worktree_root,
            "project_root": self.project_root,
            "git_common_dir": self.git_common_dir,
            "branch": self.branch,
            "head": self.head,
            "base_head": self.base_head,
            "permission_mode": self.permission_mode,
            "controller": self.controller,
            "allowed_paths": list(self.allowed_paths),
            "read_only_paths": list(self.read_only_paths),
            "forbidden_paths": list(self.forbidden_paths),
        }

    def recompute_digest(self) -> str:
        return _json_digest(self.unsigned_payload())

    def to_dict(self) -> dict[str, object]:
        return {**self.unsigned_payload(), "binding_sha256": self.digest}

    @classmethod
    def from_dict(cls, payload: object) -> "WorkspaceBinding":
        if not isinstance(payload, dict):
            raise ValueError("workspace binding must be an object")
        expected = {
            "schema_version",
            "repository_root",
            "worktree_root",
            "project_root",
            "git_common_dir",
            "branch",
            "head",
            "base_head",
            "permission_mode",
            "controller",
            "allowed_paths",
            "read_only_paths",
            "forbidden_paths",
            "binding_sha256",
        }
        if set(payload) != expected or payload.get("schema_version") != WORKSPACE_BINDING_SCHEMA_VERSION:
            raise ValueError("workspace binding fields or schema version are invalid")
        for key in ("repository_root", "worktree_root", "project_root", "permission_mode", "controller"):
            if not isinstance(payload.get(key), str) or not payload[key]:
                raise ValueError(f"workspace binding {key} is invalid")
        for key in ("git_common_dir", "branch", "head", "base_head"):
            if payload.get(key) is not None and (not isinstance(payload[key], str) or not payload[key]):
                raise ValueError(f"workspace binding {key} is invalid")
        for key in ("head", "base_head"):
            _validate_commit_id(payload.get(key), key)
        lists: dict[str, tuple[str, ...]] = {}
        for key in ("allowed_paths", "read_only_paths", "forbidden_paths"):
            raw = payload.get(key)
            if not isinstance(raw, list):
                raise ValueError(f"workspace binding {key} is invalid")
            lists[key] = _repository_paths(raw, key)
        binding = cls(
            schema_version=WORKSPACE_BINDING_SCHEMA_VERSION,
            repository_root=str(payload["repository_root"]),
            worktree_root=str(payload["worktree_root"]),
            project_root=str(payload["project_root"]),
            git_common_dir=payload.get("git_common_dir"),
            branch=payload.get("branch"),
            head=payload.get("head"),
            base_head=payload.get("base_head"),
            permission_mode=str(payload["permission_mode"]),
            controller=str(payload["controller"]),
            allowed_paths=lists["allowed_paths"],
            read_only_paths=lists["read_only_paths"],
            forbidden_paths=lists["forbidden_paths"],
            digest=str(payload.get("binding_sha256", "")),
        )
        if not re.fullmatch(r"[0-9a-f]{64}", binding.digest) or binding.recompute_digest() != binding.digest:
            raise ValueError("workspace binding digest is invalid")
        return binding


@dataclass(frozen=True)
class WorkspaceVerification:
    ok: bool
    errors: tuple[str, ...]


@dataclass(frozen=True)
class CommandAuthorization:
    ok: bool
    reason: str
    soft_guarantee: bool = True


def discover_workspace(project_root: Path) -> WorkspaceIdentity:
    project = _canonical_directory(project_root)
    marker_root, marker = _find_git_marker(project)
    if marker is None or marker_root is None:
        canonical = str(project)
        return WorkspaceIdentity(canonical, canonical, canonical, None, None, None)
    git_dir = _resolve_git_dir(marker_root, marker)
    common_dir = _resolve_common_dir(git_dir)
    repository_root = common_dir.parent if common_dir.name.casefold() == ".git" else marker_root
    branch, head = _read_head(git_dir, common_dir)
    return WorkspaceIdentity(
        repository_root=str(_canonical_path(repository_root)),
        worktree_root=str(_canonical_path(marker_root)),
        project_root=str(project),
        git_common_dir=str(_canonical_path(common_dir)),
        branch=branch,
        head=head,
    )


def build_workspace_binding(
    identity: WorkspaceIdentity,
    *,
    base_head: str | None,
    permission_mode: str,
    controller: str,
    allowed_paths: Sequence[str],
    read_only_paths: Sequence[str] = (),
    forbidden_paths: Sequence[str] = (),
) -> WorkspaceBinding:
    if permission_mode not in _WRITE_PERMISSIONS | {"READ_ONLY_REVIEW"}:
        raise ValueError("workspace permission mode is invalid")
    if not controller.strip():
        raise ValueError("workspace controller is required")
    _validate_commit_id(identity.head, "head")
    _validate_commit_id(base_head, "base_head")
    binding = WorkspaceBinding(
        schema_version=WORKSPACE_BINDING_SCHEMA_VERSION,
        repository_root=str(_canonical_path(Path(identity.repository_root))),
        worktree_root=str(_canonical_path(Path(identity.worktree_root))),
        project_root=str(_canonical_path(Path(identity.project_root))),
        git_common_dir=(
            str(_canonical_path(Path(identity.git_common_dir)))
            if identity.git_common_dir is not None
            else None
        ),
        branch=identity.branch,
        head=identity.head,
        base_head=base_head,
        permission_mode=permission_mode,
        controller=controller,
        allowed_paths=_repository_paths(allowed_paths, "allowed paths"),
        read_only_paths=_repository_paths(read_only_paths, "read-only paths"),
        forbidden_paths=_repository_paths(forbidden_paths, "forbidden paths"),
        digest="",
    )
    return WorkspaceBinding(**{**binding.__dict__, "digest": binding.recompute_digest()})


def _validate_commit_id(value: object, label: str) -> None:
    if value is not None and (
        not isinstance(value, str)
        or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value) is None
    ):
        raise ValueError(f"workspace binding {label} is not a full lowercase object ID")


def verify_workspace(
    binding: WorkspaceBinding,
    *,
    current: WorkspaceIdentity | None = None,
    cwd: Path | None = None,
) -> WorkspaceVerification:
    errors: list[str] = []
    if binding.recompute_digest() != binding.digest:
        errors.append("workspace binding digest differs")
    if current is None:
        current = discover_workspace(Path.cwd() if cwd is None else cwd)
    for field in ("repository_root", "worktree_root", "project_root", "git_common_dir"):
        expected = getattr(binding, field)
        actual = getattr(current, field)
        if not _same_optional_path(expected, actual):
            errors.append(f"{field} differs: expected={expected!r} current={actual!r}")
    for field in ("branch", "head"):
        expected = getattr(binding, field)
        actual = getattr(current, field)
        if expected != actual:
            errors.append(f"{field} differs: expected={expected!r} current={actual!r}")
    project = Path(binding.project_root)
    for label, values in (
        ("allowed", binding.allowed_paths),
        ("read-only", binding.read_only_paths),
        ("forbidden", binding.forbidden_paths),
    ):
        for value in values:
            error = _path_boundary_error(project, value)
            if error:
                errors.append(f"{label} path {value}: {error}")
    return WorkspaceVerification(not errors, tuple(errors))


def authorize_command(
    command: Sequence[str],
    *,
    resource_class: ResourceClass,
    permission_mode: str,
    allowed_classes: Sequence[ResourceClass],
    descendant: bool,
    delegated: bool = False,
) -> CommandAuthorization:
    if not command or not str(command[0]).strip():
        return CommandAuthorization(False, "command argv is empty")
    if resource_class is ResourceClass.REASONING_ONLY:
        return CommandAuthorization(False, "reasoning-only authority cannot start a local command")
    if resource_class not in allowed_classes:
        return CommandAuthorization(False, "requested resource class exceeds inherited authority")
    required = required_resource_class(command)
    if required is not None and resource_class is not required:
        return CommandAuthorization(
            False,
            f"known mutation command requires {required.value}, not {resource_class.value}",
        )
    mutation = _known_mutation(command)
    if mutation and permission_mode == "READ_ONLY_REVIEW":
        return CommandAuthorization(False, f"known mutation command is forbidden for read-only authority: {mutation}")
    if descendant and not delegated:
        return CommandAuthorization(
            False,
            "descendant cannot start a local command without an explicit root delegation",
        )
    if resource_class in {ResourceClass.REPO_WRITE, ResourceClass.SUBMIT_EXCLUSIVE} and permission_mode not in _WRITE_PERMISSIONS:
        return CommandAuthorization(False, "resource class requires write permission")
    if resource_class is ResourceClass.SUBMIT_EXCLUSIVE and permission_mode != "SUBMIT_AUTHORIZED":
        return CommandAuthorization(False, "submit-exclusive requires SUBMIT_AUTHORIZED")
    if descendant and resource_class in {ResourceClass.REPO_WRITE, ResourceClass.SUBMIT_EXCLUSIVE} and permission_mode == "READ_ONLY_REVIEW":
        return CommandAuthorization(False, "descendant permission escalation is forbidden")
    return CommandAuthorization(
        True,
        "known command boundary is authorized; arbitrary child behavior remains a soft guarantee",
    )


def required_resource_class(command: Sequence[str]) -> ResourceClass | None:
    """Return the non-negotiable class for commands whose effects are known."""

    mutation = _known_mutation(command)
    if mutation is None:
        return None
    if mutation.startswith("python -m ") or mutation.startswith("pip"):
        return ResourceClass.PACKAGE_BUILD
    if mutation.startswith("git "):
        return ResourceClass.SUBMIT_EXCLUSIVE
    return ResourceClass.REPO_WRITE


def _known_mutation(command: Sequence[str]) -> str | None:
    executable = Path(str(command[0])).name.casefold()
    args = [str(item).casefold() for item in command[1:]]
    if executable in {"git", "git.exe"} and args:
        subcommand = _git_subcommand(args)
        if subcommand == "branch" and args[-2:] == ["branch", "--show-current"]:
            return None
        if subcommand in _KNOWN_GIT_MUTATIONS:
            return f"git {subcommand}"
    if executable.startswith("python") or executable in {"py", "py.exe"}:
        for index, argument in enumerate(args):
            if argument == "-m" and index + 1 < len(args):
                module = args[index + 1]
                if module in {"pip", "build", "venv"}:
                    return f"python -m {module}"
                break
            if argument.startswith("-m") and len(argument) > 2:
                module = argument[2:]
                if module in {"pip", "build", "venv"}:
                    return f"python -m {module}"
                break
    if executable in {"pip", "pip.exe", "pip3", "pip3.exe"}:
        return executable
    if executable in {
        "bash",
        "bash.exe",
        "cmd",
        "cmd.exe",
        "cp",
        "mv",
        "powershell",
        "powershell.exe",
        "pwsh",
        "pwsh.exe",
        "rm",
        "sh",
    }:
        return executable
    return None


def _git_subcommand(args: Sequence[str]) -> str:
    options_with_value = {
        "-c",
        "--exec-path",
        "--git-dir",
        "--namespace",
        "--super-prefix",
        "--work-tree",
    }
    index = 0
    while index < len(args):
        argument = args[index]
        if argument == "--":
            return args[index + 1] if index + 1 < len(args) else ""
        if argument in options_with_value:
            index += 2
            continue
        if (
            argument.startswith("-c")
            and argument != "-c"
        ) or argument.startswith(
            ("--exec-path=", "--git-dir=", "--namespace=", "--super-prefix=", "--work-tree=")
        ):
            index += 1
            continue
        if argument.startswith("-"):
            index += 1
            continue
        return argument
    return ""


def _canonical_directory(path: Path) -> Path:
    resolved = _canonical_path(path)
    if not resolved.is_dir():
        raise NotADirectoryError(str(resolved))
    return resolved


def _canonical_path(path: Path) -> Path:
    return Path(os.path.realpath(os.path.abspath(os.fspath(path))))


def _find_git_marker(project: Path) -> tuple[Path | None, Path | None]:
    for candidate in (project, *project.parents):
        marker = candidate / ".git"
        if marker.is_dir() or marker.is_file():
            return candidate, marker
    return None, None


def _resolve_git_dir(worktree_root: Path, marker: Path) -> Path:
    if marker.is_dir():
        return _canonical_path(marker)
    line = marker.read_text(encoding="utf-8", errors="strict").strip()
    prefix = "gitdir:"
    if not line.casefold().startswith(prefix):
        raise ValueError(f"invalid Git worktree marker: {marker}")
    value = line[len(prefix) :].strip()
    git_dir = Path(value)
    if not git_dir.is_absolute():
        git_dir = worktree_root / git_dir
    resolved = _canonical_path(git_dir)
    if not resolved.is_dir():
        raise ValueError(f"Git directory does not exist: {resolved}")
    return resolved


def _resolve_common_dir(git_dir: Path) -> Path:
    marker = git_dir / "commondir"
    if not marker.is_file():
        return git_dir
    value = marker.read_text(encoding="utf-8", errors="strict").strip()
    if not value:
        raise ValueError("Git commondir marker is empty")
    path = Path(value)
    if not path.is_absolute():
        path = git_dir / path
    common = _canonical_path(path)
    if not common.is_dir():
        raise ValueError(f"Git common directory does not exist: {common}")
    return common


def _read_head(git_dir: Path, common_dir: Path) -> tuple[str | None, str | None]:
    head_path = git_dir / "HEAD"
    if not head_path.is_file():
        head_path = common_dir / "HEAD"
    value = head_path.read_text(encoding="ascii", errors="strict").strip()
    if value.startswith("ref: "):
        reference = value[5:].strip()
        branch = reference[len("refs/heads/") :] if reference.startswith("refs/heads/") else None
        return branch, _read_reference(reference, git_dir, common_dir)
    if re.fullmatch(r"[0-9a-fA-F]{40,64}", value):
        return None, value.lower()
    raise ValueError("Git HEAD is invalid or unsupported")


def _read_reference(reference: str, git_dir: Path, common_dir: Path) -> str:
    if reference.startswith("/") or ".." in PurePosixPath(reference).parts or "\\" in reference:
        raise ValueError("Git HEAD reference is unsafe")
    for base in (git_dir, common_dir):
        path = base.joinpath(*reference.split("/"))
        if path.is_file():
            value = path.read_text(encoding="ascii", errors="strict").strip()
            if re.fullmatch(r"[0-9a-fA-F]{40,64}", value):
                return value.lower()
    packed = common_dir / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="ascii", errors="strict").splitlines():
            if not line or line.startswith(("#", "^")):
                continue
            digest, separator, name = line.partition(" ")
            if separator and name == reference and re.fullmatch(r"[0-9a-fA-F]{40,64}", digest):
                return digest.lower()
    raise ValueError(f"Git reference cannot be resolved: {reference}")


def _repository_paths(values: Sequence[str], label: str) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
            raise ValueError(f"{label} contains an invalid path")
        pure = PurePosixPath(value)
        if pure.is_absolute() or value != pure.as_posix() or any(part in {"", ".", ".."} for part in pure.parts):
            raise ValueError(f"{label} contains an unsafe path: {value}")
        normalized.append(value)
    if len(normalized) != len(set(item.casefold() if os.name == "nt" else item for item in normalized)):
        raise ValueError(f"{label} contains duplicate paths")
    return tuple(normalized)


def _path_boundary_error(project_root: Path, relative: str) -> str | None:
    candidate = project_root.joinpath(*PurePosixPath(relative).parts)
    project_canonical = _canonical_path(project_root)
    current = project_root
    for part in PurePosixPath(relative).parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            break
        attributes = getattr(info, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(info.st_mode) or attributes & reparse_flag:
            return "symlink/reparse component is not allowed"
    resolved = _canonical_path(candidate)
    try:
        if os.path.commonpath([os.path.normcase(str(project_canonical)), os.path.normcase(str(resolved))]) != os.path.normcase(str(project_canonical)):
            return "path escapes project root"
    except ValueError:
        return "path is on a different drive or volume"
    return None


def _same_optional_path(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return left is right
    left_path = _canonical_path(Path(left))
    right_path = _canonical_path(Path(right))
    try:
        if left_path.exists() and right_path.exists() and os.path.samefile(left_path, right_path):
            return True
    except OSError:
        pass
    return os.path.normcase(str(left_path)) == os.path.normcase(str(right_path))


def _json_digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "CommandAuthorization",
    "WORKSPACE_BINDING_SCHEMA_VERSION",
    "WorkspaceBinding",
    "WorkspaceIdentity",
    "WorkspaceVerification",
    "authorize_command",
    "build_workspace_binding",
    "discover_workspace",
    "required_resource_class",
    "verify_workspace",
]
