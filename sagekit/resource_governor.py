"""Cross-session host and project resource leases.

The governor uses atomic directory creation rather than an in-process mutex so
independent SAGE-Kit sessions and Git worktrees observe the same exclusions.
Runtime records are deliberately stored outside tracked project content.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Mapping


LEASE_SCHEMA_VERSION = 2
DEFAULT_LEASE_TTL = 30.0
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_MAX_WAIT = 300.0
WAIT_HEARTBEAT_INTERVAL = 30.0
RESOURCE_PROFILE_ID = "conservative-host-v1"
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")


class ResourceClass(str, Enum):
    REASONING_ONLY = "reasoning-only"
    REPO_READ = "repo-read"
    REPO_WRITE = "repo-write"
    CPU_HEAVY = "cpu-heavy"
    IO_HEAVY = "io-heavy"
    PACKAGE_BUILD = "package-build"
    RUNTIME_EXCLUSIVE = "runtime-exclusive"
    SUBMIT_EXCLUSIVE = "submit-exclusive"

    @property
    def allows_local_command(self) -> bool:
        return self is not ResourceClass.REASONING_ONLY


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    creation: str


@dataclass(frozen=True)
class ResourceRequest:
    resource_class: ResourceClass
    run_id: str
    controller: str
    stage: str
    authority_digest: str
    host_identity: str
    project_identity: str
    worktree_identity: str
    permission_mode: str
    exclusive_resources: tuple[str, ...] = ()
    allowed_classes: tuple[ResourceClass, ...] | None = None
    parent_lease_id: str | None = None
    descendant: bool = False
    delegation_secret: str | None = None


@dataclass(frozen=True)
class LeaseRecord:
    schema_version: int
    lease_id: str
    resource_class: str
    host_identity: str
    project_identity: str
    worktree_identity: str
    run_id: str
    controller: str
    owner: str
    pid: int
    process_creation: str
    nonce: str
    delegation_sha256: str
    acquired_at: float
    heartbeat_at: float
    expires_at: float
    command_stage: str
    authority_digest: str
    permission_mode: str
    allowed_classes: tuple[str, ...]
    exclusive_resources: tuple[str, ...]
    claims: tuple[str, ...]
    parent_lease_id: str | None
    descendant: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "lease_id": self.lease_id,
            "resource_class": self.resource_class,
            "host_identity": self.host_identity,
            "project_identity": self.project_identity,
            "worktree_identity": self.worktree_identity,
            "run_id": self.run_id,
            "controller": self.controller,
            "owner": self.owner,
            "pid": self.pid,
            "process_creation": self.process_creation,
            "nonce": self.nonce,
            "delegation_sha256": self.delegation_sha256,
            "acquired_at": self.acquired_at,
            "heartbeat_at": self.heartbeat_at,
            "expires_at": self.expires_at,
            "command_stage": self.command_stage,
            "authority_digest": self.authority_digest,
            "permission_mode": self.permission_mode,
            "allowed_classes": list(self.allowed_classes),
            "exclusive_resources": list(self.exclusive_resources),
            "claims": list(self.claims),
            "parent_lease_id": self.parent_lease_id,
            "descendant": self.descendant,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "LeaseRecord":
        if not isinstance(payload, dict):
            raise ValueError("lease record must be an object")
        required = {
            "schema_version",
            "lease_id",
            "resource_class",
            "host_identity",
            "project_identity",
            "worktree_identity",
            "run_id",
            "controller",
            "owner",
            "pid",
            "process_creation",
            "nonce",
            "delegation_sha256",
            "acquired_at",
            "heartbeat_at",
            "expires_at",
            "command_stage",
            "authority_digest",
            "permission_mode",
            "allowed_classes",
            "exclusive_resources",
            "claims",
            "parent_lease_id",
            "descendant",
        }
        if set(payload) != required or payload.get("schema_version") != LEASE_SCHEMA_VERSION:
            raise ValueError("lease record fields or schema version are invalid")
        string_fields = required - {
            "schema_version",
            "pid",
            "acquired_at",
            "heartbeat_at",
            "expires_at",
            "allowed_classes",
            "exclusive_resources",
            "claims",
            "parent_lease_id",
            "descendant",
        }
        if any(not isinstance(payload.get(key), str) or not payload[key] for key in string_fields):
            raise ValueError("lease record contains an invalid string field")
        if type(payload.get("pid")) is not int or int(payload["pid"]) <= 0:
            raise ValueError("lease PID is invalid")
        if any(type(payload.get(key)) not in {int, float} for key in ("acquired_at", "heartbeat_at", "expires_at")):
            raise ValueError("lease timestamp is invalid")
        allowed = payload.get("allowed_classes")
        exclusive = payload.get("exclusive_resources")
        claims = payload.get("claims")
        if (
            not isinstance(allowed, list)
            or not allowed
            or not all(isinstance(item, str) for item in allowed)
        ):
            raise ValueError("lease allowed resource classes are invalid")
        try:
            normalized_allowed = tuple(
                sorted({ResourceClass(item).value for item in allowed})
            )
        except ValueError as exc:
            raise ValueError("lease allowed resource classes are invalid") from exc
        if not isinstance(exclusive, list) or not all(isinstance(item, str) for item in exclusive):
            raise ValueError("lease exclusive resources are invalid")
        if not isinstance(claims, list) or not all(isinstance(item, str) for item in claims):
            raise ValueError("lease claims are invalid")
        parent = payload.get("parent_lease_id")
        if parent is not None and (not isinstance(parent, str) or not parent):
            raise ValueError("lease parent is invalid")
        if type(payload.get("descendant")) is not bool:
            raise ValueError("lease descendant flag is invalid")
        return cls(
            schema_version=LEASE_SCHEMA_VERSION,
            lease_id=str(payload["lease_id"]),
            resource_class=str(payload["resource_class"]),
            host_identity=str(payload["host_identity"]),
            project_identity=str(payload["project_identity"]),
            worktree_identity=str(payload["worktree_identity"]),
            run_id=str(payload["run_id"]),
            controller=str(payload["controller"]),
            owner=str(payload["owner"]),
            pid=int(payload["pid"]),
            process_creation=str(payload["process_creation"]),
            nonce=str(payload["nonce"]),
            delegation_sha256=str(payload["delegation_sha256"]),
            acquired_at=float(payload["acquired_at"]),
            heartbeat_at=float(payload["heartbeat_at"]),
            expires_at=float(payload["expires_at"]),
            command_stage=str(payload["command_stage"]),
            authority_digest=str(payload["authority_digest"]),
            permission_mode=str(payload["permission_mode"]),
            allowed_classes=normalized_allowed,
            exclusive_resources=tuple(exclusive),
            claims=tuple(claims),
            parent_lease_id=parent,
            descendant=bool(payload["descendant"]),
        )


@dataclass(frozen=True)
class ResourceLease:
    record: LeaseRecord
    claim_paths: tuple[Path, ...]
    registry_path: Path
    delegation_secret: str | None = None

    @property
    def lease_id(self) -> str:
        return self.record.lease_id


class ResourceBusy(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        state: str = "WAITING_FOR_RESOURCE",
        blocking_lease: LeaseRecord | None = None,
    ) -> None:
        self.state = state
        self.blocking_lease = blocking_lease
        super().__init__(message)


def host_runtime_path(
    environment: Mapping[str, str] | None = None,
    *,
    platform_name: str | None = None,
) -> Path:
    env = os.environ if environment is None else environment
    selected = platform.system().lower() if platform_name is None else platform_name.lower()
    if selected.startswith("win"):
        base = env.get("LOCALAPPDATA")
        if base:
            return Path(base) / "SAGE-Kit" / "runtime"
        return Path.home() / "AppData" / "Local" / "SAGE-Kit" / "runtime"
    xdg = env.get("XDG_RUNTIME_DIR")
    if xdg and Path(xdg).is_absolute():
        return Path(xdg) / "sage-kit"
    if selected == "darwin":
        return Path.home() / "Library" / "Caches" / "SAGE-Kit" / "runtime"
    cache = env.get("XDG_CACHE_HOME")
    return (Path(cache) if cache and Path(cache).is_absolute() else Path.home() / ".cache") / "sage-kit" / "runtime"


def project_runtime_path(project_root: Path, git_common_dir: Path | None) -> Path:
    if git_common_dir is not None:
        return git_common_dir.resolve(strict=False) / "sagekit" / "runtime"
    return project_root.resolve(strict=True) / ".sagekit" / "runtime"


def default_host_identity() -> str:
    uid = str(os.getuid()) if hasattr(os, "getuid") else os.environ.get("USERNAME", "unknown")
    value = f"{socket.gethostname()}\0{uid}\0{platform.system()}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def current_process_identity(pid: int | None = None) -> ProcessIdentity:
    selected = os.getpid() if pid is None else int(pid)
    creation = probe_process_creation(selected)
    if creation is None:
        if selected != os.getpid():
            raise ProcessLookupError(selected)
        creation = f"fallback:{selected}:{time.time_ns()}"
    return ProcessIdentity(selected, creation)


def probe_process_creation(pid: int) -> str | None:
    if pid <= 0:
        return None
    if os.name == "nt":
        return _windows_process_creation(pid)
    if sys.platform == "darwin":
        return _macos_process_creation(pid)
    proc_stat = Path("/proc") / str(pid) / "stat"
    try:
        raw = proc_stat.read_text(encoding="ascii", errors="strict")
        close = raw.rfind(")")
        fields = raw[close + 2 :].split()
        start_ticks = fields[19]
        boot_id_path = Path("/proc/sys/kernel/random/boot_id")
        boot_id = boot_id_path.read_text(encoding="ascii").strip() if boot_id_path.is_file() else "no-boot-id"
        return f"linux:{boot_id}:{start_ticks}"
    except (OSError, IndexError, ValueError):
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        return f"posix-live:{pid}:permission-denied"
    return f"posix-live:{pid}:creation-unavailable"


def _macos_process_creation(pid: int) -> str | None:
    """Return the native proc_bsdinfo start timestamp for a macOS process."""
    class ProcBsdInfo(ctypes.Structure):
        _fields_ = [
            ("pbi_flags", ctypes.c_uint32),
            ("pbi_status", ctypes.c_uint32),
            ("pbi_xstatus", ctypes.c_uint32),
            ("pbi_pid", ctypes.c_uint32),
            ("pbi_ppid", ctypes.c_uint32),
            ("pbi_uid", ctypes.c_uint32),
            ("pbi_gid", ctypes.c_uint32),
            ("pbi_ruid", ctypes.c_uint32),
            ("pbi_rgid", ctypes.c_uint32),
            ("pbi_svuid", ctypes.c_uint32),
            ("pbi_svgid", ctypes.c_uint32),
            ("rfu_1", ctypes.c_uint32),
            ("pbi_comm", ctypes.c_char * 16),
            ("pbi_name", ctypes.c_char * 32),
            ("pbi_nfiles", ctypes.c_uint32),
            ("pbi_pgid", ctypes.c_uint32),
            ("pbi_pjobc", ctypes.c_uint32),
            ("e_tdev", ctypes.c_uint32),
            ("e_tpgid", ctypes.c_uint32),
            ("pbi_nice", ctypes.c_int32),
            ("pbi_start_tvsec", ctypes.c_uint64),
            ("pbi_start_tvusec", ctypes.c_uint64),
        ]

    try:
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        libproc.proc_pidinfo.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        libproc.proc_pidinfo.restype = ctypes.c_int
        info = ProcBsdInfo()
        size = libproc.proc_pidinfo(
            pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info)
        )
        if size != ctypes.sizeof(info):
            return None if ctypes.get_errno() in {3} else "unknown:macos-proc-pidinfo"
        return f"macos-start:{int(info.pbi_start_tvsec)}:{int(info.pbi_start_tvusec)}"
    except (AttributeError, OSError):
        return "unknown:macos-proc-pidinfo"


def _windows_process_creation(pid: int) -> str | None:
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error in {87, 1168}:
            return None
        return f"unknown:windows-open-process:{error}"
    try:
        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return f"unknown:windows-process-times:{ctypes.get_last_error()}"
        ticks = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
        return f"windows-filetime:{ticks}"
    finally:
        kernel32.CloseHandle(handle)


def _permission_rank(value: str) -> int:
    order = {
        "READ_ONLY_REVIEW": 0,
        "WRITE_AUTHORIZED": 1,
        "CORRECTIVE_AUTHORIZED": 1,
        "ENVIRONMENT_WRITE_AUTHORIZED": 2,
        "SUBMIT_AUTHORIZED": 3,
    }
    try:
        return order[value]
    except KeyError as exc:
        raise ValueError(f"unknown permission mode: {value}") from exc


def _secret_matches(secret: str, expected_sha256: str) -> bool:
    if not isinstance(secret, str) or len(secret) < 32:
        return False
    observed = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    return observed == expected_sha256


def _probe_is_unknown(observed: str | None) -> bool:
    return isinstance(observed, str) and (
        observed.startswith("unknown:")
        or observed.endswith(":permission-denied")
        or observed.endswith(":creation-unavailable")
    )


class ResourceManager:
    def __init__(
        self,
        *,
        host_runtime: Path,
        project_runtime: Path,
        process_identity: ProcessIdentity | None = None,
        process_probe: Callable[[int], str | None] = probe_process_creation,
        wall_clock: Callable[[], float] = time.time,
        monotonic_clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        parent_pid_provider: Callable[[], int] = os.getppid,
    ) -> None:
        if poll_interval < 0.25:
            raise ValueError("resource poll interval must be at least 0.25 seconds")
        self.host_runtime = host_runtime.resolve(strict=False)
        self.project_runtime = project_runtime.resolve(strict=False)
        self.process_identity = process_identity or current_process_identity()
        self._process_probe = process_probe
        self._wall_clock = wall_clock
        self._monotonic_clock = monotonic_clock
        self._sleep = sleep
        self.poll_interval = poll_interval
        self._parent_pid_provider = parent_pid_provider

    def acquire(
        self,
        request: ResourceRequest,
        *,
        wait_timeout: float = 0.0,
        lease_ttl: float = DEFAULT_LEASE_TTL,
        on_wait: Callable[[str], None] | None = None,
    ) -> ResourceLease:
        self._validate_request(request)
        if wait_timeout < 0 or wait_timeout > DEFAULT_MAX_WAIT:
            raise ValueError(
                f"resource wait timeout must be between 0 and {DEFAULT_MAX_WAIT:g} seconds"
            )
        if lease_ttl <= 0:
            raise ValueError("lease TTL must be positive")
        deadline = self._monotonic_clock() + wait_timeout
        next_wait_report = self._monotonic_clock()
        while True:
            try:
                return self._try_acquire(request, lease_ttl)
            except ResourceBusy as busy:
                remaining = deadline - self._monotonic_clock()
                if wait_timeout == 0 or remaining <= 0:
                    state = "HANDOFF_READY" if wait_timeout > 0 else busy.state
                    raise ResourceBusy(
                        str(busy), state=state, blocking_lease=busy.blocking_lease
                    ) from busy
                now = self._monotonic_clock()
                if on_wait is not None and now >= next_wait_report:
                    on_wait("WAITING_FOR_RESOURCE")
                    next_wait_report = now + WAIT_HEARTBEAT_INTERVAL
                self._sleep(min(self.poll_interval, remaining))

    def heartbeat(
        self,
        lease: ResourceLease,
        *,
        stage: str | None = None,
        lease_ttl: float = DEFAULT_LEASE_TTL,
    ) -> ResourceLease:
        if lease_ttl <= 0:
            raise ValueError("lease TTL must be positive")
        now = self._wall_clock()
        updated = replace(
            lease.record,
            heartbeat_at=now,
            expires_at=now + lease_ttl,
            command_stage=stage or lease.record.command_stage,
        )
        self._verify_owner(updated)
        with self._bundle_mutex():
            for claim_path in lease.claim_paths:
                current = self._read_record(claim_path / "lease.json")
                self._verify_same_lease(current, updated)
                self._atomic_write(claim_path / "lease.json", updated.to_dict())
            self._atomic_write(lease.registry_path, updated.to_dict())
        return ResourceLease(
            updated,
            lease.claim_paths,
            lease.registry_path,
            lease.delegation_secret,
        )

    def release(self, lease: ResourceLease) -> None:
        self._verify_owner(lease.record)
        with self._bundle_mutex():
            self._release_locked(lease)

    def _release_locked(self, lease: ResourceLease) -> None:
        errors: list[str] = []
        for claim_path in reversed(lease.claim_paths):
            try:
                record_path = claim_path / "lease.json"
                if record_path.exists():
                    current = self._read_record(record_path)
                    self._verify_same_lease(current, lease.record)
                    record_path.unlink()
                claim_path.rmdir()
            except FileNotFoundError:
                continue
            except (OSError, ValueError, PermissionError) as exc:
                errors.append(f"{claim_path}: {exc}")
        try:
            if lease.registry_path.exists():
                current = self._read_record(lease.registry_path)
                self._verify_same_lease(current, lease.record)
                lease.registry_path.unlink()
        except (OSError, ValueError, PermissionError) as exc:
            errors.append(f"{lease.registry_path}: {exc}")
        delegation_path = self._delegation_binding_path(lease.lease_id)
        try:
            binding_path = delegation_path / "binding.json"
            if binding_path.exists():
                binding_path.unlink()
            if delegation_path.exists():
                delegation_path.rmdir()
        except OSError as exc:
            errors.append(f"{delegation_path}: {exc}")
        if errors:
            raise RuntimeError("lease release incomplete: " + "; ".join(errors))

    def status(self) -> tuple[LeaseRecord, ...]:
        if not self.host_runtime.exists() and not self.project_runtime.exists():
            return ()
        with self._bundle_mutex():
            return self._status_locked()

    def _status_locked(self) -> tuple[LeaseRecord, ...]:
        records: dict[str, LeaseRecord] = {}
        registry_root = self.host_runtime / "leases"
        if registry_root.is_dir():
            for record_path in registry_root.glob("*.json"):
                try:
                    record = self._read_record(record_path)
                except (OSError, ValueError):
                    continue
                if not self._record_is_live(record):
                    self._remove_stale_registry(record_path, record)
                    continue
                records[record.lease_id] = record
        for runtime in {self.host_runtime, self.project_runtime}:
            lock_root = runtime / "locks"
            if not lock_root.is_dir():
                continue
            for record_path in lock_root.glob("*/lease.json"):
                record = self._recover_or_read(record_path.parent)
                if record is None:
                    continue
                records[record.lease_id] = record
        return tuple(records[key] for key in sorted(records))

    def _record_is_live(self, record: LeaseRecord) -> bool:
        if self._wall_clock() <= record.expires_at:
            return True
        observed = self._process_probe(record.pid)
        return (
            observed == record.process_creation
            or _probe_is_unknown(observed)
            or _probe_is_unknown(record.process_creation)
        )

    def _remove_stale_registry(self, path: Path, expected: LeaseRecord) -> None:
        try:
            current = self._read_record(path)
            self._verify_same_lease(current, expected)
            path.unlink()
        except (FileNotFoundError, OSError, ValueError, PermissionError):
            return

    def load_lease(
        self, lease_id: str, *, delegation_secret: str | None = None
    ) -> ResourceLease:
        if not lease_id or any(character not in "0123456789abcdef-" for character in lease_id):
            raise ValueError("lease ID is invalid")
        registry = self.host_runtime / "leases" / f"{lease_id}.json"
        record = self._read_record(registry)
        if delegation_secret is not None and not _secret_matches(
            delegation_secret, record.delegation_sha256
        ):
            raise PermissionError("delegation secret does not match the parent lease")
        paths = tuple(self._path_for_claim(claim) for claim in record.claims)
        return ResourceLease(record, paths, registry, delegation_secret)

    def bind_windows_gated_delegate(
        self,
        lease_id: str,
        *,
        delegation_secret: str,
        delegate_pid: int,
    ) -> None:
        """Bind the real target launched by the trusted Windows Job bootstrap."""
        if os.name != "nt":
            raise PermissionError("gated delegation binding is Windows-only")
        parent = self.load_lease(
            lease_id, delegation_secret=delegation_secret
        ).record
        observed_parent = self._process_probe(parent.pid)
        if (
            _probe_is_unknown(parent.process_creation)
            or _probe_is_unknown(observed_parent)
            or observed_parent != parent.process_creation
        ):
            raise PermissionError("parent lease process is unavailable or its PID was reused")
        if self._wall_clock() > parent.expires_at:
            raise PermissionError("parent lease is expired")
        if self._parent_pid_provider() != parent.pid:
            raise PermissionError("gated bootstrap is not the direct child of the lease owner")
        delegate_creation = self._process_probe(delegate_pid)
        if _probe_is_unknown(delegate_creation):
            raise PermissionError(
                "gated delegation requires a reliable target process creation identity"
            )
        self._bind_or_verify_delegate(
            parent,
            identity=ProcessIdentity(delegate_pid, delegate_creation),
        )

    def lease_covers(self, lease: ResourceLease, request: ResourceRequest) -> bool:
        """Return whether a live inherited lease already owns every requested claim."""
        self._validate_request(request)
        self._verify_parent_request(request, expected=lease.record)
        required = set(self._claims_for(request))
        return required.issubset(lease.record.claims)

    def _try_acquire(self, request: ResourceRequest, lease_ttl: float) -> ResourceLease:
        with self._bundle_mutex():
            return self._try_acquire_locked(request, lease_ttl)

    def _try_acquire_locked(
        self, request: ResourceRequest, lease_ttl: float
    ) -> ResourceLease:
        self._verify_parent_request(request)
        claims = self._claims_for(request)
        lease_id = str(uuid.uuid4())
        nonce = uuid.uuid4().hex
        issued_secret = None if request.descendant else uuid.uuid4().hex + uuid.uuid4().hex
        delegation_sha256 = hashlib.sha256(
            (issued_secret or uuid.uuid4().hex).encode("ascii")
        ).hexdigest()
        now = self._wall_clock()
        record = LeaseRecord(
            schema_version=LEASE_SCHEMA_VERSION,
            lease_id=lease_id,
            resource_class=request.resource_class.value,
            host_identity=request.host_identity,
            project_identity=request.project_identity,
            worktree_identity=request.worktree_identity,
            run_id=request.run_id,
            controller=request.controller,
            owner=request.controller,
            pid=self.process_identity.pid,
            process_creation=self.process_identity.creation,
            nonce=nonce,
            delegation_sha256=delegation_sha256,
            acquired_at=now,
            heartbeat_at=now,
            expires_at=now + lease_ttl,
            command_stage=request.stage,
            authority_digest=request.authority_digest,
            permission_mode=request.permission_mode,
            allowed_classes=tuple(
                sorted(
                    item.value
                    for item in (
                        request.allowed_classes
                        if request.allowed_classes is not None
                        else (request.resource_class,)
                    )
                )
            ),
            exclusive_resources=tuple(sorted(set(request.exclusive_resources))),
            claims=claims,
            parent_lease_id=request.parent_lease_id,
            descendant=request.descendant,
        )
        acquired: list[Path] = []
        try:
            for claim in claims:
                path = self._path_for_claim(claim)
                path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    path.mkdir()
                except FileExistsError:
                    blocking = self._recover_or_read(path)
                    if blocking is not None:
                        raise ResourceBusy(
                            f"resource claim is occupied: {claim}",
                            blocking_lease=blocking,
                        )
                    path.mkdir()
                acquired.append(path)
                self._atomic_write(path / "lease.json", record.to_dict())
            registry = self.host_runtime / "leases" / f"{lease_id}.json"
            registry.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write(registry, record.to_dict())
            return ResourceLease(
                record, tuple(acquired), registry, issued_secret
            )
        except BaseException:
            for path in reversed(acquired):
                self._remove_owned_claim(path, lease_id, nonce)
            raise

    @contextmanager
    def _bundle_mutex(self):
        path = self.host_runtime / "acquisition.lock"
        owner_path = path / "owner.json"
        deadline = time.monotonic() + 10.0
        token = uuid.uuid4().hex
        owner = {
            "schema_version": 1,
            "pid": self.process_identity.pid,
            "process_creation": self.process_identity.creation,
            "token": token,
            "expires_at": self._wall_clock() + 15.0,
        }
        while True:
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                path.mkdir()
                self._atomic_write(owner_path, owner)
                break
            except FileExistsError:
                if self._recover_bundle_mutex(path, owner_path):
                    continue
                if time.monotonic() >= deadline:
                    raise ResourceBusy(
                        "resource acquisition transaction is occupied",
                        state="HANDOFF_READY",
                    )
                time.sleep(0.25)
            except BaseException:
                try:
                    if path.is_dir() and not any(path.iterdir()):
                        path.rmdir()
                except OSError:
                    pass
                raise
        try:
            yield
        finally:
            try:
                current = json.loads(owner_path.read_text(encoding="utf-8"))
                if current.get("token") != token:
                    raise PermissionError("resource acquisition mutex token differs")
                owner_path.unlink()
                path.rmdir()
            except FileNotFoundError:
                pass

    def _recover_bundle_mutex(self, path: Path, owner_path: Path) -> bool:
        try:
            owner = json.loads(owner_path.read_text(encoding="utf-8"))
            pid = owner.get("pid")
            creation = owner.get("process_creation")
            expires = owner.get("expires_at")
            if (
                type(pid) is not int
                or not isinstance(creation, str)
                or type(expires) not in {int, float}
            ):
                raise ValueError("invalid acquisition mutex record")
            if self._wall_clock() <= float(expires):
                return False
            observed = self._process_probe(pid)
            if (
                observed == creation
                or _probe_is_unknown(observed)
                or _probe_is_unknown(creation)
            ):
                return False
        except (OSError, ValueError, json.JSONDecodeError):
            try:
                if self._wall_clock() - path.stat().st_mtime <= 30.0:
                    return False
            except OSError:
                return True
        self._quarantine_stale_claim(path)
        return True

    def _claims_for(self, request: ResourceRequest) -> tuple[str, ...]:
        resource_class = request.resource_class
        claims: set[str] = set()
        if resource_class is ResourceClass.REASONING_ONLY:
            claims.add(f"host:reasoning:{request.run_id}:{self.process_identity.pid}")
        elif resource_class is ResourceClass.REPO_READ:
            pass
        elif resource_class is ResourceClass.REPO_WRITE:
            claims.add(f"project:worktree-writer:{request.worktree_identity}")
        elif resource_class is ResourceClass.CPU_HEAVY:
            claims.add("host:cpu-heavy")
        elif resource_class is ResourceClass.IO_HEAVY:
            claims.add("host:io-heavy")
        elif resource_class is ResourceClass.PACKAGE_BUILD:
            claims.update({"host:cpu-heavy", "host:package-build", "project:package-build"})
        elif resource_class is ResourceClass.RUNTIME_EXCLUSIVE:
            if not request.exclusive_resources:
                claims.add("project:runtime:default")
        elif resource_class is ResourceClass.SUBMIT_EXCLUSIVE:
            claims.update(
                {
                    f"project:worktree-writer:{request.worktree_identity}",
                    "project:git-index-mutation",
                    "project:submit-exclusive",
                }
            )
        for value in request.exclusive_resources:
            normalized = self._exclusive_name(value)
            scope = "host" if normalized.split(":", 1)[0] in {"port", "browser", "service"} else "project"
            claims.add(f"{scope}:runtime:{normalized}")
        return tuple(sorted(claims))

    def _path_for_claim(self, claim: str) -> Path:
        scope, _, label = claim.partition(":")
        root = self.host_runtime if scope == "host" else self.project_runtime
        slug = re.sub(r"[^a-z0-9.-]+", "-", label.casefold()).strip("-")[:40] or "claim"
        digest = hashlib.sha256(claim.encode("utf-8")).hexdigest()[:24]
        return root / "locks" / f"{slug}-{digest}"

    def _recover_or_read(self, claim_path: Path) -> LeaseRecord | None:
        record_path = claim_path / "lease.json"
        try:
            record = self._read_record(record_path)
        except (OSError, ValueError):
            try:
                age = self._wall_clock() - claim_path.stat().st_mtime
            except OSError:
                return None
            if age <= DEFAULT_LEASE_TTL * 2:
                return LeaseRecord(
                    LEASE_SCHEMA_VERSION,
                    "unknown-corrupt-lease",
                    "unknown",
                    "0" * 64,
                    "unknown",
                    "unknown",
                    "unknown",
                    "unknown",
                    "unknown",
                    "unknown",
                    1,
                    "unknown",
                    "unknown",
                    0.0,
                    0.0,
                    self._wall_clock() + 1,
                    "unknown",
                    "0" * 64,
                    "READ_ONLY_REVIEW",
                    (ResourceClass.REASONING_ONLY.value,),
                    (),
                    ("unknown",),
                    None,
                    False,
                )
            self._quarantine_stale_claim(claim_path)
            return None
        if self._wall_clock() <= record.expires_at:
            return record
        observed = self._process_probe(record.pid)
        if (
            observed == record.process_creation
            or _probe_is_unknown(observed)
            or _probe_is_unknown(record.process_creation)
        ):
            return record
        self._quarantine_stale_claim(claim_path)
        return None

    def _quarantine_stale_claim(self, claim_path: Path) -> None:
        quarantine = claim_path.with_name(f"{claim_path.name}.stale-{uuid.uuid4().hex}")
        try:
            os.replace(claim_path, quarantine)
        except FileNotFoundError:
            return
        shutil.rmtree(quarantine)

    def _remove_owned_claim(self, path: Path, lease_id: str, nonce: str) -> None:
        try:
            record_path = path / "lease.json"
            if record_path.exists():
                record = self._read_record(record_path)
                if record.lease_id != lease_id or record.nonce != nonce:
                    return
                record_path.unlink()
            path.rmdir()
        except (FileNotFoundError, OSError, ValueError):
            return

    def _validate_request(self, request: ResourceRequest) -> None:
        if not isinstance(request.resource_class, ResourceClass):
            raise ValueError("resource class is invalid")
        for label, value in (
            ("run ID", request.run_id),
            ("controller", request.controller),
            ("stage", request.stage),
            ("host identity", request.host_identity),
            ("project identity", request.project_identity),
            ("worktree identity", request.worktree_identity),
            ("permission mode", request.permission_mode),
        ):
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise ValueError(f"{label} is invalid")
        if not _DIGEST_RE.fullmatch(request.authority_digest):
            raise ValueError("authority digest must be a lowercase SHA-256")
        if request.allowed_classes is not None and request.resource_class not in request.allowed_classes:
            raise PermissionError(
                f"resource class {request.resource_class.value} is not allowed by parent authority"
            )
        if request.parent_lease_id is None and request.descendant:
            raise PermissionError("descendant request is missing its parent lease")
        if request.parent_lease_id is not None and not request.descendant:
            raise PermissionError("parent lease requires a descendant request")
        if request.parent_lease_id is None and request.delegation_secret is not None:
            raise PermissionError("top-level request cannot carry a delegation secret")
        if request.parent_lease_id is not None and not request.delegation_secret:
            raise PermissionError("descendant request is missing its delegation secret")
        for value in request.exclusive_resources:
            self._exclusive_name(value)

    def _verify_parent_request(
        self,
        request: ResourceRequest,
        *,
        expected: LeaseRecord | None = None,
    ) -> None:
        if request.parent_lease_id is None:
            return
        parent = self.load_lease(
            request.parent_lease_id,
            delegation_secret=request.delegation_secret,
        ).record
        if expected is not None:
            self._verify_same_lease(parent, expected)
        observed = self._process_probe(parent.pid)
        if _probe_is_unknown(parent.process_creation) or _probe_is_unknown(observed):
            raise PermissionError(
                "delegation requires a reliable parent process creation identity"
            )
        if observed != parent.process_creation:
            raise PermissionError("parent lease process is unavailable or its PID was reused")
        if self._wall_clock() > parent.expires_at:
            raise PermissionError("parent lease is expired")
        if self._parent_pid_provider() != parent.pid and not (
            os.name == "nt" and self._wait_for_prebound_windows_delegate(parent)
        ):
            raise PermissionError("delegation is not being used by the direct child process")
        self._bind_or_verify_delegate(parent)
        for actual, inherited, label in (
            (request.authority_digest, parent.authority_digest, "authority digest"),
            (request.host_identity, parent.host_identity, "host identity"),
            (request.project_identity, parent.project_identity, "project identity"),
            (request.worktree_identity, parent.worktree_identity, "worktree identity"),
            (request.controller, parent.controller, "controller"),
        ):
            if actual != inherited:
                raise PermissionError(f"descendant {label} differs from parent lease")
        if _permission_rank(request.permission_mode) > _permission_rank(
            parent.permission_mode
        ):
            raise PermissionError("descendant permission mode exceeds parent lease")
        child_allowed = {
            item.value
            for item in (
                request.allowed_classes
                if request.allowed_classes is not None
                else (request.resource_class,)
            )
        }
        if not child_allowed.issubset(parent.allowed_classes):
            raise PermissionError("descendant resource classes exceed parent lease")
        required_claims = set(self._claims_for(request))
        inherited_claims = set(parent.claims)
        overlap = required_claims & inherited_claims
        if overlap and not required_claims.issubset(inherited_claims):
            raise PermissionError(
                "descendant claims partially overlap the parent lease; "
                "the root controller must acquire the complete claim set"
            )

    def _delegation_binding_path(self, lease_id: str) -> Path:
        return self.host_runtime / "delegations" / lease_id

    def _wait_for_prebound_windows_delegate(self, parent: LeaseRecord) -> bool:
        expected = self._delegation_binding_payload(parent, self.process_identity)
        path = self._delegation_binding_path(parent.lease_id) / "binding.json"
        deadline = self._monotonic_clock() + 2.0
        while True:
            try:
                observed = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                observed = None
            except OSError:
                return False
            if observed == expected:
                return True
            if observed is not None or self._monotonic_clock() >= deadline:
                return False
            self._sleep(min(0.05, deadline - self._monotonic_clock()))

    @staticmethod
    def _delegation_binding_payload(
        parent: LeaseRecord, identity: ProcessIdentity
    ) -> dict[str, object]:
        return {
            "schema_version": 1,
            "parent_lease_id": parent.lease_id,
            "parent_nonce": parent.nonce,
            "delegate_pid": identity.pid,
            "delegate_process_creation": identity.creation,
        }

    def _bind_or_verify_delegate(
        self,
        parent: LeaseRecord,
        *,
        identity: ProcessIdentity | None = None,
    ) -> None:
        selected = self.process_identity if identity is None else identity
        if _probe_is_unknown(selected.creation):
            raise PermissionError(
                "delegation requires a reliable child process creation identity"
            )
        directory = self._delegation_binding_path(parent.lease_id)
        path = directory / "binding.json"
        expected = self._delegation_binding_payload(parent, selected)
        try:
            directory.parent.mkdir(parents=True, exist_ok=True)
            directory.mkdir()
        except FileExistsError:
            try:
                observed = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PermissionError("delegation binding is incomplete or unreadable") from exc
            if observed != expected:
                raise PermissionError(
                    "delegation capability is already bound to another child process"
                )
            return
        try:
            self._atomic_write(path, expected)
        except BaseException:
            try:
                if path.exists():
                    path.unlink()
                directory.rmdir()
            except OSError:
                pass
            raise

    @staticmethod
    def _exclusive_name(value: str) -> str:
        if (
            not isinstance(value, str)
            or not value.strip()
            or value != value.strip()
            or len(value) > 200
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*", value)
            or ".." in value
        ):
            raise ValueError(f"exclusive resource name is invalid: {value!r}")
        return value.casefold()

    def _verify_owner(self, record: LeaseRecord) -> None:
        if (
            record.pid != self.process_identity.pid
            or record.process_creation != self.process_identity.creation
        ):
            raise PermissionError("lease owner process identity does not match")

    @staticmethod
    def _verify_same_lease(current: LeaseRecord, expected: LeaseRecord) -> None:
        if current.lease_id != expected.lease_id or current.nonce != expected.nonce:
            raise PermissionError("lease ID or nonce does not match the owned lease")

    @staticmethod
    def _read_record(path: Path) -> LeaseRecord:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return LeaseRecord.from_dict(payload)

    @staticmethod
    def _atomic_write(path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
        except BaseException:
            try:
                os.unlink(name)
            except OSError:
                pass
            raise


__all__ = [
    "DEFAULT_LEASE_TTL",
    "DEFAULT_MAX_WAIT",
    "LEASE_SCHEMA_VERSION",
    "ProcessIdentity",
    "RESOURCE_PROFILE_ID",
    "ResourceBusy",
    "ResourceClass",
    "ResourceLease",
    "ResourceManager",
    "ResourceRequest",
    "current_process_identity",
    "default_host_identity",
    "host_runtime_path",
    "probe_process_creation",
    "project_runtime_path",
]
