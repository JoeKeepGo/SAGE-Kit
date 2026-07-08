import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sagekit.init import fallback_content


REPO_ROOT = Path(__file__).resolve().parents[1]


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


def write_required_docs(root):
    write_file(
        root,
        "docs/PROJECT_PROFILE.md",
        """
        # Project Profile

        Goal: keep SAGE-Kit governance artifacts reviewable.
        """,
    )
    write_file(
        root,
        "docs/QUALITY_GATES.md",
        """
        # Quality Gates

        Tests and runtime smoke must be recorded or marked N/A with a reason.
        """,
    )
    write_file(
        root,
        "docs/ACTIVE_CONTEXT.md",
        """
        # Active Context

        Current focus: local SAGE-Kit governance checks.
        Next action: run sagekit check.
        """,
    )
    write_file(
        root,
        "docs/DOC_ROUTING.md",
        """
        # Document Routing

        Routing policy:
        - Implementation tasks read the active phase doc and quality gates.
        - Review tasks read completion reports and milestone ledgers.
        """,
    )


def write_valid_planning_phase(root):
    write_file(
        root,
        "docs/M1/01-planning.md",
        """
        # M1 Phase 1: Planning

        ## Goal

        Define the local runtime MVP boundary.

        ## Governance Level

        Level: Standard

        ## Permission Mode

        Mode: WRITE_AUTHORIZED

        ## File Boundary

        Allowed files:
        - docs/M1/01-planning.md

        Read-only files:
        - docs/SAGE_CORE.md

        Forbidden files:
        - secrets/

        ## Test Plan

        Tests: N/A because this phase only records the product boundary.

        ## Runtime Smoke

        Runtime smoke: N/A because this is a planning-only phase.

        ## Stop Conditions

        Stop if runtime implementation scope is requested.
        """,
    )


class SagekitCheckTests(unittest.TestCase):
    def test_version_outputs_package_version(self):
        from sagekit import __version__

        result = run_sagekit("--version", cwd=REPO_ROOT)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"sagekit {__version__}")

    def test_json_check_warns_for_missing_recommended_docs_without_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)

            result = run_sagekit("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            levels = {finding["level"] for finding in payload["findings"]}
            rules = {finding["rule"] for finding in payload["findings"]}
            self.assertIn("PASS", levels)
            self.assertIn("WARN", levels)
            self.assertNotIn("FAIL", levels)
            self.assertIn("required-docs", rules)
            self.assertIn("recommended-docs", rules)

    def test_missing_required_docs_exit_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(root, "docs/ACTIVE_CONTEXT.md", "# Active Context\n\nShort.")

            result = run_sagekit("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            failures = [item for item in payload["findings"] if item["level"] == "FAIL"]
            self.assertTrue(any(item["rule"] == "required-docs" for item in failures))

    def test_human_check_prints_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)

            result = run_sagekit("check", cwd=root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PASS required-docs:", result.stdout)
            self.assertIn("WARN recommended-docs:", result.stdout)

    def test_planning_only_phase_allows_runtime_smoke_na_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_valid_planning_phase(root)

            result = run_sagekit("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 0, result.stdout)
            payload = json.loads(result.stdout)
            self.assertFalse(
                [
                    item
                    for item in payload["findings"]
                    if item["level"] == "FAIL" and item["rule"] == "phase-runtime-smoke"
                ]
            )

    def test_phase_missing_runtime_smoke_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_file(
                root,
                "docs/M1/01-build.md",
                """
                # M1 Phase 1: Build

                ## Goal
                Build the checker.

                ## Governance Level
                Level: Standard

                ## Permission Mode
                Mode: WRITE_AUTHORIZED

                ## File Boundary
                Allowed files:
                - sagekit/

                Forbidden files:
                - secrets/

                ## Test Plan
                Tests: python -m unittest discover -s tests

                ## Stop Conditions
                Stop if publishing is requested.
                """,
            )

            result = run_sagekit("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["level"] == "FAIL" and item["rule"] == "phase-runtime-smoke"
                    for item in payload["findings"]
                )
            )

    def test_empty_runtime_smoke_section_fails_even_when_tests_have_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_file(
                root,
                "docs/M1/01-build.md",
                """
                # M1 Phase 1: Build

                ## Goal
                Build the checker.

                ## Governance Level
                Level: Standard

                ## Permission Mode
                Mode: WRITE_AUTHORIZED

                ## File Boundary
                Allowed files:
                - sagekit/

                Forbidden files:
                - secrets/

                ## Test Plan
                Tests: python -m unittest discover -s tests

                ## Runtime Smoke

                ## Stop Conditions
                Stop if publishing is requested.
                """,
            )

            result = run_sagekit("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["level"] == "FAIL" and item["rule"] == "phase-runtime-smoke"
                    for item in payload["findings"]
                )
            )

    def test_task_dispatch_records_are_wrapped_as_unified_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_file(root, "docs/M1/dispatch/TASK-001/task.yaml", "id: TASK-001")
            write_file(root, "docs/M1/dispatch/TASK-001/evidence.yaml", "task_id: TASK-001")

            result = run_sagekit("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["level"] == "FAIL" and item["rule"] == "task-dispatch"
                    for item in payload["findings"]
                )
            )

    def test_check_does_not_write_project_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            before = sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())

            result = run_sagekit("check", "--json", cwd=root)

            after = sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(before, after)

    def test_check_target_uses_target_project_from_different_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            target = workspace / "project"
            runner_cwd = workspace / "runner"
            target.mkdir()
            runner_cwd.mkdir()
            write_required_docs(target)

            result = run_sagekit("check", "--target", str(target), "--json", cwd=runner_cwd)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["level"] == "PASS"
                    and item["rule"] == "project-root"
                    and str(target) in item["message"]
                    for item in payload["findings"]
                ),
                payload,
            )

    def test_local_command_wrapper_runs_outside_repo_when_on_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            env = os.environ.copy()
            env["PATH"] = f"{REPO_ROOT}{os.pathsep}{env['PATH']}"
            env.pop("PYTHONPATH", None)

            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "sagekit check --json"],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["findings"])

    def test_local_command_wrapper_does_not_write_bytecode_to_package_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            tool_root = workspace / "tool"
            project_root = workspace / "project"
            tool_root.mkdir()
            project_root.mkdir()
            shutil.copytree(
                REPO_ROOT / "sagekit",
                tool_root / "sagekit",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            shutil.copy2(REPO_ROOT / "sagekit.cmd", tool_root / "sagekit.cmd")
            write_required_docs(project_root)

            env = os.environ.copy()
            env["PATH"] = f"{tool_root}{os.pathsep}{env['PATH']}"
            env.pop("PYTHONPATH", None)
            env.pop("PYTHONDONTWRITEBYTECODE", None)

            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "sagekit check --json"],
                cwd=project_root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((tool_root / "sagekit" / "__pycache__").exists())

    def test_pyproject_declares_cross_platform_console_script(self):
        pyproject = REPO_ROOT / "pyproject.toml"
        self.assertTrue(pyproject.exists(), "pyproject.toml should define the installable CLI entrypoint")

        text = pyproject.read_text(encoding="utf-8")

        self.assertIn('name = "sagekit"', text)
        self.assertIn('sagekit = "sagekit.cli:main"', text)

    def test_doctor_json_reports_source_repo_without_failing(self):
        result = run_sagekit("doctor", "--json", cwd=REPO_ROOT)

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(
            any(item["level"] == "PASS" and item["rule"] == "kit-source" for item in payload["findings"]),
            payload,
        )

    def test_doctor_does_not_write_project_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            before = sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())

            result = run_sagekit("doctor", "--json", cwd=root)

            after = sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, after)

    def test_doctor_target_reports_target_adopted_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            target = workspace / "project"
            runner_cwd = workspace / "runner"
            target.mkdir()
            runner_cwd.mkdir()
            write_required_docs(target)

            result = run_sagekit("doctor", "--target", str(target), "--json", cwd=runner_cwd)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(item["level"] == "PASS" and item["rule"] == "adopted-project" for item in payload["findings"]),
                payload,
            )

    def test_doctor_reports_adopted_project_without_source_repo_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)

            result = run_sagekit("doctor", "--json", cwd=root)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(item["level"] == "PASS" and item["rule"] == "adopted-project" for item in payload["findings"]),
                payload,
            )
            self.assertFalse(
                any(item["level"] == "WARN" and item["rule"] == "kit-source" for item in payload["findings"]),
                payload,
            )

    def test_init_light_dry_run_does_not_write_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = run_sagekit("init", "--mode", "light", "--dry-run", "--json", cwd=root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / "docs").exists())
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(item["level"] == "PASS" and item["rule"] == "init-plan" for item in payload["findings"]),
                payload,
            )

    def test_init_light_creates_required_docs_and_light_check_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            init_result = run_sagekit("init", "--mode", "light", "--json", cwd=root)
            check_result = run_sagekit("check", "--mode", "light", "--json", cwd=root)

            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            self.assertEqual(check_result.returncode, 0, check_result.stdout)
            for path in [
                "docs/PROJECT_PROFILE.md",
                "docs/QUALITY_GATES.md",
                "docs/ACTIVE_CONTEXT.md",
                "docs/DOC_ROUTING.md",
            ]:
                self.assertTrue((root / path).exists(), path)

            payload = json.loads(check_result.stdout)
            self.assertFalse(
                any(item["rule"] == "recommended-docs" for item in payload["findings"]),
                payload,
            )
            self.assertFalse(
                any(item["level"] == "WARN" for item in payload["findings"]),
                payload,
            )

    def test_init_target_writes_only_target_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            target = workspace / "project"
            runner_cwd = workspace / "runner"
            target.mkdir()
            runner_cwd.mkdir()

            init_result = run_sagekit("init", "--target", str(target), "--mode", "light", "--json", cwd=runner_cwd)
            check_result = run_sagekit("check", "--target", str(target), "--mode", "light", "--json", cwd=runner_cwd)
            doctor_result = run_sagekit("doctor", "--target", str(target), "--json", cwd=runner_cwd)

            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            self.assertEqual(check_result.returncode, 0, check_result.stdout)
            self.assertEqual(doctor_result.returncode, 0, doctor_result.stderr)
            self.assertTrue((target / "docs/ACTIVE_CONTEXT.md").exists())
            self.assertFalse((runner_cwd / "docs").exists())

    def test_init_target_refuses_file_target_without_writing_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            target = workspace / "target.txt"
            target.write_text("not a project directory\n", encoding="utf-8")

            result = run_sagekit("init", "--target", str(target), "--mode", "light", "--json", cwd=workspace)

            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertFalse((workspace / "docs").exists())
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(item["level"] == "FAIL" and item["rule"] == "target" for item in payload["findings"]),
                payload,
            )

    def test_init_target_child_project_does_not_write_adopted_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            target = parent / "child-project"
            target.mkdir()
            write_required_docs(parent)
            before = sorted(path.relative_to(parent) for path in parent.rglob("*") if path.is_file())

            result = run_sagekit("init", "--target", str(target), "--mode", "light", "--json", cwd=parent)

            after_parent = sorted(
                path.relative_to(parent)
                for path in parent.rglob("*")
                if path.is_file() and not path.is_relative_to(target)
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((target / "docs/ACTIVE_CONTEXT.md").exists())
            self.assertEqual(before, after_parent)

    def test_standard_check_requires_standard_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_sagekit("init", "--mode", "light", cwd=root)

            result = run_sagekit("check", "--mode", "standard", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["level"] == "FAIL"
                    and item["rule"] == "required-docs"
                    and item["path"] == "docs/TECHNICAL_DESIGN.md"
                    for item in payload["findings"]
                ),
                payload,
            )

    def test_init_standard_creates_standard_docs_and_standard_check_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            init_result = run_sagekit("init", "--mode", "standard", "--json", cwd=root)
            check_result = run_sagekit("check", "--mode", "standard", "--json", cwd=root)

            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            self.assertEqual(check_result.returncode, 0, check_result.stdout)
            for path in [
                "docs/TECHNICAL_DESIGN.md",
                "docs/ENGINEERING_SYSTEM.md",
                "docs/APPROVAL_GATES.md",
                "docs/MILESTONE_ROADMAP.md",
            ]:
                self.assertTrue((root / path).exists(), path)

    def test_init_heavy_keeps_optional_profiles_inactive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            init_result = run_sagekit("init", "--mode", "heavy", "--json", cwd=root)
            check_result = run_sagekit("check", "--mode", "heavy", "--json", cwd=root)

            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            self.assertEqual(check_result.returncode, 0, check_result.stdout)
            self.assertFalse((root / "docs/profiles/task-dispatch/DISPATCH_PROFILE.md").exists())
            self.assertFalse(list(root.glob("docs/M*/dispatch/**/task.yaml")))

    def test_init_does_not_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = write_file(root, "docs/PROJECT_PROFILE.md", "# Custom Profile\n\nKeep me.")

            result = run_sagekit("init", "--mode", "light", "--json", cwd=root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(profile.read_text(encoding="utf-8"), "# Custom Profile\n\nKeep me.\n")
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(item["level"] == "WARN" and item["rule"] == "init-skip-existing" for item in payload["findings"]),
                payload,
            )

    def test_init_force_overwrites_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = write_file(root, "docs/PROJECT_PROFILE.md", "# Custom Profile\n\nReplace me.")

            result = run_sagekit("init", "--mode", "light", "--force", "--json", cwd=root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotEqual(profile.read_text(encoding="utf-8"), "# Custom Profile\n\nReplace me.\n")
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(item["level"] == "PASS" and item["rule"] == "init-write" for item in payload["findings"]),
                payload,
            )

    def test_init_force_refuses_existing_directory_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs/PROJECT_PROFILE.md").mkdir(parents=True)

            result = run_sagekit("init", "--mode", "light", "--force", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(item["level"] == "FAIL" and item["rule"] == "init-unsafe-target" for item in payload["findings"]),
                payload,
            )

    def test_init_force_refuses_symlink_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = Path(tmp) / "outside.md"
            outside.write_text("# Outside\n", encoding="utf-8")
            link = root / "docs/PROJECT_PROFILE.md"
            link.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.symlink(outside, link)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink unavailable: {exc}")

            result = run_sagekit("init", "--mode", "light", "--force", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertEqual(outside.read_text(encoding="utf-8"), "# Outside\n")
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(item["level"] == "FAIL" and item["rule"] == "init-unsafe-target" for item in payload["findings"]),
                payload,
            )

    def test_init_refuses_source_repository(self):
        result = run_sagekit("init", "--mode", "light", "--json", cwd=REPO_ROOT)

        self.assertEqual(result.returncode, 1, result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(
            any(item["level"] == "FAIL" and item["rule"] == "init-source-repo" for item in payload["findings"]),
            payload,
        )

    def test_init_target_refuses_source_repository_and_does_not_instantiate_runtime_docs(self):
        before = {
            "docs/ACTIVE_CONTEXT.md": (REPO_ROOT / "docs/ACTIVE_CONTEXT.md").exists(),
            "docs/DOC_ROUTING.md": (REPO_ROOT / "docs/DOC_ROUTING.md").exists(),
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = run_sagekit("init", "--target", str(REPO_ROOT), "--mode", "light", "--json", cwd=Path(tmp))

        self.assertEqual(result.returncode, 1, result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(
            any(item["level"] == "FAIL" and item["rule"] == "init-source-repo" for item in payload["findings"]),
            payload,
        )
        after = {
            "docs/ACTIVE_CONTEXT.md": (REPO_ROOT / "docs/ACTIVE_CONTEXT.md").exists(),
            "docs/DOC_ROUTING.md": (REPO_ROOT / "docs/DOC_ROUTING.md").exists(),
        }
        self.assertEqual(before, after)

    def test_source_repo_check_does_not_require_instantiated_project_context(self):
        result = run_sagekit("check", "--source-repo", "--json", cwd=REPO_ROOT)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(
            any(item["level"] == "PASS" and item["rule"] == "source-repo" for item in payload["findings"]),
            payload,
        )
        self.assertFalse(any(item["rule"] == "required-docs" for item in payload["findings"]), payload)
        self.assertFalse(any(item.get("path") == "docs/ACTIVE_CONTEXT.md" for item in payload["findings"]), payload)
        self.assertFalse(any(item.get("path") == "docs/DOC_ROUTING.md" for item in payload["findings"]), payload)

    def test_source_repo_check_reports_hygiene_and_runtime_tracking(self):
        result = run_sagekit("check", "--source-repo", "--json", cwd=REPO_ROOT)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        rules = {(item["level"], item["rule"]) for item in payload["findings"]}
        self.assertIn(("PASS", "source-gitignore-runtime"), rules)
        self.assertIn(("PASS", "source-tracked-runtime"), rules)

    def test_init_fallback_doc_routing_is_checkable(self):
        text = fallback_content("docs/DOC_ROUTING.md")

        self.assertIn("Routing policy", text)
        self.assertIn("Implementation tasks", text)

    def test_packaged_resources_include_canonical_heavy_docs(self):
        from sagekit.init import package_resource_root

        root = package_resource_root()

        self.assertTrue((root / "docs/SAGE_CORE.md").exists())
        self.assertIn("External Capability Boundary", (root / "docs/SAGE_CORE.md").read_text(encoding="utf-8"))
        self.assertTrue((root / "docs/agent/GOVERNANCE_LEVELS.md").exists())


if __name__ == "__main__":
    unittest.main()
