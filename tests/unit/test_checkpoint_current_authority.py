from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from sagekit.change_control import ChangeClass
from sagekit.convergence import PreauthorizedConvergenceAuthority
from sagekit.continuity import create_checkpoint, resume_checkpoint
from sagekit.execution_limits import ExecutionCounters


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()


def init_repository(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.name", "Framework Tests")
    git(root, "config", "user.email", "framework-tests@example.invalid")
    (root / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(root, "add", "tracked.txt")
    git(root, "commit", "-m", "test baseline")


def authority() -> PreauthorizedConvergenceAuthority:
    return PreauthorizedConvergenceAuthority(
        authority_id="AUTH-CONVERGENCE-1",
        mode="preauthorized",
        execution_scope="execution-unit-1",
        root_cause_family="portability",
        allowed_paths=("tracked.txt",),
        invariant="canonical containment remains unchanged",
        semantic_change_policy="implementation-preserving-only",
        targeted_review_required=True,
        stop_conditions=("allowed path expansion", "security invariant change"),
        approved_by="project-owner-role",
        authority_ref="approval-packet-1",
    )


def create_default_checkpoint(root: Path, *, convergence_authority=None):
    return create_checkpoint(
        root,
        run_id="checkpoint-current-authority",
        goal="Resume only with current authority",
        authority_id="request",
        authority_version="1",
        authority_summary="Direct maintainer request",
        change_class=ChangeClass.C1_BOUNDED_CORRECTIVE,
        completed_work=(),
        open_findings=(),
        evidence_references=(),
        invalidated_evidence=(),
        execution_counters=ExecutionCounters(),
        next_action="continue",
        allowed_paths=("tracked.txt",),
        stop_conditions=("authority change",),
        convergence_authority=convergence_authority,
    )


class CheckpointCurrentAuthorityTests(unittest.TestCase):
    def test_convergence_checkpoint_omission_of_authority_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            create_default_checkpoint(root, convergence_authority=authority())

            resumed = resume_checkpoint(root)

        self.assertFalse(resumed.ok)
        self.assertEqual("checkpoint-mismatch", resumed.rule)
        self.assertTrue(
            any(
                "current convergence authority identity and version are required for resume"
                in mismatch
                for mismatch in resumed.mismatches
            ),
            resumed.mismatches,
        )

    def test_convergence_checkpoint_accepts_matching_authority_id_and_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            create_default_checkpoint(root, convergence_authority=authority())

            resumed = resume_checkpoint(
                root,
                expected_authority_id="request",
                expected_authority_version="1",
            )

        self.assertTrue(resumed.ok, resumed.mismatches)
        self.assertEqual("checkpoint-resumable", resumed.rule)
        self.assertEqual("continue", resumed.checkpoint["next_action"])

    def test_convergence_checkpoint_accepts_validated_current_convergence_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            create_default_checkpoint(root, convergence_authority=authority())

            resumed = resume_checkpoint(root, expected_convergence_authority=authority())

        self.assertTrue(resumed.ok, resumed.mismatches)
        self.assertEqual("checkpoint-resumable", resumed.rule)

    def test_convergence_checkpoint_rejects_authority_version_revocation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            create_default_checkpoint(root, convergence_authority=authority())

            resumed = resume_checkpoint(
                root,
                expected_authority_id="request",
                expected_authority_version="2",
            )

        self.assertFalse(resumed.ok)
        self.assertTrue(
            any("authority version differs" in mismatch for mismatch in resumed.mismatches),
            resumed.mismatches,
        )

    def test_legacy_checkpoint_resumes_without_execution_grant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            create_default_checkpoint(root)

            resumed = resume_checkpoint(root)

        self.assertTrue(resumed.ok, resumed.mismatches)
        self.assertIsNone(resumed.checkpoint["convergence_authority"])
        self.assertEqual("continue", resumed.checkpoint["next_action"])
