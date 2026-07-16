import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sagekit.change_control import (
    ChangeClass,
    ChangeRequest,
    CorrectiveEnvelope,
    RunState,
    decide_change,
)
from sagekit.continuity import (
    checkpoint_path,
    clear_checkpoint,
    create_checkpoint,
    resume_checkpoint,
)
from sagekit.check import check_source_tracked_runtime
from sagekit.evidence import ChangeEvent, EvidenceFingerprint, assess_evidence
from sagekit.execution_limits import (
    ExecutionCounters,
    ExecutionLimits,
    consume_event,
    record_root_cause_progress,
)
from sagekit.pathing import is_within, normalize_contract_path
from sagekit.review import (
    Priority,
    ReviewFinding,
    ReviewReport,
    ReviewState,
    accept_initial_report,
    evaluate_corrective_rereview,
    shared_file_density,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()


def run_sagekit(*args, cwd):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "sagekit", *args],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def init_repository(root):
    git(root, "init")
    git(root, "config", "user.name", "SAGE-Kit Tests")
    git(root, "config", "user.email", "sagekit-tests@example.invalid")
    (root / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(root, "add", "tracked.txt")
    git(root, "commit", "-m", "test baseline")


def corrective_envelope(*allowed_paths):
    return CorrectiveEnvelope(
        acceptance_criterion="Existing acceptance criterion",
        acceptance_criterion_approved=True,
        adds_product_feature=False,
        changes_external_api=False,
        changes_security_policy=False,
        changes_deployment_target=False,
        allowed_paths=tuple(allowed_paths),
        reversible=True,
        focused_verification=("python -m unittest tests.test_feature",),
        opens_closed_gate=False,
    )


def evidence(**overrides):
    values = {
        "evidence_id": "E-1",
        "kind": "focused",
        "lane": "implementation",
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "covered_paths": ("src/widget.py",),
        "covered_contracts": (),
        "command": "python -m unittest tests.test_widget",
        "dependency_fingerprint": "deps-1",
        "toolchain_fingerprint": "python-3.10",
        "platform": "windows",
        "authority_version": "A1",
        "result": "PASS",
    }
    values.update(overrides)
    return EvidenceFingerprint(**values)


class ChangeControlTests(unittest.TestCase):
    def test_c0_uses_only_record_consistency_verification(self):
        request = ChangeRequest(
            change_class=ChangeClass.C0_RECORD_ONLY,
            changed_paths=("docs/ACTIVE_CONTEXT.md",),
            purposes={"docs/ACTIVE_CONTEXT.md": "synchronize current status"},
        )

        decision = decide_change(Path.cwd(), request)

        self.assertEqual(RunState.AUTO_CORRECT, decision.state)
        self.assertEqual(("record-consistency",), decision.required_verification)

    def test_c1_inside_corrective_envelope_auto_corrects(self):
        request = ChangeRequest(
            change_class=ChangeClass.C1_BOUNDED_CORRECTIVE,
            changed_paths=("src/widget.py",),
            purposes={"src/widget.py": "satisfy the approved criterion"},
        )

        decision = decide_change(
            Path.cwd(),
            request,
            corrective_envelope("src/widget.py"),
        )

        self.assertEqual(RunState.AUTO_CORRECT, decision.state)
        self.assertEqual(("focused",), decision.required_verification)
        self.assertEqual((), decision.authority_delta)

    def test_c1_outside_scope_aggregates_all_paths_into_one_delta(self):
        request = ChangeRequest(
            change_class=ChangeClass.C1_BOUNDED_CORRECTIVE,
            changed_paths=("src/a.py", "tests/test_a.py"),
            purposes={
                "src/a.py": "repair behavior",
                "tests/test_a.py": "verify the repair",
            },
        )

        decision = decide_change(
            Path.cwd(),
            request,
            corrective_envelope("docs/"),
        )

        self.assertEqual(RunState.HUMAN_DECISION_REQUIRED, decision.state)
        self.assertEqual(
            ["src/a.py", "tests/test_a.py"],
            [item.path for item in decision.authority_delta],
        )
        self.assertIn("src/", decision.recommended_scope)
        self.assertIn("tests/", decision.recommended_scope)

    def test_c2_requires_matching_authority_and_semantic_verification(self):
        request = ChangeRequest(
            change_class=ChangeClass.C2_CONTRACT_AFFECTING,
            changed_paths=("schema/api.json",),
            authority_granted=False,
        )

        decision = decide_change(Path.cwd(), request)

        self.assertEqual(RunState.HUMAN_DECISION_REQUIRED, decision.state)
        self.assertEqual(("semantic-lane",), decision.required_verification)

    def test_c3_requires_human_decision(self):
        request = ChangeRequest(
            change_class=ChangeClass.C3_EXTERNAL_DESTRUCTIVE,
            changed_paths=(),
        )

        decision = decide_change(Path.cwd(), request)

        self.assertEqual(RunState.HUMAN_DECISION_REQUIRED, decision.state)


class EvidenceTests(unittest.TestCase):
    def test_unrelated_change_reuses_evidence(self):
        result = assess_evidence(
            evidence(),
            ChangeEvent(
                change_class=ChangeClass.C1_BOUNDED_CORRECTIVE,
                changed_paths=("docs/readme.md",),
            ),
        )

        self.assertTrue(result.reusable)
        self.assertEqual((), result.reasons)

    def test_relevant_implementation_diff_invalidates_focused_evidence(self):
        result = assess_evidence(
            evidence(),
            ChangeEvent(
                change_class=ChangeClass.C1_BOUNDED_CORRECTIVE,
                changed_paths=("src/widget.py",),
            ),
        )

        self.assertFalse(result.reusable)
        self.assertIn("covered path changed", result.reasons)

    def test_c0_invalidates_record_evidence_but_not_implementation_evidence(self):
        event = ChangeEvent(
            change_class=ChangeClass.C0_RECORD_ONLY,
            changed_paths=("docs/ACTIVE_CONTEXT.md",),
        )

        record_result = assess_evidence(
            evidence(
                kind="record-consistency",
                covered_paths=("docs/ACTIVE_CONTEXT.md",),
            ),
            event,
        )
        implementation_result = assess_evidence(evidence(), event)

        self.assertFalse(record_result.reusable)
        self.assertTrue(implementation_result.reusable)

    def test_c2_contract_change_invalidates_only_matching_semantic_evidence(self):
        event = ChangeEvent(
            change_class=ChangeClass.C2_CONTRACT_AFFECTING,
            changed_contracts=("authority-v2",),
        )
        matching = assess_evidence(
            evidence(
                kind="semantic",
                covered_paths=(),
                covered_contracts=("authority-v2",),
            ),
            event,
        )
        unrelated = assess_evidence(
            evidence(
                evidence_id="E-2",
                kind="semantic",
                covered_paths=(),
                covered_contracts=("api-v1",),
            ),
            event,
        )

        self.assertFalse(matching.reusable)
        self.assertTrue(unrelated.reusable)


class ExecutionLimitAndReviewTests(unittest.TestCase):
    def test_limit_exhaustion_returns_handoff_ready(self):
        counters = ExecutionCounters(full_suite_runs_after_baseline=1)

        decision = consume_event(counters, ExecutionLimits(), "full_suite_runs_after_baseline")

        self.assertEqual(RunState.HANDOFF_READY, decision.state)
        self.assertEqual(1, decision.counters.full_suite_runs_after_baseline)

    def test_two_no_progress_rounds_block_same_root_cause(self):
        counters = ExecutionCounters()

        first = record_root_cause_progress(counters, ExecutionLimits(), "schema-drift", False)
        second = record_root_cause_progress(
            first.counters,
            ExecutionLimits(),
            "schema-drift",
            False,
        )

        self.assertEqual(RunState.CONTINUE, first.state)
        self.assertEqual(RunState.BLOCKED, second.state)

    def test_unrelated_new_p2_and_p3_enter_backlog(self):
        state = ReviewState()
        initial = ReviewReport(
            scope="contract",
            findings=(
                ReviewFinding("F-1", Priority.P2, "validator", "bad-selection"),
            ),
        )
        accepted = accept_initial_report(state, initial, ExecutionLimits())
        rereview = ReviewReport(
            scope="contract",
            findings=(
                ReviewFinding("F-2", Priority.P2, "documentation", "wording"),
                ReviewFinding("F-3", Priority.P3, "style", "formatting"),
            ),
        )

        result = evaluate_corrective_rereview(
            accepted.state,
            initial,
            rereview,
            ExecutionLimits(),
        )

        self.assertEqual(RunState.CONTINUE, result.outcome)
        self.assertEqual(("F-2", "F-3"), tuple(item.finding_id for item in result.backlog))
        self.assertEqual((), result.blocking_findings)

    def test_shared_file_density_detects_overlapping_writes(self):
        self.assertTrue(
            shared_file_density(
                (
                    ("sagekit/cli.py", "sagekit/check.py"),
                    ("sagekit/cli.py", "tests/test_cli.py"),
                )
            )
        )


class PathingTests(unittest.TestCase):
    def test_windows_contract_paths_are_case_insensitive(self):
        left = normalize_contract_path(r"C:\Repo\Src\Widget.py", platform="windows")
        right = normalize_contract_path(r"c:/repo/src/widget.py", platform="windows")
        self.assertEqual(left, right)

    def test_resolved_symlink_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as root_name, tempfile.TemporaryDirectory() as outside_name:
            root = Path(root_name)
            link = root / "escape"
            try:
                link.symlink_to(Path(outside_name), target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation is unavailable")
            self.assertFalse(is_within(root, link / "file.txt"))


class ContinuityTests(unittest.TestCase):
    def test_matching_repo_branch_and_head_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            created = create_checkpoint(
                root,
                run_id="run-1",
                goal="Finish the approved change",
                authority_id="request",
                authority_version="1",
                authority_summary="Direct maintainer request",
                change_class=ChangeClass.C1_BOUNDED_CORRECTIVE,
                completed_work=("baseline verified",),
                open_findings=(),
                evidence_references=(),
                invalidated_evidence=(),
                execution_counters=ExecutionCounters(),
                next_action="implement focused module",
                allowed_paths=("sagekit/", "tests/"),
                stop_conditions=("authority expands",),
            )

            result = resume_checkpoint(root)

            self.assertTrue(created.ok)
            self.assertTrue(result.ok)
            self.assertEqual("implement focused module", result.checkpoint["next_action"])

    def test_head_drift_fails_closed_with_aggregate_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            create_checkpoint(
                root,
                run_id="run-2",
                goal="Resume safely",
                authority_id="request",
                authority_version="1",
                authority_summary="Direct maintainer request",
                change_class=ChangeClass.C0_RECORD_ONLY,
                completed_work=(),
                open_findings=(),
                evidence_references=(),
                invalidated_evidence=(),
                execution_counters=ExecutionCounters(),
                next_action="update a record",
                allowed_paths=("docs/",),
                stop_conditions=(),
            )
            (root / "tracked.txt").write_text("changed\n", encoding="utf-8")
            git(root, "add", "tracked.txt")
            git(root, "commit", "-m", "drift")

            result = resume_checkpoint(root)

            self.assertFalse(result.ok)
            self.assertEqual("checkpoint-mismatch", result.rule)
            self.assertTrue(any("HEAD" in mismatch for mismatch in result.mismatches))

    def test_missing_and_corrupt_checkpoint_have_clear_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)

            missing = resume_checkpoint(root)
            checkpoint_path(root).parent.mkdir(parents=True)
            checkpoint_path(root).write_text("{not json", encoding="utf-8")
            corrupt = resume_checkpoint(root)

            self.assertEqual("checkpoint-missing", missing.rule)
            self.assertEqual("checkpoint-corrupt", corrupt.rule)

    def test_clear_removes_only_current_run_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            create_checkpoint(
                root,
                run_id="run-3",
                goal="Clear safely",
                authority_id="request",
                authority_version="1",
                authority_summary="Direct maintainer request",
                change_class=ChangeClass.C0_RECORD_ONLY,
                completed_work=(),
                open_findings=(),
                evidence_references=(),
                invalidated_evidence=(),
                execution_counters=ExecutionCounters(),
                next_action="none",
                allowed_paths=("docs/",),
                stop_conditions=(),
            )
            sibling = checkpoint_path(root).parent / "keep.txt"
            sibling.write_text("keep", encoding="utf-8")

            result = clear_checkpoint(root)

            self.assertTrue(result.ok)
            self.assertFalse(checkpoint_path(root).exists())
            self.assertTrue(sibling.exists())

    def test_checkpoint_json_is_compact_and_has_required_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            create_checkpoint(
                root,
                run_id="run-4",
                goal="Compact checkpoint",
                authority_id="request",
                authority_version="1",
                authority_summary="Direct maintainer request",
                change_class=ChangeClass.C0_RECORD_ONLY,
                completed_work=("one",),
                open_findings=(),
                evidence_references=(),
                invalidated_evidence=(),
                execution_counters=ExecutionCounters(),
                next_action="two",
                allowed_paths=("docs/",),
                stop_conditions=(),
            )

            payload = json.loads(checkpoint_path(root).read_text(encoding="utf-8"))

            for field in (
                "run_id",
                "goal",
                "repository_root",
                "branch",
                "base_sha",
                "head_sha",
                "authority",
                "change_class",
                "completed_work",
                "open_findings",
                "evidence_references",
                "invalidated_evidence",
                "execution_counters",
                "next_action",
                "allowed_paths",
                "stop_conditions",
            ):
                self.assertIn(field, payload)
            self.assertLess(checkpoint_path(root).stat().st_size, 32_000)

    def test_authority_payload_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            create_checkpoint(
                root,
                run_id="run-5",
                goal="Protect authority",
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
                stop_conditions=(),
            )
            payload = json.loads(checkpoint_path(root).read_text(encoding="utf-8"))
            payload["authority"]["version"] = "2"
            checkpoint_path(root).write_text(json.dumps(payload), encoding="utf-8")

            result = resume_checkpoint(root)

            self.assertFalse(result.ok)
            self.assertTrue(any("authority payload digest" in item for item in result.mismatches))

    def test_tracked_runtime_finding_names_git_hygiene_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            runtime = root / ".sagekit/runtime/CURRENT_RUN.json"
            runtime.parent.mkdir(parents=True)
            runtime.write_text("{}\n", encoding="utf-8")
            git(root, "add", "-f", ".sagekit/runtime/CURRENT_RUN.json")
            git(root, "commit", "-m", "track forbidden runtime")

            findings = check_source_tracked_runtime(root)

            self.assertEqual("FAIL", findings[0].level)
            self.assertIn(".sagekit/runtime content is tracked by Git", findings[0].message)


class ContinuityCliTests(unittest.TestCase):
    def test_checkpoint_cli_create_status_resume_and_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)

            created = run_sagekit(
                "checkpoint",
                "create",
                "--target",
                str(root),
                "--run-id",
                "cli-run",
                "--goal",
                "Resume without copied chat",
                "--authority-id",
                "maintainer-request",
                "--authority-version",
                "1",
                "--authority-summary",
                "Direct maintainer request",
                "--change-class",
                "C1",
                "--completed-work",
                "baseline verified",
                "--next-action",
                "continue focused implementation",
                "--allowed-path",
                "sagekit/",
                "--stop-condition",
                "authority expands",
                cwd=root,
            )
            status = run_sagekit(
                "checkpoint",
                "status",
                "--target",
                str(root),
                "--json",
                cwd=root,
            )
            resumed = run_sagekit("resume", "--target", str(root), "--json", cwd=root)
            cleared = run_sagekit(
                "checkpoint",
                "clear",
                "--target",
                str(root),
                cwd=root,
            )

            self.assertEqual(0, created.returncode, created.stderr)
            self.assertEqual(0, status.returncode, status.stderr)
            self.assertEqual("checkpoint-resumable", json.loads(status.stdout)["findings"][0]["rule"])
            self.assertEqual(0, resumed.returncode, resumed.stderr)
            resume_payload = json.loads(resumed.stdout)
            self.assertEqual(
                "continue focused implementation",
                resume_payload["resume"]["next_action"],
            )
            self.assertNotIn("authority_summary", resume_payload)
            self.assertEqual(0, cleared.returncode, cleared.stderr)
            self.assertFalse(checkpoint_path(root).exists())

    def test_checkpoint_cli_reports_missing_checkpoint_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)

            result = run_sagekit("resume", "--target", str(root), cwd=root)

            self.assertEqual(1, result.returncode)
            self.assertIn("checkpoint-missing", result.stdout)
            self.assertNotIn("Traceback", result.stderr)


class DocumentationPolicyTests(unittest.TestCase):
    def test_execution_economy_and_continuity_docs_are_packaged_mirrors(self):
        for relative in (
            "agent/EXECUTION_ECONOMY.md",
            "agent/CONTINUITY_PROTOCOL.md",
        ):
            source = REPO_ROOT / "docs" / relative
            packaged = REPO_ROOT / "sagekit/resources/docs" / relative
            self.assertTrue(source.is_file(), relative)
            self.assertEqual(
                source.read_text(encoding="utf-8"),
                packaged.read_text(encoding="utf-8"),
            )

    def test_execution_economy_doc_contains_normative_contracts(self):
        text = (REPO_ROOT / "docs/agent/EXECUTION_ECONOMY.md").read_text(encoding="utf-8")
        for token in (
            "C0 Record-only",
            "C1 Bounded corrective",
            "C2 Contract-affecting",
            "C3 External/destructive",
            "Bounded Corrective Authority",
            "AUTHORITY_DELTA",
            "focused verification",
            "affected-lane verification",
            "final integration verification",
            "Evidence Fingerprint",
            "Review Convergence Contract",
            "HANDOFF_READY",
            "HUMAN_DECISION_REQUIRED",
        ):
            self.assertIn(token, text)
        self.assertNotRegex(text, r"\b(?:70|85|100)%\s+token")

    def test_continuity_doc_defines_checkpoint_and_commands(self):
        text = (REPO_ROOT / "docs/agent/CONTINUITY_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn(".sagekit/runtime/CURRENT_RUN.json", text)
        self.assertIn("sagekit checkpoint create", text)
        self.assertIn("sagekit checkpoint status", text)
        self.assertIn("sagekit resume", text)
        self.assertIn("sagekit checkpoint clear", text)
        self.assertIn("fail closed", text)

    def test_core_records_bootstrap_maintainer_exception_without_project_bypass(self):
        text = (REPO_ROOT / "docs/SAGE_CORE.md").read_text(encoding="utf-8")
        self.assertIn("Bootstrap Maintainer Policy", text)
        self.assertIn("dogfood is a validation mode", text)
        self.assertIn("does not apply to adopted target projects", text)

    def test_skill_routes_resume_and_record_only_changes_economically(self):
        text = (REPO_ROOT / "skills/sage-kit/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("sagekit resume", text)
        self.assertIn("C0 record-only", text)
        self.assertIn("targeted record consistency verification", text)
        self.assertIn("one primary review topology", text)

    def test_runtime_checkpoint_is_gitignored(self):
        lines = {
            line.strip()
            for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        }
        self.assertIn(".sagekit/", lines)

    def test_source_manifest_includes_execution_economy_runtime(self):
        from sagekit.check import SOURCE_REQUIRED_FILES

        for relative in (
            "docs/agent/EXECUTION_ECONOMY.md",
            "docs/agent/CONTINUITY_PROTOCOL.md",
            "sagekit/pathing.py",
            "sagekit/change_control.py",
            "sagekit/evidence.py",
            "sagekit/execution_limits.py",
            "sagekit/review.py",
            "sagekit/continuity.py",
            "tests/test_execution_economy.py",
        ):
            self.assertIn(relative, SOURCE_REQUIRED_FILES)


if __name__ == "__main__":
    unittest.main()
