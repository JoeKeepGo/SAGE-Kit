from __future__ import annotations

import dataclasses
import unittest
from unittest.mock import patch

from sagekit.review import (
    DeterministicReceipt,
    EvaluatorKind,
    EvaluatorRisk,
    EvaluatorSelection,
    EvaluatorVerdict,
    FreshContextReceipt,
    Priority,
    ReceiptStatus,
    ReviewFinding,
    ReviewTopology,
    select_evaluator,
    validate_evaluator_receipt,
)


ORACLE_REF = "ci://review/mechanical-status-v1"
INPUT_FINGERPRINT = "1" * 64
RESULT_FINGERPRINT = "2" * 64


class RiskBasedEvaluatorSelectionTests(unittest.TestCase):
    def test_fixed_machine_oracle_without_semantic_judgment_is_deterministic(
        self,
    ) -> None:
        selection = select_evaluator(
            (EvaluatorRisk.MECHANICAL,),
            machine_oracle_ref=ORACLE_REF,
        )

        self.assertEqual(EvaluatorKind.DETERMINISTIC, selection.evaluator)
        self.assertEqual(ReviewTopology.STANDARD, selection.topology)
        self.assertEqual(ORACLE_REF, selection.oracle_ref)

    def test_missing_oracle_or_semantic_judgment_requires_fresh_context(self) -> None:
        without_oracle = select_evaluator(())
        semantic = select_evaluator(
            (),
            machine_oracle_ref=ORACLE_REF,
            semantic_judgment_required=True,
        )

        self.assertEqual(EvaluatorKind.FRESH_CONTEXT, without_oracle.evaluator)
        self.assertEqual(EvaluatorKind.FRESH_CONTEXT, semantic.evaluator)
        self.assertIsNone(without_oracle.oracle_ref)
        self.assertIsNone(semantic.oracle_ref)

    def test_each_named_risk_requires_fresh_context(self) -> None:
        risks = (
            EvaluatorRisk.AUTHORITY,
            EvaluatorRisk.SAFETY,
            EvaluatorRisk.CROSS_CONTRACT,
            EvaluatorRisk.DESTRUCTIVE,
            EvaluatorRisk.HARNESS,
            EvaluatorRisk.SEMANTIC,
        )

        for risk in risks:
            with self.subTest(risk=risk):
                selection = select_evaluator(
                    (risk,),
                    machine_oracle_ref=ORACLE_REF,
                )
                self.assertEqual(EvaluatorKind.FRESH_CONTEXT, selection.evaluator)
                self.assertIsNone(selection.oracle_ref)

    def test_selection_reuses_topology_and_blocking_boundaries(self) -> None:
        blocking = ReviewFinding(
            "F-1",
            Priority.P2,
            "authority",
            "authority-root",
        )
        with (
            patch(
                "sagekit.review.select_topology",
                return_value=ReviewTopology.LIGHT,
            ) as topology,
            patch("sagekit.review.is_blocking", return_value=True) as blocking_check,
        ):
            selection = select_evaluator(
                (),
                machine_oracle_ref=ORACLE_REF,
                findings=(blocking,),
            )

        topology.assert_called_once_with(())
        blocking_check.assert_called_once_with(blocking)
        self.assertEqual(EvaluatorKind.FRESH_CONTEXT, selection.evaluator)

    def test_selection_is_deterministic_and_inputs_are_closed_and_bounded(self) -> None:
        arguments = (
            (EvaluatorRisk.MECHANICAL,),
            {"machine_oracle_ref": ORACLE_REF},
        )
        first = select_evaluator(arguments[0], **arguments[1])
        second = select_evaluator(arguments[0], **arguments[1])

        self.assertEqual(first, second)
        with self.assertRaises(ValueError):
            select_evaluator(
                (
                    EvaluatorRisk.MECHANICAL,
                    EvaluatorRisk.MECHANICAL,
                ),
                machine_oracle_ref=ORACLE_REF,
            )
        with self.assertRaises((TypeError, ValueError)):
            select_evaluator(
                ("mechanical",),  # type: ignore[arg-type]
                machine_oracle_ref=ORACLE_REF,
            )
        with self.assertRaises(ValueError):
            select_evaluator((), machine_oracle_ref="x" * 513)
        with self.assertRaises((TypeError, ValueError)):
            select_evaluator([], machine_oracle_ref=ORACLE_REF)  # type: ignore[arg-type]

    def test_selection_is_immutable_and_rejects_partial_states(self) -> None:
        selection = select_evaluator(
            (),
            machine_oracle_ref=ORACLE_REF,
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            selection.evaluator = EvaluatorKind.FRESH_CONTEXT  # type: ignore[misc]
        with self.assertRaises(ValueError):
            EvaluatorSelection(
                EvaluatorKind.DETERMINISTIC,
                ReviewTopology.LIGHT,
                None,
            )
        with self.assertRaises(ValueError):
            EvaluatorSelection(
                EvaluatorKind.FRESH_CONTEXT,
                ReviewTopology.LIGHT,
                ORACLE_REF,
            )


class EvaluatorReceiptValidationTests(unittest.TestCase):
    def test_deterministic_receipt_accepts_only_bound_oracle_and_fingerprints(
        self,
    ) -> None:
        selection = select_evaluator((), machine_oracle_ref=ORACLE_REF)
        receipt = DeterministicReceipt(
            ORACLE_REF,
            INPUT_FINGERPRINT,
            RESULT_FINGERPRINT,
        )

        self.assertEqual(
            ReceiptStatus.PASS,
            validate_evaluator_receipt(selection, receipt),
        )
        self.assertEqual(
            ReceiptStatus.INVALID_RECEIPT,
            validate_evaluator_receipt(
                selection,
                DeterministicReceipt(
                    "ci://review/different-oracle",
                    INPUT_FINGERPRINT,
                    RESULT_FINGERPRINT,
                ),
            ),
        )
        self.assertEqual(
            ReceiptStatus.INVALID_RECEIPT,
            validate_evaluator_receipt(
                selection,
                FreshContextReceipt(
                    "author",
                    "independent-reviewer",
                    EvaluatorVerdict.PASS,
                ),
            ),
        )

    def test_author_approval_cannot_substitute_for_deterministic_evidence(self) -> None:
        fields = tuple(field.name for field in dataclasses.fields(DeterministicReceipt))

        self.assertEqual(
            ("oracle_ref", "input_fingerprint", "result_fingerprint"),
            fields,
        )
        with self.assertRaises(TypeError):
            DeterministicReceipt(  # type: ignore[call-arg]
                oracle_ref=ORACLE_REF,
                input_fingerprint=INPUT_FINGERPRINT,
                result_fingerprint=RESULT_FINGERPRINT,
                author_approved=True,
            )

    def test_fresh_evaluator_matching_author_requires_independence_and_cannot_pass(
        self,
    ) -> None:
        selection = select_evaluator(
            (EvaluatorRisk.SEMANTIC,),
            machine_oracle_ref=ORACLE_REF,
        )
        receipt = FreshContextReceipt(
            "same-identity",
            "same-identity",
            EvaluatorVerdict.PASS,
        )

        status = validate_evaluator_receipt(selection, receipt)

        self.assertEqual(ReceiptStatus.INDEPENDENT_EVALUATOR_REQUIRED, status)
        self.assertIsNot(ReceiptStatus.PASS, status)

    def test_distinct_fresh_evaluator_may_report_pass_or_fail(self) -> None:
        selection = select_evaluator((EvaluatorRisk.HARNESS,))

        passed = validate_evaluator_receipt(
            selection,
            FreshContextReceipt(
                "author",
                "fresh-reviewer",
                EvaluatorVerdict.PASS,
            ),
        )
        failed = validate_evaluator_receipt(
            selection,
            FreshContextReceipt(
                "author",
                "fresh-reviewer",
                EvaluatorVerdict.FAIL,
            ),
        )

        self.assertEqual(ReceiptStatus.PASS, passed)
        self.assertEqual(ReceiptStatus.FAIL, failed)

    def test_receipts_are_bounded_immutable_and_never_partial(self) -> None:
        with self.assertRaises(ValueError):
            DeterministicReceipt(
                ORACLE_REF,
                "not-a-fingerprint",
                RESULT_FINGERPRINT,
            )
        with self.assertRaises(ValueError):
            FreshContextReceipt("author", "x" * 257, EvaluatorVerdict.PASS)
        with self.assertRaises(TypeError):
            DeterministicReceipt(ORACLE_REF, INPUT_FINGERPRINT)  # type: ignore[call-arg]

        receipt = DeterministicReceipt(
            ORACLE_REF,
            INPUT_FINGERPRINT,
            RESULT_FINGERPRINT,
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            receipt.oracle_ref = "ci://changed"  # type: ignore[misc]

        fresh_selection = select_evaluator((EvaluatorRisk.AUTHORITY,))
        self.assertEqual(
            ReceiptStatus.INVALID_RECEIPT,
            validate_evaluator_receipt(fresh_selection, object()),
        )


if __name__ == "__main__":
    unittest.main()
