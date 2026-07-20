"""Bounded, observable execution of one owned process tree.

The supervisor never invokes a shell. POSIX children run in a dedicated process
group; Windows children are attached to a kill-on-close Job Object and started
below normal priority. Output readers keep both pipes drained while retaining a
fixed-size tail.
"""

from __future__ import annotations

import ctypes
import base64
import json
import os
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping, Sequence

try:
    import resource as _resource
except ImportError:  # Windows
    _resource = None


DEFAULT_THREAD_LIMITS = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "RAYON_NUM_THREADS": "1",
    "CARGO_BUILD_JOBS": "1",
}


class ProcessClassification(str, Enum):
    SUCCESS = "success"
    NONZERO = "nonzero"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"
    CAPABILITY = "capability"
    INTERNAL = "internal"


class ContainmentLevel(str, Enum):
    SOFT = "SOFT"
    MANAGED = "MANAGED"
    HARD = "HARD"


@dataclass(frozen=True)
class ProcessHeartbeat:
    stage: str
    run_id: str
    lease_id: str | None
    elapsed: float
    owned_processes: int
    current_test: str | None = None


@dataclass(frozen=True)
class ProcessResult:
    stage: str
    run_id: str
    lease_id: str | None
    command: tuple[str, ...]
    cwd: str
    environment_hints: Mapping[str, str]
    classification: ProcessClassification
    exit_code: int | None
    termination_reason: str
    elapsed: float
    stdout_tail: str
    stderr_tail: str
    stdout_tail_bytes: bytes
    stderr_tail_bytes: bytes
    stdout_bytes: int
    stderr_bytes: int
    stdout_dropped_bytes: int
    stderr_dropped_bytes: int
    peak_owned_processes: int | None
    child_cpu_seconds: float | None
    peak_rss_bytes: int | None
    temp_root: str | None
    heartbeat_count: int
    cleanup_complete: bool
    containment_complete: bool
    sampling_degraded: bool
    cleanup_error: str | None
    termination_escalated: bool
    orphan_count: int | None
    containment_level: str = ContainmentLevel.SOFT.value
    orphan_check: str = "not-performed"
    platform_adapter: str = "unavailable"
    limitations: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.classification is ProcessClassification.SUCCESS and self.cleanup_complete

    @property
    def stdout(self) -> bytes:
        return self.stdout_tail_bytes

    @property
    def stderr(self) -> bytes:
        return self.stderr_tail_bytes


class _TailBuffer:
    def __init__(self, limit: int) -> None:
        if limit <= 0:
            raise ValueError("output limit must be positive")
        self.limit = limit
        self._data = bytearray()
        self._total = 0
        self._lock = threading.Lock()

    def append(self, data: bytes) -> None:
        if not data:
            return
        with self._lock:
            self._total += len(data)
            self._data.extend(data)
            if len(self._data) > self.limit:
                del self._data[: len(self._data) - self.limit]

    @property
    def value(self) -> bytes:
        with self._lock:
            return bytes(self._data)

    @property
    def total(self) -> int:
        with self._lock:
            return self._total

    @property
    def dropped(self) -> int:
        return max(0, self.total - len(self.value))


@dataclass(frozen=True)
class _Cleanup:
    complete: bool
    escalated: bool
    orphan_count: int | None
    error: str | None = None
    containment_complete: bool = False


class _Backend:
    containment_level = ContainmentLevel.SOFT
    platform_adapter = "unavailable"
    limitations: tuple[str, ...] = ()

    def popen_kwargs(self) -> dict[str, object]:
        raise NotImplementedError

    def attach(self, process: subprocess.Popen[bytes]) -> None:
        raise NotImplementedError

    def sample(self, process: subprocess.Popen[bytes]) -> tuple[int, float | None, int | None]:
        raise NotImplementedError

    def cleanup(self, process: subprocess.Popen[bytes], grace: float) -> _Cleanup:
        raise NotImplementedError

    def close(self) -> None:
        return


class _PosixBackend(_Backend):
    containment_level = ContainmentLevel.MANAGED
    platform_adapter = "posix-session-process-group-v1"
    limitations = (
        "process-group cleanup cannot prove absence of descendants that deliberately call setsid",
        "cgroup and stronger macOS sandbox adapters are optional future HARD adapters",
    )

    def __init__(self) -> None:
        self.pgid: int | None = None
        _enable_linux_subreaper()

    def popen_kwargs(self) -> dict[str, object]:
        return {"start_new_session": True}

    def attach(self, process: subprocess.Popen[bytes]) -> None:
        self.pgid = process.pid
        if hasattr(os, "setpriority"):
            try:
                os.setpriority(os.PRIO_PROCESS, process.pid, 10)
            except (OSError, PermissionError):
                pass

    def sample(self, process: subprocess.Popen[bytes]) -> tuple[int, float | None, int | None]:
        count = _posix_group_count(self.pgid)
        return max(1 if process.poll() is None else 0, count), None, None

    def cleanup(self, process: subprocess.Popen[bytes], grace: float) -> _Cleanup:
        if self.pgid is None:
            return _Cleanup(
                process.poll() is not None,
                False,
                None,
                "process group was not attached; descendant containment is unknown",
            )
        errors: list[str] = []
        escalated = False
        if _group_exists(self.pgid):
            try:
                os.killpg(self.pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError as exc:
                errors.append(f"SIGTERM failed: {exc}")
            if not _wait_group(self.pgid, process, grace):
                escalated = True
                try:
                    os.killpg(self.pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    errors.append(f"SIGKILL failed: {exc}")
                _wait_group(self.pgid, process, max(0.5, grace))
        _reap_group(self.pgid)
        try:
            process.wait(timeout=max(0.25, grace))
        except subprocess.TimeoutExpired:
            errors.append("direct child was not reaped")
        _reap_group(self.pgid)
        remaining = _posix_group_count(self.pgid)
        if remaining:
            errors.append(f"owned process group still has {remaining} process(es)")
        return _Cleanup(
            not remaining and process.poll() is not None,
            escalated,
            0 if not remaining else remaining,
            "; ".join(errors) or None,
            False,
        )


class _WindowsJob:
    _KILL_ON_JOB_CLOSE = 0x00002000
    _BASIC_ACCOUNTING = 1
    _EXTENDED_LIMITS = 9

    def __init__(self) -> None:
        from ctypes import wintypes

        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class BASIC_LIMITS(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class EXTENDED_LIMITS(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMITS),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class BASIC_ACCOUNTING(ctypes.Structure):
            _fields_ = [
                ("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD),
                ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD),
                ("TotalTerminatedProcesses", wintypes.DWORD),
            ]

        self.EXTENDED_LIMITS = EXTENDED_LIMITS
        self.BASIC_ACCOUNTING = BASIC_ACCOUNTING
        self.kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.kernel32.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
        self.kernel32.QueryInformationJobObject.restype = wintypes.BOOL
        self.kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel32.TerminateJobObject.restype = wintypes.BOOL
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel32.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = EXTENDED_LIMITS()
        limits.BasicLimitInformation.LimitFlags = self._KILL_ON_JOB_CLOSE
        if not self.kernel32.SetInformationJobObject(
            self.handle,
            self._EXTENDED_LIMITS,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process: subprocess.Popen[bytes]) -> None:
        from ctypes import wintypes

        handle = wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
        if not self.kernel32.AssignProcessToJobObject(self.handle, handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def sample(self) -> tuple[int, int, float, int]:
        accounting = self.BASIC_ACCOUNTING()
        extended = self.EXTENDED_LIMITS()
        if not self.kernel32.QueryInformationJobObject(
            self.handle,
            self._BASIC_ACCOUNTING,
            ctypes.byref(accounting),
            ctypes.sizeof(accounting),
            None,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.kernel32.QueryInformationJobObject(
            self.handle,
            self._EXTENDED_LIMITS,
            ctypes.byref(extended),
            ctypes.sizeof(extended),
            None,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        cpu = (int(accounting.TotalUserTime) + int(accounting.TotalKernelTime)) / 10_000_000.0
        return (
            int(accounting.ActiveProcesses),
            int(accounting.TotalProcesses),
            cpu,
            int(extended.PeakJobMemoryUsed),
        )

    def terminate(self) -> None:
        if not self.kernel32.TerminateJobObject(self.handle, 1):
            error = ctypes.get_last_error()
            if error:
                raise ctypes.WinError(error)

    def close(self) -> None:
        if getattr(self, "handle", None):
            self.kernel32.CloseHandle(self.handle)
            self.handle = None


class _WindowsBackend(_Backend):
    containment_level = ContainmentLevel.HARD
    platform_adapter = "windows-job-object-gated-v1"
    limitations = (
        "HARD applies only to the trusted gated launcher and target tree after successful Job binding",
        "commands that bypass resource run remain outside this containment boundary",
    )

    def __init__(self) -> None:
        self.job = _WindowsJob()

    def popen_kwargs(self) -> dict[str, object]:
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.BELOW_NORMAL_PRIORITY_CLASS
        return {"creationflags": flags}

    def attach(self, process: subprocess.Popen[bytes]) -> None:
        self.job.assign(process)

    def sample(self, process: subprocess.Popen[bytes]) -> tuple[int, float | None, int | None]:
        active, _, cpu, rss = self.job.sample()
        return active, cpu, rss

    def cleanup(self, process: subprocess.Popen[bytes], grace: float) -> _Cleanup:
        errors: list[str] = []
        try:
            active, _, _, _ = self.job.sample()
        except OSError as exc:
            active = 1 if process.poll() is None else 0
            errors.append(f"Job Object query failed: {exc}")
        if active:
            try:
                self.job.terminate()
            except OSError as exc:
                errors.append(f"Job Object termination failed: {exc}")
        deadline = time.monotonic() + max(0.5, grace)
        while time.monotonic() < deadline:
            try:
                active, _, _, _ = self.job.sample()
            except OSError:
                break
            if not active:
                break
            time.sleep(0.01)
        try:
            process.wait(timeout=max(0.25, grace))
        except subprocess.TimeoutExpired:
            errors.append("direct child was not reaped")
        if active:
            errors.append(f"Job Object still has {active} active process(es)")
        return _Cleanup(
            not active and process.poll() is not None,
            bool(active),
            0 if not active else active,
            "; ".join(errors) or None,
            not active and process.poll() is not None,
        )

    def close(self) -> None:
        self.job.close()


def run_process(
    *,
    stage: str,
    command: Sequence[str],
    cwd: Path,
    timeout: float,
    run_id: str,
    lease_id: str | None = None,
    environment: Mapping[str, str | None] | None = None,
    max_output_bytes: int = 65_536,
    heartbeat_interval: float = 10.0,
    termination_grace: float = 1.0,
    max_owned_processes: int = 32,
    required_containment: str = ContainmentLevel.MANAGED.value,
    temp_root: Path | None = None,
    on_heartbeat: Callable[[ProcessHeartbeat], None] | None = None,
) -> ProcessResult:
    argv = _validate_command(command)
    if not stage.strip() or not run_id.strip():
        raise ValueError("stage and run ID are required")
    if timeout <= 0 or heartbeat_interval <= 0 or termination_grace < 0:
        raise ValueError("timeout/heartbeat must be positive and grace non-negative")
    if type(max_owned_processes) is not int or not 2 <= max_owned_processes <= 256:
        raise ValueError("max_owned_processes must be between 2 and 256")
    canonical_cwd = Path(os.path.realpath(os.path.abspath(os.fspath(cwd))))
    if not canonical_cwd.is_dir():
        raise NotADirectoryError(str(canonical_cwd))
    if temp_root is not None:
        temp_root = Path(os.path.realpath(os.path.abspath(os.fspath(temp_root))))
    child_environment = _child_environment(environment)
    stdout = _TailBuffer(max_output_bytes)
    stderr = _TailBuffer(max_output_bytes)
    started = time.monotonic()
    usage_before = _child_usage()
    backend: _Backend
    try:
        backend = _WindowsBackend() if os.name == "nt" else _PosixBackend()
    except OSError as exc:
        return _capability_result(stage, run_id, lease_id, argv, canonical_cwd, temp_root, started, exc)
    try:
        required_level = ContainmentLevel(required_containment.upper())
    except (AttributeError, ValueError) as exc:
        backend.close()
        raise ValueError("required_containment must be SOFT, MANAGED, or HARD") from exc
    if _containment_rank(backend.containment_level) < _containment_rank(required_level):
        result = _capability_result(
            stage,
            run_id,
            lease_id,
            argv,
            canonical_cwd,
            temp_root,
            started,
            RuntimeError(
                f"required containment {required_level.value} exceeds "
                f"platform capability {backend.containment_level.value}"
            ),
            backend=backend,
        )
        backend.close()
        return result
    process: subprocess.Popen[bytes] | None = None
    readers: list[threading.Thread] = []
    classification = ProcessClassification.INTERNAL
    reason = "internal failure"
    exit_code: int | None = None
    heartbeat_count = 0
    peak_owned = 0
    owned = 0
    cpu_seconds: float | None = None
    peak_rss: int | None = None
    cleanup = _Cleanup(True, False, 0, containment_complete=True)
    sampling_degraded = False
    attach_failed = False
    interrupted = threading.Event()
    try:
        try:
            launch_argv = _windows_gated_argv(argv) if os.name == "nt" else argv
            process = subprocess.Popen(
                list(launch_argv),
                cwd=canonical_cwd,
                env=child_environment,
                stdin=subprocess.PIPE if os.name == "nt" else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                **backend.popen_kwargs(),
            )
        except (OSError, ValueError) as exc:
            return _capability_result(
                stage,
                run_id,
                lease_id,
                argv,
                canonical_cwd,
                temp_root,
                started,
                exc,
                backend=backend,
            )
        try:
            backend.attach(process)
        except (OSError, ValueError) as exc:
            attach_failed = True
            classification = ProcessClassification.CAPABILITY
            reason = f"gated-containment-bind:{type(exc).__name__}:{exc}"
            if process.poll() is None:
                process.kill()
                process.wait(timeout=max(0.25, termination_grace))
        if not attach_failed and os.name == "nt":
            try:
                assert process.stdin is not None
                process.stdin.write(b"GO\n")
                process.stdin.flush()
                process.stdin.close()
            except (OSError, ValueError) as exc:
                attach_failed = True
                classification = ProcessClassification.CAPABILITY
                reason = f"gated-launch-release:{type(exc).__name__}:{exc}"
        if not attach_failed:
            assert process.stdout is not None and process.stderr is not None
            readers = [
                threading.Thread(
                    target=_drain, args=(process.stdout, stdout), daemon=True
                ),
                threading.Thread(
                    target=_drain, args=(process.stderr, stderr), daemon=True
                ),
            ]
            for reader in readers:
                reader.start()
            deadline = started + timeout
            next_heartbeat = started
            next_sample = started
            sample_interval = max(1.0, min(heartbeat_interval, 10.0))
            with _scoped_interruption_handlers(interrupted):
                while True:
                    now = time.monotonic()
                    if now >= next_sample:
                        try:
                            owned, sampled_cpu, sampled_rss = backend.sample(process)
                            peak_owned = max(peak_owned, owned)
                            if sampled_cpu is not None:
                                cpu_seconds = sampled_cpu
                            if sampled_rss is not None:
                                peak_rss = max(peak_rss or 0, sampled_rss)
                        except OSError:
                            sampling_degraded = True
                            owned = 1 if process.poll() is None else 0
                            peak_owned = max(peak_owned, owned)
                        next_sample = now + sample_interval
                        if owned > max_owned_processes:
                            classification = ProcessClassification.CAPABILITY
                            reason = (
                                "owned-process-limit-exceeded:"
                                f"{owned}>{max_owned_processes}"
                            )
                            break
                    if now >= next_heartbeat:
                        heartbeat_count += 1
                        if on_heartbeat is not None:
                            on_heartbeat(
                                ProcessHeartbeat(
                                    stage,
                                    run_id,
                                    lease_id,
                                    now - started,
                                    owned,
                                )
                            )
                        next_heartbeat = now + heartbeat_interval
                    exit_code = process.poll()
                    if exit_code is not None:
                        classification = (
                            ProcessClassification.SUCCESS
                            if exit_code == 0
                            else ProcessClassification.NONZERO
                        )
                        reason = "exited" if exit_code == 0 else "nonzero-exit"
                        break
                    if interrupted.is_set():
                        classification = ProcessClassification.INTERRUPTED
                        reason = "interrupted-by-signal"
                        break
                    if now >= deadline:
                        classification = ProcessClassification.TIMEOUT
                        reason = "timeout"
                        break
                    time.sleep(
                        min(
                            0.05,
                            max(0.0, deadline - now),
                            max(0.0, next_heartbeat - now),
                        )
                    )
    except KeyboardInterrupt:
        classification = ProcessClassification.INTERRUPTED
        reason = "interrupted"
    except BaseException as exc:
        classification = ProcessClassification.INTERNAL
        reason = f"internal:{type(exc).__name__}:{exc}"
    finally:
        if process is not None:
            backend_cleanup = backend.cleanup(process, termination_grace)
            cleanup = (
                _Cleanup(
                    process.poll() is not None,
                    backend_cleanup.escalated,
                    None,
                    "gated containment failed before the target argv was released",
                    False,
                )
                if attach_failed
                else backend_cleanup
            )
            exit_code = process.poll()
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            for reader in readers:
                reader.join(timeout=1.0)
        backend.close()
    elapsed = time.monotonic() - started
    usage_after = _child_usage()
    if cpu_seconds is None and usage_before is not None and usage_after is not None:
        cpu_seconds = max(0.0, usage_after[0] - usage_before[0])
    if peak_rss is None and usage_after is not None:
        peak_rss = usage_after[1]
    return ProcessResult(
        stage=stage,
        run_id=run_id,
        lease_id=lease_id,
        command=argv,
        cwd=str(canonical_cwd),
        environment_hints=dict(DEFAULT_THREAD_LIMITS),
        classification=classification,
        exit_code=exit_code,
        termination_reason=reason,
        elapsed=elapsed,
        stdout_tail=stdout.value.decode("utf-8", errors="replace"),
        stderr_tail=stderr.value.decode("utf-8", errors="replace"),
        stdout_tail_bytes=stdout.value,
        stderr_tail_bytes=stderr.value,
        stdout_bytes=stdout.total,
        stderr_bytes=stderr.total,
        stdout_dropped_bytes=stdout.dropped,
        stderr_dropped_bytes=stderr.dropped,
        peak_owned_processes=peak_owned,
        child_cpu_seconds=cpu_seconds,
        peak_rss_bytes=peak_rss,
        temp_root=str(temp_root) if temp_root is not None else None,
        heartbeat_count=heartbeat_count,
        cleanup_complete=cleanup.complete,
        containment_complete=cleanup.containment_complete,
        sampling_degraded=sampling_degraded,
        cleanup_error=cleanup.error,
        termination_escalated=cleanup.escalated,
        orphan_count=cleanup.orphan_count,
        containment_level=backend.containment_level.value,
        orphan_check=(
            "job-active-processes-zero"
            if os.name == "nt" and cleanup.orphan_count == 0
            else "process-group-empty; deliberate setsid escape not observable"
            if os.name != "nt" and cleanup.orphan_count == 0
            else "incomplete"
        ),
        platform_adapter=backend.platform_adapter,
        limitations=backend.limitations,
    )


def _capability_result(
    stage: str,
    run_id: str,
    lease_id: str | None,
    command: tuple[str, ...],
    cwd: Path,
    temp_root: Path | None,
    started: float,
    error: BaseException,
    *,
    backend: _Backend | None = None,
) -> ProcessResult:
    return ProcessResult(
        stage=stage,
        run_id=run_id,
        lease_id=lease_id,
        command=command,
        cwd=str(cwd),
        environment_hints=dict(DEFAULT_THREAD_LIMITS),
        classification=ProcessClassification.CAPABILITY,
        exit_code=None,
        termination_reason=f"capability:{type(error).__name__}:{error}",
        elapsed=time.monotonic() - started,
        stdout_tail="",
        stderr_tail="",
        stdout_tail_bytes=b"",
        stderr_tail_bytes=b"",
        stdout_bytes=0,
        stderr_bytes=0,
        stdout_dropped_bytes=0,
        stderr_dropped_bytes=0,
        peak_owned_processes=0,
        child_cpu_seconds=None,
        peak_rss_bytes=None,
        temp_root=str(temp_root) if temp_root is not None else None,
        heartbeat_count=0,
        cleanup_complete=True,
        containment_complete=False,
        sampling_degraded=False,
        cleanup_error=None,
        termination_escalated=False,
        orphan_count=None,
        containment_level=(
            backend.containment_level.value if backend is not None else ContainmentLevel.SOFT.value
        ),
        orphan_check="target-not-started",
        platform_adapter=(backend.platform_adapter if backend is not None else "unavailable"),
        limitations=(
            backend.limitations
            if backend is not None
            else ("platform containment adapter could not be initialized",)
        ),
    )


def _containment_rank(level: ContainmentLevel) -> int:
    return {
        ContainmentLevel.SOFT: 0,
        ContainmentLevel.MANAGED: 1,
        ContainmentLevel.HARD: 2,
    }[level]


def _windows_gated_argv(command: tuple[str, ...]) -> tuple[str, ...]:
    payload = base64.urlsafe_b64encode(
        json.dumps(list(command), ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    return (
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        "--windows-gated-bootstrap",
        payload,
    )


def _windows_gated_bootstrap(encoded: str) -> int:
    """Wait for Job binding before starting the real target argv."""
    try:
        raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
        command = json.loads(raw.decode("utf-8"))
        argv = _validate_command(command)
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        return 126
    if sys.stdin.buffer.readline() != b"GO\n":
        return 125
    target_environment = dict(os.environ)
    host_runtime = target_environment.pop("SAGEKIT_DELEGATION_HOST_RUNTIME", None)
    project_runtime = target_environment.pop("SAGEKIT_DELEGATION_PROJECT_RUNTIME", None)
    lease_id = target_environment.get("SAGEKIT_LEASE_ID")
    delegation_secret = target_environment.get("SAGEKIT_DELEGATION_SECRET")
    try:
        child = subprocess.Popen(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            env=target_environment,
            shell=False,
        )
        if lease_id is not None:
            if not delegation_secret or not host_runtime or not project_runtime:
                child.terminate()
                child.wait()
                return 124
            try:
                package_root = str(Path(__file__).resolve().parents[1])
                if package_root not in sys.path:
                    sys.path.insert(0, package_root)
                from sagekit.resource_governor import ResourceManager

                ResourceManager(
                    host_runtime=Path(host_runtime),
                    project_runtime=Path(project_runtime),
                ).bind_windows_gated_delegate(
                    lease_id,
                    delegation_secret=delegation_secret,
                    delegate_pid=child.pid,
                )
            except (OSError, ValueError, PermissionError):
                child.terminate()
                child.wait()
                return 124
        return child.wait()
    except OSError:
        return 127


@contextmanager
def _scoped_interruption_handlers(interrupted: threading.Event):
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous: dict[int, object] = {}

    def mark_interrupted(signum, frame) -> None:
        del signum, frame
        interrupted.set()

    for name in ("SIGTERM", "SIGHUP"):
        selected = getattr(signal, name, None)
        if selected is None:
            continue
        try:
            previous[selected] = signal.getsignal(selected)
            signal.signal(selected, mark_interrupted)
        except (OSError, ValueError):
            continue
    try:
        yield
    finally:
        for selected, handler in previous.items():
            signal.signal(selected, handler)


def _validate_command(command: Sequence[str]) -> tuple[str, ...]:
    if isinstance(command, (str, bytes)):
        raise TypeError("command must be argv, not a shell string")
    argv = tuple(str(item) for item in command)
    if not argv or not argv[0] or any("\x00" in item for item in argv):
        raise ValueError("command argv is invalid")
    return argv


def _child_environment(overrides: Mapping[str, str | None] | None) -> dict[str, str]:
    environment = dict(os.environ)
    for key, value in (overrides or {}).items():
        selected = str(key)
        if value is None:
            environment.pop(selected, None)
        else:
            environment[selected] = str(value)
    environment.update(DEFAULT_THREAD_LIMITS)
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.autocrlf",
            "GIT_CONFIG_VALUE_0": "input",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_PAGER": "cat",
            "PAGER": "cat",
        }
    )
    return environment


def _drain(stream, tail: _TailBuffer) -> None:
    try:
        while True:
            data = stream.read(65_536)
            if not data:
                return
            tail.append(data)
    except (OSError, ValueError):
        return


def _enable_linux_subreaper() -> None:
    if not sys.platform.startswith("linux"):
        return
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl(36, 1, 0, 0, 0)
    except (AttributeError, OSError):
        return


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_group(pgid: int, process: subprocess.Popen[bytes], seconds: float) -> bool:
    deadline = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < deadline:
        process.poll()
        _reap_group(pgid)
        if not _group_exists(pgid):
            return True
        time.sleep(0.01)
    process.poll()
    _reap_group(pgid)
    return not _group_exists(pgid)


def _reap_group(pgid: int) -> None:
    if os.name == "nt":
        return
    while True:
        try:
            pid, _ = os.waitpid(-pgid, os.WNOHANG)
        except (ChildProcessError, OSError):
            return
        if pid == 0:
            return


def _posix_group_count(pgid: int | None) -> int:
    if pgid is None:
        return 0
    proc = Path("/proc")
    if not proc.is_dir():
        return 1 if _group_exists(pgid) else 0
    count = 0
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "stat").read_text(encoding="ascii", errors="strict")
            close = raw.rfind(")")
            fields = raw[close + 2 :].split()
            if int(fields[2]) == pgid:
                count += 1
        except (OSError, IndexError, ValueError):
            continue
    return count


def _child_usage() -> tuple[float, int] | None:
    if _resource is None:
        return None
    try:
        usage = _resource.getrusage(_resource.RUSAGE_CHILDREN)
    except (AttributeError, OSError):
        return None
    rss = int(usage.ru_maxrss)
    if sys.platform != "darwin":
        rss *= 1024
    return float(usage.ru_utime + usage.ru_stime), rss


__all__ = [
    "ContainmentLevel",
    "DEFAULT_THREAD_LIMITS",
    "ProcessClassification",
    "ProcessHeartbeat",
    "ProcessResult",
    "run_process",
]


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--windows-gated-bootstrap":
        raise SystemExit(_windows_gated_bootstrap(sys.argv[2]))
    raise SystemExit(2)
