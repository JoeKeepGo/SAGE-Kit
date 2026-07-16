import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sagekit.init import fallback_content


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


MARKDOWN_FIELD_RE = re.compile(r"^(?P<prefix>\s*(?:-\s+)?)?(?P<label>[A-Za-z][^:\n]{0,100}):\s*(?P<value>.*)$")


def parse_markdown_fields(text):
    fields = []
    current = None
    for line in text.splitlines():
        match = MARKDOWN_FIELD_RE.match(line)
        if match and not line.lstrip().startswith(("|", "#")):
            current = {
                "label": match.group("label").strip(),
                "value": match.group("value").strip(),
            }
            fields.append(current)
            continue
        stripped = line.strip()
        if current and stripped and not stripped.startswith(("|", "#", "```")):
            current["value"] = f"{current['value']} {stripped}".strip()
        else:
            current = None
    return fields


def parse_markdown_table_rows(text):
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if cells and all(re.fullmatch(r"[: -]+", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def instantiate_markdown_packet(template, values):
    seen = set()
    lines = []
    for line in template.splitlines():
        match = MARKDOWN_FIELD_RE.match(line)
        label = match.group("label").strip() if match else None
        if label in values:
            prefix = match.group("prefix") or ""
            lines.append(f"{prefix}{label}: {values[label]}")
            seen.add(label)
        else:
            lines.append(line)
    missing = set(values) - seen
    if missing:
        raise AssertionError(f"template fields missing: {sorted(missing)}")
    return "\n".join(lines)


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


def write_dispatch_pair(root, task_id, lock=None, directory_id=None):
    task = {
        "id": task_id,
        "type": "spec",
        "title": f"Dispatch {task_id}",
        "priority": "P2",
        "status": "NEW",
        "scope": {
            "objective": "Exercise repository dispatch checks.",
            "allowed_files": ["src/app.py"],
            "read_only_files": [],
            "forbidden_files": [],
            "non_goals": [],
            "stop_conditions": [],
        },
        "verification": {
            "required_levels": ["L0"],
            "evidence_file": "evidence.yaml",
            "mock_allowed": False,
            "required_commands": [],
        },
        "dependencies": {"requires": [], "blocks": []},
        "resources": {"locks": [lock] if lock else []},
        "runs": [],
        "closure": {},
    }
    evidence = {
        "task_id": task_id,
        "changed_surface": [],
        "runtime_shape": "static validation",
        "levels": {
            level: {
                "status": "PENDING" if level == "L0" else "N/A",
                "evidence": [],
                "commands": [],
                "reason": "awaiting evidence" if level == "L0" else "not required",
            }
            for level in ["L0", "L1", "L2", "L3", "L4"]
        },
        "artifacts": {
            "commands": [],
            "files_changed": [],
            "api": [],
            "sql": [],
            "browser": [],
            "logs": [],
            "screenshots": [],
            "release": [],
            "ids": [],
        },
        "runs": [],
        "blockers": [],
        "conclusion": {
            "status": "PENDING",
            "highest_level": "none",
            "mock_used": False,
            "accepted_fallback": False,
            "next_action": "collect evidence",
        },
    }
    directory = f"docs/M1/dispatch/{directory_id or task_id}"
    write_file(root, f"{directory}/task.yaml", json.dumps(task))
    write_file(root, f"{directory}/evidence.yaml", json.dumps(evidence))


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

    def test_task_dispatch_reports_orphan_evidence_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_file(
                root,
                "docs/M1/dispatch/TASK-001/evidence.yaml",
                json.dumps({"task_id": "TASK-001"}),
            )

            result = run_sagekit("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["rule"] == "task-dispatch"
                    and "evidence.yaml is present but task.yaml is missing" in item["message"]
                    for item in payload["findings"]
                ),
                payload["findings"],
            )

    def test_task_dispatch_reports_conflicting_exclusive_locks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            for task_id, owner in [("TASK-001", "worker-1"), ("TASK-002", "worker-2")]:
                write_dispatch_pair(
                    root,
                    task_id,
                    {
                        "resource": "shared-test-db",
                        "owner": owner,
                        "mode": "exclusive",
                        "status": "ACTIVE",
                        "release_rule": "after verification",
                    },
                )

            result = run_sagekit("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["rule"] == "task-dispatch-lock-conflict"
                    and "shared-test-db" in item["message"]
                    and "TASK-001" in item["message"]
                    and "TASK-002" in item["message"]
                    for item in payload["findings"]
                ),
                payload["findings"],
            )

    def test_task_dispatch_detects_containment_overlap_for_exclusive_locks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            for task_id, resource in [("TASK-001", "src/"), ("TASK-002", "src/app.py")]:
                write_dispatch_pair(
                    root,
                    task_id,
                    {
                        "resource": resource,
                        "owner": task_id,
                        "mode": "exclusive",
                        "status": "ACTIVE",
                        "release_rule": "after verification",
                    },
                )

            result = run_sagekit("check", "--json", cwd=root)

            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["rule"] == "task-dispatch-lock-conflict"
                    and "src/" in item["message"]
                    and "src/app.py" in item["message"]
                    for item in payload["findings"]
                ),
                payload["findings"],
            )

    def test_task_dispatch_reports_duplicate_declared_task_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_dispatch_pair(root, "TASK-001", directory_id="record-a")
            write_dispatch_pair(root, "TASK-001", directory_id="record-b")

            result = run_sagekit("check", "--json", cwd=root)

            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["rule"] == "task-dispatch-duplicate-id"
                    and "TASK-001" in item["message"]
                    for item in payload["findings"]
                ),
                payload["findings"],
            )

    def test_dispatch_board_reconciles_active_task_ids_with_record_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_dispatch_pair(root, "TASK-001")
            write_file(
                root,
                "docs/M1/dispatch/DISPATCH_BOARD.md",
                """
                # Dispatch Board

                ## Active Tasks

                | Task | Status |
                |---|---|
                | `TASK-BOARD-ONLY` | `NEW` |

                ## Resource Locks
                """,
            )

            result = run_sagekit("check", "--json", cwd=root)

            payload = json.loads(result.stdout)
            messages = [
                item["message"]
                for item in payload["findings"]
                if item["rule"] == "task-dispatch-board"
            ]
            self.assertTrue(any("TASK-BOARD-ONLY" in message and "no record pair" in message for message in messages), messages)
            self.assertTrue(any("TASK-001" in message and "absent from" in message for message in messages), messages)

    def test_task_dispatch_records_require_dispatch_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_dispatch_pair(root, "TASK-001")

            result = run_sagekit("check", "--json", cwd=root)

            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["rule"] == "task-dispatch-board"
                    and "DISPATCH_BOARD.md is missing" in item["message"]
                    for item in payload["findings"]
                ),
                payload["findings"],
            )

    def test_inactive_archive_decision_does_not_exempt_record_from_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_dispatch_pair(root, "TASK-001")
            write_file(root, "docs/M1/dispatch/DISPATCH_BOARD.md", "## Active Tasks\n\n| Task |\n|---|\n")
            write_file(
                root,
                "docs/M1/dispatch/decisions.md",
                "| 2026-07-15/D1 | `INACTIVE` | archive completed record | `TASK-001` | owner | ref | none | none | evidence | none |",
            )

            result = run_sagekit("check", "--json", cwd=root)

            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["rule"] == "task-dispatch-board"
                    and "TASK-001" in item["message"]
                    and "absent from" in item["message"]
                    for item in payload["findings"]
                ),
                payload["findings"],
            )

    def test_closed_record_absent_from_board_requires_active_archive_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_dispatch_pair(root, "TASK-CLOSED")
            closed_path = root / "docs/M1/dispatch/TASK-CLOSED/task.yaml"
            closed = json.loads(closed_path.read_text(encoding="utf-8"))
            closed["status"] = "CLOSED"
            closed_path.write_text(json.dumps(closed), encoding="utf-8")
            write_file(root, "docs/M1/dispatch/DISPATCH_BOARD.md", "## Active Tasks\n\n| Task |\n|---|\n")

            result = run_sagekit("check", "--json", cwd=root)

            payload = json.loads(result.stdout)
            board_messages = [
                item["message"]
                for item in payload["findings"]
                if item["rule"] == "task-dispatch-board"
            ]
            self.assertTrue(
                any("TASK-CLOSED" in message and "absent from" in message for message in board_messages),
                board_messages,
            )

    def test_dispatch_board_allows_explicitly_archived_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_dispatch_pair(root, "TASK-CLOSED")
            closed_path = root / "docs/M1/dispatch/TASK-CLOSED/task.yaml"
            closed = json.loads(closed_path.read_text(encoding="utf-8"))
            closed["status"] = "CLOSED"
            closed_path.write_text(json.dumps(closed), encoding="utf-8")
            write_dispatch_pair(root, "TASK-ARCHIVED")
            write_file(root, "docs/M1/dispatch/DISPATCH_BOARD.md", "## Active Tasks\n\n| Task |\n|---|\n")
            write_file(
                root,
                "docs/M1/dispatch/decisions.md",
                "\n".join(
                    [
                        "| 2026-07-15/D1 | `ACTIVE` | archive completed record | `TASK-CLOSED` | owner | ref | none | none | evidence | none |",
                        "| 2026-07-15/D2 | `ACTIVE` | archive completed record | `TASK-ARCHIVED` | owner | ref | none | none | evidence | none |",
                    ]
                ),
            )

            result = run_sagekit("check", "--json", cwd=root)

            payload = json.loads(result.stdout)
            board_messages = [
                item["message"]
                for item in payload["findings"]
                if item["rule"] == "task-dispatch-board"
            ]
            self.assertFalse(any("TASK-CLOSED" in message for message in board_messages), board_messages)
            self.assertFalse(any("TASK-ARCHIVED" in message for message in board_messages), board_messages)

    def test_default_schema_dir_finds_packaged_schema_location(self):
        from sagekit.check import default_schema_dir

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            package = Path(tmp) / "installed" / "sagekit"
            packaged_schemas = package / "resources/docs/profiles/task-dispatch/schemas"
            packaged_schemas.mkdir(parents=True)
            with patch("sagekit.check.__file__", str(package / "check.py")):
                result = default_schema_dir(root)

        self.assertEqual(result.resolve(), packaged_schemas.resolve())

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
            project_root_finding = next(
                item
                for item in payload["findings"]
                if item["level"] == "PASS" and item["rule"] == "project-root"
            )
            reported_root = project_root_finding["message"].removeprefix("using ").strip()
            self.assertEqual(normalized_path_key(reported_root), normalized_path_key(target))

    def test_local_command_wrapper_runs_outside_repo_when_on_path(self):
        if os.name != "nt":
            self.skipTest("sagekit.cmd wrapper is Windows-only")
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
        if os.name != "nt":
            self.skipTest("sagekit.cmd wrapper is Windows-only")
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

            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertFalse((workspace / "docs").exists())
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(item["level"] == "FAIL" and item["rule"] == "target" for item in payload["findings"]),
                payload,
            )

    def test_cli_invalid_max_findings_is_usage_error(self):
        result = run_sagekit("check", "--max-findings", "0", "--json", cwd=REPO_ROOT)

        self.assertEqual(2, result.returncode)
        self.assertIn("between 1 and 500", result.stderr)

    def test_cli_file_target_is_usage_error_for_automation(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.txt"
            target.write_text("not a directory\n", encoding="utf-8")

            result = run_sagekit("check", "--target", str(target), "--json", cwd=Path(tmp))

        self.assertEqual(2, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("target", payload["findings"][0]["rule"])

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

    def test_init_heavy_creates_session_orchestration_packet_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = run_sagekit("init", "--mode", "heavy", "--json", cwd=root)

            self.assertEqual(result.returncode, 0, result.stderr)
            for path in [
                "docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md",
                "docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md",
                "docs/templates/STRUCTURAL_GATE_TEMPLATE.md",
                "docs/templates/FINAL_REVIEW_PACKET_TEMPLATE.md",
                "docs/templates/CORRECTIVE_PACKET_TEMPLATE.md",
            ]:
                self.assertTrue((root / path).exists(), path)

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
        result = run_sagekit(
            "check", "--source-repo", "--json", "--max-findings", "500", cwd=REPO_ROOT
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        rules = {(item["level"], item["rule"]) for item in payload["findings"]}
        self.assertIn(("PASS", "source-gitignore-runtime"), rules)
        self.assertIn(("PASS", "source-tracked-runtime"), rules)

    def test_source_repo_check_reports_packaged_resource_reference_closure(self):
        result = run_sagekit(
            "check", "--source-repo", "--json", "--max-findings", "500", cwd=REPO_ROOT
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        references = [
            item for item in payload["findings"] if item["rule"] == "source-resource-reference"
        ]
        passed_paths = {item["path"] for item in references if item["level"] == "PASS"}

        self.assertTrue(references, payload)
        for path in [
            "sagekit/resources/docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md",
            "sagekit/resources/docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md",
            "sagekit/resources/docs/templates/STRUCTURAL_GATE_TEMPLATE.md",
            "sagekit/resources/docs/templates/FINAL_REVIEW_PACKET_TEMPLATE.md",
            "sagekit/resources/docs/templates/CORRECTIVE_PACKET_TEMPLATE.md",
        ]:
            self.assertIn(path, passed_paths)
        self.assertFalse(
            [item for item in references if item["level"] == "FAIL"],
            references,
        )

    def test_source_repo_check_reports_packaged_resource_mirror_parity(self):
        result = run_sagekit(
            "check", "--source-repo", "--json", "--max-findings", "500", cwd=REPO_ROOT
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        mirrors = [
            item for item in payload["findings"] if item["rule"] == "source-resource-mirror"
        ]
        passed_paths = {item["path"] for item in mirrors if item["level"] == "PASS"}

        self.assertIn("sagekit/resources/docs/SAGE_CORE.md", passed_paths)
        self.assertIn(
            "sagekit/resources/docs/agent/MILESTONE_PLANNING.md",
            passed_paths,
        )
        self.assertFalse(
            [item for item in mirrors if item["level"] == "FAIL"],
            mirrors,
        )

    def test_source_resource_mirror_reports_orphan_packaged_resource(self):
        from sagekit.check import check_source_resource_mirrors

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            resource_root = Path(tmp) / "resources"
            orphan = resource_root / "docs/templates/ORPHAN_TEMPLATE.md"
            orphan.parent.mkdir(parents=True)
            orphan.write_text("# Orphan\n", encoding="utf-8")

            with patch("sagekit.init.package_resource_root", return_value=resource_root):
                findings = check_source_resource_mirrors(root)

        failures = [item for item in findings if item.level == "FAIL"]
        self.assertEqual(len(failures), 1, findings)
        self.assertEqual(failures[0].rule, "source-resource-mirror")
        self.assertIn("has no source document", failures[0].message)

    def test_source_gitignore_runtime_patterns_require_numeric_milestone_dirs(self):
        from sagekit.check import GITIGNORE_RUNTIME_PATTERNS

        self.assertIn("docs/M[0-9]*/", GITIGNORE_RUNTIME_PATTERNS)
        self.assertNotIn("docs/M*/", GITIGNORE_RUNTIME_PATTERNS)

    def test_runtime_state_path_matches_only_numeric_milestone_dirs(self):
        from sagekit.check import is_runtime_state_path

        double_digit_milestone = "docs/M" + "19/closeout.md"
        for path in [
            "docs/ACTIVE_CONTEXT.md",
            "docs/DOC_ROUTING.md",
            "docs/M1/phase.md",
            double_digit_milestone,
            "docs/runs/run-001.md",
            "docs/task-records/task-001.yaml",
            "local/config.json",
            ".sagekit/state.json",
            ".runtime/session.json",
        ]:
            with self.subTest(path=path):
                self.assertTrue(is_runtime_state_path(path), path)

        for path in [
            "docs/MILESTONE_GUIDE.md",
            "docs/MODEL_ASSURANCE.md",
            "docs/agent/MODEL_ASSURANCE_POLICY.md",
        ]:
            with self.subTest(path=path):
                self.assertFalse(is_runtime_state_path(path), path)

    def test_source_repo_tracked_runtime_filters_numeric_milestone_paths(self):
        from sagekit.check import check_source_tracked_runtime

        double_digit_milestone = "docs/M" + "19/closeout.md"
        tracked_paths = [
            "docs/M1/phase.md",
            double_digit_milestone,
            "docs/MILESTONE_GUIDE.md",
            "docs/MODEL_ASSURANCE.md",
            "docs/agent/MODEL_ASSURANCE_POLICY.md",
        ]
        result = subprocess.CompletedProcess(
            args=["git", "ls-files"],
            returncode=0,
            stdout=("\0".join(tracked_paths) + "\0").encode("utf-8"),
            stderr=b"",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sagekit.check.subprocess.run", return_value=result) as run:
                findings = check_source_tracked_runtime(Path(tmp))

        self.assertEqual(run.call_args.args[0], ["git", "ls-files", "-z"])
        self.assertEqual(findings[0].level, "FAIL")
        self.assertIn("docs/M1/phase.md", findings[0].message)
        self.assertIn(double_digit_milestone, findings[0].message)
        self.assertNotIn("docs/MILESTONE_GUIDE.md", findings[0].message)
        self.assertNotIn("docs/MODEL_ASSURANCE.md", findings[0].message)
        self.assertNotIn("docs/agent/MODEL_ASSURANCE_POLICY.md", findings[0].message)

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

    def test_deterministic_closure_contract_is_complete_and_preserves_authority(self):
        from sagekit.init import package_resource_root

        root = package_resource_root()
        orchestration = (root / "docs/agent/SESSION_ORCHESTRATION.md").read_text(encoding="utf-8")
        governance = (root / "docs/agent/GOVERNANCE_LEVELS.md").read_text(encoding="utf-8")
        skill = (REPO_ROOT / "skills/sage-kit/SKILL.md").read_text(encoding="utf-8")
        orchestration_contract = " ".join(orchestration.split())

        self.assertIn("without starting another review lane, subagent, or", orchestration)
        self.assertIn("Closure Receipt Owner", orchestration_contract)
        self.assertIn("original Final Review Controller or named review packet author", orchestration_contract)
        self.assertIn("must be different from the Corrective Worker", orchestration_contract)
        self.assertIn(
            "run the reviewer-authored deterministic closure commands directly or cite a trusted machine/CI result",
            orchestration_contract,
        )
        self.assertIn("does not grant implementation or corrective-surface write authority", orchestration_contract)
        self.assertIn("fixer self-report", orchestration_contract)
        self.assertIn("corresponding surface owner with matching write/corrective authority", orchestration_contract)
        self.assertIn("VERDICT_FINALIZED_FROM_RECEIPT", orchestration_contract)
        self.assertIn("Final Review still owns the verdict", orchestration_contract)
        self.assertIn("Project Manager still owns acceptance", orchestration_contract)

        self.assertIn("fix according to a pre-authored Deterministic Closure predicate", governance)
        self.assertIn("must not record the closure receipt", governance)
        self.assertNotIn("satisfy a pre-authored Deterministic Closure predicate", governance)
        self.assertIn("VERDICT_FINALIZED_FROM_RECEIPT", skill)
        self.assertIn("not milestone acceptance", skill)

    def test_deterministic_closure_templates_express_receipt_and_verdict_transition(self):
        from sagekit.init import package_resource_root

        root = package_resource_root()
        template_paths = [
            "docs/templates/FINAL_REVIEW_PACKET_TEMPLATE.md",
            "docs/templates/CORRECTIVE_PACKET_TEMPLATE.md",
            "docs/templates/LANE_PACKET_TEMPLATE.md",
            "docs/agent/HANDOFF_TEMPLATE.md",
            "docs/templates/STRUCTURAL_GATE_TEMPLATE.md",
            "docs/templates/MILESTONE_LEDGER_TEMPLATE.md",
            "docs/templates/PHASE_TEMPLATE.md",
            "docs/templates/COMPLETION_REPORT_TEMPLATE.md",
        ]

        for path in template_paths:
            with self.subTest(path=path):
                text = (root / path).read_text(encoding="utf-8")
                self.assertIn("NOT_REQUIRED_DETERMINISTIC", text)
                self.assertIn("AUTO_CLOSED_BY_PREDICATE", text)
                self.assertIn("Closure Receipt Owner", text)
                self.assertIn("Closure Receipt Ref", text)
                self.assertIn("Closure Receipt Destination", text)
                self.assertIn("VERDICT_FINALIZED_FROM_RECEIPT", text)
                fields = parse_markdown_fields(text)
                field_surfaces = [
                    field for field in fields if field["label"].lower() == "re-review status"
                ]
                table_surfaces = [
                    row
                    for row in parse_markdown_table_rows(text)
                    if row[0].lower() in {"corrective re-review", "re-review status"}
                ]
                self.assertEqual(len(field_surfaces) + len(table_surfaces), 1)

        unified_status_paths = [
            "docs/templates/FINAL_REVIEW_PACKET_TEMPLATE.md",
            "docs/templates/CORRECTIVE_PACKET_TEMPLATE.md",
            "docs/templates/COMPLETION_REPORT_TEMPLATE.md",
        ]
        for path in unified_status_paths:
            with self.subTest(path=path):
                text = (root / path).read_text(encoding="utf-8")
                status_fields = [
                    field
                    for field in parse_markdown_fields(text)
                    if field["label"] == "Re-review status"
                    or field["label"].lower().endswith("deterministic closure status")
                ]
                self.assertEqual(len(status_fields), 1, status_fields)
                for status in [
                    "NOT_STARTED",
                    "IN_REVIEW",
                    "PASSED",
                    "FAILED",
                    "NOT_REQUIRED_DETERMINISTIC",
                ]:
                    self.assertIn(status, status_fields[0]["value"])
                self.assertIn("never record deterministic closure as `PASSED` re-review", text)

        final_review = (root / template_paths[0]).read_text(encoding="utf-8")
        self.assertRegex(
            final_review,
            r"NEEDS_CORRECTION[\s\S]+AUTO_CLOSED_BY_PREDICATE[\s\S]+VERDICT_FINALIZED_FROM_RECEIPT",
        )
        self.assertIn("Precommitted Final Verdict", final_review)
        self.assertIn("does not re-review files", final_review)
        self.assertIn("Project Manager acceptance remains pending", final_review)

        completion_report = (root / template_paths[-1]).read_text(encoding="utf-8")
        self.assertIn("Finding closure status", completion_report)
        self.assertIn("Finalized verdict", completion_report)
        self.assertIn("PM acceptance pending", completion_report)

    def test_planning_correction_selects_deterministic_closure_or_targeted_rereview(self):
        from sagekit.init import package_resource_root

        root = package_resource_root()
        planning_docs = [
            (root / "docs/agent/MILESTONE_PLANNING.md").read_text(encoding="utf-8"),
            (REPO_ROOT / "skills/sage-kit/references/planning.md").read_text(encoding="utf-8"),
        ]
        for text in planning_docs:
            normalized = " ".join(text.split())
            self.assertNotRegex(normalized, r"NEEDS_CORRECTION.{0,80}Targeted Fix, then Targeted Re-Review")
            branch_start = normalized.index("NEEDS_CORRECTION")
            branch = normalized[branch_start : branch_start + 700]
            self.assertLess(branch.index("Targeted Fix"), branch.index("strict Deterministic Closure"))
            self.assertLess(branch.index("strict Deterministic Closure"), branch.index("Targeted Re-Review"))
            self.assertIn("Closure Receipt Owner", normalized)
            self.assertIn("Verdict Finalization", normalized)

        review_completion = (REPO_ROOT / "skills/sage-kit/references/review-completion.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn(
            "Planning Author, Planning Review, Targeted Fix, Targeted Re-Review,",
            review_completion,
        )
        self.assertRegex(
            " ".join(review_completion.split()),
            r"Planning Author.{0,200}Closure Receipt Owner.{0,200}Verdict Finalization.{0,200}Targeted Re-Review",
        )

        skill_entry = (REPO_ROOT / "skills/sage-kit/SKILL.md").read_text(encoding="utf-8")
        engineering_source = (REPO_ROOT / "docs/ENGINEERING_SYSTEM_TEMPLATE.md").read_text(
            encoding="utf-8"
        )
        engineering_mirror = (
            root / "docs/ENGINEERING_SYSTEM_TEMPLATE.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(engineering_source, engineering_mirror)
        for text in [skill_entry, engineering_source, engineering_mirror]:
            normalized = " ".join(text.split())
            self.assertNotIn(
                "Planning Author, Planning Review, Targeted Fix, Targeted Re-Review, Closeout/Status",
                normalized,
            )
            self.assertRegex(
                normalized,
                r"Planning Author, Planning Review, Targeted Fix, Closure Verification.{0,100}strict Deterministic Closure.{0,100}Targeted Re-Review.{0,100}Closeout/Status.{0,100}Submit Controller",
            )

    def test_ledger_uses_only_canonical_corrective_rereview_row(self):
        from sagekit.init import package_resource_root

        ledger = (
            package_resource_root() / "docs/templates/MILESTONE_LEDGER_TEMPLATE.md"
        ).read_text(encoding="utf-8")
        rows = [row for row in parse_markdown_table_rows(ledger) if row[0] == "Corrective re-review"]
        self.assertEqual(len(rows), 1, rows)
        for status in [
            "NOT_STARTED",
            "IN_REVIEW",
            "PASSED",
            "FAILED",
            "NOT_REQUIRED_DETERMINISTIC",
        ]:
            self.assertIn(status, rows[0][3])

        fields = parse_markdown_fields(ledger)
        self.assertFalse([field for field in fields if field["label"] == "Re-review status"])
        canonical_refs = [
            field for field in fields if field["label"] == "Canonical re-review status source"
        ]
        self.assertEqual(len(canonical_refs), 1, canonical_refs)
        self.assertIn("Corrective re-review", canonical_refs[0]["value"])

    def test_corrective_packet_instantiates_honest_prefix_state_and_owner_followup(self):
        from sagekit.init import package_resource_root

        template = (
            package_resource_root() / "docs/templates/CORRECTIVE_PACKET_TEMPLATE.md"
        ).read_text(encoding="utf-8")
        follow_up = "Receipt Owner Follow-Up (outside Corrective Worker authority)"
        evidence_return = "Corrective Worker Evidence Return"
        self.assertLess(template.index(evidence_return), template.index(follow_up))

        receipt_labels = [
            "Closure receipt status",
            "Closure Receipt Owner",
            "Closure Receipt Ref",
            "Closure Receipt Destination",
            "Verdict finalization status",
            "Finalized verdict",
            "PM acceptance pending",
        ]
        follow_up_start = template.index(follow_up)
        for label in receipt_labels:
            self.assertGreater(template.index(f"- {label}:", follow_up_start), follow_up_start)

        template_fields = parse_markdown_fields(template)
        receipt_status_fields = [
            field for field in template_fields if field["label"] == "Closure receipt status"
        ]
        self.assertEqual(len(receipt_status_fields), 1, receipt_status_fields)
        receipt_status_default = receipt_status_fields[0]["value"]
        self.assertTrue(receipt_status_default.startswith("`PENDING_RECEIPT`"))
        self.assertIn("default before owner follow-up", receipt_status_default)

        instance = instantiate_markdown_packet(
            template,
            {
                "Re-review status": "`NOT_REQUIRED_DETERMINISTIC`",
                "Closure receipt status": "`PENDING_RECEIPT`",
                "Closure Receipt Owner": "`Final Review Controller`",
                "Closure Receipt Ref": "`pending`",
                "Closure Receipt Destination": "`review-packet.md`",
                "Verdict finalization status": "`PENDING_CORRECTION`",
                "Finalized verdict": "`N/A`",
                "PM acceptance pending": "`yes`",
            },
        )
        values = {field["label"]: field["value"] for field in parse_markdown_fields(instance)}
        self.assertEqual(values["Closure receipt status"], "`PENDING_RECEIPT`")
        self.assertEqual(values["Verdict finalization status"], "`PENDING_CORRECTION`")
        self.assertEqual(values["PM acceptance pending"], "`yes`")
        self.assertRegex(
            " ".join(template.split()),
            r"Corrective Worker Evidence Return.{0,500}must not fill or record receipt or verdict-finalization fields",
        )

    def test_authoritative_reject_table_forces_review_fallback(self):
        from sagekit.init import package_resource_root

        orchestration = (
            package_resource_root() / "docs/agent/SESSION_ORCHESTRATION.md"
        ).read_text(encoding="utf-8")
        rows = [
            row
            for row in parse_markdown_table_rows(orchestration)
            if len(row) == 2 and "INVALID_REVIEW_REQUIRED" in row[1]
        ]
        conditions = [row[0].lower() for row in rows]
        for marker in [
            "same actor",
            "non-owned surface",
            "extra or ambiguous diff",
            "trusted machine/CI",
            "State Truth Reconciliation",
        ]:
            self.assertTrue(any(marker.lower() in condition for condition in conditions), (marker, rows))
        for _, result in rows:
            self.assertIn("targeted/full re-review", result)

        self.assertIn("Project Manager acceptance remains pending", orchestration)

    def test_deterministic_closure_state_truth_path_is_reachable(self):
        from sagekit.init import package_resource_root

        root = package_resource_root()
        orchestration = (root / "docs/agent/SESSION_ORCHESTRATION.md").read_text(encoding="utf-8")
        review_completion = (REPO_ROOT / "skills/sage-kit/references/review-completion.md").read_text(
            encoding="utf-8"
        )
        quality_gates = (root / "docs/QUALITY_GATES_TEMPLATE.md").read_text(encoding="utf-8")
        combined = "\n".join([orchestration, review_completion, quality_gates])
        combined_contract = " ".join(combined.split())

        self.assertIn("State Truth conflicts block closure until the responsible surface owners reconcile them", combined_contract)
        self.assertIn("substantive evidence and authoritative value were already reviewed", combined_contract)
        self.assertIn("out-of-scope hashes", combined_contract)
        reject_rows = [
            row
            for row in parse_markdown_table_rows(orchestration)
            if len(row) == 2 and "INVALID_REVIEW_REQUIRED" in row[1]
        ]
        risk_rows = [
            row
            for row in reject_rows
            if all(marker in row[0].lower() for marker in ["authoritative value", "false-green", "gate-ready"])
        ]
        self.assertEqual(len(risk_rows), 1, reject_rows)
        self.assertIn("targeted/full re-review", risk_rows[0][1])
        self.assertIn("Outside strict Deterministic Closure", orchestration)
        self.assertIn("Outside strict Deterministic Closure", review_completion)
        self.assertNotIn("underlying evidence/verdict already accepted", combined)
        self.assertNotIn("underlying evidence and verdict already passed review", combined)
        self.assertNotIn("named status/ledger controller", combined)

    def test_core_and_readmes_do_not_unconditionally_require_corrective_rereview(self):
        core = (REPO_ROOT / "docs/SAGE_CORE.md").read_text(encoding="utf-8")
        quality = (REPO_ROOT / "docs/QUALITY_GATES_TEMPLATE.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_zh = (REPO_ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

        for text in [core, quality, readme, readme_zh]:
            self.assertIn("Deterministic Closure", text)
            self.assertIn("VERDICT_FINALIZED_FROM_RECEIPT", text)

        self.assertNotIn("- corrective re-review evidence when corrective work changes files", core)
        self.assertNotIn("\n  -> independent corrective re-review\n", readme)
        self.assertNotIn("After bounded\ncorrections, Final Review must re-review", readme)
        self.assertNotIn("Bounded corrections 完成后，Final Review 必须先复审", readme_zh)
        self.assertNotIn(
            "corrective work changes files, behavior, contracts, runtime behavior, gate\n"
            "  state, shared ownership, or required evidence without independent re-review\n"
            "  evidence;",
            quality,
        )


if __name__ == "__main__":
    unittest.main()
