import copy
import csv
import importlib
import io
import json
import os
import unittest
from unittest.mock import patch

from sagekit.runtime_recovery import (
    RecoveryAssessment,
    RecoveryClassification,
    RecoveryIssue,
    RecoveryResult,
    ReplayResult,
)
from sagekit.runtime_views import (
    build_runtime_handoff_view,
    render_runtime_csv,
)


CSV_HEADER = (
    "authority_class,view_schema,view_version,recovery_classification,"
    "valid_for_execution,required_action,source_state_canonical_digest,"
    "run_id,graph_digest,graph_generation,authority_id,controller_id,"
    "run_status,revision,last_event_sequence,node_total,nodes_truncated,"
    "record_type,node_id,node_status,node_last_event_sequence,"
    "evidence_reference_count,evidence_references_json,evidence_truncated"
)
ATTEMPT_ID = "attempt:" + ("1" * 64)


def node(node_id, status="PENDING", *, evidence_refs=()):
    return {
        "node_id": node_id,
        "status": status,
        "attempt_id": (
            ATTEMPT_ID
            if status
            in {
                "RUNNING",
                "SUCCEEDED",
                "NO_ACTION_REQUIRED",
                "FAILED",
                "NEEDS_CORRECTION",
                "DONE_WITH_CONCERNS",
            }
            else None
        ),
        "last_event_sequence": 2,
        "evidence_refs": list(evidence_refs),
    }


def state(*nodes, run_status="RUNNING"):
    return {
        "schema_id": "urn:sagekit:runtime-state-contract:v1:state",
        "schema_version": 1,
        "run_id": "run:stage3c2",
        "graph_digest": "a" * 64,
        "graph_generation": 7,
        "revision": 4,
        "last_event_sequence": 9,
        "run_status": run_status,
        "authority_id": "authority:accepted",
        "controller_id": "controller:root",
        "node_states": list(nodes),
    }


def assessment(runtime_state, classification=RecoveryClassification.CONSISTENT):
    return RecoveryAssessment(
        classification=classification,
        replay=(
            ReplayResult(
                classification=RecoveryClassification.CONSISTENT,
                reconstructed_state=runtime_state,
                last_valid_sequence=(
                    runtime_state["last_event_sequence"]
                    if runtime_state is not None
                    else 0
                ),
            )
            if classification is RecoveryClassification.CONSISTENT
            else None
        ),
        current_state=runtime_state,
    )


def canonical_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def csv_rows(value):
    return list(csv.DictReader(io.StringIO(value, newline="")))


class ImportAndPurityTests(unittest.TestCase):
    def test_import_has_no_runtime_or_filesystem_side_effects(self):
        import sagekit.runtime_recovery as recovery
        import sagekit.runtime_store as store
        import sagekit.runtime_views as views

        with (
            patch.object(
                recovery,
                "assess_runtime_recovery",
                side_effect=AssertionError("assessment must not run at import"),
            ),
            patch.object(
                store,
                "acquire_runtime_writer",
                side_effect=AssertionError("writer must not be acquired"),
            ),
            patch.object(
                store,
                "initialize_runtime_store",
                side_effect=AssertionError("store must not be initialized"),
            ),
            patch.object(
                store,
                "append_runtime_event",
                side_effect=AssertionError("events must not be appended"),
            ),
        ):
            reloaded = importlib.reload(views)
        self.assertIs(reloaded.build_runtime_handoff_view, views.build_runtime_handoff_view)

    def test_rendering_does_not_mutate_inputs_or_call_filesystem_writers(self):
        source = assessment(
            state(
                node("zeta", "RUNNING", evidence_refs=("evidence/z",)),
                node("alpha", evidence_refs=("evidence/a",)),
            )
        )
        before = copy.deepcopy(source)
        with (
            patch("pathlib.Path.mkdir", side_effect=AssertionError("mkdir")),
            patch("pathlib.Path.write_bytes", side_effect=AssertionError("write_bytes")),
            patch("pathlib.Path.write_text", side_effect=AssertionError("write_text")),
            patch("os.mkdir", side_effect=AssertionError("os.mkdir")),
            patch("os.makedirs", side_effect=AssertionError("os.makedirs")),
            patch("os.replace", side_effect=AssertionError("os.replace")),
        ):
            build_runtime_handoff_view(source)
            render_runtime_csv(source)
        self.assertEqual(before, source)

    def test_module_exposes_no_csv_import_or_filesystem_writer_surface(self):
        import sagekit.runtime_views as views

        forbidden = {
            "parse_runtime_csv",
            "import_runtime_csv",
            "load_runtime_csv",
            "write_runtime_csv",
            "write_csv",
        }
        self.assertTrue(forbidden.isdisjoint(vars(views)))
        self.assertFalse(any(name.startswith("parse_") for name in vars(views)))


class HandoffViewTests(unittest.TestCase):
    def test_opaque_graph_node_ids_are_preserved_without_reference_path_checks(self):
        opaque_ids = (
            "node with spaces",
            "path/segment\\opaque",
            "/absolute-looking-node",
            "C:\\absolute-looking-node",
            "節点-α",
            "!leading-punctuation",
            "=csv-formula",
            "x" * 300,
        )
        for node_id in opaque_ids:
            with self.subTest(node_id=node_id[:40]):
                runtime_state = state(node(node_id))
                view = build_runtime_handoff_view(assessment(runtime_state))
                self.assertEqual(node_id, view["nodes"]["waiting"]["ids"][0])
                rendered = render_runtime_csv(assessment(runtime_state))
                row = list(csv.DictReader(io.StringIO(rendered)))[0]
                expected = (
                    "'" + node_id
                    if node_id.lstrip().startswith(("=", "+", "-", "@"))
                    else node_id
                )
                self.assertEqual(expected, row["node_id"])

        unsafe = state(
            node(
                "C:\\opaque\\node",
                evidence_refs=("C:\\secret\\evidence.txt",),
            )
        )
        view = build_runtime_handoff_view(assessment(unsafe))
        self.assertFalse(view["valid_for_execution"])
        self.assertIn("SOURCE_STATE_INVALID", view["diagnostic_codes"])

    def test_consistent_handoff_is_immutable_json_compatible_and_reference_only(self):
        source = assessment(
            state(
                node("build", "RUNNING", evidence_refs=("evidence/build",)),
                node("verify", "PENDING"),
            )
        )
        view = build_runtime_handoff_view(source)

        self.assertEqual("sagekit.runtime-handoff-view", view["view_schema"])
        self.assertEqual(1, view["view_version"])
        self.assertEqual("REFERENCE_ONLY", view["authority_class"])
        self.assertEqual("run:stage3c2", view["run_id"])
        self.assertEqual("a" * 64, view["graph_digest"])
        self.assertEqual(7, view["graph_generation"])
        self.assertEqual("authority:accepted", view["authority_id"])
        self.assertEqual("controller:root", view["controller_id"])
        self.assertEqual("RUNNING", view["run_status"])
        self.assertEqual(4, view["revision"])
        self.assertEqual(9, view["last_event_sequence"])
        self.assertEqual("CONSISTENT", view["recovery_classification"])
        self.assertFalse(view["valid_for_execution"])
        self.assertEqual("consult_runtime_authority", view["required_action"])
        self.assertRegex(view["source_state_canonical_digest"], r"^[0-9a-f]{64}$")
        canonical_bytes(view)
        with self.assertRaises(TypeError):
            view["run_id"] = "run:changed"
        with self.assertRaises(TypeError):
            view["node_status_counts"]["RUNNING"] = 99

    def test_semantic_input_order_does_not_change_handoff_identity(self):
        first_state = state(
            node(
                "zeta",
                "RUNNING",
                evidence_refs=("evidence/z", "evidence/common"),
            ),
            node(
                "alpha",
                "PENDING",
                evidence_refs=("evidence/a", "evidence/common"),
            ),
        )
        second_state = copy.deepcopy(first_state)
        second_state["node_states"].reverse()
        for item in second_state["node_states"]:
            item["evidence_refs"].reverse()

        first = build_runtime_handoff_view(assessment(first_state))
        second = build_runtime_handoff_view(assessment(second_state))
        self.assertEqual(canonical_bytes(first), canonical_bytes(second))

    def test_consistent_replay_and_explicit_recovered_result_are_supported(self):
        runtime_state = state(node("build", "PENDING"))
        replay = ReplayResult(
            classification=RecoveryClassification.CONSISTENT,
            reconstructed_state=runtime_state,
            last_valid_sequence=9,
        )
        recovered = RecoveryResult(
            classification=RecoveryClassification.RECOVERED,
            recovered_state=runtime_state,
            appended_event_count=2,
        )

        replay_view = build_runtime_handoff_view(replay)
        recovered_view = build_runtime_handoff_view(recovered)
        self.assertFalse(replay_view["valid_for_execution"])
        self.assertFalse(recovered_view["valid_for_execution"])
        self.assertEqual(
            "consult_runtime_authority",
            replay_view["required_action"],
        )
        self.assertEqual(
            "consult_runtime_authority",
            recovered_view["required_action"],
        )
        self.assertEqual("RECOVERED", recovered_view["recovery_classification"])

    def test_bare_consistent_assessment_without_matching_replay_fails_closed(self):
        source = RecoveryAssessment(
            classification=RecoveryClassification.CONSISTENT,
            current_state=state(node("build", "PENDING")),
        )
        view = build_runtime_handoff_view(source)

        self.assertFalse(view["valid_for_execution"])
        self.assertEqual("handoff_required", view["required_action"])
        self.assertEqual(0, view["node_total"])
        self.assertIn("SOURCE_RESULT_INCONSISTENT", view["diagnostic_codes"])

    def test_unsafe_recovery_assessments_are_bounded_diagnostics(self):
        unsafe = (
            RecoveryClassification.STATE_MISSING,
            RecoveryClassification.STATE_BEHIND_EVENTS,
            RecoveryClassification.STATE_AHEAD_OF_EVENTS,
            RecoveryClassification.STATE_DIVERGED,
            RecoveryClassification.EVENT_LOG_TORN,
            RecoveryClassification.EVENT_LOG_CORRUPT,
            RecoveryClassification.GRAPH_CORRUPT,
            RecoveryClassification.AUTHORITY_MISMATCH,
        )
        dangerous = state(node("secret", "RUNNING", evidence_refs=("secret/ref",)))
        for classification in unsafe:
            with self.subTest(classification=classification):
                view = build_runtime_handoff_view(
                    RecoveryAssessment(
                        classification=classification,
                        current_state=dangerous,
                        issues=(
                            RecoveryIssue(
                                "UNSAFE_INPUT",
                                r"private reasoning at C:\Users\person\secret.txt",
                            ),
                        ),
                    )
                )
                self.assertFalse(view["valid_for_execution"])
                self.assertIn(
                    view["required_action"],
                    {"recovery_required", "handoff_required"},
                )
                self.assertIsNone(view["run_id"])
                self.assertEqual(0, view["node_total"])
                serialized = canonical_bytes(view)
                self.assertNotIn(b"private reasoning", serialized)
                self.assertNotIn(b"secret/ref", serialized)

    def test_every_non_safe_classification_has_no_execution_false_green(self):
        runtime_state = state(node("build", "PENDING"))
        safe = {
            RecoveryClassification.CONSISTENT,
            RecoveryClassification.RECOVERED,
        }
        for classification in RecoveryClassification:
            if classification in safe:
                continue
            with self.subTest(classification=classification):
                view = build_runtime_handoff_view(
                    RecoveryAssessment(
                        classification=classification,
                        current_state=runtime_state,
                    )
                )
                self.assertFalse(view["valid_for_execution"])
                self.assertNotEqual("none", view["required_action"])

    def test_missing_or_empty_current_state_fails_closed(self):
        for runtime_state in (None, state()):
            with self.subTest(runtime_state=runtime_state):
                view = build_runtime_handoff_view(assessment(runtime_state))
                self.assertFalse(view["valid_for_execution"])
                self.assertEqual("handoff_required", view["required_action"])
                self.assertTrue(
                    {"SOURCE_STATE_INVALID", "SOURCE_STATE_UNAVAILABLE"}
                    & set(view["diagnostic_codes"])
                )
                self.assertEqual(0, view["node_total"])

    def test_node_and_evidence_output_is_bounded_and_reports_truncation(self):
        source = assessment(
            state(
                *(
                    node(
                        f"node{index}",
                        "RUNNING",
                        evidence_refs=(
                            f"evidence/{index}/a",
                            f"evidence/{index}/b",
                        ),
                    )
                    for index in range(6)
                )
            )
        )
        view = build_runtime_handoff_view(source, node_limit=2, evidence_limit=3)

        self.assertEqual(6, view["node_total"])
        self.assertEqual(6, view["nodes"]["active"]["total"])
        self.assertEqual(("node0", "node1"), view["nodes"]["active"]["ids"])
        self.assertTrue(view["nodes"]["active"]["truncated"])
        self.assertEqual(12, view["reference_counts"]["evidence_references"])
        self.assertEqual(12, view["reference_counts"]["unique_evidence_references"])
        self.assertEqual(3, len(view["evidence_references"]["values"]))
        self.assertTrue(view["evidence_references"]["truncated"])
        self.assertTrue(view["truncated"])

    def test_statuses_preserve_concerns_and_non_success_boundaries(self):
        source = assessment(
            state(
                node("concern", "DONE_WITH_CONCERNS"),
                node("handoff", "HANDOFF"),
                node("blocked", "BLOCKED"),
                node("success", "SUCCEEDED"),
            )
        )
        view = build_runtime_handoff_view(source)

        self.assertEqual(1, view["node_status_counts"]["DONE_WITH_CONCERNS"])
        self.assertEqual(1, view["node_status_counts"]["SUCCEEDED"])
        self.assertEqual(1, view["node_status_counts"]["HANDOFF"])
        self.assertEqual(1, view["node_status_counts"]["BLOCKED"])
        self.assertEqual(("blocked", "handoff"), view["nodes"]["blocked"]["ids"])
        self.assertFalse(view["valid_for_execution"])
        self.assertEqual("handoff_required", view["required_action"])

    def test_ready_and_acceptance_or_gate_state_are_never_inferred(self):
        view = build_runtime_handoff_view(
            assessment(state(node("pending", "PENDING")))
        )
        self.assertEqual((), view["nodes"]["active"]["ids"])
        self.assertEqual(("pending",), view["nodes"]["waiting"]["ids"])
        self.assertTrue(
            {
                "accepted",
                "acceptance",
                "approval_gate",
                "pm_acceptance",
                "next_node",
                "next_phase",
                "milestone",
            }.isdisjoint(view)
        )
        serialized = canonical_bytes(view).lower()
        for forbidden in (
            b"ready_nodes",
            b"next_node",
            b"next_phase",
            b"milestone",
            b"approval_gate",
            b"pm_acceptance",
            b"proposed_next",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_invalid_private_or_absolute_path_fields_fail_closed_without_leakage(self):
        private = state(node("build", "PENDING"))
        private["transcript"] = "credential=top-secret"
        private["node_states"][0]["private_reasoning"] = "hidden chain"
        path_value = state(
            node(
                "build",
                "PENDING",
                evidence_refs=(r"C:\Users\person\secret.txt",),
            )
        )
        for runtime_state in (private, path_value):
            with self.subTest(runtime_state=runtime_state):
                view = build_runtime_handoff_view(assessment(runtime_state))
                rendered = canonical_bytes(view)
                self.assertFalse(view["valid_for_execution"])
                self.assertNotIn(b"top-secret", rendered)
                self.assertNotIn(b"hidden chain", rendered)
                self.assertNotIn(b"C:\\\\Users", rendered)

    def test_unc_rooted_path_and_obvious_secret_references_fail_closed(self):
        unsafe_references = (
            r"\\server\share\private.txt",
            r"\rooted\private.txt",
            "evidence/SAGEKIT_DELEGATION_SECRET=top-secret",
            "evidence/Authorization: Bearer credential-value",
        )
        for reference in unsafe_references:
            with self.subTest(reference=reference):
                source = assessment(
                    state(node("build", "PENDING", evidence_refs=(reference,)))
                )
                handoff = build_runtime_handoff_view(source)
                rendered = render_runtime_csv(source)
                self.assertFalse(handoff["valid_for_execution"])
                self.assertEqual(0, handoff["node_total"])
                self.assertIn("SOURCE_STATE_INVALID", handoff["diagnostic_codes"])
                self.assertNotIn(reference, canonical_bytes(handoff).decode("utf-8"))
                self.assertNotIn(reference, rendered)
                self.assertEqual("diagnostic", csv_rows(rendered)[0]["record_type"])


class CsvViewTests(unittest.TestCase):
    def test_csv_is_deterministic_fixed_header_lf_and_stably_sorted(self):
        runtime_state = state(
            node("zeta", "RUNNING"),
            node("alpha", "PENDING"),
        )
        first = render_runtime_csv(assessment(runtime_state))
        second_state = copy.deepcopy(runtime_state)
        second_state["node_states"].reverse()
        second = render_runtime_csv(assessment(second_state))

        self.assertIsInstance(first, str)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith(CSV_HEADER + "\n"))
        self.assertNotIn("\r", first)
        self.assertTrue(first.endswith("\n"))
        rows = csv_rows(first)
        self.assertEqual(["alpha", "zeta"], [row["node_id"] for row in rows])
        self.assertEqual({"REFERENCE_ONLY"}, {row["authority_class"] for row in rows})

    def test_csv_uses_rfc4180_quoting_and_canonical_unicode_reference_json(self):
        reference = '证据/alpha,"quoted"'
        rendered = render_runtime_csv(
            assessment(
                state(node("alpha", "RUNNING", evidence_refs=(reference,)))
            )
        )
        self.assertIn('"[""', rendered)
        rows = csv_rows(rendered)
        self.assertEqual(
            json.dumps([reference], ensure_ascii=False, separators=(",", ":")),
            rows[0]["evidence_references_json"],
        )
        self.assertIn("证据", rendered)

    def test_csv_cells_are_formula_safe(self):
        formula = "=SUM(A1:A2)"
        rendered = render_runtime_csv(
            assessment(
                state(node("alpha", "RUNNING", evidence_refs=(formula,)))
            )
        )
        rows = csv_rows(rendered)
        for value in rows[0].values():
            self.assertFalse(value.lstrip().startswith(("=", "+", "-", "@")))
        self.assertEqual(
            json.dumps([formula], separators=(",", ":")),
            rows[0]["evidence_references_json"],
        )

    def test_csv_is_bounded_and_marks_node_and_evidence_truncation(self):
        source = assessment(
            state(
                node("charlie", "RUNNING", evidence_refs=("e/c1", "e/c2")),
                node("bravo", "PENDING", evidence_refs=("e/b1", "e/b2")),
                node("alpha", "PENDING", evidence_refs=("e/a1", "e/a2")),
            )
        )
        rendered = render_runtime_csv(source, node_limit=2, evidence_limit=3)
        rows = csv_rows(rendered)

        self.assertEqual(["alpha", "bravo"], [row["node_id"] for row in rows])
        self.assertEqual({"3"}, {row["node_total"] for row in rows})
        self.assertEqual({"true"}, {row["nodes_truncated"] for row in rows})
        self.assertEqual("false", rows[0]["evidence_truncated"])
        self.assertEqual("true", rows[1]["evidence_truncated"])
        self.assertEqual([], json.loads(rows[1]["evidence_references_json"])[1:])

    def test_csv_empty_or_unsafe_input_emits_only_a_diagnostic_summary_row(self):
        source = RecoveryAssessment(
            classification=RecoveryClassification.EVENT_LOG_CORRUPT,
            issues=(
                RecoveryIssue(
                    "EVENT_BAD",
                    r"transcript at /home/person/private.txt",
                ),
            ),
        )
        rendered = render_runtime_csv(source)
        rows = csv_rows(rendered)

        self.assertEqual(1, len(rows))
        self.assertEqual("diagnostic", rows[0]["record_type"])
        self.assertEqual("", rows[0]["node_id"])
        self.assertEqual("false", rows[0]["valid_for_execution"])
        self.assertEqual("REFERENCE_ONLY", rows[0]["authority_class"])
        self.assertNotIn("transcript", rendered)
        self.assertNotIn("/home/person", rendered)

    def test_csv_does_not_leak_private_fields_or_absolute_paths(self):
        runtime_state = state(
            node("alpha", "PENDING", evidence_refs=(r"C:\private\secret",))
        )
        runtime_state["stdout"] = "token=secret"
        rendered = render_runtime_csv(assessment(runtime_state))

        self.assertNotIn(r"C:\private", rendered)
        self.assertNotIn("token=secret", rendered)
        self.assertEqual("diagnostic", csv_rows(rendered)[0]["record_type"])

    def test_repeated_render_is_byte_equivalent(self):
        source = assessment(
            state(
                node("alpha", "PENDING", evidence_refs=("证据/a",)),
                node("beta", "DONE_WITH_CONCERNS", evidence_refs=("evidence/b",)),
            )
        )
        outputs = [render_runtime_csv(source).encode("utf-8") for _ in range(3)]
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])


if __name__ == "__main__":
    unittest.main()
