import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from sagekit.candidate import CandidateFingerprint, assess_candidate, freeze_candidate
from sagekit.change_control import ChangeClass, RunState
from sagekit.continuity import checkpoint_path, create_checkpoint, resume_checkpoint
from sagekit.convergence import (
    ConvergenceEvidence,
    PreauthorizedConvergenceAuthority,
    load_convergence_authority,
    paths_outside_authority,
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


REPO_ROOT = Path(__file__).resolve().parents[1]


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


def commit_change(root: Path, content: str, relative: str = "tracked.txt") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    git(root, "add", relative)
    git(root, "commit", "-m", "deterministic corrective")


def run_sagekit(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
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


def authority(**overrides) -> PreauthorizedConvergenceAuthority:
    values = {
        "authority_id": "AUTH-CONVERGENCE-1",
        "mode": "preauthorized",
        "execution_scope": "execution-unit-1",
        "root_cause_family": "portability",
        "allowed_paths": ("tracked.txt", "sagekit/", "tests/"),
        "invariant": "canonical containment remains unchanged",
        "semantic_change_policy": "implementation-preserving-only",
        "targeted_review_required": True,
        "stop_conditions": (
            "allowed path expansion",
            "security invariant change",
            "test weakening",
            "two no-progress rounds",
        ),
        "approved_by": "project-owner-role",
        "authority_ref": "approval-packet-1",
    }
    values.update(overrides)
    return PreauthorizedConvergenceAuthority(**values)


def evidence(
    count: int,
    *,
    root_cause_id: str = "path-representation",
    severity: int | None = 3,
    **overrides,
) -> ConvergenceEvidence:
    values = {
        "execution_scope": "execution-unit-1",
        "root_cause_family": "portability",
        "root_cause_id": root_cause_id,
        "finding_count": count,
        "finding_severity": severity,
        "semantic_change": "implementation-preserving",
        "targeted_review_closed": True,
    }
    values.update(overrides)
    return ConvergenceEvidence(**values)


def freeze(root: Path, **overrides):
    values = {
        "contract_digest": "contracts-v1",
        "dependency_digest": "dependencies-v1",
        "review_closed": True,
        "corrective_batch_closed": True,
    }
    values.update(overrides)
    return freeze_candidate(root, **values)


def window_candidate(root: Path, count: int = 9, **overrides):
    values = {
        "convergence_authority": authority(),
        "convergence_evidence": evidence(count),
    }
    values.update(overrides)
    return freeze(root, **values)


def successor(root: Path, previous, count: int, **overrides):
    commit_change(root, f"corrective-{previous.generation}-{count}\n")
    values = {
        "previous": previous,
        "approved_corrective": True,
        "previous_final_verified": True,
        "convergence_authority": authority(),
        "convergence_evidence": evidence(count),
    }
    values.update(overrides)
    return freeze(root, **values)


def rewrite_checkpoint(root: Path, payload: dict[str, object]) -> None:
    unsigned = {key: value for key, value in payload.items() if key != "payload_sha256"}
    encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["payload_sha256"] = hashlib.sha256(encoded).hexdigest()
    checkpoint_path(root).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def resign_candidate(payload: dict[str, object]) -> None:
    unsigned = {key: value for key, value in payload.items() if key != "fingerprint"}
    encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["fingerprint"] = hashlib.sha256(encoded).hexdigest()


class AuthorityModelTests(unittest.TestCase):
    def test_authority_has_canonical_json_and_stable_digest(self):
        first = authority()
        second = PreauthorizedConvergenceAuthority.from_dict(
            json.loads(first.canonical_json)
        )

        self.assertEqual(first.canonical_json, second.canonical_json)
        self.assertEqual(first.digest, second.digest)
        self.assertRegex(first.digest, r"^[0-9a-f]{64}$")

    def test_loader_accepts_wrapped_authority_document(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.json"
            path.write_text(
                json.dumps({"convergence_authority": authority().to_dict()}),
                encoding="utf-8",
            )

            loaded = load_convergence_authority(path)

        self.assertEqual(authority(), loaded)

    def test_empty_identity_and_approval_fields_fail_closed(self):
        for field in (
            "authority_id",
            "execution_scope",
            "root_cause_family",
            "invariant",
            "approved_by",
            "authority_ref",
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    authority(**{field: " "})

    def test_missing_paths_and_stop_conditions_fail_closed(self):
        for field in ("allowed_paths", "stop_conditions"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    authority(**{field: ()})

    def test_absolute_and_parent_allowed_paths_are_rejected(self):
        for path in (
            "/tmp/outside",
            r"C:\outside",
            "../outside",
            "sagekit/../../outside",
            "sagekit/*.py",
            "tests/?fixture.py",
        ):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    authority(allowed_paths=(path,))

    def test_unknown_or_malformed_authority_fields_fail_closed(self):
        payload = authority().to_dict()
        payload["unexpected"] = True
        with self.assertRaises(ValueError):
            PreauthorizedConvergenceAuthority.from_dict(payload)

    def test_sibling_prefix_is_not_inside_allowed_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = paths_outside_authority(
                root,
                authority(allowed_paths=("sagekit/",)),
                ("sagekit-other/module.py",),
            )

        self.assertEqual(("sagekit-other/module.py",), outside)

    def test_windows_and_posix_separators_preserve_component_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            window = authority(allowed_paths=("sagekit/",))

            posix = paths_outside_authority(root, window, ("sagekit/module.py",))
            windows = paths_outside_authority(root, window, (r"sagekit\module.py",))

        self.assertEqual((), posix)
        self.assertEqual((), windows)

    def test_symlink_escape_is_outside_window_authority(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            link = root / "sagekit"
            try:
                link.symlink_to(Path(outside), target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation is unavailable")

            escaped = paths_outside_authority(
                root,
                authority(allowed_paths=("sagekit/",)),
                ("sagekit/module.py",),
            )

        self.assertEqual(("sagekit/module.py",), escaped)
        payload = authority().to_dict()
        payload["targeted_review_required"] = "yes"
        with self.assertRaises(ValueError):
            PreauthorizedConvergenceAuthority.from_dict(payload)


class CandidateCompatibilityTests(unittest.TestCase):
    def test_no_window_retains_single_automatic_successor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = freeze(root)
            commit_change(root, "first corrective\n")
            second = freeze(
                root,
                previous=first.candidate,
                approved_corrective=True,
                corrective_batch_id="batch-1",
            )

        self.assertTrue(second.ok)
        self.assertEqual(2, second.candidate.generation)
        self.assertIsNone(second.candidate.convergence_authority_digest)

    def test_no_window_rejects_later_unapproved_successor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = freeze(root)
            commit_change(root, "first corrective\n")
            second = freeze(
                root,
                previous=first.candidate,
                approved_corrective=True,
                corrective_batch_id="batch-1",
            )
            commit_change(root, "second corrective\n")
            third = freeze(
                root,
                previous=second.candidate,
                approved_corrective=False,
                corrective_batch_id="batch-2",
            )

        self.assertFalse(third.ok)
        self.assertEqual(RunState.HANDOFF_READY, third.state)

    def test_legacy_candidate_does_not_gain_an_implicit_window(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = freeze(root)
            self.assertIsNone(first.candidate.convergence_authority_digest)

            commit_change(root, "candidate changed\n")
            continued = freeze(
                root,
                previous=first.candidate,
                approved_corrective=True,
                previous_final_verified=True,
            )

        self.assertFalse(continued.ok)
        self.assertEqual(RunState.HANDOFF_READY, continued.state)

    def test_stable_legacy_candidate_rejects_explicit_window_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            current = freeze(root).candidate

            result = freeze(
                root,
                previous=current,
                convergence_authority=authority(),
                convergence_evidence=evidence(1),
            )

        self.assertFalse(result.ok)
        self.assertEqual(RunState.HANDOFF_READY, result.state)

    def test_stable_window_candidate_rejects_replacement_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            current = window_candidate(root, 3).candidate

            result = freeze(
                root,
                previous=current,
                convergence_authority=authority(invariant="replacement invariant"),
                convergence_evidence=evidence(3),
            )

        self.assertFalse(result.ok)
        self.assertEqual(RunState.HANDOFF_READY, result.state)

    def test_stable_window_candidate_rejects_policy_changing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            current = window_candidate(root, 3).candidate

            result = freeze(
                root,
                previous=current,
                convergence_authority=authority(),
                convergence_evidence=evidence(3, semantic_change="policy-changing"),
            )

        self.assertFalse(result.ok)
        self.assertEqual(RunState.HANDOFF_READY, result.state)

    def test_stable_window_candidate_blocks_unavailable_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            current = window_candidate(root, 3).candidate

            result = freeze(
                root,
                previous=current,
                convergence_authority=authority(),
                convergence_evidence=evidence(3, required_evidence_unavailable=True),
            )

        self.assertFalse(result.ok)
        self.assertEqual(RunState.BLOCKED, result.state)

    def test_stable_window_candidate_rejects_authority_precedence_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            current = window_candidate(root, 3).candidate

            result = freeze(
                root,
                previous=current,
                convergence_authority=authority(),
                convergence_evidence=evidence(3, authority_precedence_changed=True),
            )

        self.assertFalse(result.ok)
        self.assertEqual(RunState.HANDOFF_READY, result.state)


class ConvergenceSuccessorTests(unittest.TestCase):
    def test_preauthorized_window_allows_generations_two_three_and_four(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            current = window_candidate(root, 9).candidate
            generations = []
            for count in (6, 3, 0):
                result = successor(root, current, count)
                self.assertTrue(result.ok, result.message)
                current = result.candidate
                generations.append(current.generation)

        self.assertEqual([2, 3, 4], generations)

    def test_anonymous_nine_six_zero_scenario_needs_no_intermediate_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 9)
            second = successor(root, first.candidate, 6)
            third = successor(root, second.candidate, 0)

        self.assertEqual(RunState.CONTINUE, second.state)
        self.assertEqual(RunState.CONTINUE, third.state)
        self.assertEqual("finding-count-decreased", third.finding_trend)
        self.assertTrue(third.candidate.targeted_review_closed)

    def test_severity_decrease_allows_progress_when_count_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 6).candidate
            result = successor(
                root,
                first,
                6,
                convergence_evidence=evidence(6, severity=2),
            )

        self.assertTrue(result.ok, result.message)
        self.assertEqual("severity-decreased", result.finding_trend)
        self.assertEqual(0, result.candidate.no_progress_rounds)

    def test_new_root_cause_id_in_same_family_can_continue_when_findings_fall(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 6).candidate
            result = successor(
                root,
                first,
                4,
                convergence_evidence=evidence(4, root_cause_id="shell-quoting"),
            )

        self.assertTrue(result.ok, result.message)
        self.assertEqual("shell-quoting", result.candidate.root_cause_id)
        self.assertEqual("portability", result.candidate.root_cause_family)

    def test_next_layer_exception_allows_increase_only_with_targeted_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 3).candidate
            result = successor(
                root,
                first,
                5,
                convergence_evidence=evidence(
                    5,
                    root_cause_id="resource-layout",
                    next_layer_exposed=True,
                ),
            )

        self.assertTrue(result.ok, result.message)
        self.assertEqual("next-layer-exposed", result.finding_trend)

    def test_severity_drop_cannot_mask_finding_count_increase(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 1).candidate
            result = successor(
                root,
                first,
                100,
                convergence_evidence=evidence(100, severity=2),
            )

        self.assertFalse(result.ok)
        self.assertEqual(RunState.HANDOFF_READY, result.state)

    def test_successors_bind_new_fingerprint_predecessor_and_authority_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 9).candidate
            second = successor(root, first, 6).candidate

        self.assertNotEqual(first.digest, second.digest)
        self.assertEqual(first.digest, second.predecessor_digest)
        self.assertEqual(authority().digest, second.convergence_authority_digest)

    def test_each_candidate_keeps_independent_final_counters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 9).candidate
            first_assessment = assess_candidate(
                root,
                first,
                contract_digest="contracts-v1",
                dependency_digest="dependencies-v1",
            )
            prepared = prepare_verification_run(
                ExecutionCounters(),
                VerificationKind.FULL_SUITE,
                VerificationPreflight(
                    "candidate-1",
                    first.digest,
                    (VerificationPreflightCheck("ready", True),),
                ),
                candidate=first,
                assessment=first_assessment,
            )
            counted = begin_verification_run(
                prepared.counters,
                ExecutionLimits(),
                "candidate-1",
                candidate=first,
                assessment=first_assessment,
            )
            second = successor(root, first, 6).candidate
            second_assessment = assess_candidate(
                root,
                second,
                contract_digest="contracts-v1",
                dependency_digest="dependencies-v1",
            )
            second_prepared = prepare_verification_run(
                counted.counters,
                VerificationKind.FULL_SUITE,
                VerificationPreflight(
                    "candidate-2",
                    second.digest,
                    (VerificationPreflightCheck("ready", True),),
                ),
                candidate=second,
                assessment=second_assessment,
            )
            second_counted = begin_verification_run(
                second_prepared.counters,
                ExecutionLimits(),
                "candidate-2",
                candidate=second,
                assessment=second_assessment,
            )

        self.assertEqual(1, second_counted.counters.final_full_suite_runs[first.digest])
        self.assertEqual(1, second_counted.counters.final_full_suite_runs[second.digest])

    def test_same_candidate_cannot_repeat_final_full_suite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            current = window_candidate(root, 9).candidate
            assessment = assess_candidate(
                root,
                current,
                contract_digest="contracts-v1",
                dependency_digest="dependencies-v1",
            )
            first_ready = prepare_verification_run(
                ExecutionCounters(),
                VerificationKind.FULL_SUITE,
                VerificationPreflight(
                    "first", current.digest, (VerificationPreflightCheck("ready", True),)
                ),
                candidate=current,
                assessment=assessment,
            )
            first = begin_verification_run(
                first_ready.counters,
                ExecutionLimits(),
                "first",
                candidate=current,
                assessment=assessment,
            )
            second_ready = prepare_verification_run(
                first.counters,
                VerificationKind.FULL_SUITE,
                VerificationPreflight(
                    "second", current.digest, (VerificationPreflightCheck("ready", True),)
                ),
                candidate=current,
                assessment=assessment,
            )
            second = begin_verification_run(
                second_ready.counters,
                ExecutionLimits(),
                "second",
                candidate=current,
                assessment=assessment,
            )

        self.assertEqual(RunState.HANDOFF_READY, second.state)

    def test_preflight_failure_does_not_consume_candidate_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            current = window_candidate(root, 9).candidate
            assessment = assess_candidate(
                root,
                current,
                contract_digest="contracts-v1",
                dependency_digest="dependencies-v1",
            )
            decision = prepare_verification_run(
                ExecutionCounters(),
                VerificationKind.WHEEL_INSTALL,
                VerificationPreflight(
                    "preflight-fail",
                    current.digest,
                    (VerificationPreflightCheck("builder", False),),
                ),
                candidate=current,
                assessment=assessment,
            )

        self.assertFalse(decision.allowed_to_run)
        self.assertEqual({}, decision.counters.final_wheel_install_runs)


class ConvergenceStopTests(unittest.TestCase):
    def assert_authority_change_handoffs(self, field: str, value) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 6).candidate
            result = successor(
                root,
                first,
                5,
                convergence_authority=authority(**{field: value}),
            )
        self.assertFalse(result.ok)
        self.assertEqual(RunState.HANDOFF_READY, result.state)

    def test_allowed_path_expansion_handoffs(self):
        self.assert_authority_change_handoffs(
            "allowed_paths", ("tracked.txt", "sagekit/", "tests/", "shared/")
        )

    def test_invariant_change_handoffs(self):
        self.assert_authority_change_handoffs("invariant", "containment may be relaxed")

    def test_execution_scope_change_handoffs(self):
        self.assert_authority_change_handoffs("execution_scope", "execution-unit-2")

    def test_root_cause_family_change_handoffs(self):
        self.assert_authority_change_handoffs("root_cause_family", "unrelated-family")

    def test_changed_path_outside_allowed_paths_handoffs(self):
        narrow = authority(allowed_paths=("sagekit/",))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(
                root,
                6,
                convergence_authority=narrow,
            ).candidate
            result = successor(
                root,
                first,
                5,
                convergence_authority=narrow,
            )

        self.assertFalse(result.ok)
        self.assertEqual(RunState.HANDOFF_READY, result.state)
        self.assertIn("outside convergence allowed paths", result.message)

    def test_working_tree_untracked_path_cannot_bypass_convergence_authority(self):
        narrow = authority(allowed_paths=("tracked.txt",))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            (root / "outside.txt").write_text("not authorized\n", encoding="utf-8")
            result = freeze(
                root,
                snapshot_mode="working-tree",
                snapshot_authority="AUTH-SNAPSHOT-1",
                convergence_authority=narrow,
                convergence_evidence=evidence(1),
            )

        self.assertFalse(result.ok)
        self.assertEqual(RunState.HANDOFF_READY, result.state)
        self.assertIn("outside.txt", result.message)

    def test_working_tree_deleted_path_cannot_bypass_convergence_authority(self):
        narrow = authority(allowed_paths=("allowed/",))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            (root / "tracked.txt").unlink()
            result = freeze(
                root,
                snapshot_mode="working-tree",
                snapshot_authority="AUTH-SNAPSHOT-1",
                convergence_authority=narrow,
                convergence_evidence=evidence(1),
            )

        self.assertFalse(result.ok)
        self.assertIn("tracked.txt", result.message)

    @unittest.skipIf(os.name == "nt", "POSIX backslash filename regression")
    def test_committed_backslash_path_fails_closed_during_authority_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            (root / "back\\slash.txt").write_text("unsafe path\n", encoding="utf-8")
            git(root, "add", "back\\slash.txt")
            git(root, "commit", "-m", "add unrepresentable path")

            result = freeze(
                root,
                convergence_authority=authority(allowed_paths=("tracked.txt",)),
                convergence_evidence=evidence(1),
            )

        self.assertFalse(result.ok)
        self.assertIn("unsupported backslash", result.message)

    def test_dirty_submodule_fails_closed_in_working_tree_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            child = base / "child"
            root = base / "root"
            child.mkdir()
            root.mkdir()
            init_repository(child)
            init_repository(root)
            git(
                root,
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                str(child),
                "vendor/child",
            )
            git(root, "commit", "-m", "add submodule")
            (root / "vendor/child/tracked.txt").write_text(
                "dirty submodule\n", encoding="utf-8"
            )

            result = freeze(
                root,
                snapshot_mode="working-tree",
                snapshot_authority="AUTH-SNAPSHOT-1",
            )

        self.assertFalse(result.ok)
        self.assertIn("dirty submodule", result.message)

    def test_policy_changing_classification_handoffs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 6).candidate
            result = successor(
                root,
                first,
                5,
                convergence_evidence=evidence(5, semantic_change="policy-changing"),
            )

        self.assertEqual(RunState.HANDOFF_READY, result.state)

    def test_missing_targeted_review_handoffs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 6).candidate
            result = successor(
                root,
                first,
                5,
                convergence_evidence=evidence(5, targeted_review_closed=False),
            )

        self.assertEqual(RunState.HANDOFF_READY, result.state)

    def test_test_or_gate_weakening_handoffs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 6).candidate
            result = successor(
                root,
                first,
                5,
                convergence_evidence=evidence(5, test_or_gate_weakened=True),
            )

        self.assertEqual(RunState.HANDOFF_READY, result.state)

    def test_other_scope_security_and_permission_stops_handoff(self):
        flags = (
            "product_scope_expanded",
            "approval_gate_opened",
            "permissions_increased",
            "security_or_evidence_weakened",
            "contract_or_public_behavior_changed",
            "consumer_mutation",
        )
        for flag in flags:
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                init_repository(root)
                first = window_candidate(root, 6).candidate
                result = successor(
                    root,
                    first,
                    5,
                    convergence_evidence=evidence(5, **{flag: True}),
                )
                self.assertEqual(RunState.HANDOFF_READY, result.state)

    def test_finding_increase_without_next_layer_evidence_handoffs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 3).candidate
            result = successor(root, first, 5)

        self.assertEqual(RunState.HANDOFF_READY, result.state)

    def test_severity_increase_without_next_layer_evidence_handoffs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 3).candidate
            result = successor(
                root,
                first,
                3,
                convergence_evidence=evidence(3, severity=4),
            )

        self.assertEqual(RunState.HANDOFF_READY, result.state)

    def test_required_evidence_unavailable_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 3).candidate
            result = successor(
                root,
                first,
                2,
                convergence_evidence=evidence(2, required_evidence_unavailable=True),
            )

        self.assertEqual(RunState.BLOCKED, result.state)

    def test_authority_precedence_change_handoffs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 3).candidate
            result = successor(
                root,
                first,
                2,
                convergence_evidence=evidence(2, authority_precedence_changed=True),
            )

        self.assertEqual(RunState.HANDOFF_READY, result.state)

    def test_rename_from_outside_allowed_scope_handoffs(self):
        narrow = authority(allowed_paths=("allowed/",))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(
                root,
                3,
                convergence_authority=narrow,
            ).candidate
            (root / "allowed").mkdir()
            git(root, "mv", "tracked.txt", "allowed/tracked.txt")
            git(root, "commit", "-m", "rename across authority boundary")
            result = freeze(
                root,
                previous=first,
                approved_corrective=True,
                previous_final_verified=True,
                convergence_authority=narrow,
                convergence_evidence=evidence(2),
            )

        self.assertFalse(result.ok)
        self.assertEqual(RunState.HANDOFF_READY, result.state)
        self.assertIn("tracked.txt", result.message)

    def test_first_no_progress_round_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 6).candidate
            result = successor(root, first, 6)

        self.assertTrue(result.ok, result.message)
        self.assertEqual(1, result.candidate.no_progress_rounds)

    def test_six_six_six_blocks_after_two_no_progress_rounds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 6).candidate
            second = successor(root, first, 6)
            third = successor(root, second.candidate, 6)

        self.assertTrue(second.ok)
        self.assertFalse(third.ok)
        self.assertEqual(RunState.BLOCKED, third.state)

    def test_finding_reduction_resets_no_progress_rounds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            first = window_candidate(root, 6).candidate
            second = successor(root, first, 6).candidate
            third = successor(root, second, 5)

        self.assertTrue(third.ok, third.message)
        self.assertEqual(0, third.candidate.no_progress_rounds)


class ConvergenceCheckpointTests(unittest.TestCase):
    def create(self, root: Path, current=None, window=None):
        return create_checkpoint(
            root,
            run_id="convergence-run",
            goal="Converge deterministic failures",
            authority_id="request",
            authority_version="1",
            authority_summary="Direct request",
            change_class=ChangeClass.C1_BOUNDED_CORRECTIVE,
            completed_work=(),
            open_findings=(),
            evidence_references=(),
            invalidated_evidence=(),
            execution_counters=ExecutionCounters(),
            next_action="create successor",
            allowed_paths=("tracked.txt",),
            stop_conditions=("scope changes",),
            candidate=current,
            convergence_authority=window,
        )

    def test_checkpoint_persists_and_resumes_complete_window(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            current = window_candidate(root, 9).candidate
            created = self.create(root, current, authority())
            resumed = resume_checkpoint(root)

        self.assertEqual(4, created.checkpoint["schema_version"])
        self.assertTrue(resumed.ok, resumed.mismatches)
        self.assertEqual(authority().to_dict(), resumed.checkpoint["convergence_authority"])
        self.assertEqual("path-representation", resumed.checkpoint["candidate"]["root_cause_id"])
        self.assertEqual(9, resumed.checkpoint["candidate"]["open_findings_count"])

    def test_authority_digest_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            current = window_candidate(root, 9).candidate
            self.create(root, current, authority())
            payload = json.loads(checkpoint_path(root).read_text(encoding="utf-8"))
            payload["convergence_authority"]["authority_id"] = "AUTH-REPLACED"
            rewrite_checkpoint(root, payload)
            resumed = resume_checkpoint(root)

        self.assertFalse(resumed.ok)
        self.assertTrue(any("convergence authority digest" in item for item in resumed.mismatches))

    def test_allowed_path_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            current = window_candidate(root, 9).candidate
            self.create(root, current, authority())
            payload = json.loads(checkpoint_path(root).read_text(encoding="utf-8"))
            payload["convergence_authority"]["allowed_paths"].append("shared/")
            rewrite_checkpoint(root, payload)
            resumed = resume_checkpoint(root)

        self.assertFalse(resumed.ok)
        self.assertTrue(any("convergence authority digest" in item for item in resumed.mismatches))

    def test_candidate_authority_snapshot_tamper_fails_closed(self):
        replacements = {
            "convergence_authority_id": "AUTH-REPLACED",
            "execution_scope": "execution-unit-2",
            "root_cause_family": "other-family",
            "convergence_allowed_paths": ["shared/"],
            "convergence_invariant": "replacement invariant",
            "convergence_semantic_change_policy": "replacement policy",
            "convergence_stop_conditions": ["replacement stop"],
        }
        for field, replacement in replacements.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                init_repository(root)
                current = window_candidate(root, 9).candidate
                self.create(root, current, authority())
                payload = json.loads(checkpoint_path(root).read_text(encoding="utf-8"))
                payload["candidate"][field] = replacement
                resign_candidate(payload["candidate"])
                rewrite_checkpoint(root, payload)

                resumed = resume_checkpoint(root)

                self.assertFalse(resumed.ok)
                self.assertTrue(
                    any("candidate convergence authority" in item for item in resumed.mismatches),
                    resumed.mismatches,
                )

    def test_old_v3_checkpoint_migrates_without_implicit_window(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            created = self.create(root)
            payload = dict(created.checkpoint)
            payload["schema_version"] = 3
            payload.pop("convergence_authority")
            rewrite_checkpoint(root, payload)
            resumed = resume_checkpoint(root)

        self.assertTrue(resumed.ok, resumed.mismatches)
        self.assertNotIn("convergence_authority", resumed.checkpoint)
        self.assertIsNone(resumed.checkpoint["candidate"])

    def test_resume_rejects_different_expected_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            current = window_candidate(root, 9).candidate
            self.create(root, current, authority())
            resumed = resume_checkpoint(
                root,
                expected_convergence_authority=authority(invariant="different invariant"),
            )

        self.assertFalse(resumed.ok)
        self.assertTrue(any("expected convergence authority" in item for item in resumed.mismatches))


class ConvergenceCliTests(unittest.TestCase):
    def write_authority(self, root: Path, value=None) -> Path:
        path = root / ".sagekit/runtime/convergence-authority.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = authority().to_dict() if value is None else value
        if isinstance(payload, PreauthorizedConvergenceAuthority):
            payload = payload.to_dict()
        path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
        return path

    def test_malformed_authority_is_configuration_failure_not_internal_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            path = root / "bad-authority.json"
            path.write_text("{bad json", encoding="utf-8")
            result = run_sagekit(
                "candidate",
                "freeze",
                "--target",
                str(root),
                "--contract-digest",
                "contracts-v1",
                "--dependency-digest",
                "dependencies-v1",
                "--review-closed",
                "--corrective-batch-closed",
                "--convergence-authority",
                str(path),
                "--root-cause-id",
                "path-representation",
                "--finding-count",
                "9",
                "--finding-severity",
                "3",
                "--semantic-change",
                "implementation-preserving",
                "--targeted-review-closed",
                cwd=root,
            )

        self.assertEqual(2, result.returncode)
        self.assertIn("configuration-error", result.stdout + result.stderr)
        self.assertNotIn("internal-error", result.stdout + result.stderr)

    def test_wrong_authority_json_types_are_configuration_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            payload = authority().to_dict()
            payload["semantic_change_policy"] = ["implementation-preserving-only"]
            path = self.write_authority(root, payload)
            result = run_sagekit(
                "candidate",
                "freeze",
                "--target",
                str(root),
                "--contract-digest",
                "contracts-v1",
                "--dependency-digest",
                "dependencies-v1",
                "--review-closed",
                "--corrective-batch-closed",
                "--convergence-authority",
                str(path),
                "--root-cause-id",
                "path-representation",
                "--finding-count",
                "9",
                "--semantic-change",
                "implementation-preserving",
                "--targeted-review-closed",
                cwd=root,
            )

        self.assertEqual(2, result.returncode)
        self.assertIn("configuration-error", result.stdout + result.stderr)
        self.assertNotIn("internal-error", result.stdout + result.stderr)

    def test_candidate_text_and_json_status_report_active_window_consistently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            path = self.write_authority(root)
            common = (
                "candidate",
                "freeze",
                "--target",
                str(root),
                "--contract-digest",
                "contracts-v1",
                "--dependency-digest",
                "dependencies-v1",
                "--review-closed",
                "--corrective-batch-closed",
                "--convergence-authority",
                str(path),
                "--root-cause-id",
                "path-representation",
                "--finding-count",
                "9",
                "--finding-severity",
                "3",
                "--semantic-change",
                "implementation-preserving",
                "--targeted-review-closed",
            )
            text = run_sagekit(*common, cwd=root)
            machine = run_sagekit(*common, "--json", cwd=root)

        payload = json.loads(machine.stdout)
        self.assertEqual(0, text.returncode, text.stderr)
        self.assertEqual(0, machine.returncode, machine.stderr)
        self.assertIn("CONVERGENCE_WINDOW active", text.stdout)
        self.assertIn("AUTHORITY_ID AUTH-CONVERGENCE-1", text.stdout)
        self.assertIn("ROOT_CAUSE_FAMILY portability", text.stdout)
        self.assertTrue(payload["convergence"]["active"])
        self.assertEqual("AUTH-CONVERGENCE-1", payload["convergence"]["authority_id"])

    def test_candidate_without_window_reports_inactive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_repository(root)
            result = run_sagekit(
                "candidate",
                "freeze",
                "--target",
                str(root),
                "--contract-digest",
                "contracts-v1",
                "--dependency-digest",
                "dependencies-v1",
                "--review-closed",
                "--corrective-batch-closed",
                "--json",
                cwd=root,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(json.loads(result.stdout)["convergence"]["active"])


class ConvergenceDocumentationTests(unittest.TestCase):
    def test_required_guidance_is_present_and_packaged(self):
        sources = (
            "docs/agent/EXECUTION_ECONOMY.md",
            "docs/agent/CONTINUITY_PROTOCOL.md",
            "docs/QUALITY_GATES_TEMPLATE.md",
            "docs/templates/CORRECTIVE_PACKET_TEMPLATE.md",
            "docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md",
        )
        for relative in sources:
            source = REPO_ROOT / relative
            packaged = REPO_ROOT / "sagekit/resources" / relative
            self.assertEqual(source.read_bytes(), packaged.read_bytes(), relative)
        combined = "\n".join(
            (REPO_ROOT / relative).read_text(encoding="utf-8") for relative in sources
        )
        for phrase in (
            "Preauthorized Convergence Window",
            "opt-in",
            "semantic-preserving",
            "policy-changing",
            "single automatic successor",
            "targeted review",
            "not an unlimited retry",
            "transient rerun",
        ):
            self.assertIn(phrase, combined)

    def test_repository_skill_routes_convergence_without_changing_installed_skill(self):
        text = (REPO_ROOT / "skills/sage-kit/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Preauthorized Convergence Window", text)
        self.assertIn("docs/agent/EXECUTION_ECONOMY.md", text)
        self.assertIn("#sage-loop-008", text)
        self.assertIn("#sage-loop-010", text)


if __name__ == "__main__":
    unittest.main()
