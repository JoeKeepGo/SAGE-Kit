import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from sagekit.candidate import CandidateAssessment, CandidateFingerprint, assess_candidate, freeze_candidate
from sagekit.change_control import ChangeClass, RunState
from sagekit.continuity import checkpoint_path, create_checkpoint, resume_checkpoint
from sagekit.execution_limits import (
    ExecutionCounters,
    ExecutionLimits,
    VerificationAttemptState,
    VerificationKind,
    VerificationNode,
    VerificationNodeDisposition,
    VerificationNodeResult,
    VerificationPreflight,
    VerificationPreflightCheck,
    begin_verification_run,
    complete_verification_run,
    decide_verification_node,
    prepare_verification_run,
)


def candidate() -> CandidateFingerprint:
    return CandidateFingerprint(
        head_sha="a" * 40,
        diff_hash="b" * 64,
        contract_digest="contracts-v2",
        dependency_digest="dependencies-v1",
        review_closed=True,
        corrective_batch_closed=True,
    )


def matching_assessment() -> CandidateAssessment:
    return CandidateAssessment(True, RunState.CONTINUE, "candidate matches")


def preflight(
    attempt_id: str,
    *,
    current_candidate: CandidateFingerprint | None,
    checks: tuple[VerificationPreflightCheck, ...] | None = None,
) -> VerificationPreflight:
    return VerificationPreflight(
        attempt_id=attempt_id,
        candidate_fingerprint=(
            current_candidate.digest if current_candidate is not None else None
        ),
        checks=checks
        or (
            VerificationPreflightCheck("builder_available", True),
            VerificationPreflightCheck("module_resolution_clean", True),
        ),
    )


def prepare_final(
    attempt_id: str,
    *,
    counters: ExecutionCounters | None = None,
    current_candidate: CandidateFingerprint | None = None,
    proof: VerificationPreflight | None = None,
    kind: VerificationKind = VerificationKind.FULL_SUITE,
):
    current_candidate = current_candidate or candidate()
    return prepare_verification_run(
        counters or ExecutionCounters(),
        kind,
        proof or preflight(attempt_id, current_candidate=current_candidate),
        candidate=current_candidate,
        assessment=matching_assessment(),
    )


def begin_final(attempt_id: str, counters: ExecutionCounters, current_candidate=None):
    current_candidate = current_candidate or candidate()
    return begin_verification_run(
        counters,
        ExecutionLimits(),
        attempt_id,
        candidate=current_candidate,
        assessment=matching_assessment(),
    )


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
    git(root, "config", "user.name", "SAGE-Kit Tests")
    git(root, "config", "user.email", "sagekit-tests@example.invalid")
    (root / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(root, "add", "tracked.txt")
    git(root, "commit", "-m", "test baseline")


def rewrite_checkpoint(root: Path, payload: dict[str, object]) -> None:
    digest_payload = {
        key: value for key, value in payload.items() if key != "payload_sha256"
    }
    encoded = json.dumps(
        digest_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload["payload_sha256"] = hashlib.sha256(encoded).hexdigest()
    checkpoint_path(root).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


class VerificationLifecycleTests(unittest.TestCase):
    def test_missing_builder_preflight_failure_does_not_count(self):
        current = candidate()
        proof = preflight(
            "missing-builder",
            current_candidate=current,
            checks=(VerificationPreflightCheck("builder_available", False),),
        )

        decision = prepare_final(
            "missing-builder",
            current_candidate=current,
            proof=proof,
            kind=VerificationKind.WHEEL_INSTALL,
        )

        self.assertEqual(VerificationAttemptState.PREFLIGHT, decision.attempt_state)
        self.assertFalse(decision.allowed_to_run)
        self.assertEqual({}, decision.counters.final_wheel_install_runs)

    def test_local_module_shadowing_preflight_failure_does_not_count(self):
        current = candidate()
        proof = preflight(
            "module-shadowing",
            current_candidate=current,
            checks=(VerificationPreflightCheck("module_resolution_clean", False),),
        )

        decision = prepare_final(
            "module-shadowing",
            current_candidate=current,
            proof=proof,
            kind=VerificationKind.WHEEL_INSTALL,
        )

        self.assertEqual(VerificationAttemptState.PREFLIGHT, decision.attempt_state)
        self.assertFalse(decision.counted_now)
        self.assertEqual({}, decision.counters.final_wheel_install_runs)

    def test_ready_does_not_count(self):
        ready = prepare_final("ready")

        self.assertEqual(VerificationAttemptState.READY, ready.attempt_state)
        self.assertTrue(ready.allowed_to_run)
        self.assertFalse(ready.counted_now)
        self.assertEqual({}, ready.counters.final_full_suite_runs)

    def test_started_atomically_counts_exactly_once(self):
        current = candidate()
        ready = prepare_final("start-once", current_candidate=current)

        started = begin_final("start-once", ready.counters, current)

        self.assertEqual(VerificationAttemptState.STARTED, started.attempt_state)
        self.assertTrue(started.counted_now)
        self.assertEqual(1, started.counters.final_full_suite_runs[current.digest])

    def test_duplicate_attempt_id_does_not_count_twice(self):
        current = candidate()
        ready = prepare_final("duplicate", current_candidate=current)
        first = begin_final("duplicate", ready.counters, current)

        duplicate = begin_final("duplicate", first.counters, current)

        self.assertEqual(VerificationAttemptState.STARTED, duplicate.attempt_state)
        self.assertFalse(duplicate.counted_now)
        self.assertFalse(duplicate.allowed_to_run)
        self.assertEqual(1, duplicate.counters.final_full_suite_runs[current.digest])

    def test_backend_failure_after_start_remains_counted(self):
        current = candidate()
        ready = prepare_final("backend-fail", current_candidate=current)
        started = begin_final("backend-fail", ready.counters, current)

        failed = complete_verification_run(
            started.counters,
            "backend-fail",
            VerificationAttemptState.FAILED,
        )

        self.assertEqual(VerificationAttemptState.FAILED, failed.attempt_state)
        self.assertEqual(1, failed.counters.final_full_suite_runs[current.digest])

    def test_abort_after_start_remains_counted(self):
        current = candidate()
        ready = prepare_final("backend-abort", current_candidate=current)
        started = begin_final("backend-abort", ready.counters, current)

        aborted = complete_verification_run(
            started.counters,
            "backend-abort",
            VerificationAttemptState.ABORTED,
        )

        self.assertEqual(VerificationAttemptState.ABORTED, aborted.attempt_state)
        self.assertEqual(1, aborted.counters.final_full_suite_runs[current.digest])

    def test_candidate_fingerprint_mismatch_cannot_start_or_count(self):
        current = candidate()
        proof = VerificationPreflight(
            attempt_id="mismatch",
            candidate_fingerprint="different-candidate",
            checks=(VerificationPreflightCheck("builder_available", True),),
        )

        prepared = prepare_final(
            "mismatch",
            current_candidate=current,
            proof=proof,
        )

        self.assertEqual(VerificationAttemptState.PREFLIGHT, prepared.attempt_state)
        self.assertFalse(prepared.allowed_to_run)
        self.assertEqual({}, prepared.counters.final_full_suite_runs)

    def test_preliminary_and_final_attempts_use_separate_counters(self):
        preliminary_proof = preflight("preliminary", current_candidate=None)
        ready = prepare_verification_run(
            ExecutionCounters(),
            VerificationKind.FULL_SUITE,
            preliminary_proof,
            candidate=None,
            assessment=None,
        )
        preliminary = begin_verification_run(
            ready.counters,
            ExecutionLimits(),
            "preliminary",
            candidate=None,
            assessment=None,
        )

        self.assertEqual(1, preliminary.counters.preliminary_full_suite_runs)
        self.assertEqual({}, preliminary.counters.final_full_suite_runs)

    def test_checkpoint_resume_preserves_started_attempt_without_recounting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            frozen = freeze_candidate(
                root,
                contract_digest="contracts-v2",
                dependency_digest="dependencies-v1",
                review_closed=True,
                corrective_batch_closed=True,
            )
            assessment = assess_candidate(
                root,
                frozen.candidate,
                contract_digest="contracts-v2",
                dependency_digest="dependencies-v1",
            )
            proof = preflight("resume-started", current_candidate=frozen.candidate)
            ready = prepare_verification_run(
                ExecutionCounters(),
                VerificationKind.FULL_SUITE,
                proof,
                candidate=frozen.candidate,
                assessment=assessment,
            )
            started = begin_verification_run(
                ready.counters,
                ExecutionLimits(),
                "resume-started",
                candidate=frozen.candidate,
                assessment=assessment,
            )
            create_checkpoint(
                root,
                run_id="attempt-run",
                goal="Preserve started verification attempt",
                authority_id="request",
                authority_version="1",
                authority_summary="Direct request",
                change_class=ChangeClass.C1_BOUNDED_CORRECTIVE,
                completed_work=(),
                open_findings=(),
                evidence_references=(),
                invalidated_evidence=(),
                execution_counters=started.counters,
                next_action="resume verification",
                allowed_paths=("tracked.txt",),
                stop_conditions=(),
                candidate=frozen.candidate,
            )

            resumed = resume_checkpoint(root)
            restored = ExecutionCounters.from_dict(
                resumed.checkpoint["execution_counters"]
            )
            duplicate = begin_verification_run(
                restored,
                ExecutionLimits(),
                "resume-started",
                candidate=frozen.candidate,
                assessment=assessment,
            )

        self.assertTrue(resumed.ok, resumed.mismatches)
        self.assertFalse(duplicate.counted_now)
        self.assertEqual(
            1,
            duplicate.counters.final_full_suite_runs[frozen.candidate.digest],
        )

    def test_v1_counter_migration_is_conservative(self):
        migrated = ExecutionCounters.from_dict(
            {
                "implementation_workers": 0,
                "read_only_review_agents": 0,
                "parallel_agent_waves": 0,
                "corrective_re_review_rounds": 0,
                "full_suite_runs_after_baseline": 1,
                "wheel_install_verification_runs": 1,
                "reviewer_reports_per_scope": 0,
                "root_cause_no_progress": {},
                "exception_events": [],
            }
        )

        self.assertEqual(1, migrated.preliminary_full_suite_runs)
        self.assertEqual(1, migrated.preliminary_wheel_install_runs)
        self.assertEqual({}, migrated.final_full_suite_runs)
        self.assertEqual({}, migrated.verification_attempts)

    def test_independent_node_continues_after_another_node_fails(self):
        decision = decide_verification_node(
            VerificationNode("source-check"),
            {"wheel": VerificationNodeResult("wheel", VerificationAttemptState.FAILED)},
        )

        self.assertTrue(decision.independent)
        self.assertEqual(VerificationNodeDisposition.EXECUTED, decision.disposition)

    def test_dependent_node_is_skipped_after_dependency_fails(self):
        decision = decide_verification_node(
            VerificationNode("wheel-install", depends_on=("wheel",)),
            {"wheel": VerificationNodeResult("wheel", VerificationAttemptState.FAILED)},
        )

        self.assertFalse(decision.independent)
        self.assertEqual(
            VerificationNodeDisposition.SKIPPED_DUE_TO_DEPENDENCY,
            decision.disposition,
        )
        self.assertEqual(("wheel",), decision.blocked_by)

    def test_text_and_json_attempt_status_report_the_same_counters(self):
        current = candidate()
        ready = prepare_final("status", current_candidate=current)
        started = begin_final("status", ready.counters, current)

        payload = started.to_dict()
        text_counters = next(
            line.removeprefix("COUNTERS ")
            for line in started.to_text().splitlines()
            if line.startswith("COUNTERS ")
        )

        self.assertEqual(payload["counters"], json.loads(text_counters))
        self.assertEqual("STARTED", payload["attempt_state"])


class CheckpointAttemptMigrationTests(unittest.TestCase):
    def create_current_checkpoint(self, root: Path) -> dict[str, object]:
        result = create_checkpoint(
            root,
            run_id="migration",
            goal="Migrate verification attempts",
            authority_id="request",
            authority_version="1",
            authority_summary="Direct request",
            change_class=ChangeClass.C1_BOUNDED_CORRECTIVE,
            completed_work=(),
            open_findings=(),
            evidence_references=(),
            invalidated_evidence=(),
            execution_counters=ExecutionCounters(),
            next_action="resume",
            allowed_paths=("tracked.txt",),
            stop_conditions=(),
        )
        return dict(result.checkpoint)

    def test_v2_checkpoint_without_attempt_records_resumes_conservatively(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            payload = self.create_current_checkpoint(root)
            payload["schema_version"] = 2
            counters = dict(payload["execution_counters"])
            counters.pop("verification_attempts")
            payload["execution_counters"] = counters
            rewrite_checkpoint(root, payload)

            resumed = resume_checkpoint(root)

        self.assertTrue(resumed.ok, resumed.mismatches)
        restored = ExecutionCounters.from_dict(
            resumed.checkpoint["execution_counters"]
        )
        self.assertEqual({}, restored.verification_attempts)

    def test_v1_checkpoint_migrates_aggregate_runs_to_preliminary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            payload = self.create_current_checkpoint(root)
            payload["schema_version"] = 1
            payload.pop("candidate")
            payload["execution_counters"] = {
                "implementation_workers": 0,
                "read_only_review_agents": 0,
                "parallel_agent_waves": 0,
                "corrective_re_review_rounds": 0,
                "full_suite_runs_after_baseline": 1,
                "wheel_install_verification_runs": 1,
                "reviewer_reports_per_scope": 0,
                "root_cause_no_progress": {},
                "exception_events": [],
            }
            rewrite_checkpoint(root, payload)

            resumed = resume_checkpoint(root)

        self.assertTrue(resumed.ok, resumed.mismatches)
        restored = ExecutionCounters.from_dict(
            resumed.checkpoint["execution_counters"]
        )
        self.assertEqual(1, restored.preliminary_full_suite_runs)
        self.assertEqual(1, restored.preliminary_wheel_install_runs)
        self.assertEqual({}, restored.verification_attempts)


if __name__ == "__main__":
    unittest.main()
