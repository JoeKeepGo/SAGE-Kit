from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from sagekit.candidate import (
    CandidateFingerprint,
    RepositorySnapshot,
    WorkingTreeSnapshot,
    assess_candidate_snapshot,
    candidate_fingerprint_from_snapshot,
    freeze_candidate,
)
from sagekit.change_control import RunState
from sagekit.normalization import NormalizationFinding, NormalizationKind


class CandidateSnapshotUnitTests(unittest.TestCase):
    def test_freeze_routes_safe_whitespace_to_auto_normalization_corrective(self) -> None:
        finding = NormalizationFinding(
            "src/example.py",
            NormalizationKind.MISSING_FINAL_NEWLINE,
            "a" * 64,
            "b" * 64,
            True,
            "safe whitespace-only correction inside writable scope",
        )
        snapshot = RepositorySnapshot(
            repository_root="repo",
            head_sha="head-1",
            diff_hash="diff-1",
            snapshot_mode="working-tree",
            worktree_changes=(),
            working_tree=WorkingTreeSnapshot("tree-1", ("src/example.py",)),
            normalization_findings=(finding,),
        )
        with (
            patch("sagekit.candidate._repository_root", return_value=Path("repo")),
            patch("sagekit.candidate._collect_repository_snapshot", return_value=snapshot),
        ):
            result = freeze_candidate(
                Path("repo"),
                contract_digest="contract-1",
                dependency_digest="dependency-1",
                review_closed=True,
                corrective_batch_closed=True,
                snapshot_mode="working-tree",
                snapshot_authority="normalization-test-authority",
            )
        self.assertFalse(result.ok)
        self.assertEqual(RunState.AUTO_CORRECT, result.state)
        self.assertEqual("AUTO_NORMALIZATION_CORRECTIVE", result.message)

    def test_freeze_candidate_uses_collected_snapshots_without_direct_git(self) -> None:
        snapshot = RepositorySnapshot(
            repository_root="C:/work/repository",
            head_sha="head-1",
            diff_hash="diff-1",
            snapshot_mode="clean-head",
            worktree_changes=(),
            working_tree=None,
        )
        with (
            patch(
                "sagekit.candidate._repository_root",
                return_value=Path(snapshot.repository_root),
            ),
            patch(
                "sagekit.candidate._collect_repository_snapshot",
                side_effect=(snapshot, snapshot),
            ) as collect,
            patch(
                "sagekit.candidate._git_bytes",
                side_effect=AssertionError("freeze must use the collected snapshots"),
            ),
        ):
            result = freeze_candidate(
                Path(snapshot.repository_root),
                contract_digest="contract-1",
                dependency_digest="dependency-1",
                review_closed=True,
                corrective_batch_closed=True,
            )

        self.assertTrue(result.ok, result.mismatches)
        self.assertEqual(2, collect.call_count)
        self.assertEqual("head-1", result.candidate.head_sha)

    def test_fingerprint_freeze_from_synthetic_snapshot_is_pure(self) -> None:
        snapshot = RepositorySnapshot(
            repository_root="C:/work/repository",
            head_sha="head-1",
            diff_hash="diff-1",
            snapshot_mode="clean-head",
            worktree_changes=(),
            working_tree=None,
        )

        with patch(
            "sagekit.candidate._git_bytes",
            side_effect=AssertionError("pure freeze must not invoke Git"),
        ):
            candidate = candidate_fingerprint_from_snapshot(
                snapshot,
                contract_digest="contract-1",
                dependency_digest="dependency-1",
                review_closed=True,
                corrective_batch_closed=True,
                fingerprint_version=2,
            )

        self.assertEqual("head-1", candidate.head_sha)
        self.assertEqual("diff-1", candidate.diff_hash)
        self.assertEqual("clean-head", candidate.snapshot_mode)

    def test_assessment_from_synthetic_snapshot_is_pure(self) -> None:
        snapshot = RepositorySnapshot(
            repository_root="C:/work/repository",
            head_sha="head-1",
            diff_hash="diff-1",
            snapshot_mode="clean-head",
            worktree_changes=(),
            working_tree=None,
        )
        candidate = CandidateFingerprint(
            head_sha="head-1",
            diff_hash="diff-1",
            contract_digest="contract-1",
            dependency_digest="dependency-1",
            review_closed=True,
            corrective_batch_closed=True,
        )

        with patch(
            "sagekit.candidate._git_bytes",
            side_effect=AssertionError("pure assessment must not invoke Git"),
        ):
            assessment = assess_candidate_snapshot(
                snapshot,
                candidate,
                contract_digest="contract-1",
                dependency_digest="dependency-1",
            )

        self.assertTrue(assessment.ok, assessment.mismatches)

    def test_synthetic_snapshot_reports_worktree_drift_without_git(self) -> None:
        snapshot = RepositorySnapshot(
            repository_root="C:/work/repository",
            head_sha="head-1",
            diff_hash="diff-1",
            snapshot_mode="clean-head",
            worktree_changes=(" M src/widget.py",),
            working_tree=None,
        )
        candidate = CandidateFingerprint(
            head_sha="head-1",
            diff_hash="diff-1",
            contract_digest="contract-1",
            dependency_digest="dependency-1",
            review_closed=True,
            corrective_batch_closed=True,
        )

        assessment = assess_candidate_snapshot(
            snapshot,
            candidate,
            contract_digest="contract-1",
            dependency_digest="dependency-1",
        )

        self.assertFalse(assessment.ok)
        self.assertEqual(
            ("unexpected worktree changes:  M src/widget.py",),
            assessment.mismatches,
        )


if __name__ == "__main__":
    unittest.main()
