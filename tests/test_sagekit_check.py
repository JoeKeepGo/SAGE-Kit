import json
import os
import re
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from sagekit.check import (
    check_adapter_evidence,
    default_schema_dir,
    run_check,
    run_source_repo_check,
)
from sagekit.check import detect_root
from sagekit.reporting import build_finding_report, finding_report_payload


REPO_ROOT = Path(__file__).resolve().parents[1]


def normalized_path_key(path):
    return os.path.normcase(os.path.normpath(str(Path(path).resolve(strict=False))))


@dataclass(frozen=True)
class _CommandResult:
    returncode: int
    stdout: str
    stderr: str


def _as_payload_report(findings, max_findings=500):
    report = build_finding_report(findings, max_findings=max_findings)
    return finding_report_payload(report), any(finding.level == "FAIL" for finding in report.findings)


def _target_not_directory_payload(path: str) -> _CommandResult:
    findings = [
        {"level": "FAIL", "rule": "target", "path": path, "message": "target must be an existing directory"}
    ]
    payload = {
        "findings": findings,
        "summary": {
            "total": 1,
            "displayed": 1,
            "truncated": 0,
            "by_level": {"PASS": 0, "WARN": 0, "FAIL": 1},
        },
    }
    return _CommandResult(2, json.dumps(payload), "")


def _human_output(payload: dict[str, object]) -> str:
    findings = payload["findings"]
    return "\n".join(
        f"{finding['level']} {finding['rule']}: {finding['message']}" for finding in findings
    )


def _run_check_command(start: Path, parsed) -> _CommandResult:
    if parsed["target"] is not None and not Path(parsed["target"]).is_dir():
        return _target_not_directory_payload(parsed["target"])

    root = detect_root(start if parsed["target"] is None else Path(parsed["target"]))
    if not (1 <= parsed["max_findings"] <= 500):
        return _CommandResult(2, "", "between 1 and 500")

    findings = (
        run_source_repo_check(root)
        if parsed["source_repo"]
        else run_check(
            root,
            mode=parsed["mode"],
            scope_manifest_path=parsed["scope_manifest"],
            scope=parsed["scope"],
        )
    )
    payload, has_failures = _as_payload_report(findings, max_findings=parsed["max_findings"])
    output = json.dumps(payload) if parsed["json"] else _human_output(payload)
    return _CommandResult(1 if has_failures else 0, output, "")


def run_compatibility_check(*args, cwd):
    if not args:
        return _CommandResult(2, "", "no command provided")

    if args[0] != "check":
        return _CommandResult(2, "", f"unsupported command: {args[0]}")

    start = Path(cwd).resolve()
    parsed = {
        "target": None,
        "mode": None,
        "scope": None,
        "scope_manifest": None,
        "source_repo": False,
        "max_findings": 500,
        "json": False,
    }
    argv = list(args[1:])
    while argv:
        option = argv.pop(0)
        if option in {"--json", "--source-repo"}:
            parsed["json"] = option == "--json" or parsed["json"]
            if option == "--source-repo":
                parsed["source_repo"] = True
            continue
        if option in {"--target", "--mode", "--scope", "--scope-manifest", "--max-findings"}:
            if not argv:
                return _CommandResult(
                    2,
                    "",
                    f"{option} requires a value",
                )
            value = argv.pop(0)
            if option == "--target":
                parsed["target"] = value
            elif option == "--mode":
                parsed["mode"] = value
            elif option == "--scope":
                parsed["scope"] = value
            elif option == "--scope-manifest":
                parsed["scope_manifest"] = value
            else:
                try:
                    parsed["max_findings"] = int(value)
                except ValueError:
                    return _CommandResult(2, "", str(value))
            continue
        return _CommandResult(
            2,
            "",
            f"unsupported check flags: {option}",
        )

    parsed["scope_manifest"] = (
        Path(parsed["scope_manifest"]) if parsed["scope_manifest"] else None
    )
    return _run_check_command(start, parsed)


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
        Next action: run the active compatibility check.
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


def write_active_milestones(root, *milestones):
    value = ", ".join(milestones) if milestones else "none"
    write_file(
        root,
        "docs/ACTIVE_CONTEXT.md",
        f"# Active Context\n\n- Current milestone: `{value}`",
    )


def write_closeout(root, milestone, status=None, prose=None):
    lines = ["# Milestone Closeout", "", "## Outcome", ""]
    if status is not None:
        lines.append(f"- Status: `{status}`")
    if prose is not None:
        lines.extend(["", prose])
    write_file(root, f"docs/{milestone}/MILESTONE_CLOSEOUT.md", "\n".join(lines))


def write_scope_manifest(root, *, active=(), accepted=()):
    for milestone in (*active, *accepted):
        (root / "docs" / milestone).mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "active_containers": [
            {"id": milestone, "path": f"docs/{milestone}"} for milestone in active
        ],
        "accepted_legacy_containers": [
            {
                "id": milestone,
                "path": f"docs/{milestone}",
                "contract_version": 1,
                "supersedes": [],
            }
            for milestone in accepted
        ],
        "authority": {
            "source": "project-owner migration acceptance",
            "approved_by": "project-owner",
            "approved_at": "2026-01-01T00:00:00Z",
            "baseline_head": "0123456789abcdef0123456789abcdef01234567",
        },
    }
    write_file(root, "docs/SAGE_VALIDATION_SCOPE.json", json.dumps(payload))


def write_historical_phase(root, milestone, name="01-foundation.md"):
    write_file(
        root,
        f"docs/{milestone}/{name}",
        f"""
        # {milestone} Historical Phase

        Goal: Preserve the accepted foundation.
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
    def test_capability_prose_does_not_activate_adapter_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "docs" / "M1" / "PHASE.md"
            findings = check_adapter_evidence(
                root,
                path,
                "This phase improves the product capability without an external adapter.",
            )

        self.assertEqual([], findings)

    def test_structured_adapter_declaration_activates_adapter_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "docs" / "M1" / "PHASE.md"
            findings = check_adapter_evidence(
                root,
                path,
                "## Capability Adapter\n\nAdapter: browser-qa\n",
            )

        self.assertTrue(findings)
        self.assertIn("adapter-authorization", {item.rule for item in findings})
    def test_json_check_warns_for_missing_recommended_docs_without_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            failures = [item for item in payload["findings"] if item["level"] == "FAIL"]
            self.assertTrue(any(item["rule"] == "required-docs" for item in failures))

    def test_human_check_prints_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)

            result = run_compatibility_check("check", cwd=root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PASS required-docs:", result.stdout)
            self.assertIn("WARN recommended-docs:", result.stdout)

    def test_planning_only_phase_allows_runtime_smoke_na_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_valid_planning_phase(root)

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["level"] == "FAIL" and item["rule"] == "phase-runtime-smoke"
                    for item in payload["findings"]
                )
            )

    def test_accepted_historical_phase_is_not_retroactively_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_active_milestones(root, "M2")
            write_closeout(root, "M1", status="ACCEPTED")
            write_scope_manifest(root, active=("M2",), accepted=("M1",))
            write_historical_phase(root, "M1")

            result = run_compatibility_check("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 0, result.stdout)
            payload = json.loads(result.stdout)
            historical = [
                item
                for item in payload["findings"]
                if item["path"] and item["path"].startswith("docs/M1")
            ]
            self.assertEqual(
                1,
                len(
                    [
                        item
                        for item in historical
                        if item["rule"] == "phase-scope-compatibility"
                    ]
                ),
                historical,
            )
            self.assertTrue(
                any(
                    item["rule"] == "phase-scope-compatibility"
                    and "immutable accepted history" in item["message"].lower()
                    for item in historical
                ),
                historical,
            )
            self.assertFalse(
                [
                    item
                    for item in historical
                    if item["level"] == "FAIL" and item["rule"].startswith("phase-")
                ],
                historical,
            )

    def test_history_audits_thin_documents_in_manifest_selected_generic_container(self):
        from sagekit.check import check_execution_documents
        from sagekit.validation_scope_manifest import load_validation_scope_manifest
        from tests.test_thin_execution_documents import create_project

        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            archive = root / "docs/history/archive"
            archive.parent.mkdir(parents=True)
            (root / "docs/M36").replace(archive)
            write_file(
                root,
                "docs/SAGE_VALIDATION_SCOPE.json",
                json.dumps(
                    {
                        "schema_version": 1,
                        "active_containers": [],
                        "accepted_legacy_containers": [
                            {
                                "id": "M36",
                                "path": "docs/history/archive",
                                "contract_version": 1,
                                "supersedes": [],
                            }
                        ],
                        "authority": {
                            "source": "project-owner migration acceptance",
                            "approved_by": "project-owner",
                            "approved_at": "2026-01-01T00:00:00Z",
                            "baseline_head": "0123456789abcdef0123456789abcdef01234567",
                        },
                    }
                ),
            )
            manifest = load_validation_scope_manifest(root / "docs/SAGE_VALIDATION_SCOPE.json")

            findings = check_execution_documents(root, scope_manifest=manifest)

        self.assertTrue(
            any(
                item.rule == "execution-document-history" and item.level == "PASS"
                for item in findings
            ),
            findings,
        )
        self.assertFalse(
            any(item.rule == "unsupported-history" for item in findings),
            findings,
        )

    def test_history_blocks_unadaptable_thin_documents_in_manifest_selected_container(self):
        from sagekit.check import check_execution_documents
        from sagekit.validation_scope_manifest import load_validation_scope_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_file(root, "docs/history/archive/MILESTONE_MANIFEST.json", "{}\n")
            write_file(
                root,
                "docs/SAGE_VALIDATION_SCOPE.json",
                json.dumps(
                    {
                        "schema_version": 1,
                        "active_containers": [],
                        "accepted_legacy_containers": [
                            {
                                "id": "M36",
                                "path": "docs/history/archive",
                                "contract_version": 1,
                                "supersedes": [],
                            }
                        ],
                        "authority": {
                            "source": "project-owner migration acceptance",
                            "approved_by": "project-owner",
                            "approved_at": "2026-01-01T00:00:00Z",
                            "baseline_head": "0123456789abcdef0123456789abcdef01234567",
                        },
                    }
                ),
            )
            manifest = load_validation_scope_manifest(root / "docs/SAGE_VALIDATION_SCOPE.json")

            findings = check_execution_documents(root, scope_manifest=manifest)

        self.assertTrue(
            any(item.rule == "unsupported-history" and item.level == "FAIL" for item in findings),
            findings,
        )

    def test_current_phase_still_requires_latest_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_active_milestones(root, "M2")
            write_historical_phase(root, "M2", name="01-current.md")

            result = run_compatibility_check("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["level"] == "FAIL"
                    and item["rule"] == "phase-governance"
                    and item["path"].startswith("docs/M2")
                    for item in payload["findings"]
                ),
                payload,
            )

    def test_active_and_accepted_phase_authority_conflict_reports_root_cause_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_active_milestones(root, "M3")
            write_closeout(root, "M3", status="DONE")
            write_scope_manifest(root, active=("M3",))
            write_historical_phase(root, "M3")
            write_historical_phase(root, "M3", name="02-second.md")

            result = run_compatibility_check("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            scope_failures = [
                item
                for item in payload["findings"]
                if item["level"] == "FAIL"
                and item["rule"] == "milestone-scope"
                and item["path"] == "docs/M3"
            ]
            self.assertEqual(1, len(scope_failures), payload)
            self.assertIn("authority conflict", scope_failures[0]["message"].lower())
            self.assertFalse(
                [
                    item
                    for item in payload["findings"]
                    if item["level"] == "FAIL"
                    and item["path"]
                    and item["path"].startswith("docs/M3/")
                    and item["rule"].startswith("phase-")
                ],
                payload,
            )

    def test_phase_checker_resolves_each_milestone_scope_once(self):
        from sagekit.check import check_phase_docs
        from sagekit.milestone_scope import RepositoryScopeResolver

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_active_milestones(root, "M1")
            write_historical_phase(root, "M1")
            write_historical_phase(root, "M1", name="02-second.md")
            original = RepositoryScopeResolver.resolve
            calls = []

            def tracked_resolve(resolver, milestone_dir):
                calls.append(milestone_dir.name)
                return original(resolver, milestone_dir)

            with patch.object(RepositoryScopeResolver, "resolve", tracked_resolve):
                check_phase_docs(root)

        self.assertEqual(["M1"], calls)

    def test_unstructured_closeout_authority_fails_closed_without_phase_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_active_milestones(root, "M2")
            write_closeout(
                root,
                "M3",
                prose="This narrative says accepted but has no structured outcome.",
            )
            write_historical_phase(root, "M3")

            result = run_compatibility_check("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["level"] == "FAIL"
                    and item["rule"] == "milestone-scope"
                    and item["path"] == "docs/M3"
                    and "ambiguous" in item["message"].lower()
                    for item in payload["findings"]
                ),
                payload,
            )
            self.assertFalse(
                [
                    item
                    for item in payload["findings"]
                    if item["level"] == "FAIL"
                    and item["path"]
                    and item["path"].startswith("docs/M3/")
                    and item["rule"].startswith("phase-")
                ],
                payload,
            )

    def test_generic_scope_fixture_routes_history_current_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_docs(root)
            write_active_milestones(root, "M2", "M3")
            write_closeout(root, "M1", status="DONE_WITH_CONCERNS")
            write_closeout(root, "M3", status="ACCEPTED")
            write_scope_manifest(root, active=("M2", "M3"), accepted=("M1",))
            write_historical_phase(root, "M1")
            write_valid_planning_phase(root)
            source = root / "docs/M1/01-planning.md"
            (root / "docs/M2").mkdir(parents=True, exist_ok=True)
            source.replace(root / "docs/M2/01-current.md")
            write_historical_phase(root, "M3")

            result = run_compatibility_check("check", "--json", cwd=root)

            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(
                any(
                    item["rule"] == "phase-scope-compatibility"
                    and item["path"] == "docs/M1"
                    for item in payload["findings"]
                ),
                payload,
            )
            self.assertFalse(
                any(
                    item["level"] == "FAIL"
                    and item["path"]
                    and item["path"].startswith("docs/M2/")
                    for item in payload["findings"]
                ),
                payload,
            )
            self.assertEqual(
                1,
                len(
                    [
                        item
                        for item in payload["findings"]
                        if item["rule"] == "milestone-scope"
                        and item["path"] == "docs/M3"
                    ]
                ),
                payload,
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

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--json", cwd=root)

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

            result = run_compatibility_check("check", "--target", str(target), "--json", cwd=runner_cwd)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            project_root_finding = next(
                item
                for item in payload["findings"]
                if item["level"] == "PASS" and item["rule"] == "project-root"
            )
            reported_root = project_root_finding["message"].removeprefix("using ").strip()
            self.assertEqual(normalized_path_key(reported_root), normalized_path_key(target))

    def test_source_repo_check_does_not_require_instantiated_project_context(self):
        result = run_compatibility_check("check", "--source-repo", "--json", cwd=REPO_ROOT)

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
        result = run_compatibility_check(
            "check", "--source-repo", "--json", "--max-findings", "500", cwd=REPO_ROOT
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        rules = {(item["level"], item["rule"]) for item in payload["findings"]}
        self.assertIn(("PASS", "source-gitignore-runtime"), rules)
        self.assertIn(("PASS", "source-tracked-runtime"), rules)

    def test_source_repo_check_reports_packaged_resource_reference_closure(self):
        result = run_compatibility_check(
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
        result = run_compatibility_check(
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
        from sagekit.check import check_source_tracked_runtime_paths

        double_digit_milestone = "docs/M" + "19/closeout.md"
        tracked_paths = [
            "docs/M1/phase.md",
            double_digit_milestone,
            "docs/MILESTONE_GUIDE.md",
            "docs/MODEL_ASSURANCE.md",
            "docs/agent/MODEL_ASSURANCE_POLICY.md",
        ]
        findings = check_source_tracked_runtime_paths(tracked_paths)

        self.assertEqual(findings[0].level, "FAIL")
        self.assertIn("docs/M1/phase.md", findings[0].message)
        self.assertIn(double_digit_milestone, findings[0].message)
        self.assertNotIn("docs/MILESTONE_GUIDE.md", findings[0].message)
        self.assertNotIn("docs/MODEL_ASSURANCE.md", findings[0].message)
        self.assertNotIn("docs/agent/MODEL_ASSURANCE_POLICY.md", findings[0].message)

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

    def test_planning_isolates_serial_barriers_before_rejecting_parallelism(self):
        from sagekit.init import package_resource_root

        root = package_resource_root()
        core = (root / "docs/SAGE_CORE.md").read_text(encoding="utf-8")
        wave = (root / "docs/agent/WAVE_EXECUTION.md").read_text(encoding="utf-8")
        planning = (root / "docs/agent/MILESTONE_PLANNING.md").read_text(
            encoding="utf-8"
        )
        orchestration = (root / "docs/agent/SESSION_ORCHESTRATION.md").read_text(
            encoding="utf-8"
        )
        skill_planning = (
            REPO_ROOT / "skills/sage-kit/references/planning.md"
        ).read_text(encoding="utf-8")

        self.assertIn('<a id="sage-grf-001"></a>', core)
        self.assertIn("Begin with one bounded execution loop", core)
        self.assertIn("Light work is never required to upgrade to Graph execution", core)
        for anchor in ("sage-grf-002", "sage-grf-005", "sage-grf-006"):
            self.assertIn(f'<a id="{anchor}"></a>', wave)

        self.assertIn(
            "Shared serial ownership does not justify milestone-wide serial execution",
            wave,
        )
        for requirement in [
            "dependency DAG",
            "parallel candidates",
            "serial barriers",
            "phase-internal lanes",
        ]:
            self.assertIn(requirement, wave)
        self.assertRegex(
            " ".join(wave.split()),
            r"SERIAL.{0,500}(phase|lane).{0,200}(dependency|conflict|gate|runtime)",
        )
        self.assertIn(
            "A missing readiness item serializes only the affected node",
            wave,
        )
        self.assertIn(
            "continue evaluating unaffected parallel candidates",
            " ".join(wave.split()),
        )
        self.assertIn(
            "Milestone-wide `SERIAL` is allowed only when the barrier cannot be isolated",
            " ".join(wave.split()),
        )

        for text in (planning, orchestration, skill_planning):
            self.assertIn("docs/SAGE_CORE.md#sage-grf-001", text)
            self.assertIn("docs/agent/WAVE_EXECUTION.md#sage-grf-002", text)

        packet = (
            root / "docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Dependency DAG", packet)
        self.assertIn("Parallel candidates", packet)
        self.assertIn("Serial barriers", packet)

    def test_controller_launch_envelope_references_readable_project_authority(self):
        from sagekit.init import package_resource_root

        root = package_resource_root()
        harness = (root / "docs/agent/AGENT_HARNESS.md").read_text(encoding="utf-8")
        prompt_template = (
            root / "docs/templates/AGENT_PROMPT_TEMPLATE.md"
        ).read_text(encoding="utf-8")
        execution_packet = (
            root / "docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md"
        ).read_text(encoding="utf-8")
        orchestration = (
            root / "docs/agent/SESSION_ORCHESTRATION.md"
        ).read_text(encoding="utf-8")
        skill_execution = (
            REPO_ROOT / "skills/sage-kit/references/execution.md"
        ).read_text(encoding="utf-8")
        combined = " ".join(
            " ".join(text.split())
            for text in [harness, prompt_template, execution_packet, orchestration, skill_execution]
        )

        self.assertIn('<a id="sage-auth-010"></a>', harness)
        self.assertIn("it must not change scope, gates, permission, ownership", harness)
        self.assertIn("fail closed before editing", harness)
        self.assertIn("Compact Controller Launch Envelope", combined)
        for field in [
            "role and objective",
            "authority references",
            "baseline or entry condition",
            "permission mode",
            "PM authority deltas",
            "terminal state",
        ]:
            self.assertIn(field, combined)
        self.assertIn("must not duplicate the execution packet", combined)
        self.assertIn("Worker prompts remain explicit", combined)
        self.assertIn("guideline, not a correctness gate", combined)
        self.assertIn("Standalone Task Exception", prompt_template)
        self.assertIn("complete and self-contained", prompt_template)
        self.assertIn("does not require inaccessible local paths", prompt_template)
        self.assertIn("Missing required authority fails closed", prompt_template)
        self.assertIn("These are mutually exclusive paths", prompt_template)
        standalone = prompt_template.split("## Standalone Task Exception", 1)[1].split(
            "## Explicit Local Worker Prompt", 1
        )[0]
        for local_path in [
            "docs/ACTIVE_CONTEXT.md",
            "docs/DOC_ROUTING.md",
            "docs/agent/GOVERNANCE_LEVELS.md",
        ]:
            self.assertNotIn(local_path, standalone)
        local_worker = prompt_template.split("## Explicit Local Worker Prompt", 1)[1]
        self.assertIn("docs/ACTIVE_CONTEXT.md", local_worker)
        self.assertNotIn("cannot read", local_worker)
        for field in [
            "authority ID",
            "source",
            "priority",
            "reconciliation destination",
        ]:
            self.assertIn(field, combined)
        self.assertIn("launch-only delta", combined)
        self.assertIn("fail closed before editing", combined)
        for non_owner in [
            prompt_template,
            execution_packet,
            orchestration,
            skill_execution,
        ]:
            self.assertIn("docs/agent/AGENT_HARNESS.md#sage-auth-010", non_owner)

    def test_stage1b_context_and_graph_rules_have_canonical_owners_and_pointers(self):
        paths = {
            "core": "docs/SAGE_CORE.md",
            "harness": "docs/agent/AGENT_HARNESS.md",
            "source": "docs/agent/SPEC_SOURCE_CONTRACT.md",
            "planning": "docs/agent/MILESTONE_PLANNING.md",
            "session": "docs/agent/SESSION_ORCHESTRATION.md",
            "wave": "docs/agent/WAVE_EXECUTION.md",
            "agent_prompt": "docs/templates/AGENT_PROMPT_TEMPLATE.md",
            "milestone_packet": "docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md",
            "lane_packet": "docs/templates/LANE_PACKET_TEMPLATE.md",
            "result_packet": "docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md",
            "skill": "skills/sage-kit/SKILL.md",
            "adoption": "skills/sage-kit/references/adoption.md",
            "skill_planning": "skills/sage-kit/references/planning.md",
            "skill_execution": "skills/sage-kit/references/execution.md",
            "skill_review": "skills/sage-kit/references/review-completion.md",
        }
        sources = {
            name: (REPO_ROOT / path).read_text(encoding="utf-8")
            for name, path in paths.items()
        }
        owners = {
            "sage-auth-010": "harness",
            "sage-ctx-001": "source",
            "sage-ctx-002": "source",
            "sage-ctx-005": "harness",
            "sage-grf-001": "core",
            "sage-grf-002": "wave",
            "sage-grf-005": "wave",
            "sage-grf-006": "wave",
            "sage-grf-011": "wave",
        }
        for anchor, owner in owners.items():
            marker = f'<a id="{anchor}"></a>'
            self.assertEqual(sources[owner].count(marker), 1, anchor)
            for name, text in sources.items():
                if name != owner:
                    self.assertNotIn(marker, text, (anchor, name))

        pointer_matrix = {
            "docs/agent/AGENT_HARNESS.md#sage-auth-010": (
                "agent_prompt",
                "milestone_packet",
                "session",
                "skill_execution",
            ),
            "docs/agent/SPEC_SOURCE_CONTRACT.md#sage-ctx-001": (
                "core",
                "harness",
                "skill",
                "adoption",
                "skill_planning",
                "skill_execution",
                "skill_review",
            ),
            "docs/agent/SPEC_SOURCE_CONTRACT.md#sage-ctx-002": (
                "core",
                "harness",
                "skill",
                "adoption",
                "skill_review",
            ),
            "docs/agent/AGENT_HARNESS.md#sage-ctx-005": ("skill",),
            "docs/SAGE_CORE.md#sage-grf-001": (
                "planning",
                "session",
                "wave",
                "skill",
                "skill_planning",
                "skill_execution",
            ),
            "docs/agent/WAVE_EXECUTION.md#sage-grf-002": (
                "planning",
                "session",
                "milestone_packet",
                "skill",
                "skill_planning",
                "skill_execution",
            ),
            "docs/agent/WAVE_EXECUTION.md#sage-grf-005": (
                "planning",
                "session",
                "skill_planning",
            ),
            "docs/agent/WAVE_EXECUTION.md#sage-grf-006": (
                "planning",
                "session",
                "skill_planning",
                "skill_execution",
            ),
            "docs/agent/WAVE_EXECUTION.md#sage-grf-011": (
                "lane_packet",
                "result_packet",
            ),
        }
        for pointer, non_owners in pointer_matrix.items():
            for non_owner in non_owners:
                self.assertIn(pointer, sources[non_owner], (pointer, non_owner))

        source = sources["source"]
        self.assertIn("Resolve one current source in this order", source)
        self.assertIn("An explicit or configured source fails closed", source)
        self.assertIn("not a complete execution specification", source)
        self.assertIn("ACCEPTED_HISTORY` is non-executable", source)

        harness = sources["harness"]
        self.assertIn("Load active authority and exposed capability metadata first", harness)
        self.assertIn("Skill or reference bodies relevant to the routed task", harness)
        self.assertIn("docs/agent/AGENT_HARNESS.md#sage-ctx-005", sources["skill"])

        wave = sources["wave"]
        for status in ("`DONE`", "`DONE_WITH_CONCERNS`", "`HANDOFF`", "`BLOCKED`"):
            self.assertIn(status, wave)
        self.assertIn("HANDOFF`: nonterminal", wave)
        self.assertIn("cannot auto-advance a phase or acceptance", wave)

    def test_codex_gpt56_uses_native_workflows_without_superpowers(self):
        from sagekit.init import package_resource_root

        root = package_resource_root()
        capability_source = (REPO_ROOT / "docs/agent/CAPABILITY_ADAPTERS.md").read_text(
            encoding="utf-8"
        )
        capability_packaged = (
            root / "docs/agent/CAPABILITY_ADAPTERS.md"
        ).read_text(encoding="utf-8")
        prompt = (root / "docs/templates/AGENT_PROMPT_TEMPLATE.md").read_text(
            encoding="utf-8"
        )
        packet = (
            root / "docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md"
        ).read_text(encoding="utf-8")
        skill = (REPO_ROOT / "skills/sage-kit/SKILL.md").read_text(encoding="utf-8")
        execution = (
            REPO_ROOT / "skills/sage-kit/references/execution.md"
        ).read_text(encoding="utf-8")
        openai_profile = (
            REPO_ROOT / "skills/sage-kit/agents/openai.yaml"
        ).read_text(encoding="utf-8")

        self.assertEqual(capability_source, capability_packaged)
        codex_contracts = [
            capability_source,
            prompt,
            packet,
            skill,
            execution,
            openai_profile,
        ]
        combined = " ".join(" ".join(text.split()) for text in codex_contracts)
        for rule in [
            "Codex GPT-5.6 Runtime Override",
            "DISABLED_BY_RUNTIME_POLICY",
            "must not read, invoke, or delegate to Superpowers",
            "`using-superpowers` is explicitly disabled even when its skill metadata describes invocation as mandatory",
            "model-native brainstorming, planning, test-driven implementation, systematic debugging, subagent orchestration, review, and verification",
            "native behaviors, not similarly named skill invocations",
            "descendants inherit",
            "Every subagent launch packet must explicitly repeat",
            "descendant authorized to delegate must",
            "compaction, handoff, or resume",
            "must not treat disabled Superpowers as a capability gap",
        ]:
            self.assertIn(rule, combined)

        for text in [capability_source, skill, execution]:
            normalized = " ".join(text.split())
            self.assertIn("Codex GPT-5.6 Runtime Override", normalized)
            self.assertIn("DISABLED_BY_RUNTIME_POLICY", normalized)
            self.assertIn("model-native brainstorming", normalized)

        self.assertIn("When running a GPT-5.6 family model in Codex", " ".join(openai_profile.split()))
        self.assertIn("Otherwise use the runtime's normal adapter policy", " ".join(openai_profile.split()))
        self.assertIn("Superpowers Reference Integration", capability_source)
        self.assertIn("references/kimi-runtime.md", skill)
        self.assertIn("references/claude.md", skill)
        self.assertIn("references/opencode.md", skill)

    def test_working_tree_candidate_snapshot_is_explicit_and_bound(self):
        from sagekit.init import package_resource_root

        root = package_resource_root()
        source = (REPO_ROOT / "docs/agent/EXECUTION_ECONOMY.md").read_text(
            encoding="utf-8"
        )
        packaged = (root / "docs/agent/EXECUTION_ECONOMY.md").read_text(
            encoding="utf-8"
        )
        packet = (
            REPO_ROOT / "docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md"
        ).read_text(encoding="utf-8")
        skill = (REPO_ROOT / "skills/sage-kit/SKILL.md").read_text(encoding="utf-8")
        execution = (
            REPO_ROOT / "skills/sage-kit/references/execution.md"
        ).read_text(encoding="utf-8")

        self.assertEqual(source, packaged)
        contract = " ".join(
            " ".join(text.split()) for text in [source, packet, skill, execution]
        )
        for rule in [
            "clean-head",
            "working-tree",
            "must be authorized by the active execution packet",
            "`snapshot_authority` field",
            "binds it into the versioned candidate fingerprint",
            "index/staged state",
            "non-ignored untracked",
            "symlink identity",
            "before and after final verification",
            "Dirty submodules",
            "not a commit, submit, acceptance, or permission upgrade",
            "must not accept an unbound dirty-worktree bypass",
            "Older candidate fingerprints retain their original clean-worktree semantics",
        ]:
            self.assertIn(rule, contract)

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

        for text in [core, quality]:
            self.assertIn("Deterministic Closure", text)
            self.assertIn("VERDICT_FINALIZED_FROM_RECEIPT", text)
        for text in [readme, readme_zh]:
            self.assertIn("EXECUTION_ECONOMY_REDESIGN.md", text)

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
