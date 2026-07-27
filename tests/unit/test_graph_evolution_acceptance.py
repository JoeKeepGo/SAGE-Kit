from __future__ import annotations

import copy
import time
import unittest
from unittest.mock import patch

from sagekit import evidence, graph_evolution_contract
from sagekit.convergence import PreauthorizedConvergenceAuthority
from sagekit.evidence import EvidenceLineageOutcome
from sagekit.graph_evolution_acceptance import (
    GraphEvolutionAcceptanceCode,
    GraphEvolutionAcceptanceOutcome,
    resolve_graph_evolution_acceptance,
)
from sagekit.graph_evolution_convergence import (
    GraphEvolutionConvergenceEvidence,
    evaluate_graph_evolution_convergence,
)
from sagekit.graph_evolution_contract import canonical_graph_evolution_digest
from sagekit.graph_evolution_proposal import build_graph_evolution_proposal
from sagekit.review import (
    DeterministicEvaluatorAssignment,
    DeterministicReceipt,
    EvaluatorKind,
    EvaluatorSelection,
    ReceiptStatus,
    ReviewTopology,
)
from tests.unit.test_graph_evolution_proposal import (
    OPERATIONS,
    parent_graph,
    preauthorization,
    request,
)


ORACLE_REF = "oracle/graph-evolution"
INPUT_FINGERPRINT = "1" * 64
RESULT_FINGERPRINT = "2" * 64


def convergence_authority() -> PreauthorizedConvergenceAuthority:
    return PreauthorizedConvergenceAuthority(
        authority_id="pm/rebuild",
        mode="preauthorized",
        execution_scope="graph/spec",
        root_cause_family="verification-gap",
        allowed_paths=("sagekit/", "tests/unit/"),
        invariant="the accepted graph contract remains authoritative",
        semantic_change_policy="implementation-preserving-only",
        targeted_review_required=True,
        stop_conditions=("two no-progress rounds",),
        approved_by="project-manager",
        authority_ref="authority/stage6",
    )


def convergence_evidence(
    *,
    no_change: bool = False,
    evidence_refs: tuple[str, ...] = ("evidence/stage5/failure-001",),
) -> GraphEvolutionConvergenceEvidence:
    return GraphEvolutionConvergenceEvidence(
        execution_scope="graph/spec",
        root_cause_family="verification-gap",
        root_cause_id="root-cause/review-001",
        finding_count=0 if no_change else 1,
        finding_severity=None if no_change else 1,
        evidence_refs=evidence_refs,
        affected_scope=("sagekit/graph_contract.py",),
        targeted_review_closed=True,
        no_change_decision=no_change,
    )


def evaluator_inputs():
    selection = EvaluatorSelection(
        EvaluatorKind.DETERMINISTIC,
        ReviewTopology.LIGHT,
        ORACLE_REF,
    )
    assignment = DeterministicEvaluatorAssignment(
        ORACLE_REF,
        INPUT_FINGERPRINT,
        RESULT_FINGERPRINT,
    )
    receipt = DeterministicReceipt(
        ORACLE_REF,
        INPUT_FINGERPRINT,
        RESULT_FINGERPRINT,
    )
    return selection, receipt, assignment


def lineage_outcome(*, reuse_final: bool = False) -> EvidenceLineageOutcome:
    disposition = "REUSE" if reuse_final else "INVALIDATE"
    reasons = ["FINGERPRINTS_MATCH"] if reuse_final else ["CANDIDATE_CHANGED"]
    return EvidenceLineageOutcome._from_result(
        {
            "schema_id": "urn:sagekit:evidence-lineage:v1:result",
            "schema_version": 1,
            "graph_id": "graph/spec",
            "graph_generation": 7,
            "graph_digest": request("ADD_VERIFICATION")["parent_graph_digest"],
            "decisions": {
                "evidence/final": {
                    "disposition": disposition,
                    "input_fingerprint": "3" * 64,
                    "output_fingerprint": "4" * 64,
                    "changed_edge_types": (
                        [] if reuse_final else ["CANDIDATE"]
                    ),
                    "reason_codes": reasons,
                }
            },
            "final_evidence_node_id": "evidence/final",
        }
    )


def resolve(
    operation: str,
    *,
    req=None,
    preauth=None,
    lineage=None,
    current_evidence=None,
    previous=None,
    pm_acceptance=None,
    proposal_outcome=None,
    authority=None,
):
    selection, receipt, assignment = evaluator_inputs()
    lineage = (
        lineage_outcome(reuse_final=operation == "NO_CHANGE")
        if lineage is None
        else lineage
    )
    with patch.object(
        evidence,
        "resolve_evidence_lineage",
        return_value=lineage,
    ):
        return resolve_graph_evolution_acceptance(
            parent_graph(),
            request(operation) if req is None else req,
            preauthorization() if preauth is None else preauth,
            {"frozen": "lineage-source"},
            convergence_authority() if authority is None else authority,
            (
                convergence_evidence(no_change=operation == "NO_CHANGE")
                if current_evidence is None
                else current_evidence
            ),
            selection,
            receipt,
            assignment,
            previous_convergence=previous,
            pm_acceptance=pm_acceptance,
            proposal_outcome=proposal_outcome,
        )


def accepted_pm_record(outcome: GraphEvolutionAcceptanceOutcome) -> dict:
    proposal = outcome.proposal
    assert proposal is not None
    preauth = preauthorization()
    proposal_digest = canonical_graph_evolution_digest("proposal", proposal)
    preauth_digest = canonical_graph_evolution_digest(
        "preauthorization",
        preauth,
    )
    return {
        "schema_id": "urn:sagekit:graph-evolution:v1:acceptance",
        "schema_version": 1,
        "acceptance_id": f"acceptance/pm/{proposal_digest}",
        "proposal_digest": proposal_digest,
        "preauthorization_digest": preauth_digest,
        "decision": "ACCEPTED",
        "authority": copy.deepcopy(preauth["authority"]),
        "evaluator": {
            "node_id": preauth["evaluator"]["node_id"],
            "role": preauth["evaluator"]["role"],
            "decision": "APPROVE",
            "decision_ref": "decision/independent-review",
        },
        "reason_code": "WITHIN_PREAUTHORIZATION",
        "decision_refs": [
            "decision/independent-review",
            "decision/project-manager",
        ],
    }


class GraphEvolutionAcceptanceTests(unittest.TestCase):
    def test_all_six_operations_resolve_without_runtime_authority(self) -> None:
        started = time.monotonic()
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                outcome = resolve(operation)
                expected = (
                    GraphEvolutionAcceptanceCode.NO_CHANGE_ACCEPTED
                    if operation == "NO_CHANGE"
                    else GraphEvolutionAcceptanceCode.AUTO_ACCEPTED
                )
                self.assertEqual(expected, outcome.code, outcome.error)
                self.assertIsInstance(outcome, GraphEvolutionAcceptanceOutcome)
                self.assertIsNotNone(outcome.acceptance)
                self.assertIsNotNone(outcome.graph_evolution_result)
                for grant in (
                    "grants_execution_authority",
                    "grants_graph_mutation_authority",
                    "grants_gate_authority",
                    "grants_write_authority",
                    "grants_acceptance_authority",
                ):
                    self.assertIs(outcome.result[grant], False)
                if operation == "NO_CHANGE":
                    self.assertNotIn("target_generation", outcome.proposal)
                    self.assertNotIn(
                        "target_generation",
                        outcome.graph_evolution_result,
                    )
        self.assertLess(time.monotonic() - started, 60)

    def test_c2_and_source_authority_changes_require_external_pm_decision(self) -> None:
        req = request("ADD_VERIFICATION")
        req["change_class"] = "C2"
        preauth = preauthorization()
        preauth["allowed_change_classes"].append("C2")

        required = resolve("ADD_VERIFICATION", req=req, preauth=preauth)
        self.assertEqual(
            GraphEvolutionAcceptanceCode.PM_DECISION_REQUIRED,
            required.code,
        )

        pm_record = accepted_pm_record(required)
        pm_record["preauthorization_digest"] = canonical_graph_evolution_digest(
            "preauthorization",
            preauth,
        )
        accepted = resolve(
            "ADD_VERIFICATION",
            req=req,
            preauth=preauth,
            pm_acceptance=pm_record,
        )
        self.assertEqual(GraphEvolutionAcceptanceCode.PM_ACCEPTED, accepted.code)

        changed_authority = request("ADD_VERIFICATION")
        changed_authority["authority"]["authority_id"] = "pm/replacement"
        self.assertEqual(
            GraphEvolutionAcceptanceCode.PM_DECISION_REQUIRED,
            resolve("ADD_VERIFICATION", req=changed_authority).code,
        )

        wrong_convergence_authority = PreauthorizedConvergenceAuthority(
            **{
                **convergence_authority().to_dict(),
                "authority_id": "pm/replacement",
            }
        )
        self.assertEqual(
            GraphEvolutionAcceptanceCode.PM_DECISION_REQUIRED,
            resolve(
                "ADD_VERIFICATION",
                authority=wrong_convergence_authority,
            ).code,
        )

    def test_proposer_cannot_accept_or_evaluate_its_own_proposal(self) -> None:
        preauth = preauthorization()
        preauth["evaluator"] = {
            "node_id": "node/controller",
            "role": "Controller",
            "permission": "WRITE_AUTHORIZED",
            "authority_ref": "authority/evaluator",
            "independent": True,
        }

        outcome = resolve("ADD_VERIFICATION", preauth=preauth)

        self.assertEqual(GraphEvolutionAcceptanceCode.REJECTED, outcome.code)
        self.assertEqual(ReceiptStatus.INDEPENDENT_EVALUATOR_REQUIRED, outcome.receipt_status)

    def test_sources_are_snapshotted_before_validation(self) -> None:
        req = request("ADD_VERIFICATION")
        original = copy.deepcopy(req)
        real_validator = graph_evolution_contract.validate_graph_evolution_request

        def mutate_source_after_snapshot(snapshot):
            req["change_class"] = "C2"
            return real_validator(snapshot)

        with patch.object(
            graph_evolution_contract,
            "validate_graph_evolution_request",
            side_effect=mutate_source_after_snapshot,
        ):
            outcome = resolve("ADD_VERIFICATION", req=req)

        self.assertEqual(GraphEvolutionAcceptanceCode.AUTO_ACCEPTED, outcome.code)
        self.assertEqual(original["change_class"], outcome.proposal["change_class"])
        exposed = outcome.result
        exposed["proposal"]["target_graph"]["nodes"].clear()
        self.assertTrue(outcome.proposal["target_graph"]["nodes"])

    def test_mutating_candidate_cannot_reuse_final_evidence(self) -> None:
        stale = resolve(
            "ADD_VERIFICATION",
            lineage=lineage_outcome(reuse_final=True),
        )
        fresh = resolve(
            "ADD_VERIFICATION",
            lineage=lineage_outcome(reuse_final=False),
        )

        self.assertEqual(GraphEvolutionAcceptanceCode.REJECTED, stale.code)
        self.assertEqual(GraphEvolutionAcceptanceCode.AUTO_ACCEPTED, fresh.code)
        self.assertIn("FINAL_EVIDENCE_REUSE_FORBIDDEN", stale.issue_codes)

    def test_stale_proposal_cannot_be_substituted(self) -> None:
        lineage = lineage_outcome(reuse_final=False)
        stale = build_graph_evolution_proposal(
            parent_graph(),
            request("ADD_VERIFICATION"),
            preauthorization(),
            lineage,
        )

        outcome = resolve(
            "ADD_INVESTIGATION",
            lineage=lineage,
            proposal_outcome=stale,
        )

        self.assertEqual(
            GraphEvolutionAcceptanceCode.PM_DECISION_REQUIRED,
            outcome.code,
        )
        self.assertIn("STALE_PROPOSAL", outcome.issue_codes)

    def test_second_no_progress_round_blocks_without_acceptance(self) -> None:
        current = convergence_evidence(
            no_change=True,
            evidence_refs=(),
        )
        initial = evaluate_graph_evolution_convergence(
            convergence_authority(),
            current,
        )
        first = evaluate_graph_evolution_convergence(
            convergence_authority(),
            current,
            previous=initial.state,
        )

        outcome = resolve(
            "NO_CHANGE",
            current_evidence=current,
            previous=first.state,
        )

        self.assertEqual(
            GraphEvolutionAcceptanceCode.BLOCKED_NO_PROGRESS,
            outcome.code,
        )
        self.assertIsNone(outcome.acceptance)
        self.assertIsNone(outcome.graph_evolution_result)

    def test_outcome_is_resolver_created_and_deterministic(self) -> None:
        first = resolve("ADD_VERIFICATION")
        second = resolve("ADD_VERIFICATION")
        self.assertEqual(first, second)
        with self.assertRaises(ValueError):
            GraphEvolutionAcceptanceOutcome()
        with self.assertRaises(AttributeError):
            first._result_snapshot = None


if __name__ == "__main__":
    unittest.main()
