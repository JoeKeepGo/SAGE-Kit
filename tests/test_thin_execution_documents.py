import hashlib
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sagekit.execution_documents import (
    ExecutionDocumentError,
    _reject_reparse_components,
    compare_milestone_ids,
    load_execution_project,
    load_execution_contract,
)
from sagekit.policy_resolution import PolicyResolutionError, resolve_policy


CONTRACT_VERSION = "2026.7.19.3"


def canonical_digest(payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def canonical_file_digest(path):
    return canonical_digest(json.loads(path.read_text(encoding="utf-8")))


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def create_contract(base):
    root = base / CONTRACT_VERSION
    contract = {
        "schema_version": 1,
        "contract_id": CONTRACT_VERSION,
        "execution_document_model": "thin-v1",
        "project_schema": "project.schema.json",
        "milestone_schema": "milestone.schema.json",
        "phase_schema": "phase.schema.json",
        "runtime_defaults": {
            "approval_required_for_write": True,
            "verification_economy": "focused-first",
        },
        "overrideable_policy_keys": ["verification_economy"],
        "profiles": {
            "standard-milestone@v1": "profiles/standard-milestone-v1.json",
            "standard-phase@v1": "profiles/standard-phase-v1.json",
        },
    }
    write_json(root / "contract.json", contract)
    for name in ("project.schema.json", "milestone.schema.json", "phase.schema.json"):
        write_json(root / name, {"type": "object"})
    write_json(
        root / "profiles/standard-milestone-v1.json",
        {
            "schema_version": 1,
            "id": "standard-milestone@v1",
            "generic_rules": ["Keep milestone authority explicit."],
            "policy": {
                "verification_economy": "focused-first",
                "approval_required_for_write": True,
            },
        },
    )
    write_json(
        root / "profiles/standard-phase-v1.json",
        {
            "schema_version": 1,
            "id": "standard-phase@v1",
            "generic_rules": ["Stop when authority is missing."],
            "policy": {
                "verification_economy": "focused-first",
                "approval_required_for_write": True,
            },
        },
    )
    return base


def project_payload():
    return {
        "schema_version": 1,
        "sagekit_contract": CONTRACT_VERSION,
        "execution_document_model": "thin-v1",
        "effective_from": "M36",
        "legacy_documents": "immutable",
        "profiles": ["standard-milestone@v1", "standard-phase@v1"],
        "overrides": {
            "standard-phase@v1": {"verification_economy": "targeted"}
        },
    }


def milestone_payload():
    return {
        "schema_version": 1,
        "sagekit_contract": CONTRACT_VERSION,
        "document_model": "thin-v1",
        "milestone_id": "M36",
        "objective": "Adopt thin execution documents.",
        "capability_outcome": "Compile deterministic execution packets.",
        "authority_references": ["docs/APPROVAL_GATES.md"],
        "governance_profile": "standard-milestone@v1",
        "dependency_dag": {"P1": [], "P2": ["P1"]},
        "approval_gates": [
            {
                "id": "GATE-P2-WRITE",
                "applies_to": ["P2"],
                "status": "approved",
                "permission_mode": "WRITE_AUTHORIZED",
                "authority_reference": "docs/APPROVAL_GATES.md#write",
            }
        ],
        "phase_ids": ["P1", "P2"],
        "acceptance_criteria": ["Both phase manifests validate."],
        "invariants": ["Historical documents remain immutable."],
        "state": "active",
        "evidence_references": ["docs/evidence/M36.md"],
    }


def phase_payload(phase_id, depends_on, permission_mode="READ_ONLY_REVIEW"):
    return {
        "schema_version": 1,
        "sagekit_contract": CONTRACT_VERSION,
        "document_model": "thin-v1",
        "phase_id": phase_id,
        "objective": f"Execute {phase_id}.",
        "depends_on": list(depends_on),
        "execution_profile": "standard-phase@v1",
        "permission_mode": permission_mode,
        "owner": "Root Controller",
        "writable_paths": [] if permission_mode == "READ_ONLY_REVIEW" else ["src/widget.py"],
        "read_only_references": ["README.md"],
        "forbidden_paths": ["secrets"],
        "inherit_forbidden": False,
        "acceptance_criteria": [f"{phase_id} checks pass."],
        "verification_commands": ["python -B -m unittest"],
        "evidence_requirements": ["Record command and exit code."],
        "stop_conditions": ["Stop on missing authority."],
        "handoff_target": "Root Controller",
        "state": "ready",
    }


def create_project(root, contract_root):
    create_contract(contract_root)
    write_json(root / "SAGE_PROJECT.json", project_payload())
    write_json(root / "docs/M36/MILESTONE_MANIFEST.json", milestone_payload())
    first_phase = phase_payload("P1", [])
    first_phase["state"] = "complete"
    write_json(root / "docs/M36/phases/P1.json", first_phase)
    write_json(
        root / "docs/M36/phases/P2.json",
        phase_payload("P2", ["P1"], "WRITE_AUTHORIZED"),
    )
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs/APPROVAL_GATES.md").write_text("# Gates\n", encoding="utf-8")
    (root / "docs/evidence").mkdir(parents=True, exist_ok=True)
    (root / "docs/evidence/M36.md").write_text("# Evidence\n", encoding="utf-8")
    (root / "README.md").write_text("# Project\n", encoding="utf-8")


class ThinExecutionDocumentTests(unittest.TestCase):
    def test_v19_contract_resources_match_base_commit_bytes(self):
        repository = Path(__file__).resolve().parents[1]
        roots = (
            "docs/contracts/execution-documents",
            "sagekit/resources/docs/contracts/execution-documents",
            "sagekit/resources/execution_documents",
        )
        for root in roots:
            frozen_root = repository / root / "2026.7.19.3"
            for path in sorted(frozen_root.rglob("*.json")):
                relative = path.relative_to(repository).as_posix()
                with self.subTest(relative=relative):
                    expected = subprocess.run(
                        ["git", "show", f"6669ba279169dfc2ccf3cc202788ae709f98b772:{relative}"],
                        cwd=repository,
                        check=True,
                        stdout=subprocess.PIPE,
                    ).stdout
                    self.assertEqual(expected, path.read_bytes())

    def test_v20_uses_urn_ids_and_has_a_distinct_contract_digest(self):
        repository = Path(__file__).resolve().parents[1]
        contracts = repository / "sagekit/resources/execution_documents"
        v19_lock = SimpleNamespace(
            sagekit_contract="2026.7.19.3",
            execution_document_model="thin-v1",
            profiles=("standard-milestone@v1", "standard-phase@v1"),
            resource_contract=None,
        )
        v20_lock = SimpleNamespace(
            sagekit_contract="2026.7.20.1",
            execution_document_model="thin-v1",
            profiles=("standard-milestone@v1", "standard-phase@v1"),
            resource_contract="conservative-host-v1",
        )
        v19 = load_execution_contract(v19_lock, contract_root=contracts)
        v20 = load_execution_contract(v20_lock, contract_root=contracts)
        self.assertNotEqual(v19.digest, v20.digest)
        for name in ("milestone", "phase", "project"):
            payload = json.loads(
                (contracts / "2026.7.20.1" / f"{name}.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                f"urn:sage-kit:execution-documents:2026.7.20.1:{name}",
                payload["$id"],
            )

    def test_project_lock_selects_exact_version_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            self.assertEqual(
                "2026.7.19.3",
                load_execution_project(root, contract_root=contracts).contract.contract_id,
            )
            lock = project_payload()
            lock["sagekit_contract"] = "2026.7.20.1"
            lock["resource_contract"] = "conservative-host-v1"
            write_json(root / "SAGE_PROJECT.json", lock)
            for path in (root / "docs/M36").rglob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["sagekit_contract"] = "2026.7.20.1"
                if path.parent.name == "phases":
                    payload["resource_profile"] = "conservative-host-v1"
                    payload["resource_overrides"] = {}
                write_json(path, payload)
            package_contracts = repository = (
                Path(__file__).resolve().parents[1]
                / "sagekit/resources/execution_documents"
            )
            self.assertEqual(
                "2026.7.20.1",
                load_execution_project(root, contract_root=package_contracts).contract.contract_id,
            )
            lock["sagekit_contract"] = "2026.7.20.999"
            write_json(root / "SAGE_PROJECT.json", lock)
            with self.assertRaises(ExecutionDocumentError):
                load_execution_project(root, contract_root=package_contracts)

    def test_resource_aware_contract_pins_profile_without_copying_policy_body(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            for relative in (
                "SAGE_PROJECT.json",
                "docs/M36/MILESTONE_MANIFEST.json",
                "docs/M36/phases/P1.json",
                "docs/M36/phases/P2.json",
            ):
                path = root / relative
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["sagekit_contract"] = "2026.7.20.1"
                if relative == "SAGE_PROJECT.json":
                    payload["resource_contract"] = "conservative-host-v1"
                elif "/phases/" in relative:
                    payload["resource_profile"] = "conservative-host-v1"
                    payload["resource_overrides"] = (
                        {"runtime_exclusive": ["database:test-state", "port:4173"]}
                        if relative.endswith("P2.json")
                        else {}
                    )
                path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            package_contracts = (
                Path(__file__).resolve().parents[1]
                / "sagekit/resources/execution_documents"
            )
            project = load_execution_project(
                root, "M36", contract_root=package_contracts
            )

        self.assertEqual("conservative-host-v1", project.project_lock.resource_contract)
        self.assertEqual("conservative-host-v1", project.phases["P2"].resource_profile)
        self.assertEqual(
            {"runtime_exclusive": ["database:test-state", "port:4173"]},
            project.phases["P2"].resource_overrides,
        )

    def test_resource_aware_contract_accepts_neutral_profile_with_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            for relative in (
                "SAGE_PROJECT.json",
                "docs/M36/MILESTONE_MANIFEST.json",
                "docs/M36/phases/P1.json",
                "docs/M36/phases/P2.json",
            ):
                path = root / relative
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["sagekit_contract"] = "2026.7.20.1"
                if relative == "SAGE_PROJECT.json":
                    payload["resource_contract"] = "conservative-host-v1"
                elif "/phases/" in relative:
                    payload["resource_profile"] = "conservative-host-v1"
                    payload["resource_overrides"] = {}
                    payload.pop("resource_profile_reason", None)
                if relative == "docs/M36/phases/P2.json":
                    payload["resource_profile"] = "N/A"
                    payload["resource_profile_reason"] = "planning-only phase"
                path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            package_contracts = (
                Path(__file__).resolve().parents[1]
                / "sagekit/resources/execution_documents"
            )
            project = load_execution_project(root, "M36", contract_root=package_contracts)

        self.assertIsNone(project.phases["P2"].resource_profile)
        self.assertEqual("planning-only phase", project.phases["P2"].resource_profile_reason)

    def test_resource_aware_contract_rejects_neutral_profile_without_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            for relative in (
                "SAGE_PROJECT.json",
                "docs/M36/MILESTONE_MANIFEST.json",
                "docs/M36/phases/P1.json",
                "docs/M36/phases/P2.json",
            ):
                path = root / relative
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["sagekit_contract"] = "2026.7.20.1"
                if relative == "SAGE_PROJECT.json":
                    payload["resource_contract"] = "conservative-host-v1"
                elif "/phases/" in relative:
                    payload["resource_profile"] = "conservative-host-v1"
                    payload["resource_overrides"] = {}
                    payload.pop("resource_profile_reason", None)
                if relative == "docs/M36/phases/P2.json":
                    payload["resource_profile"] = "N/A"
                path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            package_contracts = (
                Path(__file__).resolve().parents[1]
                / "sagekit/resources/execution_documents"
            )
            with self.assertRaisesRegex(ExecutionDocumentError, "resource_profile_reason"):
                load_execution_project(root, "M36", contract_root=package_contracts)

    def test_resource_aware_contract_rejects_missing_or_unknown_resource_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            lock_path = root / "SAGE_PROJECT.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["sagekit_contract"] = "2026.7.20.1"
            lock["resource_contract"] = "unknown-resource-v1"
            lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
            package_contracts = (
                Path(__file__).resolve().parents[1]
                / "sagekit/resources/execution_documents"
            )
            with self.assertRaisesRegex(ExecutionDocumentError, "resource contract"):
                load_execution_project(root, "M36", contract_root=package_contracts)

    def test_direct_load_rejects_pre_anchor_and_ambiguous_ordering(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            lock = project_payload()
            lock["effective_from"] = "M37"
            write_json(root / "SAGE_PROJECT.json", lock)
            with self.assertRaisesRegex(ExecutionDocumentError, "precedes effective_from"):
                load_execution_project(root, "M36", contract_root=contracts)

        with self.assertRaisesRegex(ExecutionDocumentError, "ordering is ambiguous"):
            compare_milestone_ids("M36.alpha", "M36.beta")

    def test_valid_project_loads_with_stable_digests_and_resolved_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)

            first = load_execution_project(root, contract_root=contracts)
            second = load_execution_project(root, contract_root=contracts)
            resolved = resolve_policy(first, first.milestone, first.phases["P2"])
            expected_lock = canonical_file_digest(root / "SAGE_PROJECT.json")
            expected_milestone = canonical_file_digest(
                root / "docs/M36/MILESTONE_MANIFEST.json"
            )
            expected_phase = canonical_file_digest(root / "docs/M36/phases/P2.json")
            contract_directory = contracts / CONTRACT_VERSION
            resource_names = (
                "contract.json",
                "project.schema.json",
                "milestone.schema.json",
                "phase.schema.json",
                "profiles/standard-milestone-v1.json",
                "profiles/standard-phase-v1.json",
            )
            expected_resources = {
                name: canonical_file_digest(contract_directory / name)
                for name in resource_names
            }
            expected_contract = canonical_digest(expected_resources)
            expected_resolved = canonical_digest(
                {
                    "profile_id": resolved.profile_id,
                    "profile_digest": resolved.profile_digest,
                    "values": dict(resolved.values),
                    "sources": dict(resolved.sources),
                }
            )

        self.assertEqual(first.project_lock.digest, second.project_lock.digest)
        self.assertEqual(first.milestone.digest, second.milestone.digest)
        self.assertEqual(expected_lock, first.project_lock.digest)
        self.assertEqual(expected_milestone, first.milestone.digest)
        self.assertEqual(expected_phase, first.phases["P2"].digest)
        self.assertEqual(expected_contract, first.contract.digest)
        self.assertEqual(expected_resolved, resolved.digest)
        self.assertEqual("WRITE_AUTHORIZED", resolved.values["permission_mode"])
        self.assertEqual("approved-gate:GATE-P2-WRITE", resolved.sources["permission_mode"])
        self.assertEqual("targeted", resolved.values["verification_economy"])
        self.assertEqual(
            "project-override:standard-phase@v1",
            resolved.sources["verification_economy"],
        )

    def test_duplicate_json_key_and_missing_contract_resource_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            lock = root / "SAGE_PROJECT.json"
            lock.write_text(
                json.dumps(project_payload())[:-1] + ', "schema_version": 1}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ExecutionDocumentError, "duplicate JSON key"):
                load_execution_project(root, contract_root=contracts)

            write_json(lock, project_payload())
            (contracts / CONTRACT_VERSION / "phase.schema.json").unlink()
            with self.assertRaisesRegex(ExecutionDocumentError, "phase.schema.json"):
                load_execution_project(root, contract_root=contracts)

    def test_contract_digest_binds_schema_and_profile_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            first = load_execution_project(root, contract_root=contracts)
            schema = contracts / CONTRACT_VERSION / "phase.schema.json"
            write_json(schema, {"type": "object", "additionalProperties": False})
            second = load_execution_project(root, contract_root=contracts)

            self.assertNotEqual(first.contract.digest, second.contract.digest)

    def test_dag_missing_cycle_duplicate_and_manifest_dependency_mismatch_fail(self):
        mutations = (
            (lambda data: data["dependency_dag"].__setitem__("P2", ["P9"]), "missing dependency"),
            (lambda data: data["dependency_dag"]["P1"].append("P2"), "cycle"),
            (lambda data: data["phase_ids"].append("P1"), "duplicate phase ID"),
            (lambda data: data["dependency_dag"].__setitem__("P2", []), "does not match"),
        )
        for mutate, message in mutations:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                root = workspace / "project"
                contracts = workspace / "contracts"
                create_project(root, contracts)
                payload = milestone_payload()
                mutate(payload)
                write_json(root / "docs/M36/MILESTONE_MANIFEST.json", payload)
                with self.assertRaisesRegex(ExecutionDocumentError, message):
                    load_execution_project(root, contract_root=contracts)

    def test_undeclared_phase_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            write_json(root / "docs/M36/phases/P9.json", phase_payload("P9", []))

            with self.assertRaisesRegex(ExecutionDocumentError, "undeclared phase manifest"):
                load_execution_project(root, contract_root=contracts)

    def test_path_overlap_parent_absolute_and_symlink_escape_fail(self):
        cases = (
            (["../outside"], ["secrets"], "normalized project-relative"),
            (["C:/outside"], ["secrets"], "normalized project-relative"),
            (["src"], ["src/private"], "overlap"),
        )
        for writable, forbidden, message in cases:
            with self.subTest(writable=writable), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                root = workspace / "project"
                contracts = workspace / "contracts"
                create_project(root, contracts)
                payload = phase_payload("P2", ["P1"], "WRITE_AUTHORIZED")
                payload["writable_paths"] = writable
                payload["forbidden_paths"] = forbidden
                write_json(root / "docs/M36/phases/P2.json", payload)
                with self.assertRaisesRegex(ExecutionDocumentError, message):
                    load_execution_project(root, contract_root=contracts)

        if hasattr(os, "symlink"):
            with tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                root = workspace / "project"
                outside = workspace / "outside"
                contracts = workspace / "contracts"
                create_project(root, contracts)
                outside.mkdir()
                try:
                    (root / "escape").symlink_to(outside, target_is_directory=True)
                except OSError:
                    self.skipTest("symlink creation is unavailable on this platform")
                payload = phase_payload("P2", ["P1"], "WRITE_AUTHORIZED")
                payload["writable_paths"] = ["escape/new.py"]
                write_json(root / "docs/M36/phases/P2.json", payload)
                with self.assertRaisesRegex(ExecutionDocumentError, "symlink or reparse"):
                    load_execution_project(root, contract_root=contracts)

        if hasattr(os, "symlink"):
            with tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                root = workspace / "project"
                contracts = workspace / "contracts"
                create_project(root, contracts)
                (root / "src/private").mkdir(parents=True)
                try:
                    (root / "alias").symlink_to(root / "src/private", target_is_directory=True)
                except OSError:
                    self.skipTest("symlink creation is unavailable on this platform")
                payload = phase_payload("P2", ["P1"], "WRITE_AUTHORIZED")
                payload["writable_paths"] = ["alias/new.py"]
                payload["forbidden_paths"] = ["src/private"]
                write_json(root / "docs/M36/phases/P2.json", payload)
                with self.assertRaisesRegex(ExecutionDocumentError, "symlink or reparse"):
                    load_execution_project(root, contract_root=contracts)

    def test_reparse_component_rejection_is_hermetic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            alias = root / "alias"
            alias.mkdir()
            metadata = SimpleNamespace(
                st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            )
            with patch.object(Path, "is_symlink", return_value=False), patch.object(
                Path, "lstat", return_value=metadata
            ):
                with self.assertRaisesRegex(ExecutionDocumentError, "reparse component"):
                    _reject_reparse_components(root, alias / "new.py", "test path")

    def test_unknown_override_and_rejected_write_gate_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            lock = project_payload()
            lock["overrides"]["standard-phase@v1"]["unknown"] = True
            write_json(root / "SAGE_PROJECT.json", lock)
            with self.assertRaisesRegex(PolicyResolutionError, "unknown override"):
                load_execution_project(root, contract_root=contracts)

        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            milestone = milestone_payload()
            milestone["approval_gates"][0]["status"] = "rejected"
            write_json(root / "docs/M36/MILESTONE_MANIFEST.json", milestone)
            with self.assertRaisesRegex(PolicyResolutionError, "rejected gate"):
                load_execution_project(root, contract_root=contracts)

    def test_runtime_enforces_schema_profile_roles_and_nonempty_authority(self):
        mutations = (
            ("authority", lambda data: data.__setitem__("authority_references", []), "non-empty"),
            (
                "milestone-profile",
                lambda data: data.__setitem__("governance_profile", "standard-phase@v1"),
                "standard-milestone@v1",
            ),
        )
        for name, mutate, message in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                root = workspace / "project"
                contracts = workspace / "contracts"
                create_project(root, contracts)
                payload = milestone_payload()
                mutate(payload)
                write_json(root / "docs/M36/MILESTONE_MANIFEST.json", payload)
                with self.assertRaisesRegex(ExecutionDocumentError, message):
                    load_execution_project(root, contract_root=contracts)

        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            contracts = workspace / "contracts"
            create_project(root, contracts)
            payload = phase_payload("P2", ["P1"], "WRITE_AUTHORIZED")
            payload["execution_profile"] = "standard-milestone@v1"
            write_json(root / "docs/M36/phases/P2.json", payload)
            with self.assertRaisesRegex(ExecutionDocumentError, "standard-phase@v1"):
                load_execution_project(root, contract_root=contracts)


if __name__ == "__main__":
    unittest.main()
