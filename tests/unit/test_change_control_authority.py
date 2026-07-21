from __future__ import annotations

import unittest
from pathlib import Path

from sagekit.change_control import ChangeClass, ChangeRequest, CorrectiveEnvelope, RunState, decide_change


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _corrective_envelope() -> CorrectiveEnvelope:
    return CorrectiveEnvelope(
        acceptance_criterion="approved",
        acceptance_criterion_approved=True,
        adds_product_feature=False,
        changes_external_api=False,
        changes_security_policy=False,
        changes_deployment_target=False,
        allowed_paths=("sagekit/",),
        reversible=True,
        focused_verification=("python -m unittest tests/unit/test_change_control_authority.py",),
        opens_closed_gate=False,
    )


class ChangeControlAuthorityTests(unittest.TestCase):
    def test_c0_without_explicit_authority_requires_human_decision(self):
        request = ChangeRequest(
            change_class=ChangeClass.C0_RECORD_ONLY,
            changed_paths=("docs/ACTIVE_CONTEXT.md",),
            purposes={"docs/ACTIVE_CONTEXT.md": "sync current status"},
        )
        decision = decide_change(_repo_root(), request)

        self.assertEqual(RunState.HUMAN_DECISION_REQUIRED, decision.state)
        self.assertEqual(("record owner write authority is missing",), decision.reasons)

    def test_c1_without_explicit_authority_requires_human_decision(self):
        request = ChangeRequest(
            change_class=ChangeClass.C1_BOUNDED_CORRECTIVE,
            changed_paths=("sagekit/change_control.py",),
            purposes={"sagekit/change_control.py": "apply scoped repair"},
        )
        decision = decide_change(
            _repo_root(),
            request,
            _corrective_envelope(),
        )

        self.assertEqual(RunState.HUMAN_DECISION_REQUIRED, decision.state)
        self.assertEqual(("bounded corrective authority is missing",), decision.reasons)

    def test_c2_without_explicit_authority_is_not_authorized(self):
        request = ChangeRequest(
            change_class=ChangeClass.C2_CONTRACT_AFFECTING,
            changed_paths=("sagekit/change_control.py",),
        )
        decision = decide_change(_repo_root(), request)

        self.assertEqual(RunState.HUMAN_DECISION_REQUIRED, decision.state)
        self.assertEqual(("contract-affecting authority is missing",), decision.reasons)
        self.assertEqual(("contract-scoped",), decision.required_verification)

    def test_c2_authorized_change_uses_contract_scoped_verification(self):
        request = ChangeRequest(
            change_class=ChangeClass.C2_CONTRACT_AFFECTING,
            changed_paths=("sagekit/change_control.py",),
            authority_granted=True,
        )
        decision = decide_change(_repo_root(), request)

        self.assertEqual(RunState.CONTINUE, decision.state)
        self.assertEqual(("contract-scoped",), decision.required_verification)
        self.assertEqual((), decision.reasons)

    def test_c0_c1_c2_require_explicit_grant_in_request(self):
        for request in (
            ChangeRequest(
                ChangeClass.C0_RECORD_ONLY,
                ("docs/ACTIVE_CONTEXT.md",),
                authority_granted=False,
            ),
            ChangeRequest(
                ChangeClass.C1_BOUNDED_CORRECTIVE,
                ("sagekit/change_control.py",),
                authority_granted=False,
            ),
            ChangeRequest(
                ChangeClass.C2_CONTRACT_AFFECTING,
                ("sagekit/change_control.py",),
                authority_granted=False,
            ),
        ):
            with self.subTest(change_class=request.change_class):
                decision = decide_change(
                    _repo_root(),
                    request,
                    _corrective_envelope() if request.change_class is ChangeClass.C1_BOUNDED_CORRECTIVE else None,
                )
                self.assertEqual(RunState.HUMAN_DECISION_REQUIRED, decision.state)
