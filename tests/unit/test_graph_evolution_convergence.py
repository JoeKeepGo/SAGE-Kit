from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest
from unittest.mock import patch

from sagekit import convergence
from sagekit.change_control import RunState
from sagekit.convergence import PreauthorizedConvergenceAuthority
from sagekit.graph_evolution_convergence import (
    GraphEvolutionConvergenceCode,
    GraphEvolutionConvergenceEvidence,
    evaluate_graph_evolution_convergence,
)


def authority() -> PreauthorizedConvergenceAuthority:
    return PreauthorizedConvergenceAuthority(
        authority_id="authority/stage6",
        mode="preauthorized",
        execution_scope="graph/spec",
        root_cause_family="verification-gap",
        allowed_paths=("sagekit/", "tests/unit/"),
        invariant="the accepted graph contract remains authoritative",
        semantic_change_policy="implementation-preserving-only",
        targeted_review_required=True,
        stop_conditions=("two no-progress rounds",),
        approved_by="project-manager",
        authority_ref="decision/stage6",
    )


def evidence(
    count: int = 2,
    *,
    severity: int | None = 2,
    root_cause_id: str = "root-cause/review-001",
    **overrides: object,
) -> GraphEvolutionConvergenceEvidence:
    values: dict[str, object] = {
        "execution_scope": "graph/spec",
        "root_cause_family": "verification-gap",
        "root_cause_id": root_cause_id,
        "finding_count": count,
        "finding_severity": severity,
        "evidence_refs": ("evidence/stage5/failure-001",),
        "affected_scope": ("sagekit/graph_contract.py",),
        "targeted_review_closed": True,
    }
    values.update(overrides)
    return GraphEvolutionConvergenceEvidence(**values)


class GraphEvolutionConvergenceTests(unittest.TestCase):
    def test_same_root_blocks_only_on_second_no_progress_round(self) -> None:
        initial = evaluate_graph_evolution_convergence(authority(), evidence())
        first = evaluate_graph_evolution_convergence(
            authority(), evidence(), previous=initial.state
        )
        second = evaluate_graph_evolution_convergence(
            authority(), evidence(), previous=first.state
        )

        self.assertEqual(GraphEvolutionConvergenceCode.CONTINUE, first.code)
        self.assertEqual(1, first.state.no_progress_rounds)
        self.assertEqual(
            GraphEvolutionConvergenceCode.BLOCKED_NO_PROGRESS, second.code
        )
        self.assertEqual(RunState.BLOCKED, second.run_state)
        self.assertEqual(2, second.state.no_progress_rounds)

    def test_open_targeted_review_hands_off_without_counting_progress(self) -> None:
        initial = evaluate_graph_evolution_convergence(authority(), evidence())
        result = evaluate_graph_evolution_convergence(
            authority(),
            evidence(targeted_review_closed=False),
            previous=initial.state,
        )

        self.assertEqual(GraphEvolutionConvergenceCode.HANDOFF, result.code)
        self.assertEqual(RunState.HANDOFF_READY, result.run_state)
        self.assertEqual(0, result.state.no_progress_rounds)

    def test_worsening_requires_project_manager_decision(self) -> None:
        initial = evaluate_graph_evolution_convergence(authority(), evidence())
        result = evaluate_graph_evolution_convergence(
            authority(), evidence(3, severity=3), previous=initial.state
        )

        self.assertEqual(
            GraphEvolutionConvergenceCode.PM_DECISION_REQUIRED, result.code
        )
        self.assertEqual("findings-increased", result.trend)

    def test_closed_targeted_review_resets_on_new_evidence_layer(self) -> None:
        initial = evaluate_graph_evolution_convergence(authority(), evidence())
        stalled = evaluate_graph_evolution_convergence(
            authority(), evidence(), previous=initial.state
        )
        result = evaluate_graph_evolution_convergence(
            authority(),
            evidence(
                3,
                severity=3,
                root_cause_id="root-cause/review-002",
                evidence_refs=("evidence/stage5/failure-002",),
                next_evidence_layer_exposed=True,
            ),
            previous=stalled.state,
        )

        self.assertEqual(GraphEvolutionConvergenceCode.CONTINUE, result.code)
        self.assertEqual("next-layer-exposed", result.trend)
        self.assertEqual(0, result.state.no_progress_rounds)

    def test_no_change_acceptance_requires_bound_evidence_and_closed_review(self) -> None:
        result = evaluate_graph_evolution_convergence(
            authority(),
            evidence(
                0,
                severity=None,
                no_change_decision=True,
                evidence_refs=("evidence/stage5/graph-sufficient-001",),
            ),
        )

        self.assertEqual(
            GraphEvolutionConvergenceCode.NO_CHANGE_ACCEPTED, result.code
        )
        self.assertEqual(RunState.STOP, result.run_state)
        self.assertEqual(0, result.state.no_progress_rounds)

    def test_unsubstantiated_no_change_counts_as_no_progress(self) -> None:
        initial = evaluate_graph_evolution_convergence(authority(), evidence())
        first = evaluate_graph_evolution_convergence(
            authority(),
            evidence(no_change_decision=True, evidence_refs=()),
            previous=initial.state,
        )
        second = evaluate_graph_evolution_convergence(
            authority(),
            evidence(no_change_decision=True, evidence_refs=()),
            previous=first.state,
        )

        self.assertEqual(GraphEvolutionConvergenceCode.CONTINUE, first.code)
        self.assertEqual(1, first.state.no_progress_rounds)
        self.assertEqual(
            GraphEvolutionConvergenceCode.BLOCKED_NO_PROGRESS, second.code
        )

    def test_initial_unsubstantiated_no_change_records_first_stall(self) -> None:
        result = evaluate_graph_evolution_convergence(
            authority(),
            evidence(no_change_decision=True, evidence_refs=()),
        )

        self.assertEqual(GraphEvolutionConvergenceCode.CONTINUE, result.code)
        self.assertEqual(1, result.state.no_progress_rounds)

    def test_decision_binds_exact_evidence_and_does_not_mutate_graph(self) -> None:
        current = evidence()
        result = evaluate_graph_evolution_convergence(authority(), current)

        self.assertIs(current, result.evidence)
        self.assertEqual(current.evidence_refs, result.state.evidence_refs)
        self.assertEqual(current.affected_scope, result.state.affected_scope)
        self.assertFalse(hasattr(result, "target_graph"))
        self.assertFalse(hasattr(result, "graph_mutation"))
        self.assertFalse(hasattr(result, "authority"))
        with self.assertRaises(FrozenInstanceError):
            result.state.no_progress_rounds = 9  # type: ignore[misc]

    def test_evidence_is_typed_and_bounded(self) -> None:
        with self.assertRaises(ValueError):
            evidence(evidence_refs=tuple(f"evidence/{index}" for index in range(101)))
        with self.assertRaises(ValueError):
            evidence(finding_count=-1)
        with self.assertRaises(ValueError):
            evidence(targeted_review_closed="yes")

    def test_repeated_evaluation_is_deterministic(self) -> None:
        current = evidence()
        first = evaluate_graph_evolution_convergence(authority(), current)
        second = evaluate_graph_evolution_convergence(authority(), current)

        self.assertEqual(first, second)

    def test_existing_convergence_evaluator_is_reused(self) -> None:
        with patch.object(
            convergence,
            "evaluate_convergence",
            wraps=convergence.evaluate_convergence,
        ) as evaluator:
            evaluate_graph_evolution_convergence(authority(), evidence())

        evaluator.assert_called_once()


if __name__ == "__main__":
    unittest.main()
