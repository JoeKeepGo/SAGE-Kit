import copy
from datetime import datetime, timezone
import hashlib
import importlib
import inspect
import json
import ntpath
import os
from pathlib import Path
import posixpath
import tempfile
import threading
import unittest
from unittest.mock import patch

import sagekit
from sagekit.graph_contract import canonical_graph_digest, validate_graph_contract
import sagekit.runtime_store as runtime_store
from sagekit.runtime_store import (
    RuntimeStoreBusy,
    RuntimeStoreError,
    RuntimeStoreIncomplete,
    RuntimeStoreInspection,
    RuntimeStoreIntegrityError,
    RuntimeStoreStatus,
    acquire_runtime_writer,
    append_runtime_event,
    derive_attempt_id,
    derive_event_id,
    derive_run_id,
    initialize_runtime_store,
    inspect_runtime_store,
    release_runtime_writer,
    validate_runtime_event,
    validate_runtime_state,
)


FIXED_TIME = "2026-07-23T12:00:00+12:00"
STATE_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "sagekit"
    / "resources"
    / "contracts"
    / "runtime-state"
    / "v1"
    / "state.schema.json"
)
EVENT_SCHEMA = STATE_SCHEMA.with_name("event.schema.json")


def node(node_id="build", *, depends_on=None):
    return {
        "id": node_id,
        "role": "implementation",
        "depends_on": list(depends_on or []),
        "permission": "WRITE_AUTHORIZED",
        "verifier": "focused-tests",
        "output_contract": "urn:sagekit:graph-contract:v1:node-result",
        "resources": [],
        "classification": "required",
    }


def minimal_graph():
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:graph",
        "schema_version": 1,
        "graph_id": "graph-1",
        "generation": 1,
        "source_authority": {
            "identity": "accepted-authority",
            "reference": "docs/authority.md#graph",
        },
        "governance_level": "Standard",
        "autonomy_level": "turn-based",
        "human_gates": [],
        "nodes": [node()],
        "joins": [
            {
                "id": "complete",
                "requires": ["build"],
                "policy": "all-required",
            }
        ],
    }


def two_node_graph():
    graph = minimal_graph()
    graph["nodes"].append(node("verify", depends_on=["build"]))
    graph["joins"][0]["requires"].append("verify")
    return graph


def canonical_bytes(payload):
    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def runtime_paths(root):
    runtime = root / ".sagekit" / "runtime"
    return {
        "runtime": runtime,
        "graph": runtime / "graph.json",
        "state": runtime / "state.json",
        "events": runtime / "events.jsonl",
        "lock": runtime / "writer.lock",
    }


def takeover_authority(writer, *, new_writer_id="writer:takeover", **overrides):
    values = {
        "confirmation_id": "takeover:host-confirmed-001",
        "run_id": writer.run_id,
        "graph_digest": writer.graph_digest,
        "authority_id": writer.authority_id,
        "controller_id": writer.controller_id,
        "expected_prior_writer_id": writer.writer_id,
        "expected_prior_lock_digest": hashlib.sha256(writer._lock_bytes).hexdigest(),
        "new_writer_id": new_writer_id,
        "reason_code": "HOST_CONFIRMED_ABANDONED_WRITER",
    }
    values.update(overrides)
    return runtime_store.RuntimeTakeoverAuthority(**values)


def acquire(root, graph=None, **overrides):
    values = {
        "authority_id": "authority:accepted",
        "controller_id": "controller:root",
        "run_key": "accepted-attempt:stage3b",
        "writer_id": "writer:root",
    }
    values.update(overrides)
    return acquire_runtime_writer(root, graph or minimal_graph(), **values)


def initialize(root, graph=None, **overrides):
    graph = graph or minimal_graph()
    writer = acquire(root, graph, **overrides)
    result = initialize_runtime_store(writer, graph, clock=lambda: FIXED_TIME)
    return writer, result


def transition_payloads(root, *, previous="PENDING", next_status="READY"):
    paths = runtime_paths(root)
    state = load_json(paths["state"])
    event = {
        "schema_id": runtime_store.EVENT_SCHEMA_ID,
        "schema_version": 1,
        "event_id": derive_event_id(state["run_id"], state["last_event_sequence"] + 1),
        "run_id": state["run_id"],
        "sequence": state["last_event_sequence"] + 1,
        "graph_digest": state["graph_digest"],
        "event_type": "NODE_TRANSITIONED",
        "authority_id": state["authority_id"],
        "actor_id": state["controller_id"],
        "observed_at": FIXED_TIME,
        "reason_code": "NODE_STATUS_CHANGED",
        "evidence_refs": [],
        "artifact_refs": [],
        "node_id": "build",
        "previous_status": previous,
        "next_status": next_status,
    }
    updated = copy.deepcopy(state)
    updated["revision"] += 1
    updated["last_event_sequence"] = event["sequence"]
    updated["node_states"][0]["status"] = next_status
    updated["node_states"][0]["last_event_sequence"] = event["sequence"]
    return event, updated


def event_for_state(state, event_type, **optional):
    sequence = state["last_event_sequence"] + 1
    event = {
        "schema_id": runtime_store.EVENT_SCHEMA_ID,
        "schema_version": 1,
        "event_id": derive_event_id(state["run_id"], sequence),
        "run_id": state["run_id"],
        "sequence": sequence,
        "graph_digest": state["graph_digest"],
        "event_type": event_type,
        "authority_id": state["authority_id"],
        "actor_id": state["controller_id"],
        "observed_at": FIXED_TIME,
        "reason_code": f"{event_type}_OBSERVED",
        "evidence_refs": [],
        "artifact_refs": [],
    }
    event.update(optional)
    return event


def foreign_lock_bytes():
    return canonical_bytes(
        {
            "schema_id": runtime_store.LOCK_SCHEMA_ID,
            "schema_version": 1,
            "run_id": "run:foreign",
            "graph_digest": "f" * 64,
            "authority_id": "authority:foreign",
            "controller_id": "controller:foreign",
            "writer_id": "writer:foreign",
        }
    )


def tree_snapshot(root):
    snapshot = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            snapshot[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            stat_result = path.stat()
            snapshot[relative] = (
                "file",
                path.read_bytes(),
                stat_result.st_mtime_ns,
            )
        else:
            snapshot[relative] = ("directory",)
    return snapshot


class ImportReadAndPathBoundaryTests(unittest.TestCase):
    def test_import_and_missing_inspect_are_zero_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = tree_snapshot(root)
            importlib.import_module("sagekit.runtime_store")
            result = inspect_runtime_store(root)
            self.assertEqual(RuntimeStoreStatus.NOT_INITIALIZED, result.status)
            self.assertEqual(before, tree_snapshot(root))
            self.assertFalse((root / ".sagekit").exists())

    def test_graph_modules_remain_inert_and_runtime_api_is_not_top_level(self):
        import sagekit.graph_contract as graph_contract
        import sagekit.graph_normalization as graph_normalization

        self.assertIsNotNone(graph_contract)
        self.assertIsNotNone(graph_normalization)
        for name in (
            "RuntimeStoreError",
            "RuntimeWriter",
            "derive_run_id",
            "acquire_runtime_writer",
            "inspect_runtime_store",
        ):
            self.assertNotIn(name, vars(sagekit))

    def test_missing_or_non_directory_root_is_rejected_without_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            missing = parent / "missing"
            with self.assertRaises(RuntimeStoreError):
                inspect_runtime_store(missing)
            self.assertFalse(missing.exists())
            regular_file = parent / "file"
            regular_file.write_text("x", encoding="utf-8")
            with self.assertRaises(RuntimeStoreError):
                inspect_runtime_store(regular_file)

    def test_invalid_graph_is_rejected_before_any_runtime_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = minimal_graph()
            graph["nodes"][0]["unexpected"] = True
            with self.assertRaises(RuntimeStoreIntegrityError):
                acquire(root, graph)
            self.assertFalse((root / ".sagekit").exists())

    def test_runtime_symlink_escape_is_rejected_without_following_it(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "project"
            outside = parent / "outside"
            root.mkdir()
            outside.mkdir()
            try:
                (root / ".sagekit").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"directory symlink unavailable: {exc}")
            before = tree_snapshot(outside)
            with self.assertRaises(RuntimeStoreIntegrityError):
                acquire(root)
            self.assertEqual(before, tree_snapshot(outside))

    def test_nt_and_posix_containment_handles_case_separators_and_prefixes(self):
        self.assertTrue(
            runtime_store._path_is_within(
                r"C:\Repo",
                r"c:/repo/.sagekit/runtime",
                path_module=ntpath,
            )
        )
        self.assertFalse(
            runtime_store._path_is_within(
                r"C:\Repo",
                r"C:\Repository\.sagekit\runtime",
                path_module=ntpath,
            )
        )
        self.assertTrue(
            runtime_store._path_is_within(
                "/work/repo",
                "/work/repo/.sagekit/runtime",
                path_module=posixpath,
            )
        )
        self.assertFalse(
            runtime_store._path_is_within(
                "/work/repo",
                "/work/repository/runtime",
                path_module=posixpath,
            )
        )


class StableIdentityTests(unittest.TestCase):
    def test_run_event_and_attempt_identities_are_stable_and_bounded(self):
        digest = "a" * 64
        run = derive_run_id(
            digest,
            "authority:accepted",
            "controller:root",
            "accepted-attempt:stage3b",
        )
        self.assertEqual(
            run,
            derive_run_id(
                digest,
                "authority:accepted",
                "controller:root",
                "accepted-attempt:stage3b",
            ),
        )
        self.assertEqual(derive_event_id(run, 7), derive_event_id(run, 7))
        self.assertEqual(
            derive_attempt_id(run, "node:build", 2),
            derive_attempt_id(run, "node:build", 2),
        )
        for identity in (
            run,
            derive_event_id(run, 7),
            derive_attempt_id(run, "node:build", 2),
        ):
            self.assertRegex(identity, runtime_store.IDENTITY_PATTERN)
            self.assertLessEqual(len(identity), 256)

    def test_each_semantic_identity_input_changes_the_result(self):
        base = ("a" * 64, "authority:a", "controller:a", "run-key:a")
        baseline = derive_run_id(*base)
        variants = (
            ("b" * 64, *base[1:]),
            (base[0], "authority:b", *base[2:]),
            (*base[:2], "controller:b", base[3]),
            (*base[:3], "run-key:b"),
        )
        self.assertEqual(4, len({derive_run_id(*item) for item in variants}))
        self.assertNotIn(baseline, {derive_run_id(*item) for item in variants})
        self.assertNotEqual(derive_event_id(baseline, 1), derive_event_id(baseline, 2))
        self.assertNotEqual(
            derive_attempt_id(baseline, "node:a", 1),
            derive_attempt_id(baseline, "node:b", 1),
        )
        self.assertNotEqual(
            derive_attempt_id(baseline, "node:a", 1),
            derive_attempt_id(baseline, "node:a", 2),
        )

    def test_positive_integer_identity_inputs_reject_bool_zero_and_negative(self):
        run = derive_run_id("a" * 64, "authority:a", "controller:a", "run:a")
        for invalid in (True, False, 0, -1, 1.0):
            with self.subTest(invalid=invalid):
                with self.assertRaises(RuntimeStoreIntegrityError):
                    derive_event_id(run, invalid)
                with self.assertRaises(RuntimeStoreIntegrityError):
                    derive_attempt_id(run, "node:a", invalid)


class WriterLockTests(unittest.TestCase):
    def test_second_writer_is_immediately_busy_even_for_same_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = minimal_graph()
            writer = acquire(root, graph)
            with self.assertRaises(RuntimeStoreBusy):
                acquire(root, graph, writer_id="writer:second")
            self.assertTrue(runtime_paths(root)["lock"].exists())
            release_runtime_writer(writer)

    def test_lock_is_canonical_bound_and_fsynced_before_acquire_returns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("sagekit.runtime_store.os.fsync", wraps=os.fsync) as fsync:
                writer = acquire(root)
            lock_path = runtime_paths(root)["lock"]
            self.assertEqual(canonical_bytes(load_json(lock_path)), lock_path.read_bytes())
            lock = load_json(lock_path)
            self.assertEqual(writer.run_id, lock["run_id"])
            self.assertEqual(writer.graph_digest, lock["graph_digest"])
            self.assertEqual(writer.authority_id, lock["authority_id"])
            self.assertEqual(writer.controller_id, lock["controller_id"])
            self.assertEqual(writer.writer_id, lock["writer_id"])
            self.assertTrue(fsync.called)
            release_runtime_writer(writer)

    def test_replaced_or_malformed_lock_rejects_mutation_before_data_write(self):
        for replacement in (
            b"{not-json\n",
            canonical_bytes(
                {
                    "schema_id": runtime_store.LOCK_SCHEMA_ID,
                    "schema_version": 1,
                    "run_id": "run:foreign",
                    "graph_digest": "f" * 64,
                    "authority_id": "authority:foreign",
                    "controller_id": "controller:foreign",
                    "writer_id": "writer:foreign",
                }
            ),
        ):
            with self.subTest(replacement=replacement[:20]):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    writer = acquire(root)
                    lock_path = runtime_paths(root)["lock"]
                    lock_path.unlink()
                    lock_path.write_bytes(replacement)
                    before = tree_snapshot(root)
                    with self.assertRaises(RuntimeStoreIntegrityError):
                        initialize_runtime_store(
                            writer, minimal_graph(), clock=lambda: FIXED_TIME
                        )
                    self.assertEqual(before, tree_snapshot(root))

    def test_missing_lock_rejects_mutation_without_recreating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = acquire(root)
            lock_path = runtime_paths(root)["lock"]
            lock_path.unlink()
            before = tree_snapshot(root)
            with self.assertRaises(RuntimeStoreIntegrityError):
                initialize_runtime_store(
                    writer, minimal_graph(), clock=lambda: FIXED_TIME
                )
            self.assertEqual(before, tree_snapshot(root))
            self.assertFalse(lock_path.exists())

    def test_release_is_idempotent_and_never_deletes_replacement_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = acquire(root)
            release_runtime_writer(writer)
            release_runtime_writer(writer)
            foreign = acquire(root, writer_id="writer:foreign")
            release_runtime_writer(writer)
            self.assertTrue(runtime_paths(root)["lock"].exists())
            release_runtime_writer(foreign)

    def test_release_refuses_malformed_or_foreign_lock_without_deleting_it(self):
        for replacement in (b"bad\n", canonical_bytes({
            "schema_id": runtime_store.LOCK_SCHEMA_ID,
            "schema_version": 1,
            "run_id": "run:foreign",
            "graph_digest": "f" * 64,
            "authority_id": "authority:foreign",
            "controller_id": "controller:foreign",
            "writer_id": "writer:foreign",
        })):
            with self.subTest(replacement=replacement[:10]):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    writer = acquire(root)
                    lock_path = runtime_paths(root)["lock"]
                    lock_path.unlink()
                    lock_path.write_bytes(replacement)
                    with self.assertRaises(RuntimeStoreIntegrityError):
                        release_runtime_writer(writer)
                    self.assertEqual(replacement, lock_path.read_bytes())

    def test_release_race_quarantines_and_restores_foreign_lock_without_deleting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = acquire(root)
            lock_path = runtime_paths(root)["lock"]
            foreign = foreign_lock_bytes()
            original_rename = os.rename
            injected = False

            def replace_before_rename(source, target):
                nonlocal injected
                source = Path(source)
                if source.name == "writer.lock" and not injected:
                    injected = True
                    source.unlink()
                    source.write_bytes(foreign)
                return original_rename(source, target)

            with patch(
                "sagekit.runtime_store.os.rename",
                side_effect=replace_before_rename,
            ):
                with self.assertRaises(RuntimeStoreIntegrityError):
                    release_runtime_writer(writer)
            self.assertEqual(foreign, lock_path.read_bytes())
            self.assertFalse(
                any(
                    path.name.startswith(".writer.lock.release.")
                    for path in lock_path.parent.iterdir()
                )
            )


class InitializationAndSchemaTests(unittest.TestCase):
    def test_valid_initialize_writes_only_three_data_files_plus_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, result = initialize(root)
            paths = runtime_paths(root)
            self.assertEqual(RuntimeStoreStatus.LOCKED, result.status)
            self.assertEqual(
                {"events.jsonl", "graph.json", "state.json", "writer.lock"},
                {path.name for path in paths["runtime"].iterdir()},
            )
            release_runtime_writer(writer)
            self.assertEqual(RuntimeStoreStatus.VALID, inspect_runtime_store(root).status)

    def test_initial_state_and_two_events_are_consistent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root, two_node_graph())
            paths = runtime_paths(root)
            state = load_json(paths["state"])
            events = [
                json.loads(line)
                for line in paths["events"].read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(0, state["revision"])
            self.assertEqual(2, state["last_event_sequence"])
            self.assertEqual("INITIALIZED", state["run_status"])
            self.assertEqual(["RUN_INITIALIZED", "GRAPH_BOUND"], [e["event_type"] for e in events])
            self.assertEqual([1, 2], [e["sequence"] for e in events])
            self.assertEqual(
                [derive_event_id(state["run_id"], 1), derive_event_id(state["run_id"], 2)],
                [e["event_id"] for e in events],
            )
            self.assertEqual({"build", "verify"}, {n["node_id"] for n in state["node_states"]})
            for node_state in state["node_states"]:
                self.assertEqual("PENDING", node_state["status"])
                self.assertIsNone(node_state["attempt_id"])
                self.assertEqual([], node_state["evidence_refs"])
                self.assertEqual(0, node_state["last_event_sequence"])
            self.assertEqual({FIXED_TIME}, {e["observed_at"] for e in events})
            release_runtime_writer(writer)

    def test_graph_snapshot_is_exact_canonical_unmodified_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = two_node_graph()
            original = copy.deepcopy(graph)
            writer, _ = initialize(root, graph)
            graph_path = runtime_paths(root)["graph"]
            self.assertEqual(original, graph)
            self.assertEqual(original, load_json(graph_path))
            self.assertEqual(canonical_bytes(original), graph_path.read_bytes())
            self.assertEqual(canonical_graph_digest(original), writer.graph_digest)
            release_runtime_writer(writer)

    def test_state_and_event_validator_constants_match_stage3a_schema(self):
        state_schema = load_json(STATE_SCHEMA)
        event_schema = load_json(EVENT_SCHEMA)
        node_schema = state_schema["$defs"]["node_state"]
        self.assertEqual(frozenset(state_schema["required"]), runtime_store._STATE_REQUIRED_FIELDS)
        self.assertEqual(frozenset(state_schema["properties"]), runtime_store._STATE_FIELDS)
        self.assertEqual(frozenset(node_schema["required"]), runtime_store._NODE_STATE_REQUIRED_FIELDS)
        self.assertEqual(frozenset(node_schema["properties"]), runtime_store._NODE_STATE_FIELDS)
        self.assertEqual(
            frozenset(state_schema["properties"]["run_status"]["enum"]),
            runtime_store.RUN_STATUSES,
        )
        self.assertEqual(
            frozenset(node_schema["properties"]["status"]["enum"]),
            runtime_store.NODE_STATUSES,
        )
        self.assertEqual(frozenset(event_schema["required"]), runtime_store._EVENT_REQUIRED_FIELDS)
        self.assertEqual(frozenset(event_schema["properties"]), runtime_store._EVENT_FIELDS)
        self.assertEqual(
            frozenset(event_schema["properties"]["event_type"]["enum"]),
            runtime_store.EVENT_TYPES,
        )

    def test_strict_validators_reject_extra_fields_bool_duplicate_refs_and_nodes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root, two_node_graph())
            paths = runtime_paths(root)
            graph = load_json(paths["graph"])
            state = load_json(paths["state"])
            event = json.loads(paths["events"].read_text(encoding="utf-8").splitlines()[0])
            for field in ("revision", "last_event_sequence", "graph_generation"):
                invalid = copy.deepcopy(state)
                invalid[field] = True
                with self.subTest(field=field), self.assertRaises(RuntimeStoreIntegrityError):
                    validate_runtime_state(invalid, graph)
            invalid = copy.deepcopy(state)
            invalid["unexpected"] = True
            with self.assertRaises(RuntimeStoreIntegrityError):
                validate_runtime_state(invalid, graph)
            invalid = copy.deepcopy(state)
            invalid["node_states"][1]["node_id"] = invalid["node_states"][0]["node_id"]
            with self.assertRaises(RuntimeStoreIntegrityError):
                validate_runtime_state(invalid, graph)
            invalid_event = copy.deepcopy(event)
            invalid_event["sequence"] = True
            with self.assertRaises(RuntimeStoreIntegrityError):
                validate_runtime_event(invalid_event, graph)
            invalid_event = copy.deepcopy(event)
            invalid_event["evidence_refs"] = ["evidence:x", "evidence:x"]
            with self.assertRaises(RuntimeStoreIntegrityError):
                validate_runtime_event(invalid_event, graph)
            release_runtime_writer(writer)

    def test_node_membership_and_event_conditionals_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            paths = runtime_paths(root)
            graph = load_json(paths["graph"])
            state = load_json(paths["state"])
            event, _ = transition_payloads(root)
            event["node_id"] = "unknown"
            with self.assertRaises(RuntimeStoreIntegrityError):
                validate_runtime_event(event, graph)
            state["node_states"][0]["node_id"] = "unknown"
            with self.assertRaises(RuntimeStoreIntegrityError):
                validate_runtime_state(state, graph)
            started, _ = transition_payloads(root)
            started["event_type"] = "NODE_STARTED"
            started.pop("previous_status")
            started.pop("next_status")
            with self.assertRaises(RuntimeStoreIntegrityError):
                validate_runtime_event(started, graph)
            result = copy.deepcopy(started)
            result["event_type"] = "NODE_RESULT_RECORDED"
            result["attempt_id"] = derive_attempt_id(result["run_id"], "build", 1)
            with self.assertRaises(RuntimeStoreIntegrityError):
                validate_runtime_event(result, graph)
            release_runtime_writer(writer)


class AtomicInitializationTests(unittest.TestCase):
    def test_graph_only_partial_initialization_retries_without_rewriting_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = minimal_graph()
            writer = acquire(root, graph)
            paths = runtime_paths(root)
            original = runtime_store._replace_file

            def fail_events(source, target, **kwargs):
                if Path(target).name == "events.jsonl":
                    raise OSError("injected events replace failure")
                return original(source, target, **kwargs)

            with patch("sagekit.runtime_store._replace_file", side_effect=fail_events):
                with self.assertRaises(RuntimeStoreIncomplete):
                    initialize_runtime_store(writer, graph, clock=lambda: FIXED_TIME)
            graph_bytes = paths["graph"].read_bytes()
            self.assertFalse(paths["events"].exists())
            self.assertFalse(paths["state"].exists())

            result = initialize_runtime_store(writer, graph, clock=lambda: FIXED_TIME)
            self.assertEqual(RuntimeStoreStatus.LOCKED, result.status)
            self.assertEqual(graph_bytes, paths["graph"].read_bytes())
            self.assertEqual(
                ["RUN_INITIALIZED", "GRAPH_BOUND"],
                [
                    json.loads(line)["event_type"]
                    for line in paths["events"].read_text(encoding="utf-8").splitlines()
                ],
            )
            second = initialize_runtime_store(writer, graph, clock=lambda: FIXED_TIME)
            self.assertEqual(RuntimeStoreStatus.LOCKED, second.status)
            self.assertEqual(
                2,
                len(paths["events"].read_text(encoding="utf-8").splitlines()),
            )

    def test_graph_only_binding_cannot_be_released_or_reacquired_by_foreign_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = minimal_graph()
            old = acquire(root, graph)
            paths = runtime_paths(root)
            original = runtime_store._replace_file

            def fail_events(source, target, **kwargs):
                if Path(target).name == "events.jsonl":
                    raise OSError("injected events replace failure")
                return original(source, target, **kwargs)

            with patch(
                "sagekit.runtime_store._replace_file",
                side_effect=fail_events,
            ):
                with self.assertRaises(RuntimeStoreIncomplete):
                    initialize_runtime_store(old, graph, clock=lambda: FIXED_TIME)
            lock_bytes = paths["lock"].read_bytes()
            with self.assertRaises(RuntimeStoreIntegrityError):
                release_runtime_writer(old)
            self.assertEqual(lock_bytes, paths["lock"].read_bytes())
            with self.assertRaises(RuntimeStoreBusy):
                acquire(
                    root,
                    graph,
                    authority_id="authority:foreign",
                    controller_id="controller:foreign",
                    run_key="foreign-run",
                    writer_id="writer:foreign",
                )

            successor = runtime_store.takeover_runtime_writer(
                root,
                takeover_authority(old),
            )
            result = initialize_runtime_store(
                successor,
                graph,
                clock=lambda: FIXED_TIME,
            )
            self.assertEqual(RuntimeStoreStatus.LOCKED, result.status)
            release_runtime_writer(successor)

    def test_initialization_total_resource_bounds_fail_before_any_resource_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = acquire(root)
            paths = runtime_paths(root)
            before = {
                path.name: path.read_bytes()
                for path in paths["runtime"].iterdir()
            }
            with patch.object(runtime_store, "MAX_EVENTS_BYTES", 1):
                with self.assertRaises(RuntimeStoreIntegrityError):
                    initialize_runtime_store(
                        writer,
                        minimal_graph(),
                        clock=lambda: FIXED_TIME,
                    )
            after = {
                path.name: path.read_bytes()
                for path in paths["runtime"].iterdir()
            }
            self.assertEqual(before, after)

    def test_graph_only_mismatch_and_unknown_data_are_zero_write_failures(self):
        for mode in ("mismatch", "malformed", "unknown"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                graph = minimal_graph()
                writer = acquire(root, graph)
                paths = runtime_paths(root)
                if mode == "mismatch":
                    other = minimal_graph()
                    other["graph_id"] = "graph-other"
                    paths["graph"].write_bytes(canonical_bytes(other))
                elif mode == "malformed":
                    paths["graph"].write_bytes(b"{malformed}\n")
                else:
                    paths["graph"].write_bytes(canonical_bytes(graph))
                    (paths["runtime"] / "unknown-runtime-data").write_bytes(b"foreign")
                before = tree_snapshot(paths["runtime"])
                with self.assertRaises(RuntimeStoreIntegrityError):
                    initialize_runtime_store(writer, graph, clock=lambda: FIXED_TIME)
                self.assertEqual(before, tree_snapshot(paths["runtime"]))

    def test_events_state_partial_combinations_are_not_initialization_continuations(self):
        for present in ({"graph", "events"}, {"graph", "state"}):
            with (
                self.subTest(present=present),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                graph = minimal_graph()
                writer = acquire(root, graph)
                paths = runtime_paths(root)
                state, events = runtime_store._initial_payloads(
                    writer,
                    graph,
                    FIXED_TIME,
                )
                paths["graph"].write_bytes(canonical_bytes(graph))
                if "events" in present:
                    paths["events"].write_bytes(
                        b"".join(canonical_bytes(event) for event in events)
                    )
                if "state" in present:
                    paths["state"].write_bytes(canonical_bytes(state))
                before = tree_snapshot(paths["runtime"])
                with self.assertRaises(RuntimeStoreIntegrityError):
                    initialize_runtime_store(writer, graph, clock=lambda: FIXED_TIME)
                self.assertEqual(before, tree_snapshot(paths["runtime"]))

    def test_graph_change_during_continuation_is_detected_before_event_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = minimal_graph()
            writer = acquire(root, graph)
            paths = runtime_paths(root)
            original_replace = runtime_store._replace_file

            def fail_events(source, target, **kwargs):
                if Path(target).name == "events.jsonl":
                    raise OSError("injected events replace failure")
                return original_replace(source, target, **kwargs)

            with patch(
                "sagekit.runtime_store._replace_file",
                side_effect=fail_events,
            ):
                with self.assertRaises(RuntimeStoreIncomplete):
                    initialize_runtime_store(writer, graph, clock=lambda: FIXED_TIME)
            graph_bytes = paths["graph"].read_bytes()
            original_write_temp = runtime_store._write_temp
            changed = False

            def change_graph_after_temps(target, payload, owner, **kwargs):
                nonlocal changed
                temporary = original_write_temp(target, payload, owner, **kwargs)
                if Path(target).name == "state.json" and not changed:
                    changed = True
                    paths["graph"].write_bytes(graph_bytes)
                return temporary

            with patch(
                "sagekit.runtime_store._write_temp",
                side_effect=change_graph_after_temps,
            ):
                with self.assertRaises(RuntimeStoreIntegrityError):
                    initialize_runtime_store(writer, graph, clock=lambda: FIXED_TIME)
            self.assertFalse(paths["events"].exists())
            self.assertFalse(paths["state"].exists())

    def test_replace_order_is_graph_events_state_and_all_temps_are_same_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = acquire(root)
            calls = []
            original = runtime_store._replace_file

            def record(source, target, **kwargs):
                calls.append((Path(source), Path(target)))
                return original(source, target, **kwargs)

            with patch("sagekit.runtime_store._replace_file", side_effect=record):
                initialize_runtime_store(writer, minimal_graph(), clock=lambda: FIXED_TIME)
            self.assertEqual(["graph.json", "events.jsonl", "state.json"], [t.name for _, t in calls])
            self.assertTrue(all(source.parent == target.parent for source, target in calls))
            release_runtime_writer(writer)

    def test_partial_initialize_never_reports_valid_and_preserves_committed_evidence(self):
        for failure_target, expected_existing in (
            ("graph.json", set()),
            ("events.jsonl", {"graph.json"}),
            ("state.json", {"graph.json", "events.jsonl"}),
        ):
            with self.subTest(failure_target=failure_target):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    writer = acquire(root)
                    original = runtime_store._replace_file

                    def fail_at(source, target, **kwargs):
                        if Path(target).name == failure_target:
                            raise OSError("injected replace failure")
                        return original(source, target, **kwargs)

                    with patch("sagekit.runtime_store._replace_file", side_effect=fail_at):
                        with self.assertRaises(RuntimeStoreIncomplete):
                            initialize_runtime_store(
                                writer, minimal_graph(), clock=lambda: FIXED_TIME
                            )
                    paths = runtime_paths(root)
                    existing = {
                        name
                        for name in ("graph.json", "events.jsonl", "state.json")
                        if (paths["runtime"] / name).exists()
                    }
                    self.assertEqual(expected_existing, existing)
                    self.assertNotEqual(
                        RuntimeStoreStatus.VALID,
                        inspect_runtime_store(root).status,
                    )

    def test_failure_cleanup_removes_only_this_operation_temps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = acquire(root)
            runtime = runtime_paths(root)["runtime"]
            foreign = runtime / ".foreign-writer.tmp"
            foreign.write_bytes(b"keep")
            original = runtime_store._replace_file

            def fail_state(source, target, **kwargs):
                if Path(target).name == "state.json":
                    raise OSError("injected state failure")
                return original(source, target, **kwargs)

            with patch("sagekit.runtime_store._replace_file", side_effect=fail_state):
                with self.assertRaises(RuntimeStoreIncomplete):
                    initialize_runtime_store(writer, minimal_graph(), clock=lambda: FIXED_TIME)
            self.assertEqual(b"keep", foreign.read_bytes())
            own_temps = [
                path for path in runtime.iterdir()
                if path.name.endswith(".tmp") and path != foreign
            ]
            self.assertEqual([], own_temps)

    def test_directory_durability_is_reported_as_capability_not_hard_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = acquire(root)
            with patch("sagekit.runtime_store._directory_fsync", return_value=False):
                result = initialize_runtime_store(
                    writer, minimal_graph(), clock=lambda: FIXED_TIME
                )
            self.assertEqual("UNAVAILABLE", result.capabilities.directory_fsync)
            self.assertNotIn("HARD", repr(result.capabilities).upper())
            release_runtime_writer(writer)

    def test_runtime_directory_identity_swap_is_rejected_before_temp_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = acquire(root)
            runtime = runtime_paths(root)["runtime"]
            parked = runtime.with_name("runtime-parked")
            original = runtime_store._write_temp
            injected = False

            def swap_before_write(target, payload, owner, **kwargs):
                nonlocal injected
                if not injected:
                    injected = True
                    try:
                        runtime.rename(parked)
                    except OSError as exc:
                        self.skipTest(f"directory rename unavailable: {exc}")
                    runtime.mkdir()
                return original(target, payload, owner, **kwargs)

            with patch(
                "sagekit.runtime_store._write_temp",
                side_effect=swap_before_write,
            ):
                with self.assertRaises(RuntimeStoreIntegrityError):
                    initialize_runtime_store(
                        writer,
                        minimal_graph(),
                        clock=lambda: FIXED_TIME,
                    )
            self.assertEqual([], list(runtime.iterdir()))
            self.assertEqual({"writer.lock"}, {path.name for path in parked.iterdir()})

    def test_lock_replacement_between_initialization_commits_stops_next_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = acquire(root)
            paths = runtime_paths(root)
            original = runtime_store._replace_file

            def replace_lock_after_graph(source, target, **kwargs):
                original(source, target, **kwargs)
                if Path(target).name == "graph.json":
                    paths["lock"].unlink()
                    paths["lock"].write_bytes(foreign_lock_bytes())

            with patch(
                "sagekit.runtime_store._replace_file",
                side_effect=replace_lock_after_graph,
            ):
                with self.assertRaises(RuntimeStoreIncomplete) as raised:
                    initialize_runtime_store(
                        writer,
                        minimal_graph(),
                        clock=lambda: FIXED_TIME,
                    )
            self.assertEqual(RuntimeStoreStatus.INCOMPLETE, raised.exception.status)
            self.assertTrue(paths["graph"].exists())
            self.assertFalse(paths["events"].exists())
            self.assertFalse(paths["state"].exists())


class AppendAndRecoveryTests(unittest.TestCase):
    def test_valid_transition_appends_one_line_and_atomically_advances_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            paths = runtime_paths(root)
            before_events = paths["events"].read_bytes()
            event, updated = transition_payloads(root)
            result = append_runtime_event(writer, event, updated)
            self.assertEqual(RuntimeStoreStatus.LOCKED, result.status)
            after_events = paths["events"].read_bytes()
            self.assertTrue(after_events.startswith(before_events))
            self.assertEqual(before_events + canonical_bytes(event), after_events)
            self.assertEqual(updated, load_json(paths["state"]))
            release_runtime_writer(writer)
            self.assertEqual(RuntimeStoreStatus.VALID, inspect_runtime_store(root).status)

    def test_invalid_transition_gap_reuse_and_wrong_event_id_are_rejected_without_writes(self):
        mutations = (
            ("invalid-transition", lambda event, state: (
                event.update({"previous_status": "PENDING", "next_status": "RUNNING"}),
                state["node_states"][0].update({"status": "RUNNING"}),
            )),
            ("gap", lambda event, state: (
                event.update({"sequence": event["sequence"] + 1}),
                state.update({"last_event_sequence": state["last_event_sequence"] + 1}),
            )),
            ("wrong-id", lambda event, state: event.update({"event_id": "event:wrong"})),
        )
        for name, mutate in mutations:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    writer, _ = initialize(root)
                    paths = runtime_paths(root)
                    event, updated = transition_payloads(root)
                    mutate(event, updated)
                    before_events = paths["events"].read_bytes()
                    before_state = paths["state"].read_bytes()
                    with self.assertRaises(RuntimeStoreIntegrityError):
                        append_runtime_event(writer, event, updated)
                    self.assertEqual(before_events, paths["events"].read_bytes())
                    self.assertEqual(before_state, paths["state"].read_bytes())

    def test_event_durable_state_commit_failure_returns_recovery_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            paths = runtime_paths(root)
            event, updated = transition_payloads(root)
            before_events = paths["events"].read_bytes()
            before_state = paths["state"].read_bytes()
            original = runtime_store._replace_file

            def fail_state(source, target, **kwargs):
                if Path(target).name == "state.json":
                    raise OSError("injected state commit failure")
                return original(source, target, **kwargs)

            with patch("sagekit.runtime_store._replace_file", side_effect=fail_state):
                with self.assertRaises(RuntimeStoreIncomplete) as raised:
                    append_runtime_event(writer, event, updated)
            self.assertEqual(RuntimeStoreStatus.RECOVERY_REQUIRED, raised.exception.status)
            self.assertEqual(before_events + canonical_bytes(event), paths["events"].read_bytes())
            self.assertEqual(before_state, paths["state"].read_bytes())
            self.assertEqual(
                RuntimeStoreStatus.RECOVERY_REQUIRED,
                inspect_runtime_store(root).status,
            )

    def test_torn_jsonl_is_recovery_required_and_never_repaired(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            release_runtime_writer(writer)
            events = runtime_paths(root)["events"]
            events.write_bytes(events.read_bytes() + b'{"schema_id":"torn"')
            before = events.read_bytes()
            first = inspect_runtime_store(root)
            second = inspect_runtime_store(root)
            self.assertEqual(RuntimeStoreStatus.RECOVERY_REQUIRED, first.status)
            self.assertEqual(first, second)
            self.assertEqual(before, events.read_bytes())

    def test_partial_event_write_is_failure_and_recovery_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            paths = runtime_paths(root)
            event, updated = transition_payloads(root)
            before_state = paths["state"].read_bytes()

            def partial_append(path, payload, **kwargs):
                with Path(path).open("ab") as stream:
                    stream.write(payload[:31])
                    stream.flush()
                    os.fsync(stream.fileno())
                raise OSError("injected partial append")

            with patch(
                "sagekit.runtime_store._append_event_bytes",
                side_effect=partial_append,
            ):
                with self.assertRaises(RuntimeStoreIncomplete) as raised:
                    append_runtime_event(writer, event, updated)
            self.assertEqual(
                RuntimeStoreStatus.RECOVERY_REQUIRED,
                raised.exception.status,
            )
            self.assertEqual(before_state, paths["state"].read_bytes())
            self.assertEqual(
                RuntimeStoreStatus.RECOVERY_REQUIRED,
                inspect_runtime_store(root).status,
            )

    def test_duplicate_gap_and_state_ahead_are_corrupt(self):
        cases = {}
        with tempfile.TemporaryDirectory() as template:
            template_root = Path(template)
            writer, _ = initialize(template_root)
            release_runtime_writer(writer)
            paths = runtime_paths(template_root)
            graph_bytes = paths["graph"].read_bytes()
            state = load_json(paths["state"])
            events = [
                json.loads(line)
                for line in paths["events"].read_text(encoding="utf-8").splitlines()
            ]
            duplicate = copy.deepcopy(events)
            duplicate[1]["sequence"] = 1
            duplicate[1]["event_id"] = derive_event_id(state["run_id"], 1)
            cases["duplicate"] = (state, duplicate)
            gap = copy.deepcopy(events)
            gap[1]["sequence"] = 3
            gap[1]["event_id"] = derive_event_id(state["run_id"], 3)
            cases["gap"] = (state, gap)
            ahead = copy.deepcopy(state)
            ahead["last_event_sequence"] = 3
            cases["state-ahead"] = (ahead, events)
            for name, (case_state, case_events) in cases.items():
                with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    runtime = runtime_paths(root)["runtime"]
                    runtime.mkdir(parents=True)
                    (runtime / "graph.json").write_bytes(graph_bytes)
                    (runtime / "state.json").write_bytes(canonical_bytes(case_state))
                    (runtime / "events.jsonl").write_bytes(
                        b"".join(canonical_bytes(item) for item in case_events)
                    )
                    self.assertEqual(
                        RuntimeStoreStatus.CORRUPT,
                        inspect_runtime_store(root).status,
                    )

    def test_state_last_sequence_graph_digest_and_authority_mismatches_fail_closed(self):
        for name, mutate, expected in (
            (
                "graph-digest",
                lambda state, events: state.update({"graph_digest": "f" * 64}),
                RuntimeStoreStatus.CORRUPT,
            ),
            (
                "authority",
                lambda state, events: events[0].update({"authority_id": "authority:foreign"}),
                RuntimeStoreStatus.AUTHORITY_MISMATCH,
            ),
            (
                "run",
                lambda state, events: events[0].update({"run_id": "run:foreign"}),
                RuntimeStoreStatus.AUTHORITY_MISMATCH,
            ),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                writer, _ = initialize(root)
                release_runtime_writer(writer)
                paths = runtime_paths(root)
                state = load_json(paths["state"])
                events = [
                    json.loads(line)
                    for line in paths["events"].read_text(encoding="utf-8").splitlines()
                ]
                mutate(state, events)
                paths["state"].write_bytes(canonical_bytes(state))
                paths["events"].write_bytes(
                    b"".join(canonical_bytes(item) for item in events)
                )
                self.assertEqual(expected, inspect_runtime_store(root).status)

    def test_oversized_event_is_rejected_before_append(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            paths = runtime_paths(root)
            event, updated = transition_payloads(root)
            event["evidence_refs"] = [
                f"evidence/{index:03d}/" + ("x" * 1000) for index in range(100)
            ]
            event["artifact_refs"] = [
                f"artifact/{index:03d}/" + ("y" * 1000) for index in range(100)
            ]
            self.assertGreater(len(canonical_bytes(event)), runtime_store.MAX_EVENT_BYTES)
            before = tree_snapshot(paths["runtime"])
            with self.assertRaises(RuntimeStoreIntegrityError):
                append_runtime_event(writer, event, updated)
            self.assertEqual(before, tree_snapshot(paths["runtime"]))

    def test_event_specific_delta_rejects_unrelated_state_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            paths = runtime_paths(root)
            current = load_json(paths["state"])
            event = event_for_state(current, "RUN_STARTED")
            updated = copy.deepcopy(current)
            updated["revision"] += 1
            updated["last_event_sequence"] = event["sequence"]
            updated["run_status"] = "COMPLETED"
            updated["node_states"][0]["result_digest"] = "result:unrelated"
            before = tree_snapshot(paths["runtime"])
            with self.assertRaises(RuntimeStoreIntegrityError):
                append_runtime_event(writer, event, updated)
            self.assertEqual(before, tree_snapshot(paths["runtime"]))

    def test_illegal_transition_in_persisted_history_is_corrupt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            release_runtime_writer(writer)
            paths = runtime_paths(root)
            state = load_json(paths["state"])
            attempt = derive_attempt_id(state["run_id"], "build", 1)
            event = event_for_state(
                state,
                "NODE_TRANSITIONED",
                node_id="build",
                previous_status="PENDING",
                next_status="RUNNING",
                attempt_id=attempt,
            )
            state["revision"] += 1
            state["last_event_sequence"] = event["sequence"]
            state["node_states"][0].update(
                {
                    "status": "RUNNING",
                    "attempt_id": attempt,
                    "last_event_sequence": event["sequence"],
                }
            )
            paths["events"].write_bytes(
                paths["events"].read_bytes() + canonical_bytes(event)
            )
            paths["state"].write_bytes(canonical_bytes(state))
            self.assertEqual(
                RuntimeStoreStatus.CORRUPT,
                inspect_runtime_store(root).status,
            )

    def test_lock_replacement_after_event_append_prevents_state_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            paths = runtime_paths(root)
            event, updated = transition_payloads(root)
            before_state = paths["state"].read_bytes()
            original = runtime_store._append_event_bytes

            def replace_lock_after_append(path, payload, **kwargs):
                original(path, payload, **kwargs)
                paths["lock"].unlink()
                paths["lock"].write_bytes(foreign_lock_bytes())

            with patch(
                "sagekit.runtime_store._append_event_bytes",
                side_effect=replace_lock_after_append,
            ):
                with self.assertRaises(RuntimeStoreIncomplete) as raised:
                    append_runtime_event(writer, event, updated)
            self.assertEqual(
                RuntimeStoreStatus.RECOVERY_REQUIRED,
                raised.exception.status,
            )
            self.assertEqual(before_state, paths["state"].read_bytes())
            self.assertEqual(
                RuntimeStoreStatus.RECOVERY_REQUIRED,
                inspect_runtime_store(root).status,
            )

    def test_attempt_identity_must_be_derived_and_match_history_ordinal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            paths = runtime_paths(root)
            ready_event, ready_state = transition_payloads(root)
            append_runtime_event(writer, ready_event, ready_state)
            current = load_json(paths["state"])
            arbitrary = event_for_state(
                current,
                "NODE_STARTED",
                node_id="build",
                attempt_id="attempt:foreign",
            )
            with self.assertRaises(RuntimeStoreIntegrityError):
                validate_runtime_event(arbitrary, load_json(paths["graph"]))
            wrong_derived = "attempt:" + ("f" * 64)
            event = event_for_state(
                current,
                "NODE_STARTED",
                node_id="build",
                attempt_id=wrong_derived,
            )
            updated = copy.deepcopy(current)
            updated["revision"] += 1
            updated["last_event_sequence"] = event["sequence"]
            updated["node_states"][0].update(
                {
                    "status": "RUNNING",
                    "attempt_id": wrong_derived,
                    "last_event_sequence": event["sequence"],
                }
            )
            with self.assertRaises(RuntimeStoreIntegrityError):
                append_runtime_event(writer, event, updated)

            expected_attempt = derive_attempt_id(
                current["run_id"],
                "build",
                1,
            )
            event["attempt_id"] = expected_attempt
            updated["node_states"][0]["attempt_id"] = expected_attempt
            append_runtime_event(writer, event, updated)
            self.assertEqual(updated, load_json(paths["state"]))

    def test_total_event_log_bound_is_checked_before_append(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            paths = runtime_paths(root)
            event, updated = transition_payloads(root)
            before = tree_snapshot(paths["runtime"])
            limit = len(paths["events"].read_bytes()) + len(canonical_bytes(event)) - 1
            with patch("sagekit.runtime_store.MAX_EVENTS_BYTES", limit):
                with self.assertRaises(RuntimeStoreIntegrityError):
                    append_runtime_event(writer, event, updated)
            self.assertEqual(before, tree_snapshot(paths["runtime"]))


class ExistingStoreAuthorityTests(unittest.TestCase):
    def test_existing_store_rejects_foreign_authority_and_remains_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            release_runtime_writer(writer)
            with self.assertRaises(RuntimeStoreIntegrityError):
                acquire(
                    root,
                    authority_id="authority:foreign",
                    writer_id="writer:foreign",
                )
            self.assertFalse(runtime_paths(root)["lock"].exists())
            self.assertEqual(
                RuntimeStoreStatus.VALID,
                inspect_runtime_store(root).status,
            )
            matching = acquire(root, writer_id="writer:next")
            self.assertEqual(
                RuntimeStoreStatus.LOCKED,
                inspect_runtime_store(root).status,
            )
            release_runtime_writer(matching)


class InspectionAndScopeTests(unittest.TestCase):
    def test_inspect_is_fully_read_only_for_valid_locked_and_corrupt_stores(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            before = tree_snapshot(root)
            self.assertEqual(RuntimeStoreStatus.LOCKED, inspect_runtime_store(root).status)
            self.assertEqual(before, tree_snapshot(root))
            release_runtime_writer(writer)
            before = tree_snapshot(root)
            self.assertEqual(RuntimeStoreStatus.VALID, inspect_runtime_store(root).status)
            self.assertEqual(before, tree_snapshot(root))
            runtime_paths(root)["events"].write_bytes(b"torn")
            before = tree_snapshot(root)
            self.assertEqual(
                RuntimeStoreStatus.RECOVERY_REQUIRED,
                inspect_runtime_store(root).status,
            )
            self.assertEqual(before, tree_snapshot(root))

    def test_malformed_lock_has_explicit_integrity_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            lock = runtime_paths(root)["lock"]
            lock.write_bytes(b"bad\n")
            self.assertEqual(
                RuntimeStoreStatus.LOCK_INTEGRITY_ERROR,
                inspect_runtime_store(root).status,
            )
            self.assertTrue(
                any(
                    issue.code == "LOCK_INTEGRITY_ERROR"
                    for issue in inspect_runtime_store(root).issues
                )
            )

    def test_no_active_context_history_cli_network_or_high_cpu_behavior(self):
        source_path = Path(runtime_store.__file__)
        source = source_path.read_text(encoding="utf-8")
        forbidden = (
            "ACTIVE_CONTEXT",
            "subprocess",
            "socket",
            "urllib",
            "requests",
            "time.sleep",
            "while True",
            "ThreadPoolExecutor",
            "concurrent.futures",
            "argparse",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_store_writes_are_confined_to_fixed_runtime_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "unrelated.txt"
            outside.write_bytes(b"unchanged")
            writer, _ = initialize(root)
            event, updated = transition_payloads(root)
            append_runtime_event(writer, event, updated)
            release_runtime_writer(writer)
            self.assertEqual(b"unchanged", outside.read_bytes())
            self.assertEqual(
                {"unrelated.txt", ".sagekit"},
                {path.name for path in root.iterdir()},
            )

    def test_datetime_clock_is_normalized_without_entering_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = minimal_graph()
            writer = acquire(root, graph)
            result = initialize_runtime_store(
                writer,
                graph,
                clock=lambda: datetime(2026, 7, 23, tzinfo=timezone.utc),
            )
            self.assertEqual(RuntimeStoreStatus.LOCKED, result.status)
            events = runtime_paths(root)["events"].read_text(encoding="utf-8")
            self.assertIn("2026-07-23T00:00:00Z", events)
            self.assertEqual(
                derive_run_id(
                    canonical_graph_digest(graph),
                    "authority:accepted",
                    "controller:root",
                    "accepted-attempt:stage3b",
                ),
                writer.run_id,
            )


class OpaqueNodeIdCorrectiveTests(unittest.TestCase):
    def test_stage2_accepts_each_runtime_opaque_node_id_fixture(self):
        values = (
            "node with spaces",
            "path/segment\\opaque",
            "節点-α",
            "!leading-punctuation",
            "x" * 300,
        )
        for node_id in values:
            with self.subTest(node_id=node_id[:40]):
                graph = minimal_graph()
                graph["nodes"][0]["id"] = node_id
                graph["joins"][0]["requires"] = [node_id]
                result = validate_graph_contract(graph)
                self.assertTrue(result.valid, result.issues)

    def test_graph_valid_opaque_node_ids_round_trip_and_attempt_ids_are_stable(self):
        values = (
            "node with spaces",
            "path/segment\\opaque",
            "節点-α",
            "!leading-punctuation",
            "x" * 300,
        )
        for node_id in values:
            with (
                self.subTest(node_id=node_id[:40]),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                graph = minimal_graph()
                graph["nodes"][0]["id"] = node_id
                graph["joins"][0]["requires"] = [node_id]
                writer, _ = initialize(root, graph)
                state = load_json(runtime_paths(root)["state"])
                self.assertEqual(node_id, state["node_states"][0]["node_id"])
                self.assertEqual(
                    derive_attempt_id(writer.run_id, node_id, 1),
                    derive_attempt_id(writer.run_id, node_id, 1),
                )
                release_runtime_writer(writer)

    def test_attempt_identity_uses_exact_opaque_node_id_bytes(self):
        run_id = "run:" + "a" * 64
        pairs = (
            ("path/node", "path\\node"),
            ("é", "e\u0301"),
            (" node", "node "),
        )
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                self.assertNotEqual(
                    derive_attempt_id(run_id, left, 1),
                    derive_attempt_id(run_id, right, 1),
                )

    def test_empty_node_id_remains_rejected(self):
        graph = minimal_graph()
        graph["nodes"][0]["id"] = ""
        graph["joins"][0]["requires"] = [""]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeStoreIntegrityError):
                acquire(Path(directory), graph)


class ExplicitTakeoverCorrectiveTests(unittest.TestCase):
    def test_ordinary_acquire_stays_busy_and_exact_takeover_invalidates_old_handle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = minimal_graph()
            old, _ = initialize(root, graph)
            before = {
                name: runtime_paths(root)[name].read_bytes()
                for name in ("graph", "events", "state")
            }
            with self.assertRaises(RuntimeStoreBusy):
                acquire(root, graph, writer_id="writer:ordinary")

            authority = takeover_authority(old)
            new = runtime_store.takeover_runtime_writer(root, authority)
            self.assertEqual("writer:takeover", new.writer_id)
            with self.assertRaises(RuntimeStoreIntegrityError):
                release_runtime_writer(old)
            for name, payload in before.items():
                self.assertEqual(payload, runtime_paths(root)[name].read_bytes())
            lock = load_json(runtime_paths(root)["lock"])
            self.assertEqual(
                authority.confirmation_id,
                lock["takeover_authority"]["confirmation_id"],
            )
            release_runtime_writer(new)

    def test_old_handle_all_mutations_fail_and_new_writer_can_recover(self):
        import sagekit.runtime_recovery as recovery

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = minimal_graph()
            old, _ = initialize(root, graph)
            new = runtime_store.takeover_runtime_writer(
                root,
                takeover_authority(old),
            )
            paths = runtime_paths(root)
            event, updated = transition_payloads(root)
            paths["state"].unlink()

            with self.assertRaises(RuntimeStoreIntegrityError):
                initialize_runtime_store(old, graph, clock=lambda: FIXED_TIME)
            with self.assertRaises(RuntimeStoreIntegrityError):
                append_runtime_event(old, event, updated)
            self.assertEqual(
                recovery.RecoveryClassification.LOCK_INTEGRITY_ERROR,
                recovery.recover_runtime_state(old, clock=lambda: FIXED_TIME).classification,
            )
            with self.assertRaises(RuntimeStoreIntegrityError):
                release_runtime_writer(old)

            recovered = recovery.recover_runtime_state(new, clock=lambda: FIXED_TIME)
            self.assertEqual(
                recovery.RecoveryClassification.RECOVERED,
                recovered.classification,
            )
            self.assertTrue(paths["state"].exists())
            release_runtime_writer(new)

    def test_takeover_is_exact_bound_and_two_contenders_have_one_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, _ = initialize(root)
            authority = takeover_authority(old)
            start = threading.Barrier(3)
            results = []

            def contend():
                start.wait()
                try:
                    results.append(runtime_store.takeover_runtime_writer(root, authority))
                except Exception as exc:
                    results.append(exc)

            threads = [threading.Thread(target=contend) for _ in range(2)]
            for thread in threads:
                thread.start()
            start.wait()
            for thread in threads:
                thread.join(5)
                self.assertFalse(thread.is_alive())
            winners = [
                item for item in results
                if isinstance(item, runtime_store.RuntimeWriter)
            ]
            self.assertEqual(1, len(winners))
            self.assertEqual(1, len(results) - len(winners))
            release_runtime_writer(winners[0])

    def test_takeover_mismatch_or_malformed_lock_fails_closed(self):
        mismatches = (
            {"expected_prior_writer_id": "writer:wrong"},
            {"expected_prior_lock_digest": "0" * 64},
            {"run_id": "run:wrong"},
            {"graph_digest": "0" * 64},
            {"authority_id": "authority:wrong"},
            {"controller_id": "controller:wrong"},
            {"reason_code": "FORCE"},
        )
        for override in mismatches:
            with (
                self.subTest(override=override),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                old, _ = initialize(root)
                before = runtime_paths(root)["lock"].read_bytes()
                with self.assertRaises(RuntimeStoreIntegrityError):
                    runtime_store.takeover_runtime_writer(
                        root,
                        takeover_authority(old, **override),
                    )
                self.assertEqual(before, runtime_paths(root)["lock"].read_bytes())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, _ = initialize(root)
            runtime_paths(root)["lock"].write_bytes(b"{malformed}\n")
            with self.assertRaises(RuntimeStoreIntegrityError):
                runtime_store.takeover_runtime_writer(
                    root,
                    takeover_authority(old),
                )

    def test_lock_changed_during_takeover_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, _ = initialize(root)
            paths = runtime_paths(root)
            original = runtime_store._write_temp
            changed = False

            def change_prior_lock(target, payload, owner, **kwargs):
                nonlocal changed
                temporary = original(target, payload, owner, **kwargs)
                if Path(target).name == "writer.lock" and not changed:
                    changed = True
                    prior = paths["lock"].read_bytes()
                    paths["lock"].write_bytes(prior)
                return temporary

            with patch(
                "sagekit.runtime_store._write_temp",
                side_effect=change_prior_lock,
            ):
                with self.assertRaises(RuntimeStoreIntegrityError):
                    runtime_store.takeover_runtime_writer(
                        root,
                        takeover_authority(old),
                    )
            self.assertEqual(old._lock_bytes, paths["lock"].read_bytes())

    def test_takeover_authority_is_immutable_bounded_and_has_no_inference_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, _ = initialize(root)
            authority = takeover_authority(old)
            self.assertTrue(
                runtime_store.RuntimeTakeoverAuthority.__dataclass_params__.frozen
            )
            with self.assertRaises(AttributeError):
                authority.new_writer_id = "writer:changed"
            source = inspect.getsource(runtime_store.takeover_runtime_writer).casefold()
            for forbidden in (
                "getpid",
                "timeout",
                "stale",
                "force",
                "sleep",
                "poll",
            ):
                self.assertNotIn(forbidden, source)


class SameWriterSerializationCorrectiveTests(unittest.TestCase):
    def _assert_second_append_is_serialized(self, *, copy_handle):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            equivalent = copy.copy(writer) if copy_handle else writer
            event, updated = transition_payloads(root)
            first_entered = threading.Event()
            allow_first = threading.Event()
            second_entered = threading.Event()
            calls = 0
            original = runtime_store._append_event_bytes
            outcomes = []

            def block_first(path, payload, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    first_entered.set()
                    self.assertTrue(allow_first.wait(5))
                else:
                    second_entered.set()
                return original(path, payload, **kwargs)

            def append_with(handle):
                try:
                    outcomes.append(append_runtime_event(handle, event, updated))
                except Exception as exc:
                    outcomes.append(exc)

            with patch(
                "sagekit.runtime_store._append_event_bytes",
                side_effect=block_first,
            ):
                first = threading.Thread(target=append_with, args=(writer,))
                second = threading.Thread(target=append_with, args=(equivalent,))
                first.start()
                self.assertTrue(first_entered.wait(5))
                second.start()
                self.assertFalse(second_entered.wait(0.2))
                allow_first.set()
                first.join(5)
                second.join(5)
                self.assertFalse(first.is_alive())
                self.assertFalse(second.is_alive())

            events = [
                json.loads(line)
                for line in runtime_paths(root)["events"]
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            sequences = [item["sequence"] for item in events]
            self.assertEqual(list(range(1, len(events) + 1)), sequences)
            self.assertEqual(len(sequences), len(set(sequences)))
            self.assertEqual(
                1,
                sum(isinstance(item, RuntimeStoreInspection) for item in outcomes),
            )
            self.assertEqual(
                1,
                sum(isinstance(item, RuntimeStoreIntegrityError) for item in outcomes),
            )

    def test_same_handle_append_calls_are_serialized(self):
        self._assert_second_append_is_serialized(copy_handle=False)

    def test_copied_equivalent_handle_append_calls_are_serialized(self):
        self._assert_second_append_is_serialized(copy_handle=True)

    def test_append_and_release_cannot_interleave(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            event, updated = transition_payloads(root)
            append_entered = threading.Event()
            allow_append = threading.Event()
            release_done = threading.Event()
            outcomes = []
            original = runtime_store._append_event_bytes

            def block_append(path, payload, **kwargs):
                append_entered.set()
                self.assertTrue(allow_append.wait(5))
                return original(path, payload, **kwargs)

            def append_call():
                try:
                    outcomes.append(append_runtime_event(writer, event, updated))
                except Exception as exc:
                    outcomes.append(exc)

            def release_call():
                try:
                    release_runtime_writer(writer)
                    outcomes.append("released")
                except Exception as exc:
                    outcomes.append(exc)
                finally:
                    release_done.set()

            with patch(
                "sagekit.runtime_store._append_event_bytes",
                side_effect=block_append,
            ):
                append_thread = threading.Thread(target=append_call)
                release_thread = threading.Thread(target=release_call)
                append_thread.start()
                self.assertTrue(append_entered.wait(5))
                release_thread.start()
                released_early = release_done.wait(0.2)
                allow_append.set()
                append_thread.join(5)
                release_thread.join(5)
            self.assertFalse(released_early)
            self.assertFalse(append_thread.is_alive())
            self.assertFalse(release_thread.is_alive())
            self.assertEqual(
                1,
                sum(isinstance(item, RuntimeStoreInspection) for item in outcomes),
            )
            self.assertIn("released", outcomes)
            paths = runtime_paths(root)
            self.assertFalse(paths["lock"].exists())
            events = [
                json.loads(line)
                for line in paths["events"].read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual([1, 2, 3], [item["sequence"] for item in events])
            self.assertEqual(3, load_json(paths["state"])["last_event_sequence"])

    def test_recovery_and_append_share_the_same_operation_guard(self):
        import sagekit.runtime_recovery as recovery

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            paths = runtime_paths(root)
            event, updated = transition_payloads(root)
            runtime_store._append_event_bytes(
                paths["events"],
                canonical_bytes(event),
                expected_directory_identity=writer._runtime_identity,
                writer=writer,
            )
            recovery_inside = threading.Event()
            allow_recovery = threading.Event()
            append_done = threading.Event()
            outcomes = []
            original = recovery._assess_with_snapshot

            def block_after_assessment(*args, **kwargs):
                result = original(*args, **kwargs)
                recovery_inside.set()
                self.assertTrue(allow_recovery.wait(5))
                return result

            def recover_call():
                outcomes.append(
                    recovery.recover_runtime_state(writer, clock=lambda: FIXED_TIME)
                )

            def append_call():
                try:
                    outcomes.append(append_runtime_event(writer, event, updated))
                except Exception as exc:
                    outcomes.append(exc)
                finally:
                    append_done.set()

            with patch(
                "sagekit.runtime_recovery._assess_with_snapshot",
                side_effect=block_after_assessment,
            ):
                recovery_thread = threading.Thread(target=recover_call)
                append_thread = threading.Thread(target=append_call)
                recovery_thread.start()
                self.assertTrue(recovery_inside.wait(5))
                append_thread.start()
                append_finished_early = append_done.wait(0.2)
                allow_recovery.set()
                recovery_thread.join(5)
                append_thread.join(5)
            self.assertFalse(append_finished_early)
            self.assertFalse(recovery_thread.is_alive())
            self.assertFalse(append_thread.is_alive())
            self.assertTrue(
                any(
                    isinstance(item, recovery.RecoveryResult)
                    and item.classification
                    is recovery.RecoveryClassification.RECOVERED
                    for item in outcomes
                )
            )
            self.assertTrue(
                any(isinstance(item, RuntimeStoreIntegrityError) for item in outcomes)
            )
            events = [
                json.loads(line)
                for line in paths["events"].read_text(encoding="utf-8").splitlines()
            ]
            sequences = [item["sequence"] for item in events]
            self.assertEqual(list(range(1, len(events) + 1)), sequences)
            self.assertEqual(
                sequences[-1],
                load_json(paths["state"])["last_event_sequence"],
            )

    def test_operation_guard_is_released_after_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer, _ = initialize(root)
            event, updated = transition_payloads(root)
            with patch(
                "sagekit.runtime_store._write_temp",
                side_effect=OSError("injected pre-append failure"),
            ):
                with self.assertRaises(RuntimeStoreIncomplete):
                    append_runtime_event(writer, event, updated)
            result = append_runtime_event(writer, event, updated)
            self.assertEqual(RuntimeStoreStatus.LOCKED, result.status)


if __name__ == "__main__":
    unittest.main()
