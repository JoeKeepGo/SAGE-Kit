import json
import tempfile
import unittest
from pathlib import Path

from sagekit.check import check_phase_docs, check_task_dispatch, run_check
from sagekit.compatibility import select_validation_contract, validate_compatible_records
from sagekit.milestone_scope import (
    MilestoneScopeKind,
    RepositoryScopeResolver,
    read_active_milestones,
)
from sagekit.task_dispatch_validator import load_record
from sagekit.validation_scope_manifest import (
    LOCAL_SCOPE_MANIFEST,
    ScopeManifestError,
    load_validation_scope_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPO_ROOT / "docs/profiles/task-dispatch/templates"
BASELINE_HEAD = "0123456789abcdef0123456789abcdef01234567"


def manifest_payload(
    *,
    active=(),
    accepted=("M1",),
    supersedes=None,
    contract_version=1,
):
    supersedes = supersedes or {}
    return {
        "schema_version": 1,
        "active_containers": [
            {"id": container_id, "path": f"docs/{container_id}"}
            for container_id in active
        ],
        "accepted_legacy_containers": [
            {
                "id": container_id,
                "path": f"docs/{container_id}",
                "contract_version": contract_version,
                "supersedes": list(supersedes.get(container_id, ())),
            }
            for container_id in accepted
        ],
        "authority": {
            "source": "project-owner migration acceptance",
            "approved_by": "project-owner",
            "approved_at": "2026-01-01T00:00:00Z",
            "baseline_head": BASELINE_HEAD,
        },
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def write_manifest(root, payload=None, *, relative=LOCAL_SCOPE_MANIFEST):
    payload = payload or manifest_payload()
    for field in ("active_containers", "accepted_legacy_containers"):
        for container in payload.get(field, ()):
            value = container.get("path")
            if (
                isinstance(value, str)
                and value.startswith("docs/")
                and not any(character in value for character in "*?[")
                and ".." not in Path(value).parts
            ):
                (root / value).mkdir(parents=True, exist_ok=True)
    return write_json(root / relative, payload)


def write_active_context(root, milestones=()):
    value = ", ".join(milestones) if milestones else "none"
    path = root / "docs/ACTIVE_CONTEXT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Active Context\n\n- Current milestone: `{value}`\n",
        encoding="utf-8",
    )


def write_closeout(root, milestone, status=None, *, prose=None):
    path = root / "docs" / milestone / "MILESTONE_CLOSEOUT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "# Milestone Closeout\n"
    if status is not None:
        text += f"\n- Status: `{status}`\n"
    if prose is not None:
        text += f"\n{prose}\n"
    path.write_text(text, encoding="utf-8")
    return path


def record_pair(*, status="VERIFIED", explicit_version=None):
    task = load_record(TEMPLATE_ROOT / "TASK_RECORD_TEMPLATE.yaml")
    evidence = load_record(TEMPLATE_ROOT / "EVIDENCE_RECORD_TEMPLATE.yaml")
    task["id"] = "TASK-GENERIC"
    evidence["task_id"] = task["id"]
    task["status"] = status
    task["lifecycle"].update(
        {
            "phase": "closed",
            "review_result": "ACCEPTABLE",
            "next_action": "none; historical record",
        }
    )
    task["closure"].update(
        {
            "accepted_by": "reviewer",
            "accepted_at": "2025-01-01T00:00:00Z",
            "closed_at": "2025-01-01T00:00:00Z",
            "review_result": "ACCEPTABLE",
            "evidence_ref": "evidence.yaml",
        }
    )
    evidence["phase"] = "closed"
    evidence["levels"]["L0"].update(
        {"status": "PASS", "evidence": ["accepted"], "reason": None}
    )
    evidence["conclusion"].update(
        {
            "status": "VERIFIED",
            "highest_level": "L0",
            "review_result": "ACCEPTABLE",
            "next_action": "none; historical record",
        }
    )
    if explicit_version is None:
        task.pop("validation_contract")
        evidence.pop("validation_contract")
    elif explicit_version == 1:
        from sagekit.validation_contracts.v1 import contract_metadata

        task["validation_contract"] = contract_metadata()
        evidence["validation_contract"] = contract_metadata()
    return task, evidence


def write_dispatch_pair(root, milestone, task, evidence, *, name="record"):
    directory = root / "docs" / milestone / "dispatch" / name
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "task.yaml", task)
    write_json(directory / "evidence.yaml", evidence)
    board = root / "docs" / milestone / "dispatch" / "DISPATCH_BOARD.md"
    board.write_text("## Active Tasks\n\n| Task |\n|---|\n", encoding="utf-8")
    return directory


class ScopeManifestParsingTests(unittest.TestCase):
    def test_valid_external_manifest_is_loaded_with_auditable_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_json(Path(directory) / "scope.json", manifest_payload())

            manifest = load_validation_scope_manifest(path)

        self.assertEqual(
            ("M1",),
            tuple(container.id for container in manifest.accepted_legacy_containers),
        )
        self.assertEqual(BASELINE_HEAD, manifest.authority.baseline_head)
        self.assertRegex(manifest.digest, r"^[0-9a-f]{64}$")
        self.assertEqual(path.resolve(), manifest.path)

    def test_project_local_manifest_is_used_and_cli_manifest_has_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = load_validation_scope_manifest(
                write_manifest(root, manifest_payload(accepted=("M1",)))
            )
            external = load_validation_scope_manifest(
                write_json(
                    root / "outside/scope.json",
                    manifest_payload(active=("M1",), accepted=()),
                )
            )

            local_scope = RepositoryScopeResolver(root, manifest=local).resolve(
                root / "docs/M1"
            )
            external_scope = RepositoryScopeResolver(root, manifest=external).resolve(
                root / "docs/M1"
            )

        self.assertEqual(
            MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY, local_scope.kind
        )
        self.assertEqual(MilestoneScopeKind.CURRENT, external_scope.kind)

    def test_external_manifest_authority_does_not_expose_absolute_path(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "target"
            manifest = load_validation_scope_manifest(
                write_json(
                    workspace / "external/scope.json",
                    manifest_payload(),
                )
            )
            (root / "docs/M1").mkdir(parents=True)

            scope = RepositoryScopeResolver(
                root,
                manifest=manifest,
                manifest_source="explicit-harness",
            ).resolve(root / "docs/M1")

        rendered = " ".join((*scope.authorities, scope.detail))
        self.assertNotIn(str(workspace), rendered)
        self.assertIn("validation scope manifest authority: explicit-harness", rendered)

    def test_malformed_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scope.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaisesRegex(ScopeManifestError, "JSON"):
                load_validation_scope_manifest(path)

    def test_unknown_schema_and_contract_versions_are_rejected(self):
        cases = (
            ("schema", 2, "schema_version"),
            ("contract", 2, "contract_version"),
            ("schema", True, "schema_version"),
            ("contract", True, "contract_version"),
        )
        for field, value, message in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                payload = manifest_payload()
                if field == "schema":
                    payload["schema_version"] = value
                else:
                    payload["accepted_legacy_containers"][0][
                        "contract_version"
                    ] = value
                path = write_json(Path(directory) / "scope.json", payload)
                with self.assertRaisesRegex(ScopeManifestError, message):
                    load_validation_scope_manifest(path)

    def test_missing_or_invalid_authority_is_rejected(self):
        cases = (
            ("missing", None, "authority"),
            ("approved_by", "", "approved_by"),
            ("approved_at", "not-a-timestamp", "approved_at"),
            ("baseline_head", "ABC123", "baseline_head"),
        )
        for field, value, message in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                payload = manifest_payload()
                if field == "missing":
                    payload.pop("authority")
                else:
                    payload["authority"][field] = value
                path = write_json(Path(directory) / "scope.json", payload)
                with self.assertRaisesRegex(ScopeManifestError, message):
                    load_validation_scope_manifest(path)

    def test_duplicate_milestones_overlap_and_alias_collisions_are_rejected(self):
        cases = (
            (manifest_payload(accepted=("M1", "M1")), "duplicate"),
            (manifest_payload(active=("M1",), accepted=("M1",)), "overlapping"),
            (
                manifest_payload(active=("M34-1",), accepted=("M34_1",)),
                "alias",
            ),
        )
        for payload, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                path = write_json(Path(directory) / "scope.json", payload)
                with self.assertRaisesRegex(ScopeManifestError, message):
                    load_validation_scope_manifest(path)

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scope.json"
            path.write_text(
                json.dumps(manifest_payload())[:-1] + ', "schema_version": 1}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ScopeManifestError, "duplicate JSON key"):
                load_validation_scope_manifest(path)

    def test_ranges_globs_and_unknown_supersedes_milestones_are_rejected(self):
        cases = (
            (manifest_payload(accepted=("M0-M99",)), "container ID"),
            (manifest_payload(accepted=("M*",)), "container ID"),
            (
                {
                    **manifest_payload(),
                    "accepted_legacy_containers": [
                        {
                            "id": "M1",
                            "path": "docs/M1",
                            "contract_version": 1,
                            "supersedes": [
                                "docs/M2/MILESTONE_CLOSEOUT.md"
                            ],
                        }
                    ],
                },
                "outside docs/M1",
            ),
            (
                manifest_payload(accepted=("M34-1", "M34_1")),
                "alias",
            ),
        )
        for payload, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = write_manifest(root, payload)
                if "outside" in message:
                    manifest = load_validation_scope_manifest(path)
                    scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                        root / "docs/M1"
                    )
                    self.assertIn(message, scope.detail)
                else:
                    with self.assertRaisesRegex(ScopeManifestError, message):
                        load_validation_scope_manifest(path)


class ScopeManifestResolverTests(unittest.TestCase):
    def test_external_manifest_cannot_authorize_supersedes_symlink_escape(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_name:
            root = Path(directory)
            external_manifest = Path(outside_name) / "scope.json"
            closeout = root / "docs/M1/MILESTONE_CLOSEOUT.md"
            closeout.parent.mkdir(parents=True)
            outside_closeout = Path(outside_name) / "MILESTONE_CLOSEOUT.md"
            outside_closeout.write_text("- Status: `BLOCKED`\n", encoding="utf-8")
            try:
                closeout.symlink_to(outside_closeout)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            manifest = load_validation_scope_manifest(
                write_json(
                    external_manifest,
                    manifest_payload(
                        supersedes={"M1": ["docs/M1/MILESTONE_CLOSEOUT.md"]}
                    ),
                )
            )

            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M1"
            )

        self.assertEqual(MilestoneScopeKind.AMBIGUOUS, scope.kind)
        self.assertIn("symlink", scope.detail)

    def test_manifest_acceptance_handles_missing_ambiguous_and_accepted_closeouts(self):
        closeouts = (
            ("missing", None),
            ("ambiguous", None),
            ("accepted", "ACCEPTED"),
        )
        for label, status in closeouts:
            with self.subTest(closeout=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = load_validation_scope_manifest(write_manifest(root))
                if label == "ambiguous":
                    write_closeout(root, "M1", prose="Acceptance is discussed in prose.")
                elif label == "accepted":
                    write_closeout(root, "M1", status)

                scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                    root / "docs/M1"
                )

                self.assertEqual(
                    MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY, scope.kind
                )
                self.assertIn("manifest", " ".join(scope.authorities).lower())

    def test_nonaccepted_closeout_requires_exact_supersedes_path(self):
        cases = (
            (None, MilestoneScopeKind.AMBIGUOUS),
            (
                {"M1": ["docs/M2/MILESTONE_CLOSEOUT.md"]},
                MilestoneScopeKind.AMBIGUOUS,
            ),
            (
                {"M1": ["docs/M1/MILESTONE_CLOSEOUT.md"]},
                MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY,
            ),
        )
        for supersedes, expected in cases:
            with self.subTest(supersedes=supersedes), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = load_validation_scope_manifest(
                    write_manifest(
                        root,
                        manifest_payload(supersedes=supersedes)
                        if supersedes is not None
                        else manifest_payload(),
                    )
                )
                write_closeout(root, "M1", "BLOCKED")

                scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                    root / "docs/M1"
                )

                self.assertEqual(expected, scope.kind)

    def test_manifest_acceptance_conflicts_with_structured_active_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(write_manifest(root))
            write_active_context(root, ("M1",))

            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M1"
            )

        self.assertEqual(MilestoneScopeKind.AMBIGUOUS, scope.kind)
        self.assertIn("conflict", scope.detail)

    def test_manifest_acceptance_overrides_incomplete_active_set_placeholder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(write_manifest(root))
            active_context = root / "docs/ACTIVE_CONTEXT.md"
            active_context.parent.mkdir(parents=True, exist_ok=True)
            active_context.write_text(
                "# Active Context\n\n"
                "- Current milestone: `<milestone ID or none>`\n",
                encoding="utf-8",
            )

            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M1"
            )

        self.assertEqual(
            MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY, scope.kind
        )

    def test_manifest_does_not_hide_active_id_inside_conflicting_structured_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(write_manifest(root))
            active_context = root / "docs/ACTIVE_CONTEXT.md"
            active_context.parent.mkdir(parents=True, exist_ok=True)
            active_context.write_text(
                "# Active Context\n\n"
                "- Current milestone: `M1`\n"
                "- Active milestone: `M2`\n",
                encoding="utf-8",
            )

            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M1"
            )

        self.assertEqual(MilestoneScopeKind.AMBIGUOUS, scope.kind)
        self.assertIn("conflict", scope.detail)

    def test_manifest_active_conflicts_with_accepted_closeout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(
                write_manifest(root, manifest_payload(active=("M1",), accepted=()))
            )
            write_closeout(root, "M1", "ACCEPTED")

            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M1"
            )

        self.assertEqual(MilestoneScopeKind.AMBIGUOUS, scope.kind)

    def test_unlisted_milestone_never_becomes_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(write_manifest(root))
            write_active_context(root, ())
            write_closeout(root, "M2", "ACCEPTED")

            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M2"
            )

        self.assertNotEqual(MilestoneScopeKind.IMMUTABLE_ACCEPTED_HISTORY, scope.kind)
        self.assertIn("not listed", scope.detail)

    def test_supersedes_must_identify_an_existing_nonaccepted_closeout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(
                write_manifest(
                    root,
                    manifest_payload(
                        supersedes={"M1": ["docs/M1/MILESTONE_CLOSEOUT.md"]}
                    ),
                )
            )

            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M1"
            )

        self.assertEqual(MilestoneScopeKind.AMBIGUOUS, scope.kind)
        self.assertIn("does not identify", scope.detail)

    def test_one_inaccurate_supersedes_blocks_legacy_for_every_manifest_milestone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(
                write_manifest(
                    root,
                    manifest_payload(
                        accepted=("M1", "M3"),
                        supersedes={"M1": ["docs/M2/MILESTONE_CLOSEOUT.md"]},
                    ),
                )
            )

            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M3"
            )

        self.assertEqual(MilestoneScopeKind.AMBIGUOUS, scope.kind)
        self.assertIn("every container", scope.detail)


class ScopeManifestContractTests(unittest.TestCase):
    def test_terminal_verified_and_closed_pairs_select_frozen_v1(self):
        for status in ("VERIFIED", "CLOSED"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = load_validation_scope_manifest(write_manifest(root))
                scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                    root / "docs/M1"
                )
                task, evidence = record_pair(status=status)

                selection = select_validation_contract(
                    task, evidence, container_scope=scope
                )

                self.assertEqual(1, selection.version)
                self.assertTrue(selection.implicit_legacy)
                self.assertTrue(any("baseline_head" in item for item in selection.authority_basis))

    def test_nonterminal_pair_cannot_use_manifest_to_select_v1(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(write_manifest(root))
            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M1"
            )
            task, evidence = record_pair(status="IN_PROGRESS")

            result = validate_compatible_records(task, evidence, container_scope=scope)

        self.assertIsNone(result.selection)
        self.assertTrue(result.active_reconciliation)

    def test_manifest_active_unversioned_terminal_pair_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(
                write_manifest(root, manifest_payload(active=("M1",), accepted=()))
            )
            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M1"
            )
            task, evidence = record_pair()

            result = validate_compatible_records(task, evidence, container_scope=scope)

        self.assertIsNone(result.selection)
        self.assertTrue(result.active_reconciliation)

    def test_explicit_v2_is_selected_and_never_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(write_manifest(root))
            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M1"
            )
            task, evidence = record_pair()
            from sagekit.validation_contracts.v2 import contract_metadata

            task["validation_contract"] = contract_metadata()
            evidence["validation_contract"] = contract_metadata()
            evidence["task_id"] = "TASK-WRONG"

            result = validate_compatible_records(task, evidence, container_scope=scope)

        self.assertEqual(2, result.selection.version)
        self.assertTrue(result.errors)
        self.assertTrue(result.active_reconciliation)

    def test_explicit_v1_still_requires_terminal_manifest_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(write_manifest(root))
            scope = RepositoryScopeResolver(root, manifest=manifest).resolve(
                root / "docs/M1"
            )
            task, evidence = record_pair(status="IN_PROGRESS", explicit_version=1)

            result = validate_compatible_records(task, evidence, container_scope=scope)

        self.assertIsNone(result.selection)
        self.assertTrue(any("terminal" in error for error in result.errors))

    def test_accepted_legacy_is_excluded_from_active_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(write_manifest(root))
            task, evidence = record_pair()
            for name in ("one", "two"):
                task_copy = json.loads(json.dumps(task))
                evidence_copy = json.loads(json.dumps(evidence))
                task_copy["resources"]["locks"] = [
                    {
                        "resource": "src/shared",
                        "owner": "worker",
                        "mode": "EXCLUSIVE",
                        "status": "ACTIVE",
                        "carried": False,
                    }
                ]
                write_dispatch_pair(root, "M1", task_copy, evidence_copy, name=name)

            findings = check_task_dispatch(root, scope_manifest=manifest)

        rules = {finding.rule for finding in findings}
        self.assertNotIn("task-dispatch-duplicate-id", rules)
        self.assertNotIn("task-dispatch-lock-conflict", rules)
        self.assertNotIn("task-dispatch-board", rules)


class ScopeManifestPhaseAndRuntimeTests(unittest.TestCase):
    def test_nested_manifest_history_is_audited_without_current_phase_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = manifest_payload(active=("M2",), accepted=("M1",))
            payload["accepted_legacy_containers"][0]["path"] = "docs/M2/history/M1"
            load_validation_scope_manifest(write_manifest(root, payload))
            phase = root / "docs/M2/history/M1/01-old.md"
            phase.write_text("# Historical phase\n", encoding="utf-8")

            findings = run_check(root, scope="history")

        history_findings = [
            finding
            for finding in findings
            if finding.path and finding.path.startswith("docs/M2/history/M1")
        ]
        self.assertTrue(
            any(
                finding.rule == "phase-scope-compatibility"
                and finding.level == "PASS"
                for finding in history_findings
            ),
            history_findings,
        )
        self.assertFalse(
            [finding for finding in history_findings if finding.level == "FAIL"],
            history_findings,
        )

    def test_duplicate_or_conflicting_active_milestone_fields_fail_closed(self):
        cases = {
            "duplicate": "- Current milestone: `M1`\n- Current milestone: `M1`\n",
            "conflict": "- Current milestone: `M1`\n- Current milestone: `M2`\n",
        }
        for label, text in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                context = root / "docs/ACTIVE_CONTEXT.md"
                context.parent.mkdir(parents=True)
                context.write_text(text, encoding="utf-8")

                _milestones, _authorities, error, available = read_active_milestones(
                    root, context
                )

            self.assertTrue(available)
            self.assertIsNotNone(error)
            self.assertIn(label, error)

    def test_manifest_history_skips_current_phase_format_with_one_audit_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(write_manifest(root))
            milestone = root / "docs/M1"
            milestone.mkdir(parents=True, exist_ok=True)
            for name in ("01-old.md", "02-old.md"):
                (milestone / name).write_text("# Historical phase\n", encoding="utf-8")

            findings = check_phase_docs(root, scope_manifest=manifest)

        self.assertEqual(
            1,
            sum(finding.rule == "phase-scope-compatibility" for finding in findings),
        )
        self.assertFalse(
            [finding for finding in findings if finding.level == "FAIL"], findings
        )

    def test_manifest_active_phase_remains_strict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(
                write_manifest(root, manifest_payload(active=("M2",), accepted=()))
            )
            phase = root / "docs/M2/01-current.md"
            phase.parent.mkdir(parents=True, exist_ok=True)
            phase.write_text("# Current phase\n", encoding="utf-8")

            findings = check_phase_docs(root, scope_manifest=manifest)

        self.assertTrue(any(finding.level == "FAIL" for finding in findings))

    def test_multiple_phases_resolve_manifest_scope_once(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = load_validation_scope_manifest(write_manifest(root))
            milestone = root / "docs/M1"
            milestone.mkdir(parents=True, exist_ok=True)
            for name in ("01-old.md", "02-old.md"):
                (milestone / name).write_text("# Historical phase\n", encoding="utf-8")
            original = RepositoryScopeResolver.resolve
            calls = []

            def tracked_resolve(resolver, milestone_dir):
                calls.append(milestone_dir.name)
                return original(resolver, milestone_dir)

            with patch.object(RepositoryScopeResolver, "resolve", tracked_resolve):
                check_phase_docs(root, scope_manifest=manifest)

        self.assertEqual(["M1"], calls)

    def test_run_check_reports_local_manifest_source_digest_and_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root)

            findings = run_check(root)

        authority = [
            item for item in findings if item.rule == "validation-scope-manifest"
        ]
        self.assertEqual(1, len(authority))
        self.assertEqual("PASS", authority[0].level)
        self.assertIn("project-local", authority[0].message)
        self.assertIn(BASELINE_HEAD, authority[0].message)

    def test_invalid_local_manifest_is_a_blocking_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / LOCAL_SCOPE_MANIFEST
            path.parent.mkdir(parents=True)
            path.write_text("{broken", encoding="utf-8")

            findings = run_check(root)

        self.assertTrue(
            any(
                item.level == "FAIL" and item.rule == "validation-scope-manifest"
                for item in findings
            )
        )

    def test_explicit_nonfile_manifest_fails_closed_for_active_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid_manifest = root / "scope-directory"
            invalid_manifest.mkdir()

            findings = run_check(
                root,
                scope="active",
                scope_manifest_path=invalid_manifest,
            )

        failures = [item for item in findings if item.level == "FAIL"]
        self.assertEqual(["validation-scope-manifest"], [item.rule for item in failures])
        self.assertIn("must be a file", failures[0].message)

    def test_cli_manifest_replaces_invalid_project_local_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            target = workspace / "project"
            runner = workspace / "runner"
            target.mkdir()
            runner.mkdir()
            local = target / LOCAL_SCOPE_MANIFEST
            local.parent.mkdir(parents=True)
            (target / "docs/M1").mkdir(parents=True)
            local.write_text("{broken", encoding="utf-8")
            external = write_json(runner / "scope.json", manifest_payload())

            findings = run_check(target, scope_manifest_path=external)

        authority = [
            item for item in findings if item.rule == "validation-scope-manifest"
        ]
        self.assertEqual(1, len(authority))
        self.assertEqual("PASS", authority[0].level)
        self.assertIn("explicit-harness", authority[0].message)

class ScopeManifestPackagingTests(unittest.TestCase):
    def test_source_template_and_packaged_mirror_are_equal(self):
        source = REPO_ROOT / "docs/templates/SAGE_VALIDATION_SCOPE_TEMPLATE.json"
        packaged = (
            REPO_ROOT
            / "sagekit/resources/docs/templates/SAGE_VALIDATION_SCOPE_TEMPLATE.json"
        )
        self.assertTrue(source.is_file())
        self.assertEqual(source.read_bytes(), packaged.read_bytes())

    def test_template_is_not_valid_authority_until_placeholders_are_completed(self):
        source = REPO_ROOT / "docs/templates/SAGE_VALIDATION_SCOPE_TEMPLATE.json"

        with self.assertRaises(ScopeManifestError):
            load_validation_scope_manifest(source)

    def test_init_does_not_create_scope_manifest(self):
        from sagekit.init import init_files_for_mode, package_resource_root

        for mode in ("light", "standard", "heavy"):
            destinations = {
                item.destination
                for item in init_files_for_mode(
                    mode, package_resource_root(), profile="vendored-legacy"
                )
            }
            self.assertNotIn(LOCAL_SCOPE_MANIFEST, destinations)


if __name__ == "__main__":
    unittest.main()
