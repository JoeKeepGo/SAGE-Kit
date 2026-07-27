from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

from sagekit.candidate import CandidateAssessment, CandidateFingerprint
from sagekit.change_control import RunState
from sagekit.convergence import (
    ConvergenceEvidence,
    PreauthorizedConvergenceAuthority,
    evaluate_convergence_stops,
)
from sagekit.execution_limits import (
    ExecutionCounters,
    ExecutionLimits,
    VerificationKind,
    VerificationPreflight,
    VerificationPreflightCheck,
    begin_verification_run,
    prepare_verification_run,
)
from sagekit.evidence import (
    canonical_node_input_fingerprint,
    resolve_evidence_lineage,
)
from sagekit.graph_contract import canonical_graph_digest
from sagekit.normalization import (
    apply_auto_normalization,
    classify_bytes,
    non_whitespace_digest,
)
from sagekit.review import EvaluatorRisk, select_evaluator


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = REPO_ROOT / "docs/design/rebuild/SCENARIO_EVAL_CANDIDATES.json"
FIXTURE_PATH = (
    REPO_ROOT / "tests/fixtures/stage5_observed_failure_corpus_v1.json"
)
STAGE_5_ADAPTERS = {
    "duplicate-full-review",
    "status-only-targeted-review",
    "deterministic-whitespace-normalization",
}


def _strict_json(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    loaded = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicates,
    )
    if not isinstance(loaded, dict):
        raise TypeError("corpus root must be an object")
    return loaded


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json_sha256(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_projection(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _sha256_text(item["id"]): {
            "provenance_status": item["provenance_status"],
            "admission_status": item["admission_status"],
            "first_relevant_stage": item["first_relevant_stage"],
            "source_ref_sha256": [
                _sha256_text(reference) for reference in item["existing_test_refs"]
            ],
        }
        for item in source["scenarios"]
    }


def _candidate() -> CandidateFingerprint:
    return CandidateFingerprint(
        head_sha="1" * 40,
        diff_hash="2" * 64,
        contract_digest="3" * 64,
        dependency_digest="4" * 64,
        review_closed=True,
        corrective_batch_closed=True,
    )


def _lineage_graph() -> dict[str, Any]:
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:graph",
        "schema_version": 1,
        "graph_id": "graph/stage5-corpus",
        "generation": 1,
        "source_authority": {
            "identity": "Stage 5 corpus fixture",
            "reference": "stage5-observed-failure-corpus-v1",
        },
        "governance_level": "Standard",
        "autonomy_level": "turn-based",
        "human_gates": [],
        "nodes": [
            {
                "id": "node/review",
                "role": "stage5-corpus-review",
                "depends_on": [],
                "permission": "READ_ONLY_REVIEW",
                "verifier": "stage5-corpus-oracle",
                "output_contract": "urn:sagekit:graph-contract:v1:node-result",
                "resources": [],
                "classification": "required",
            }
        ],
        "joins": [],
    }


def _refresh_lineage_fingerprints(snapshot: dict[str, Any]) -> None:
    nodes = {
        item["lineage_node_id"]: item for item in snapshot["lineage_nodes"]
    }
    incoming: dict[str, list[dict[str, str]]] = {
        node_id: [] for node_id in nodes
    }
    for edge in snapshot["lineage_edges"]:
        source = nodes[edge["source_node_id"]]
        edge["source_output_fingerprint"] = source["output_fingerprint"]
        incoming[edge["target_node_id"]].append(
            {
                "edge_type": edge["edge_type"],
                "source_node_id": edge["source_node_id"],
                "source_output_fingerprint": source["output_fingerprint"],
            }
        )
    for node_id, node in nodes.items():
        node["input_fingerprint"] = canonical_node_input_fingerprint(
            snapshot["graph_binding"],
            incoming[node_id],
        )
    for edge in snapshot["lineage_edges"]:
        edge["target_input_fingerprint"] = nodes[edge["target_node_id"]][
            "input_fingerprint"
        ]


def _lineage_snapshot(
    candidate_graph: dict[str, Any],
    path_material: bytes,
) -> dict[str, Any]:
    snapshot = {
        "graph_binding": {
            "graph_id": candidate_graph["graph_id"],
            "graph_generation": candidate_graph["generation"],
            "graph_digest": canonical_graph_digest(candidate_graph),
        },
        "stage4_bindings": {
            "ready_input_digest": "1" * 64,
            "transition_bindings": [
                {
                    "node_id": "node/review",
                    "transition_input_digest": "2" * 64,
                    "node_result_digest": "3" * 64,
                }
            ],
        },
        "lineage_nodes": [
            {
                "lineage_node_id": "path/observed",
                "owner_kind": "PATH",
                "owner_id": "observed.json",
                "input_fingerprint": "0" * 64,
                "output_fingerprint": hashlib.sha256(path_material).hexdigest(),
            },
            {
                "lineage_node_id": "node/review",
                "owner_kind": "GRAPH_NODE",
                "owner_id": "node/review",
                "input_fingerprint": "0" * 64,
                "output_fingerprint": "3" * 64,
            },
            {
                "lineage_node_id": "candidate/release",
                "owner_kind": "CANDIDATE",
                "owner_id": "candidate/release",
                "input_fingerprint": "0" * 64,
                "output_fingerprint": "4" * 64,
            },
            {
                "lineage_node_id": "evidence/final",
                "owner_kind": "EVIDENCE",
                "owner_id": "evidence/final",
                "input_fingerprint": "0" * 64,
                "output_fingerprint": "5" * 64,
            },
        ],
        "lineage_edges": [
            {
                "source_node_id": "path/observed",
                "target_node_id": "node/review",
                "edge_type": "PATH",
                "source_output_fingerprint": "0" * 64,
                "target_input_fingerprint": "0" * 64,
            },
            {
                "source_node_id": "candidate/release",
                "target_node_id": "evidence/final",
                "edge_type": "CANDIDATE",
                "source_output_fingerprint": "0" * 64,
                "target_input_fingerprint": "0" * 64,
            },
        ],
        "join_integrations": [],
        "final_evidence_node_id": "evidence/final",
    }
    _refresh_lineage_fingerprints(snapshot)
    return snapshot


def _stage5_api_fields(
    evaluator_input: dict[str, Any],
    baseline_path: bytes,
    candidate_path: bytes,
) -> dict[str, Any]:
    selection = select_evaluator(
        tuple(EvaluatorRisk(item) for item in evaluator_input["risk_flags"]),
        machine_oracle_ref=evaluator_input["machine_oracle_ref"],
        semantic_judgment_required=evaluator_input[
            "semantic_judgment_required"
        ],
    )
    candidate_graph = _lineage_graph()
    baseline = _lineage_snapshot(candidate_graph, baseline_path)
    candidate = _lineage_snapshot(candidate_graph, candidate_path)
    outcome = resolve_evidence_lineage(
        candidate_graph,
        {
            "schema_id": "urn:sagekit:evidence-lineage:v1:input",
            "schema_version": 1,
            "baseline": baseline,
            "candidate": candidate,
        },
    )
    if outcome.error is not None or outcome.result is None:
        raise AssertionError(f"synthetic Stage 5 lineage failed: {outcome.error}")
    return {
        "evaluator": selection.evaluator.value,
        "topology": selection.topology.value,
        "oracle_ref": selection.oracle_ref,
        "lineage_disposition": outcome.result["decisions"]["node/review"][
            "disposition"
        ],
    }


def _decode_lineage_paths(inputs: dict[str, Any]) -> tuple[bytes, bytes]:
    lineage = inputs["lineage"]
    return (
        base64.b64decode(lineage["baseline_path_b64"], validate=True),
        base64.b64decode(lineage["candidate_path_b64"], validate=True),
    )


def _bounded_material(chunks: list[bytes]) -> bytes:
    return b"".join(len(chunk).to_bytes(4, "big") + chunk for chunk in chunks)


def _duplicate_full_review_adapter(case: dict[str, Any]) -> dict[str, Any]:
    candidate = _candidate()
    inputs = case["input"]
    prior_candidate = (
        candidate
        if inputs["candidate_unchanged"]
        else replace(candidate, head_sha="5" * 40)
    )
    counters = ExecutionCounters(
        final_full_suite_runs={
            prior_candidate.digest: inputs["prior_final_runs"]
        }
    )
    assessment = CandidateAssessment(
        True,
        RunState.CONTINUE,
        "synthetic candidate remains unchanged",
    )
    prepared = prepare_verification_run(
        counters,
        VerificationKind(inputs["proposed_run_kind"]),
        VerificationPreflight(
            "attempt-002",
            candidate.digest,
            (VerificationPreflightCheck("ready", True),),
        ),
        candidate=candidate,
        assessment=assessment,
    )
    decision = begin_verification_run(
        prepared.counters,
        ExecutionLimits(),
        "attempt-002",
        candidate=candidate,
        assessment=assessment,
    )
    baseline_path, candidate_path = _decode_lineage_paths(inputs)
    return {
        "decision": "reject",
        "state": decision.state.value,
        "allowed_to_run": decision.allowed_to_run,
        "final_runs_after": decision.counters.final_full_suite_runs.get(
            candidate.digest,
            0,
        ),
        **_stage5_api_fields(
            inputs["evaluator"],
            baseline_path,
            candidate_path,
        ),
    }


def _status_only_targeted_review_adapter(case: dict[str, Any]) -> dict[str, Any]:
    change = case["input"]
    selected_scope = (
        "targeted"
        if change["initial_review_complete"]
        and change["changed_fields"] == ["status"]
        and not change["semantic_change"]
        and not change["authority_change"]
        else "full"
    )
    authority = PreauthorizedConvergenceAuthority(
        authority_id="authority-001",
        mode="preauthorized",
        execution_scope="scope-001",
        root_cause_family="status-consistency",
        allowed_paths=("record.json",),
        invariant="status correction does not change semantics or authority",
        semantic_change_policy="implementation-preserving-only",
        targeted_review_required=True,
        stop_conditions=("semantic or authority change",),
        approved_by="request",
        authority_ref="reference-001",
    )
    evidence = ConvergenceEvidence(
        execution_scope=authority.execution_scope,
        root_cause_family=authority.root_cause_family,
        root_cause_id="status-001",
        finding_count=0,
        finding_severity=0,
        semantic_change="implementation-preserving",
        targeted_review_closed=False,
    )
    before_close = evaluate_convergence_stops(
        authority,
        evidence,
        previous_no_progress_rounds=0,
    )
    after_close = evaluate_convergence_stops(
        authority,
        replace(evidence, targeted_review_closed=True),
        previous_no_progress_rounds=0,
    )
    baseline_path, candidate_path = _decode_lineage_paths(change)
    return {
        "selected_scope": selected_scope,
        "full_review": selected_scope == "full",
        "state_before_targeted_close": before_close.state.value,
        "state_after_targeted_close": (
            RunState.CONTINUE.value if after_close is None else after_close.state.value
        ),
        **_stage5_api_fields(
            change["evaluator"],
            baseline_path,
            candidate_path,
        ),
    }


def _deterministic_whitespace_adapter(case: dict[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    normalized_vectors: list[bytes] = []
    for vector in case["input"]["vectors"]:
        before = base64.b64decode(vector["before_b64"], validate=True)
        after = base64.b64decode(vector["after_b64"], validate=True)
        findings = classify_bytes("sample.py", before, after)
        selected = tuple(item for item in findings if item.auto_eligible)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "sample.py"
            target.write_bytes(after)
            receipt = apply_auto_normalization(
                root,
                selected,
                writable_paths=("sample.py",),
            )
            normalized = target.read_bytes()
        normalized_vectors.append(normalized)
        results.append(
            {
                "kind": vector["kind"],
                "auto_eligible": any(
                    item.kind.value == vector["kind"] and item.auto_eligible
                    for item in findings
                ),
                "normalized_b64": base64.b64encode(normalized).decode("ascii"),
                "semantic_digest_preserved": (
                    non_whitespace_digest(after)
                    == non_whitespace_digest(normalized)
                    == receipt.non_whitespace_sha256["sample.py"]
                ),
            }
        )
    baseline_vectors = [
        base64.b64decode(value, validate=True)
        for value in case["input"]["lineage_baseline_b64"]
    ]
    return {
        "decision": "AUTO_NORMALIZATION_CORRECTIVE",
        **_stage5_api_fields(
            case["input"]["evaluator"],
            _bounded_material(baseline_vectors),
            _bounded_material(normalized_vectors),
        ),
        "vectors": results,
    }


ADAPTERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "duplicate-full-review": _duplicate_full_review_adapter,
    "status-only-targeted-review": _status_only_targeted_review_adapter,
    "deterministic-whitespace-normalization": _deterministic_whitespace_adapter,
}


class Stage5ObservedFailureCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = _strict_json(SOURCE_PATH)
        cls.corpus = _strict_json(FIXTURE_PATH)
        cls.cases = cls.corpus["cases"]

    def test_fixture_is_bounded_non_authoritative_and_source_bound(self) -> None:
        self.assertEqual(1, self.corpus["schema_version"])
        self.assertEqual("regression_fixture", self.corpus["role"])
        self.assertFalse(self.corpus["normative"])
        self.assertFalse(self.corpus["can_grant_authority"])
        self.assertEqual(5, self.corpus["bounded_stage"])
        self.assertEqual(
            {
                "schema_version",
                "corpus_id",
                "role",
                "normative",
                "can_grant_authority",
                "bounded_stage",
                "source_document_canonical_sha256",
                "cases",
            },
            set(self.corpus),
        )
        self.assertEqual(
            _canonical_json_sha256(self.source),
            self.corpus["source_document_canonical_sha256"],
        )
        self.assertEqual(12, len(self.cases))
        self.assertEqual(12, len({case["case_id"] for case in self.cases}))
        self.assertEqual(
            12,
            len({case["source_scenario_sha256"] for case in self.cases}),
        )

    def test_anonymous_provenance_and_references_match_tracked_candidates(self) -> None:
        expected = _source_projection(self.source)
        actual = {
            case["source_scenario_sha256"]: {
                field: case[field]
                for field in (
                    "provenance_status",
                    "admission_status",
                    "first_relevant_stage",
                    "source_ref_sha256",
                )
            }
            for case in self.cases
        }
        self.assertEqual(expected, actual)
        admitted = [
            case for case in self.cases
            if case["admission_status"] == "admitted_candidate"
        ]
        self.assertEqual(9, len(admitted))
        self.assertEqual(
            {"direct_regression": 7, "observed_failure": 2},
            {
                status: sum(
                    case["provenance_status"] == status for case in admitted
                )
                for status in ("direct_regression", "observed_failure")
            },
        )
        self.assertTrue(all(case["source_ref_sha256"] for case in admitted))

    def test_only_admitted_stage5_cases_have_executable_adapters(self) -> None:
        executable = [
            case for case in self.cases if case["disposition"] == "executable"
        ]
        self.assertEqual(3, len(executable))
        self.assertEqual(
            STAGE_5_ADAPTERS,
            {case["adapter"] for case in executable},
        )
        for case in executable:
            self.assertEqual("admitted_candidate", case["admission_status"])
            self.assertEqual(5, case["first_relevant_stage"])
            self.assertEqual(
                {
                    "case_id",
                    "source_scenario_sha256",
                    "provenance_status",
                    "admission_status",
                    "first_relevant_stage",
                    "source_ref_sha256",
                    "disposition",
                    "adapter",
                    "input",
                    "expected",
                },
                set(case),
            )
            evaluator = case["input"]["evaluator"]
            self.assertEqual(
                {
                    "risk_flags",
                    "machine_oracle_ref",
                    "semantic_judgment_required",
                },
                set(evaluator),
            )
            self.assertLessEqual(len(evaluator["risk_flags"]), 16)
        for case in self.cases:
            if case not in executable:
                self.assertEqual("reference_only", case["disposition"])
                self.assertNotIn("adapter", case)
                self.assertNotIn("input", case)
                self.assertNotIn("expected", case)

    def test_hypotheses_remain_unadmitted_nonblocking_references(self) -> None:
        hypotheses = [
            case for case in self.cases
            if case["admission_status"] == "hypothesis_unadmitted"
        ]
        self.assertEqual(3, len(hypotheses))
        for case in hypotheses:
            self.assertEqual("prospective_hypothesis", case["provenance_status"])
            self.assertEqual("reference_only", case["disposition"])
            self.assertFalse(case["can_block"])
            self.assertFalse(case["test_execution"])
            self.assertNotIn("adapter", case)
        admitted = [
            case for case in self.cases
            if case["admission_status"] == "admitted_candidate"
        ]
        self.assertTrue(all("can_block" not in case for case in admitted))
        self.assertTrue(all("test_execution" not in case for case in admitted))

    def test_other_stages_are_references_without_scenario_rewrites(self) -> None:
        references = [
            case for case in self.cases
            if case["first_relevant_stage"] in {2, 3, 7, 8}
        ]
        self.assertEqual(9, len(references))
        for case in references:
            expected_fields = {
                "case_id",
                "source_scenario_sha256",
                "provenance_status",
                "admission_status",
                "first_relevant_stage",
                "source_ref_sha256",
                "disposition",
            }
            if case["admission_status"] == "hypothesis_unadmitted":
                expected_fields |= {"can_block", "test_execution"}
            self.assertEqual(expected_fields, set(case))

    def test_fixture_does_not_leak_source_paths_or_names(self) -> None:
        fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")
        source_names = [item["id"] for item in self.source["scenarios"]]
        source_refs = [
            reference
            for item in self.source["scenarios"]
            for reference in item["existing_test_refs"]
        ]
        for leaked in (*source_names, *source_refs):
            self.assertNotIn(leaked, fixture_text)
        self.assertNotIn(str(REPO_ROOT), fixture_text)
        self.assertNotIn("\\", fixture_text)
        self.assertNotRegex(fixture_text, r"[A-Za-z]:[/\\]")
        for case in self.cases:
            self.assertRegex(case["source_scenario_sha256"], r"^[0-9a-f]{64}$")
            for reference in case["source_ref_sha256"]:
                self.assertRegex(reference, r"^[0-9a-f]{64}$")

    def test_executable_stage5_cases_match_expected_decisions(self) -> None:
        for case in self.cases:
            if case["disposition"] != "executable":
                continue
            with self.subTest(case=case["case_id"]):
                adapter = ADAPTERS[case["adapter"]]
                observed = adapter(case)
                self.assertEqual(case["expected"], observed)
                self.assertEqual(observed, adapter(case))

    def test_every_executable_adapter_calls_both_stage5_apis(self) -> None:
        executable = [
            case for case in self.cases if case["disposition"] == "executable"
        ]
        with (
            patch(
                f"{__name__}.select_evaluator",
                wraps=select_evaluator,
            ) as evaluator,
            patch(
                f"{__name__}.resolve_evidence_lineage",
                wraps=resolve_evidence_lineage,
            ) as lineage,
        ):
            for case in executable:
                ADAPTERS[case["adapter"]](case)
        self.assertEqual(len(executable), evaluator.call_count)
        self.assertEqual(len(executable), lineage.call_count)


if __name__ == "__main__":
    unittest.main()
