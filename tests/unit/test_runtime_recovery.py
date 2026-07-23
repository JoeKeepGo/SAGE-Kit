import copy
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sagekit.graph_contract import canonical_graph_digest
import sagekit.runtime_store as runtime_store
from sagekit.runtime_store import (
    RuntimeStoreIncomplete,
    acquire_runtime_writer,
    append_runtime_event,
    derive_attempt_id,
    derive_event_id,
    initialize_runtime_store,
)


FIXED_TIME = "2026-07-24T09:30:00+12:00"


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


def graph_fixture():
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:graph",
        "schema_version": 1,
        "graph_id": "graph-recovery",
        "generation": 1,
        "source_authority": {
            "identity": "accepted-authority",
            "reference": "docs/authority.md#recovery",
        },
        "governance_level": "Standard",
        "autonomy_level": "turn-based",
        "human_gates": [],
        "nodes": [
            node(),
            node("verify", depends_on=["build"]),
        ],
        "joins": [
            {
                "id": "complete",
                "requires": ["build", "verify"],
                "policy": "all-required",
            }
        ],
    }


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


def runtime_paths(root):
    runtime = root / ".sagekit" / "runtime"
    return {
        "runtime": runtime,
        "graph": runtime / "graph.json",
        "state": runtime / "state.json",
        "events": runtime / "events.jsonl",
        "lock": runtime / "writer.lock",
    }


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_events(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def initialize(root):
    graph = graph_fixture()
    writer = acquire_runtime_writer(
        root,
        graph,
        authority_id="authority:accepted",
        controller_id="controller:root",
        run_key="attempt:stage3c1",
        writer_id="writer:root",
    )
    initialize_runtime_store(writer, graph, clock=lambda: FIXED_TIME)
    return graph, writer


def expected_binding(writer):
    return {
        "run_id": writer.run_id,
        "graph_digest": writer.graph_digest,
        "authority_id": writer.authority_id,
        "controller_id": writer.controller_id,
    }


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


def advance_state(state, event):
    updated = copy.deepcopy(state)
    updated["revision"] += 1
    updated["last_event_sequence"] = event["sequence"]
    if event["event_type"] == "NODE_READY":
        node_state = next(
            item for item in updated["node_states"]
            if item["node_id"] == event["node_id"]
        )
        node_state["status"] = "READY"
        node_state["last_event_sequence"] = event["sequence"]
    elif event["event_type"] == "NODE_STARTED":
        node_state = next(
            item for item in updated["node_states"]
            if item["node_id"] == event["node_id"]
        )
        node_state["status"] = "RUNNING"
        node_state["attempt_id"] = event["attempt_id"]
        node_state["last_event_sequence"] = event["sequence"]
    elif event["event_type"] == "NODE_RESULT_RECORDED":
        node_state = next(
            item for item in updated["node_states"]
            if item["node_id"] == event["node_id"]
        )
        node_state["result_digest"] = event["result_digest"]
        node_state["last_event_sequence"] = event["sequence"]
    return updated


def append_valid_transition(root, writer):
    paths = runtime_paths(root)
    current = load_json(paths["state"])
    ready = event_for_state(current, "NODE_READY", node_id="build")
    ready_state = advance_state(current, ready)
    append_runtime_event(writer, ready, ready_state)
    current = load_json(paths["state"])
    attempt = derive_attempt_id(current["run_id"], "build", 1)
    started = event_for_state(
        current,
        "NODE_STARTED",
        node_id="build",
        attempt_id=attempt,
    )
    started_state = advance_state(current, started)
    append_runtime_event(writer, started, started_state)
    current = load_json(paths["state"])
    result = event_for_state(
        current,
        "NODE_RESULT_RECORDED",
        node_id="build",
        attempt_id=attempt,
        result_digest="result:verified",
    )
    result_state = advance_state(current, result)
    append_runtime_event(writer, result, result_state)


def snapshot_tree(root):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_file():
            result[relative] = path.read_bytes()
        else:
            result[relative] = None
    return result


class PureReplayAndAssessmentTests(unittest.TestCase):
    def test_import_and_assessment_are_zero_write(self):
        recovery = importlib.import_module("sagekit.runtime_recovery")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = snapshot_tree(root)
            result = recovery.assess_runtime_recovery(
                root,
                run_id="run:expected",
                graph_digest="0" * 64,
                authority_id="authority:accepted",
                controller_id="controller:root",
            )
            self.assertEqual(
                recovery.RecoveryClassification.GRAPH_CORRUPT,
                result.classification,
            )
            self.assertEqual(before, snapshot_tree(root))

    def test_same_input_is_deterministic_and_inputs_are_not_modified(self):
        from sagekit.runtime_recovery import (
            RecoveryClassification,
            replay_runtime_events,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph, writer = initialize(root)
            events = load_events(runtime_paths(root)["events"])
            graph_before = copy.deepcopy(graph)
            events_before = copy.deepcopy(events)
            binding = expected_binding(writer)
            first = replay_runtime_events(graph, events, **binding)
            second = replay_runtime_events(graph, events, **binding)
            self.assertEqual(first, second)
            self.assertEqual(RecoveryClassification.CONSISTENT, first.classification)
            self.assertEqual(2, first.last_valid_sequence)
            self.assertEqual((("build", 0), ("verify", 0)), first.attempt_counts)
            self.assertEqual(graph_before, graph)
            self.assertEqual(events_before, events)

    def test_replay_projects_node_attempt_and_result_transitions(self):
        from sagekit.runtime_recovery import (
            RecoveryClassification,
            replay_runtime_events,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph, writer = initialize(root)
            append_valid_transition(root, writer)
            paths = runtime_paths(root)
            result = replay_runtime_events(
                graph,
                load_events(paths["events"]),
                **expected_binding(writer),
            )
            self.assertEqual(RecoveryClassification.CONSISTENT, result.classification)
            self.assertEqual(5, result.last_valid_sequence)
            self.assertEqual((("build", 1), ("verify", 0)), result.attempt_counts)
            build = next(
                item for item in result.reconstructed_state["node_states"]
                if item["node_id"] == "build"
            )
            self.assertEqual("RUNNING", build["status"])
            self.assertEqual("result:verified", build["result_digest"])

    def test_valid_locked_store_assesses_consistent_without_writes(self):
        from sagekit.runtime_recovery import (
            RecoveryClassification,
            assess_runtime_recovery,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, writer = initialize(root)
            before = snapshot_tree(root)
            result = assess_runtime_recovery(
                root,
                writer_id=writer.writer_id,
                **expected_binding(writer),
            )
            self.assertEqual(RecoveryClassification.CONSISTENT, result.classification)
            self.assertEqual(before, snapshot_tree(root))

    def test_wrong_authority_sequence_and_event_identity_fail_closed(self):
        from sagekit.runtime_recovery import (
            RecoveryClassification,
            replay_runtime_events,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph, writer = initialize(root)
            events = load_events(runtime_paths(root)["events"])
            wrong_authority = replay_runtime_events(
                graph,
                events,
                **{
                    **expected_binding(writer),
                    "authority_id": "authority:foreign",
                },
            )
            self.assertEqual(
                RecoveryClassification.AUTHORITY_MISMATCH,
                wrong_authority.classification,
            )
            for name, mutate in (
                ("sequence", lambda item: item.update({"sequence": 4})),
                ("identity", lambda item: item.update({"event_id": "event:wrong"})),
            ):
                with self.subTest(name=name):
                    invalid = copy.deepcopy(events)
                    mutate(invalid[1])
                    result = replay_runtime_events(
                        graph,
                        invalid,
                        **expected_binding(writer),
                    )
                    self.assertEqual(
                        RecoveryClassification.EVENT_LOG_CORRUPT,
                        result.classification,
                    )
                    self.assertLessEqual(len(result.issues), 8)

    def test_assessment_classifies_state_ahead_diverged_torn_and_malformed_middle(self):
        from sagekit.runtime_recovery import (
            RecoveryClassification,
            assess_runtime_recovery,
        )

        cases = (
            (
                "ahead",
                lambda paths: _mutate_state(
                    paths,
                    lambda state: state.update(
                        {"last_event_sequence": state["last_event_sequence"] + 1}
                    ),
                ),
                RecoveryClassification.STATE_AHEAD_OF_EVENTS,
            ),
            (
                "diverged",
                lambda paths: _mutate_state(
                    paths,
                    lambda state: state["node_states"][0].update(
                        {"evidence_refs": ["evidence/diverged"]}
                    ),
                ),
                RecoveryClassification.STATE_DIVERGED,
            ),
            (
                "torn",
                lambda paths: paths["events"].write_bytes(
                    paths["events"].read_bytes() + b'{"schema_id":"torn"'
                ),
                RecoveryClassification.EVENT_LOG_TORN,
            ),
            (
                "middle",
                _insert_malformed_middle,
                RecoveryClassification.EVENT_LOG_CORRUPT,
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _, writer = initialize(root)
                mutate(runtime_paths(root))
                result = assess_runtime_recovery(
                    root,
                    writer_id=writer.writer_id,
                    **expected_binding(writer),
                )
                self.assertEqual(expected, result.classification)
                self.assertLessEqual(len(result.issues), 8)

    def test_root_path_representation_does_not_change_semantic_assessment(self):
        from sagekit.runtime_recovery import assess_runtime_recovery

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, writer = initialize(root)
            first = assess_runtime_recovery(
                root,
                writer_id=writer.writer_id,
                **expected_binding(writer),
            )
            second = assess_runtime_recovery(
                os.fspath(root),
                writer_id=writer.writer_id,
                **expected_binding(writer),
            )
            self.assertEqual(first, second)

    def test_results_and_source_do_not_leak_local_or_consumer_details(self):
        import sagekit.runtime_recovery as recovery

        source = Path(recovery.__file__).read_text(encoding="utf-8")
        forbidden = (
            "SPEC Framework",
            "KayAnn",
            "consumer",
            "ACTIVE_CONTEXT",
            "subprocess",
            "socket",
            "requests",
            "time.sleep",
            "while True",
            "threading",
            "argparse",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)


def _mutate_state(paths, mutate):
    state = load_json(paths["state"])
    mutate(state)
    paths["state"].write_bytes(canonical_bytes(state))


def _insert_malformed_middle(paths):
    lines = paths["events"].read_bytes().splitlines(keepends=True)
    paths["events"].write_bytes(lines[0] + b"{malformed}\n" + lines[1])


class WriterAuthorizedRecoveryTests(unittest.TestCase):
    def test_state_missing_recovery_is_explicit_atomic_and_idempotent(self):
        from sagekit.runtime_recovery import (
            RecoveryClassification,
            assess_runtime_recovery,
            recover_runtime_state,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, writer = initialize(root)
            paths = runtime_paths(root)
            paths["state"].unlink()
            before_events = paths["events"].read_bytes()
            assessment = assess_runtime_recovery(
                root,
                writer_id=writer.writer_id,
                **expected_binding(writer),
            )
            self.assertEqual(
                RecoveryClassification.STATE_MISSING,
                assessment.classification,
            )
            recovered = recover_runtime_state(writer, clock=lambda: FIXED_TIME)
            self.assertEqual(
                RecoveryClassification.RECOVERED,
                recovered.classification,
            )
            self.assertEqual(
                "INITIALIZED",
                load_json(paths["state"])["run_status"],
            )
            first_events = paths["events"].read_bytes()
            self.assertTrue(first_events.startswith(before_events))
            event_types = [item["event_type"] for item in load_events(paths["events"])]
            self.assertEqual(
                ["RECOVERY_STARTED", "RECOVERY_COMPLETED"],
                event_types[-2:],
            )
            repeated = recover_runtime_state(writer, clock=lambda: FIXED_TIME)
            self.assertEqual(
                RecoveryClassification.CONSISTENT,
                repeated.classification,
            )
            self.assertEqual(first_events, paths["events"].read_bytes())

    def test_state_lag_after_committed_event_is_recovered_without_event_loss(self):
        from sagekit.runtime_recovery import (
            RecoveryClassification,
            assess_runtime_recovery,
            recover_runtime_state,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, writer = initialize(root)
            paths = runtime_paths(root)
            current = load_json(paths["state"])
            event = event_for_state(current, "NODE_READY", node_id="build")
            updated = advance_state(current, event)
            original = runtime_store._replace_file

            def fail_state(source, target, **kwargs):
                if Path(target).name == "state.json":
                    raise OSError("injected state replace failure")
                return original(source, target, **kwargs)

            with patch("sagekit.runtime_store._replace_file", side_effect=fail_state):
                with self.assertRaises(RuntimeStoreIncomplete):
                    append_runtime_event(writer, event, updated)
            committed = paths["events"].read_bytes()
            assessment = assess_runtime_recovery(
                root,
                writer_id=writer.writer_id,
                **expected_binding(writer),
            )
            self.assertEqual(
                RecoveryClassification.STATE_BEHIND_EVENTS,
                assessment.classification,
            )
            result = recover_runtime_state(writer, clock=lambda: FIXED_TIME)
            self.assertEqual(RecoveryClassification.RECOVERED, result.classification)
            self.assertTrue(paths["events"].read_bytes().startswith(committed))
            self.assertEqual("READY", load_json(paths["state"])["node_states"][0]["status"])

    def test_interrupted_recovery_continues_with_only_missing_completion(self):
        import sagekit.runtime_recovery as recovery

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, writer = initialize(root)
            paths = runtime_paths(root)
            paths["state"].unlink()
            original = runtime_store._append_event_bytes
            calls = 0

            def fail_second(path, payload, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected completion append failure")
                return original(path, payload, **kwargs)

            with patch(
                "sagekit.runtime_store._append_event_bytes",
                side_effect=fail_second,
            ):
                with self.assertRaises(RuntimeStoreIncomplete):
                    recovery.recover_runtime_state(writer, clock=lambda: FIXED_TIME)
            event_types = [item["event_type"] for item in load_events(paths["events"])]
            self.assertEqual("RECOVERY_STARTED", event_types[-1])
            assessment = recovery.assess_runtime_recovery(
                root,
                writer_id=writer.writer_id,
                **expected_binding(writer),
            )
            self.assertEqual(
                recovery.RecoveryClassification.RECOVERY_IN_PROGRESS,
                assessment.classification,
            )
            result = recovery.recover_runtime_state(writer, clock=lambda: FIXED_TIME)
            self.assertEqual(
                recovery.RecoveryClassification.RECOVERED,
                result.classification,
            )
            event_types = [item["event_type"] for item in load_events(paths["events"])]
            self.assertEqual(1, event_types.count("RECOVERY_STARTED"))
            self.assertEqual(1, event_types.count("RECOVERY_COMPLETED"))

    def test_recovery_state_replace_failure_keeps_events_and_retries_state_only(self):
        import sagekit.runtime_recovery as recovery

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, writer = initialize(root)
            paths = runtime_paths(root)
            paths["state"].unlink()
            original = runtime_store._replace_file

            def fail_state(source, target, **kwargs):
                if Path(target).name == "state.json":
                    raise OSError("injected recovery state failure")
                return original(source, target, **kwargs)

            with patch("sagekit.runtime_store._replace_file", side_effect=fail_state):
                with self.assertRaises(RuntimeStoreIncomplete):
                    recovery.recover_runtime_state(writer, clock=lambda: FIXED_TIME)
            committed = paths["events"].read_bytes()
            self.assertFalse(paths["state"].exists())
            result = recovery.recover_runtime_state(writer, clock=lambda: FIXED_TIME)
            self.assertEqual(
                recovery.RecoveryClassification.RECOVERED,
                result.classification,
            )
            self.assertEqual(committed, paths["events"].read_bytes())

    def test_state_changed_during_recovery_is_not_overwritten(self):
        import sagekit.runtime_recovery as recovery

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, writer = initialize(root)
            paths = runtime_paths(root)
            stale_state = paths["state"].read_bytes()
            paths["state"].unlink()
            original = runtime_store._append_event_bytes
            calls = 0

            def replace_state_after_completion(path, payload, **kwargs):
                nonlocal calls
                original(path, payload, **kwargs)
                calls += 1
                if calls == 2:
                    paths["state"].write_bytes(stale_state)

            with patch(
                "sagekit.runtime_store._append_event_bytes",
                side_effect=replace_state_after_completion,
            ):
                with self.assertRaises(RuntimeStoreIncomplete):
                    recovery.recover_runtime_state(
                        writer,
                        clock=lambda: FIXED_TIME,
                    )
            self.assertEqual(stale_state, paths["state"].read_bytes())
            assessment = recovery.assess_runtime_recovery(
                root,
                writer_id=writer.writer_id,
                **expected_binding(writer),
            )
            self.assertEqual(
                recovery.RecoveryClassification.STATE_BEHIND_EVENTS,
                assessment.classification,
            )

    def test_replaced_writer_and_foreign_lock_fail_closed(self):
        import sagekit.runtime_recovery as recovery

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, writer = initialize(root)
            paths = runtime_paths(root)
            paths["state"].unlink()
            before_events = paths["events"].read_bytes()
            paths["lock"].unlink()
            foreign = {
                "schema_id": runtime_store.LOCK_SCHEMA_ID,
                "schema_version": 1,
                "run_id": writer.run_id,
                "graph_digest": writer.graph_digest,
                "authority_id": writer.authority_id,
                "controller_id": writer.controller_id,
                "writer_id": "writer:foreign",
            }
            paths["lock"].write_bytes(canonical_bytes(foreign))
            assessment = recovery.assess_runtime_recovery(
                root,
                writer_id=writer.writer_id,
                **expected_binding(writer),
            )
            self.assertEqual(
                recovery.RecoveryClassification.LOCKED_BY_OTHER_WRITER,
                assessment.classification,
            )
            result = recovery.recover_runtime_state(writer, clock=lambda: FIXED_TIME)
            self.assertEqual(
                recovery.RecoveryClassification.LOCK_INTEGRITY_ERROR,
                result.classification,
            )
            self.assertEqual(before_events, paths["events"].read_bytes())
            self.assertFalse(paths["state"].exists())

    def test_graph_or_events_changed_after_assessment_prevents_recovery_commit(self):
        import sagekit.runtime_recovery as recovery

        for name in ("graph", "events"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _, writer = initialize(root)
                paths = runtime_paths(root)
                paths["state"].unlink()
                original = runtime_store._commit_runtime_recovery

                def change_before_commit(*args, **kwargs):
                    if name == "graph":
                        paths["graph"].write_bytes(paths["graph"].read_bytes() + b" ")
                    else:
                        paths["events"].write_bytes(
                            paths["events"].read_bytes() + b'{"changed":true}\n'
                        )
                    return original(*args, **kwargs)

                with patch(
                    "sagekit.runtime_store._commit_runtime_recovery",
                    side_effect=change_before_commit,
                ):
                    with self.assertRaises(runtime_store.RuntimeStoreIntegrityError):
                        recovery.recover_runtime_state(
                            writer,
                            clock=lambda: FIXED_TIME,
                        )

    def test_authority_mismatch_and_state_divergence_are_never_mutated(self):
        import sagekit.runtime_recovery as recovery

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, writer = initialize(root)
            paths = runtime_paths(root)
            state = load_json(paths["state"])
            state["node_states"][0]["evidence_refs"] = ["evidence/diverged"]
            paths["state"].write_bytes(canonical_bytes(state))
            before = snapshot_tree(root)
            diverged = recovery.recover_runtime_state(
                writer,
                clock=lambda: FIXED_TIME,
            )
            self.assertEqual(
                recovery.RecoveryClassification.STATE_DIVERGED,
                diverged.classification,
            )
            self.assertEqual(before, snapshot_tree(root))
            wrong = recovery.assess_runtime_recovery(
                root,
                writer_id=writer.writer_id,
                **{
                    **expected_binding(writer),
                    "authority_id": "authority:foreign",
                },
            )
            self.assertEqual(
                recovery.RecoveryClassification.AUTHORITY_MISMATCH,
                wrong.classification,
            )


if __name__ == "__main__":
    unittest.main()
