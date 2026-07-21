from __future__ import annotations

import unittest

from sagekit.change_control import RunState
from sagekit.execution_limits import ExecutionLimits
from sagekit.review import (
    Priority,
    ReviewFinding,
    ReviewReport,
    ReviewState,
    accept_initial_report,
    evaluate_corrective_rereview,
)


def finding(
    finding_id: str,
    *,
    root: str = "same-root",
    priority: Priority = Priority.P1,
    category: str = "authority",
) -> ReviewFinding:
    return ReviewFinding(finding_id, priority, category, root)


class CorrectiveReviewConvergenceTests(unittest.TestCase):
    def test_fixed_rereview_limit_does_not_force_handoff(self) -> None:
        original = ReviewReport("scope", (finding("F-1"),))
        state = accept_initial_report(
            ReviewState(), original, ExecutionLimits(corrective_re_review_rounds=0)
        ).state

        first = evaluate_corrective_rereview(
            state,
            original,
            original,
            ExecutionLimits(corrective_re_review_rounds=0),
        )

        self.assertEqual(RunState.CONTINUE, first.outcome)
        self.assertNotEqual(RunState.HANDOFF_READY, first.outcome)

    def test_two_consecutive_no_progress_rounds_block_same_root(self) -> None:
        original = ReviewReport("scope", (finding("F-1"),))
        state = accept_initial_report(ReviewState(), original, ExecutionLimits()).state
        first = evaluate_corrective_rereview(
            state, original, original, ExecutionLimits()
        )
        second = evaluate_corrective_rereview(
            first.state, original, original, ExecutionLimits()
        )

        self.assertEqual(RunState.CONTINUE, first.outcome)
        self.assertEqual(RunState.BLOCKED, second.outcome)

    def test_progress_is_compared_with_previous_round(self) -> None:
        original = ReviewReport("scope", (finding("F-1"), finding("F-2")))
        reduced = ReviewReport("scope", (finding("F-1"),))
        state = accept_initial_report(ReviewState(), original, ExecutionLimits()).state

        progressed = evaluate_corrective_rereview(
            state, original, reduced, ExecutionLimits()
        )
        stalled_once = evaluate_corrective_rereview(
            progressed.state, original, reduced, ExecutionLimits()
        )
        stalled_twice = evaluate_corrective_rereview(
            stalled_once.state, original, reduced, ExecutionLimits()
        )

        self.assertEqual(RunState.CONTINUE, progressed.outcome)
        self.assertEqual(RunState.CONTINUE, stalled_once.outcome)
        self.assertEqual(RunState.BLOCKED, stalled_twice.outcome)

    def test_new_blocking_root_requires_human_decision(self) -> None:
        original = ReviewReport("scope", (finding("F-1"),))
        changed = ReviewReport("scope", (finding("F-2", root="new-root"),))
        state = accept_initial_report(ReviewState(), original, ExecutionLimits()).state

        result = evaluate_corrective_rereview(
            state, original, changed, ExecutionLimits()
        )

        self.assertEqual(RunState.HUMAN_DECISION_REQUIRED, result.outcome)

    def test_same_finding_nonblocking_severity_increase_requires_human_decision(
        self,
    ) -> None:
        for original_priority in (Priority.P2, Priority.P3):
            for escalated_priority in (Priority.P0, Priority.P1):
                with self.subTest(
                    original_priority=original_priority,
                    escalated_priority=escalated_priority,
                ):
                    original = ReviewReport(
                        "scope",
                        (
                            finding(
                                "F-1",
                                priority=original_priority,
                                category="documentation",
                            ),
                        ),
                    )
                    escalated = ReviewReport(
                        "scope", (finding("F-1", priority=escalated_priority),)
                    )
                    state = accept_initial_report(
                        ReviewState(), original, ExecutionLimits()
                    ).state

                    result = evaluate_corrective_rereview(
                        state, original, escalated, ExecutionLimits()
                    )

                    self.assertEqual(
                        RunState.HUMAN_DECISION_REQUIRED, result.outcome
                    )
                    self.assertEqual(escalated.findings, result.blocking_findings)

    def test_same_finding_becoming_blocking_p2_requires_human_decision(self) -> None:
        for category in ("authority", "safety", "validator"):
            with self.subTest(category=category):
                original = ReviewReport(
                    "scope",
                    (finding("F-1", priority=Priority.P3, category="documentation"),),
                )
                escalated = ReviewReport(
                    "scope", (finding("F-1", priority=Priority.P2, category=category),)
                )
                state = accept_initial_report(
                    ReviewState(), original, ExecutionLimits()
                ).state

                result = evaluate_corrective_rereview(
                    state, original, escalated, ExecutionLimits()
                )

                self.assertEqual(RunState.HUMAN_DECISION_REQUIRED, result.outcome)
                self.assertEqual(escalated.findings, result.blocking_findings)

    def test_root_cause_state_is_isolated_by_scope(self) -> None:
        scope_a = ReviewReport(
            "scope-a", (finding("F-1", priority=Priority.P2),)
        )
        scope_b = ReviewReport(
            "scope-b", (finding("F-2", priority=Priority.P1),)
        )
        state = accept_initial_report(ReviewState(), scope_a, ExecutionLimits()).state
        state = accept_initial_report(state, scope_b, ExecutionLimits()).state

        result = evaluate_corrective_rereview(
            state,
            scope_a,
            scope_a,
            ExecutionLimits(repeated_root_cause_without_progress=1),
        )

        self.assertEqual(RunState.BLOCKED, result.outcome)
        self.assertEqual(
            {"same-root": (1, 2)},
            result.state.root_cause_status_by_scope["scope-a"],
        )
        self.assertEqual(
            {"same-root": (1, 3)},
            result.state.root_cause_status_by_scope["scope-b"],
        )


if __name__ == "__main__":
    unittest.main()
