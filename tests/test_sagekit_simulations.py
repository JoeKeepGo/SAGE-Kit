import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def normalized_path_key(path):
    return os.path.normcase(os.path.normpath(str(Path(path).resolve(strict=False))))


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


def write_file(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text.strip() + "\n", encoding="utf-8")
    return target


def load_findings(result):
    return json.loads(result.stdout)["findings"]


def findings_for(findings, rule, level=None, path=None):
    return [
        finding
        for finding in findings
        if finding["rule"] == rule
        and (level is None or finding["level"] == level)
        and (path is None or finding.get("path") == path)
    ]


def nonempty_line_count(path):
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def write_required_docs(root):
    write_file(
        root,
        "docs/PROJECT_PROFILE.md",
        """
        # Project Profile

        Product: Control Portal + Local Runtime Agent
        Goal: coordinate local operational workflows with clear governance.
        """,
    )
    write_file(
        root,
        "docs/QUALITY_GATES.md",
        """
        # Quality Gates

        Tests and runtime smoke must be recorded or marked N/A with a concrete reason.
        """,
    )
    write_file(
        root,
        "docs/ACTIVE_CONTEXT.md",
        """
        # Active Context

        Current focus: validate adopted-project governance.
        Next action: run SAGE-Kit checks.
        Current blocker: none.
        """,
    )
    write_file(
        root,
        "docs/DOC_ROUTING.md",
        """
        # Document Routing

        Routing policy:
        - Planning tasks read project profile and quality gates.
        - Implementation tasks read active context, this routing file, and the active phase.
        - Review tasks read completion reports and milestone closeouts.
        """,
    )


def write_planning_phase(root):
    write_file(
        root,
        "docs/M1/01-planning.md",
        """
        # M1 Phase 1: Planning

        ## Goal

        Define the project governance boundary.

        ## Governance Level

        Level: Light

        ## Permission Mode

        Mode: WRITE_AUTHORIZED

        ## File Boundary

        Allowed files:
        - docs/M1/01-planning.md

        Forbidden files:
        - production-data/

        ## Test Plan

        Tests: N/A because this phase only records planning decisions.

        ## Runtime Smoke

        Runtime Smoke: N/A because this is a planning-only phase.

        ## Stop Conditions

        Stop if implementation scope is requested.
        """,
    )


def write_heavy_phase(root):
    write_file(
        root,
        "docs/M1/01-runtime-observability.md",
        """
        # M1 Phase 1: Runtime Observability

        ## Goal

        Prove that the Control Portal can report Local Runtime Agent status.

        ## Governance Level

        Governance Level: Heavy

        ## Permission Mode

        Mode: WRITE_AUTHORIZED

        ## File Boundary

        Allowed files:
        - apps/control-portal/
        - services/local-runtime-agent/
        - docs/M1/01-runtime-observability.md

        Forbidden files:
        - secrets/
        - production-data/
        - release-manifests/

        ## Test Plan

        Tests: python -m unittest discover -s tests

        ## Runtime Smoke

        Runtime smoke: python -m control_portal.smoke --agent local

        ## Stop Conditions

        Stop if production credentials, release changes, or destructive operations are requested.
        """,
    )


class SagekitSimulationTests(unittest.TestCase):
    def test_light_adoption_simulation_stays_lightweight_and_allows_planning_only_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            target = workspace / "light-project"
            runner = workspace / "runner"
            target.mkdir()
            runner.mkdir()

            init_result = run_sagekit(
                "init", "--target", str(target), "--mode", "light",
                "--profile", "vendored-legacy", cwd=runner
            )
            doctor_result = run_sagekit("doctor", "--target", str(target), cwd=runner)
            check_result = run_sagekit("check", "--target", str(target), "--mode", "light", "--json", cwd=runner)

            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            self.assertEqual(doctor_result.returncode, 0, doctor_result.stderr)
            self.assertEqual(check_result.returncode, 0, check_result.stdout)

            for path in [
                "docs/PROJECT_PROFILE.md",
                "docs/QUALITY_GATES.md",
                "docs/ACTIVE_CONTEXT.md",
                "docs/DOC_ROUTING.md",
            ]:
                self.assertTrue((target / path).exists(), path)

            findings = load_findings(check_result)
            required_paths = {finding["path"] for finding in findings_for(findings, "required-docs")}
            self.assertEqual(
                required_paths,
                {
                    "docs/PROJECT_PROFILE.md",
                    "docs/QUALITY_GATES.md",
                    "docs/ACTIVE_CONTEXT.md",
                    "docs/DOC_ROUTING.md",
                },
            )
            self.assertNotIn("docs/agent/SESSION_ORCHESTRATION.md", required_paths)
            self.assertFalse(findings_for(findings, "task-dispatch"), findings)
            self.assertFalse([finding for finding in findings if "worktree" in finding["rule"]], findings)
            self.assertLessEqual(nonempty_line_count(target / "docs/ACTIVE_CONTEXT.md"), 120)
            self.assertLessEqual(nonempty_line_count(target / "docs/DOC_ROUTING.md"), 120)
            self.assertFalse(findings_for(findings, "doc-routing", level="WARN"), findings)

            write_planning_phase(target)
            phase_result = run_sagekit("check", "--target", str(target), "--mode", "light", "--json", cwd=runner)

            self.assertEqual(phase_result.returncode, 0, phase_result.stdout)
            phase_findings = load_findings(phase_result)
            self.assertTrue(
                findings_for(
                    phase_findings,
                    "phase-runtime-smoke",
                    level="PASS",
                    path="docs/M1/01-planning.md",
                ),
                phase_findings,
            )
            self.assertFalse(findings_for(phase_findings, "task-dispatch"), phase_findings)

    def test_heavy_adoption_simulation_validates_controller_docs_and_phase_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            target = workspace / "heavy-project"
            runner = workspace / "runner"
            target.mkdir()
            runner.mkdir()

            init_result = run_sagekit(
                "init", "--target", str(target), "--mode", "heavy",
                "--profile", "vendored-legacy", cwd=runner
            )
            write_heavy_phase(target)

            check_result = run_sagekit("check", "--target", str(target), "--mode", "heavy", "--json", cwd=runner)

            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            self.assertEqual(check_result.returncode, 0, check_result.stdout)
            findings = load_findings(check_result)
            project_root = findings_for(findings, "project-root", level="PASS")[0]["message"]
            reported_root = project_root.removeprefix("using ").strip()
            self.assertEqual(normalized_path_key(reported_root), normalized_path_key(target))

            for path in [
                "docs/SAGE_CORE.md",
                "docs/agent/GOVERNANCE_LEVELS.md",
                "docs/agent/SESSION_ORCHESTRATION.md",
            ]:
                self.assertTrue(findings_for(findings, "required-docs", level="PASS", path=path), path)

            self.assertTrue(
                findings_for(
                    findings,
                    "phase-runtime-smoke",
                    level="PASS",
                    path="docs/M1/01-runtime-observability.md",
                ),
                findings,
            )
            boundary_findings = findings_for(
                findings,
                "phase-boundary",
                level="PASS",
                path="docs/M1/01-runtime-observability.md",
            )
            self.assertTrue(any("allowed files" in item["message"] for item in boundary_findings), boundary_findings)
            self.assertTrue(any("forbidden files" in item["message"] for item in boundary_findings), boundary_findings)
            self.assertFalse(findings_for(findings, "task-dispatch"), findings)
            self.assertFalse([finding for finding in findings if finding["rule"].startswith("source-")], findings)

    def test_failure_simulation_reports_missing_runtime_smoke_for_runtime_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_file(
                root,
                "docs/M1/01-runtime-claim.md",
                """
                # M1 Phase 1: Runtime Claim

                ## Goal

                Change runtime behavior for the Local Runtime Agent.

                ## Governance Level

                Level: Standard

                ## Permission Mode

                Mode: WRITE_AUTHORIZED

                ## File Boundary

                Allowed files:
                - services/local-runtime-agent/

                Forbidden files:
                - secrets/

                ## Test Plan

                Tests: python -m unittest discover -s tests

                ## Stop Conditions

                Stop if runtime ownership changes.
                """,
            )

            result = run_sagekit("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            findings = load_findings(result)
            self.assertTrue(
                findings_for(
                    findings,
                    "phase-runtime-smoke",
                    level="FAIL",
                    path="docs/M1/01-runtime-claim.md",
                ),
                findings,
            )

    def test_failure_simulation_reports_incomplete_completion_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_file(
                root,
                "docs/M1/01-COMPLETION.md",
                """
                # Completion Report

                Status: Done.

                ## Files Changed

                - services/local-runtime-agent/status.py

                ## Runtime Smoke

                Runtime smoke: python -m control_portal.smoke --agent local

                ## Approval Gates

                No closed approval gates were opened.

                ## Remaining Gaps

                None.
                """,
            )

            result = run_sagekit("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            findings = load_findings(result)
            self.assertTrue(findings_for(findings, "completion-tests", level="FAIL"), findings)
            self.assertTrue(findings_for(findings, "completion-skipped-checks", level="FAIL"), findings)

    def test_failure_simulation_warns_when_doc_routing_is_progress_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_file(
                root,
                "docs/DOC_ROUTING.md",
                """
                # Document Routing

                Routing policy:
                - Read the active phase before implementation.

                Progress log:
                - Done: initialized the project documents.
                """,
            )

            result = run_sagekit("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 0, result.stdout)
            findings = load_findings(result)
            self.assertTrue(findings_for(findings, "doc-routing", level="WARN"), findings)

    def test_failure_simulation_warns_when_active_context_is_too_long(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            long_context = "\n".join(f"- Current fact {index}" for index in range(1, 203))
            write_file(
                root,
                "docs/ACTIVE_CONTEXT.md",
                f"""
                # Active Context

                {long_context}
                """,
            )

            result = run_sagekit("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 0, result.stdout)
            findings = load_findings(result)
            warnings = findings_for(findings, "active-context", level="WARN", path="docs/ACTIVE_CONTEXT.md")
            self.assertTrue(any("startup context may be too large" in item["message"] for item in warnings), findings)

    def test_source_repo_runtime_path_classifier_covers_numeric_milestones_only(self):
        from sagekit.check import is_runtime_state_path

        runtime_paths = [
            "docs/M1/phase.md",
            "docs/M20/closeout.md",
        ]
        durable_paths = [
            "docs/MILESTONE_GUIDE.md",
            "docs/agent/MODEL_ASSURANCE_POLICY.md",
        ]

        for path in runtime_paths:
            with self.subTest(path=path):
                self.assertTrue(is_runtime_state_path(path), path)

        for path in durable_paths:
            with self.subTest(path=path):
                self.assertFalse(is_runtime_state_path(path), path)


if __name__ == "__main__":
    unittest.main()
