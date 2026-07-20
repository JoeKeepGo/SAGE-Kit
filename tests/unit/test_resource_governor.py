from __future__ import annotations

import tempfile
import threading
import time
import unittest
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from sagekit.resource_governor import (
    ProcessIdentity,
    ResourceBusy,
    ResourceClass,
    ResourceManager,
    ResourceRequest,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 1_000.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.value

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


def request(
    resource_class: ResourceClass,
    *,
    run_id: str,
    exclusive: tuple[str, ...] = (),
    allowed: tuple[ResourceClass, ...] | None = None,
    worktree: str = "worktree-A",
) -> ResourceRequest:
    return ResourceRequest(
        resource_class=resource_class,
        run_id=run_id,
        controller="root-controller",
        stage="focused-test",
        authority_digest="a" * 64,
        host_identity="host-A",
        project_identity="project-A",
        worktree_identity=worktree,
        permission_mode="WRITE_AUTHORIZED",
        exclusive_resources=exclusive,
        allowed_classes=allowed,
    )


class ResourceGovernorTests(unittest.TestCase):
    def test_windows_gated_target_is_prebound_without_authorizing_grandchild(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            creations = {
                101: "parent-process",
                202: "bootstrap-process",
                303: "target-process",
                404: "grandchild-process",
            }
            parent_manager = ResourceManager(
                host_runtime=root / "host",
                project_runtime=root / "project",
                process_identity=ProcessIdentity(101, creations[101]),
                process_probe=creations.get,
                parent_pid_provider=lambda: 0,
                wall_clock=clock.time,
                monotonic_clock=clock.monotonic,
                sleep=clock.sleep,
            )
            parent = parent_manager.acquire(
                request(
                    ResourceClass.PACKAGE_BUILD,
                    run_id="windows-parent",
                    allowed=(ResourceClass.PACKAGE_BUILD,),
                )
            )
            inherited_request = replace(
                request(
                    ResourceClass.PACKAGE_BUILD,
                    run_id="windows-target",
                    allowed=(ResourceClass.PACKAGE_BUILD,),
                ),
                parent_lease_id=parent.lease_id,
                descendant=True,
                delegation_secret=parent.delegation_secret,
            )
            bootstrap = ResourceManager(
                host_runtime=root / "host",
                project_runtime=root / "project",
                process_identity=ProcessIdentity(202, creations[202]),
                process_probe=creations.get,
                parent_pid_provider=lambda: 101,
                wall_clock=clock.time,
                monotonic_clock=clock.monotonic,
                sleep=clock.sleep,
            )

            with patch("sagekit.resource_governor.os.name", "nt"):
                bootstrap.bind_windows_gated_delegate(
                    parent.lease_id,
                    delegation_secret=parent.delegation_secret,
                    delegate_pid=303,
                )
                target = ResourceManager(
                    host_runtime=root / "host",
                    project_runtime=root / "project",
                    process_identity=ProcessIdentity(303, creations[303]),
                    process_probe=creations.get,
                    parent_pid_provider=lambda: 202,
                    wall_clock=clock.time,
                    monotonic_clock=clock.monotonic,
                    sleep=clock.sleep,
                )
                inherited = target.load_lease(
                    parent.lease_id, delegation_secret=parent.delegation_secret
                )
                self.assertTrue(target.lease_covers(inherited, inherited_request))

                grandchild = ResourceManager(
                    host_runtime=root / "host",
                    project_runtime=root / "project",
                    process_identity=ProcessIdentity(404, creations[404]),
                    process_probe=creations.get,
                    parent_pid_provider=lambda: 303,
                    wall_clock=clock.time,
                    monotonic_clock=clock.monotonic,
                    sleep=clock.sleep,
                )
                with self.assertRaisesRegex(PermissionError, "direct child"):
                    grandchild.lease_covers(inherited, inherited_request)

            parent_manager.release(parent)

    def test_delegation_secret_is_private_and_bound_to_direct_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            parent_manager = ResourceManager(
                host_runtime=root / "host",
                project_runtime=root / "project",
                process_identity=ProcessIdentity(101, "parent-process"),
                process_probe=lambda pid: (
                    "parent-process" if pid == 101 else "child-process"
                ),
                parent_pid_provider=lambda: 0,
                wall_clock=clock.time,
                monotonic_clock=clock.monotonic,
                sleep=clock.sleep,
            )
            parent = parent_manager.acquire(
                request(
                    ResourceClass.REPO_READ,
                    run_id="parent",
                    allowed=(ResourceClass.REPO_READ,),
                )
            )
            registry = json.loads(parent.registry_path.read_text(encoding="utf-8"))
            self.assertIsNotNone(parent.delegation_secret)
            self.assertNotIn(parent.delegation_secret, parent.registry_path.read_text(encoding="utf-8"))
            self.assertRegex(registry["delegation_sha256"], r"^[0-9a-f]{64}$")

            child_manager = ResourceManager(
                host_runtime=root / "host",
                project_runtime=root / "project",
                process_identity=ProcessIdentity(202, "child-process"),
                process_probe=lambda pid: (
                    "parent-process" if pid == 101 else "child-process"
                ),
                parent_pid_provider=lambda: 101,
                wall_clock=clock.time,
                monotonic_clock=clock.monotonic,
                sleep=clock.sleep,
            )
            child_request = replace(
                request(
                    ResourceClass.REPO_READ,
                    run_id="child",
                    allowed=(ResourceClass.REPO_READ,),
                ),
                parent_lease_id=parent.lease_id,
                descendant=True,
                delegation_secret=parent.delegation_secret,
            )
            inherited = child_manager.load_lease(
                parent.lease_id, delegation_secret=parent.delegation_secret
            )
            self.assertTrue(child_manager.lease_covers(inherited, child_request))
            binding_path = (
                root / "host" / "delegations" / parent.lease_id / "binding.json"
            )
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
            self.assertEqual(202, binding["delegate_pid"])
            self.assertEqual("child-process", binding["delegate_process_creation"])
            with self.assertRaisesRegex(PermissionError, "delegation"):
                child_manager.load_lease(
                    parent.lease_id, delegation_secret="not-the-secret"
                )

            other_direct_child = ResourceManager(
                host_runtime=root / "host",
                project_runtime=root / "project",
                process_identity=ProcessIdentity(303, "other-child-process"),
                process_probe=lambda pid: "parent-process" if pid == 101 else None,
                parent_pid_provider=lambda: 101,
                wall_clock=clock.time,
                monotonic_clock=clock.monotonic,
                sleep=clock.sleep,
            )
            with self.assertRaisesRegex(PermissionError, "another child"):
                other_direct_child.lease_covers(inherited, child_request)

            grandchild_manager = ResourceManager(
                host_runtime=root / "host",
                project_runtime=root / "project",
                process_identity=ProcessIdentity(303, "grandchild-process"),
                process_probe=lambda pid: "parent-process" if pid == 101 else None,
                parent_pid_provider=lambda: 202,
                wall_clock=clock.time,
                monotonic_clock=clock.monotonic,
                sleep=clock.sleep,
            )
            with self.assertRaisesRegex(PermissionError, "direct child"):
                grandchild_manager.lease_covers(inherited, child_request)
            parent_manager.release(parent)
            self.assertFalse(binding_path.exists())

    def test_bundle_acquisition_is_not_observable_in_partial_state(self) -> None:
        class ControlledManager(ResourceManager):
            wrote_first = threading.Event()
            continue_acquire = threading.Event()

            def _claims_for(self, item):
                if item.run_id == "holder":
                    return ("project:z-conflict",)
                return ("host:a-partial", "project:z-conflict")

            def _atomic_write(self, path, payload):
                super()._atomic_write(path, payload)
                if (
                    payload.get("run_id") == "contender"
                    and "a-partial" in str(path)
                    and not self.wrote_first.is_set()
                ):
                    self.wrote_first.set()
                    self.continue_acquire.wait(5)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            manager = ControlledManager(
                host_runtime=root / "host",
                project_runtime=root / "project",
                process_identity=ProcessIdentity(101, "one"),
                process_probe=lambda candidate: "one",
                wall_clock=clock.time,
                monotonic_clock=clock.monotonic,
                sleep=clock.sleep,
            )
            holder = manager.acquire(
                request(ResourceClass.REPO_READ, run_id="holder")
            )
            failures: list[BaseException] = []

            def contend() -> None:
                try:
                    manager.acquire(
                        request(ResourceClass.PACKAGE_BUILD, run_id="contender"),
                        wait_timeout=0,
                    )
                except BaseException as exc:
                    failures.append(exc)

            thread = threading.Thread(target=contend)
            thread.start()
            self.assertTrue(manager.wrote_first.wait(2))
            timer = threading.Timer(0.2, manager.continue_acquire.set)
            timer.start()
            observed = manager.status()
            thread.join(2)
            timer.cancel()
            self.assertFalse(thread.is_alive())
            self.assertEqual(1, len(observed))
            self.assertEqual("holder", observed[0].run_id)
            self.assertTrue(any(isinstance(item, ResourceBusy) for item in failures))
            manager.release(holder)

    def make_manager(
        self,
        root: Path,
        clock: FakeClock,
        *,
        pid: int,
        created: str,
        project: str = "project",
        probe=None,
    ) -> ResourceManager:
        return ResourceManager(
            host_runtime=root / "host",
            project_runtime=root / project,
            process_identity=ProcessIdentity(pid, created),
            process_probe=probe or (lambda candidate: created if candidate == pid else None),
            wall_clock=clock.time,
            monotonic_clock=clock.monotonic,
            sleep=clock.sleep,
        )

    def test_host_cpu_heavy_allows_only_one_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            first = self.make_manager(root, clock, pid=101, created="proc-101")
            second = self.make_manager(root, clock, pid=202, created="proc-202")
            lease = first.acquire(request(ResourceClass.CPU_HEAVY, run_id="run-1"))
            with self.assertRaises(ResourceBusy):
                second.acquire(
                    request(ResourceClass.CPU_HEAVY, run_id="run-2"),
                    wait_timeout=0,
                )
            first.release(lease)
            replacement = second.acquire(request(ResourceClass.CPU_HEAVY, run_id="run-2"))
            second.release(replacement)

    def test_two_projects_still_compete_for_host_package_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            first = self.make_manager(root, clock, pid=101, created="one", project="p1")
            second = self.make_manager(root, clock, pid=202, created="two", project="p2")
            lease = first.acquire(request(ResourceClass.PACKAGE_BUILD, run_id="build-1"))
            with self.assertRaises(ResourceBusy):
                second.acquire(
                    request(ResourceClass.PACKAGE_BUILD, run_id="build-2"),
                    wait_timeout=0,
                )
            first.release(lease)

    def test_repo_writer_is_exclusive_within_one_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            first = self.make_manager(root, clock, pid=101, created="one")
            second = self.make_manager(root, clock, pid=202, created="two")
            writer = first.acquire(request(ResourceClass.REPO_WRITE, run_id="writer"))
            with self.assertRaises(ResourceBusy):
                second.acquire(
                    request(ResourceClass.REPO_WRITE, run_id="writer-2"),
                    wait_timeout=0,
                )
            first.release(writer)

    def test_repo_writers_in_different_worktrees_can_coexist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            first = self.make_manager(root, clock, pid=101, created="one")
            second = self.make_manager(root, clock, pid=202, created="two")
            one = first.acquire(
                request(ResourceClass.REPO_WRITE, run_id="writer-a", worktree="worktree-A")
            )
            two = second.acquire(
                request(ResourceClass.REPO_WRITE, run_id="writer-b", worktree="worktree-B")
            )
            second.release(two)
            first.release(one)

    def test_submit_is_exclusive_across_git_common_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            first = self.make_manager(root, clock, pid=101, created="one")
            second = self.make_manager(root, clock, pid=202, created="two")
            submit = first.acquire(
                request(ResourceClass.SUBMIT_EXCLUSIVE, run_id="submit-a", worktree="worktree-A")
            )
            with self.assertRaises(ResourceBusy):
                second.acquire(
                    request(ResourceClass.SUBMIT_EXCLUSIVE, run_id="submit-b", worktree="worktree-B")
                )
            first.release(submit)

    def test_repo_scan_does_not_consume_git_index_mutation_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            first = self.make_manager(root, clock, pid=101, created="one")
            second = self.make_manager(root, clock, pid=202, created="two")
            scan = first.acquire(request(ResourceClass.REPO_READ, run_id="scan"))
            submit = second.acquire(
                request(ResourceClass.SUBMIT_EXCLUSIVE, run_id="submit"),
                wait_timeout=0,
            )
            second.release(submit)
            first.release(scan)

    def test_heartbeat_keeps_live_lease_from_stale_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            first = self.make_manager(root, clock, pid=101, created="one")
            second = self.make_manager(root, clock, pid=202, created="two")
            lease = first.acquire(
                request(ResourceClass.CPU_HEAVY, run_id="one"), lease_ttl=5
            )
            clock.value += 4
            first.heartbeat(lease, stage="still-running")
            clock.value += 4
            with self.assertRaises(ResourceBusy):
                second.acquire(
                    request(ResourceClass.CPU_HEAVY, run_id="two"),
                    wait_timeout=0,
                )
            first.release(lease)

    def test_dead_stale_lease_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            first = self.make_manager(root, clock, pid=101, created="one")
            lease = first.acquire(
                request(ResourceClass.CPU_HEAVY, run_id="one"), lease_ttl=5
            )
            clock.value += 6
            second = self.make_manager(
                root,
                clock,
                pid=202,
                created="two",
                probe=lambda candidate: None,
            )
            recovered = second.acquire(
                request(ResourceClass.CPU_HEAVY, run_id="two"), wait_timeout=0
            )
            self.assertNotEqual(lease.lease_id, recovered.lease_id)
            second.release(recovered)

    def test_status_recovers_dead_claimless_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            first = self.make_manager(root, clock, pid=101, created="one")
            lease = first.acquire(
                request(ResourceClass.REPO_READ, run_id="claimless"), lease_ttl=5
            )
            self.assertEqual((lease.record,), first.status())
            clock.value += 6
            observer = self.make_manager(
                root,
                clock,
                pid=202,
                created="two",
                probe=lambda candidate: None,
            )
            self.assertEqual((), observer.status())
            self.assertFalse(lease.registry_path.exists())

    def test_pid_reuse_does_not_make_expired_lease_live(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            first = self.make_manager(root, clock, pid=101, created="old-instance")
            first.acquire(request(ResourceClass.CPU_HEAVY, run_id="one"), lease_ttl=5)
            clock.value += 6
            second = self.make_manager(
                root,
                clock,
                pid=202,
                created="two",
                probe=lambda candidate: "reused-instance" if candidate == 101 else "two",
            )
            recovered = second.acquire(
                request(ResourceClass.CPU_HEAVY, run_id="two"), wait_timeout=0
            )
            second.release(recovered)

    def test_wait_is_bounded_low_frequency_and_auto_continues(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            first = self.make_manager(root, clock, pid=101, created="one")
            lease = first.acquire(request(ResourceClass.CPU_HEAVY, run_id="one"))

            def releasing_sleep(seconds: float) -> None:
                clock.sleep(seconds)
                first.release(lease)

            second = ResourceManager(
                host_runtime=root / "host",
                project_runtime=root / "project",
                process_identity=ProcessIdentity(202, "two"),
                process_probe=lambda candidate: "one" if candidate == 101 else "two",
                wall_clock=clock.time,
                monotonic_clock=clock.monotonic,
                sleep=releasing_sleep,
                poll_interval=1.0,
            )
            waiting: list[str] = []
            acquired = second.acquire(
                request(ResourceClass.CPU_HEAVY, run_id="two"),
                wait_timeout=5,
                on_wait=lambda state: waiting.append(state),
            )
            self.assertEqual(["WAITING_FOR_RESOURCE"], waiting)
            self.assertEqual([1.0], clock.sleeps)
            second.release(acquired)

    def test_long_wait_reports_low_frequency_heartbeats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            first = self.make_manager(root, clock, pid=101, created="one")
            lease = first.acquire(request(ResourceClass.CPU_HEAVY, run_id="one"))
            second = self.make_manager(
                root,
                clock,
                pid=202,
                created="two",
                probe=lambda candidate: "one" if candidate == 101 else "two",
            )
            waiting: list[str] = []
            try:
                with self.assertRaises(ResourceBusy):
                    second.acquire(
                        request(ResourceClass.CPU_HEAVY, run_id="two"),
                        wait_timeout=65,
                        on_wait=waiting.append,
                    )
                self.assertEqual(
                    ["WAITING_FOR_RESOURCE"] * 3,
                    waiting,
                )
            finally:
                first.release(lease)

    def test_descendant_cannot_request_ungranted_class(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            manager = self.make_manager(root, clock, pid=101, created="one")
            with self.assertRaisesRegex(PermissionError, "not allowed"):
                manager.acquire(
                    request(
                        ResourceClass.REPO_WRITE,
                        run_id="child",
                        allowed=(ResourceClass.REASONING_ONLY, ResourceClass.REPO_READ),
                    )
                )

    def test_delegation_fails_closed_for_unknown_creation_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            parent_manager = self.make_manager(
                root, clock, pid=101, created="unknown:parent-creation"
            )
            parent = parent_manager.acquire(
                request(
                    ResourceClass.REPO_READ,
                    run_id="parent",
                    allowed=(ResourceClass.REPO_READ,),
                )
            )
            child_manager = ResourceManager(
                host_runtime=root / "host",
                project_runtime=root / "project",
                process_identity=ProcessIdentity(202, "child-process"),
                process_probe=lambda candidate: "unknown:parent-creation",
                parent_pid_provider=lambda: 101,
                wall_clock=clock.time,
                monotonic_clock=clock.monotonic,
                sleep=clock.sleep,
            )
            child_request = replace(
                request(
                    ResourceClass.REPO_READ,
                    run_id="child",
                    allowed=(ResourceClass.REPO_READ,),
                ),
                parent_lease_id=parent.lease_id,
                descendant=True,
                delegation_secret=parent.delegation_secret,
            )
            inherited = child_manager.load_lease(
                parent.lease_id, delegation_secret=parent.delegation_secret
            )
            with self.assertRaisesRegex(PermissionError, "reliable parent"):
                child_manager.lease_covers(inherited, child_request)
            parent_manager.release(parent)

    def test_descendant_partial_claim_overlap_is_rejected_instead_of_waiting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = FakeClock()
            manager = self.make_manager(root, clock, pid=101, created="one")
            parent = manager.acquire(
                request(
                    ResourceClass.REPO_WRITE,
                    run_id="parent",
                    allowed=(ResourceClass.REPO_WRITE, ResourceClass.SUBMIT_EXCLUSIVE),
                )
            )
            child = replace(
                request(
                    ResourceClass.SUBMIT_EXCLUSIVE,
                    run_id="child",
                    allowed=(ResourceClass.SUBMIT_EXCLUSIVE,),
                ),
                parent_lease_id=parent.lease_id,
                descendant=True,
                delegation_secret=parent.delegation_secret,
            )
            child_manager = ResourceManager(
                host_runtime=root / "host",
                project_runtime=root / "project",
                process_identity=ProcessIdentity(202, "child"),
                process_probe=lambda candidate: "one" if candidate == 101 else "child",
                parent_pid_provider=lambda: 101,
                wall_clock=clock.time,
                monotonic_clock=clock.monotonic,
                sleep=clock.sleep,
            )
            try:
                with self.assertRaisesRegex(PermissionError, "partially overlap"):
                    child_manager.acquire(child)
            finally:
                manager.release(parent)

    def test_reasoning_only_cannot_be_used_to_start_a_command(self) -> None:
        self.assertFalse(ResourceClass.REASONING_ONLY.allows_local_command)


if __name__ == "__main__":
    unittest.main()
