from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

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
from sagekit.normalization import (
    apply_auto_normalization,
    classify_bytes,
    non_whitespace_digest,
)


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
    return {
        "decision": "reject",
        "state": decision.state.value,
        "allowed_to_run": decision.allowed_to_run,
        "final_runs_after": decision.counters.final_full_suite_runs.get(
            candidate.digest,
            0,
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
    return {
        "selected_scope": selected_scope,
        "full_review": selected_scope == "full",
        "state_before_targeted_close": before_close.state.value,
        "state_after_targeted_close": (
            RunState.CONTINUE.value if after_close is None else after_close.state.value
        ),
    }


def _deterministic_whitespace_adapter(case: dict[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
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
    return {
        "decision": "AUTO_NORMALIZATION_CORRECTIVE",
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
                self.assertEqual(case["expected"], ADAPTERS[case["adapter"]](case))


if __name__ == "__main__":
    unittest.main()
