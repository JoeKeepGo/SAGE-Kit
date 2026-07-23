from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sagekit
from sagekit.spec_sources import (
    _SemanticAttestation,
    NormalizedSpecAttestationError,
    load_normalized_spec,
    package_identity,
    verify_normalized_spec_attestation,
)
from tests.test_thin_execution_documents import (
    create_project,
    milestone_payload,
    phase_payload,
)


REPOSITORY = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = REPOSITORY / "sagekit/resources/execution_documents"
CONTRACT_VERSION = "2026.7.20.1"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def configure_project(
    root: Path,
    *,
    project_id: str = "attested-project",
    milestone_change: str = "",
    phase_change: str = "",
    gate_id: str = "GATE-P2-WRITE",
    gate_order: tuple[str, ...] | None = None,
    permission: str = "WRITE_AUTHORIZED",
    resources: tuple[str, ...] = ("repo-writer",),
) -> None:
    unused_contracts = root.parent / "unused-contracts"
    create_project(root, unused_contracts)

    project = json.loads((root / "SAGE_PROJECT.json").read_text(encoding="utf-8"))
    project["sagekit_contract"] = CONTRACT_VERSION
    project["resource_contract"] = "conservative-host-v1"
    write_json(root / "SAGE_PROJECT.json", project)

    milestone = milestone_payload()
    milestone["sagekit_contract"] = CONTRACT_VERSION
    milestone["objective"] += milestone_change
    milestone["approval_gates"][0]["id"] = gate_id
    milestone["approval_gates"][0]["permission_mode"] = permission
    if gate_order is not None:
        template = milestone["approval_gates"][0]
        milestone["approval_gates"] = [
            {**template, "id": item}
            for item in gate_order
        ]
    write_json(root / "docs/M36/MILESTONE_MANIFEST.json", milestone)

    first = phase_payload("P1", [])
    first["sagekit_contract"] = CONTRACT_VERSION
    first["objective"] += phase_change
    first["state"] = "complete"
    first["resource_profile"] = "conservative-host-v1"
    first["resource_overrides"] = {}
    write_json(root / "docs/M36/phases/P1.json", first)

    second = phase_payload("P2", ["P1"], permission)
    second["sagekit_contract"] = CONTRACT_VERSION
    second["resource_profile"] = "conservative-host-v1"
    second["resource_overrides"] = {"runtime_exclusive": list(resources)}
    write_json(root / "docs/M36/phases/P2.json", second)

    write_json(
        root / "SAGEKIT_CONFIG.json",
        {
            "schema_version": 1,
            "project_id": project_id,
            "adoption_profile": "package-bound",
            "execution_scope": "active-only",
            "active_context": "docs/ACTIVE_CONTEXT.md",
            "package": package_identity(),
            "profiles": [],
            "sources": {
                "M36": {"adapter": "thin-v1", "path": "docs/M36"}
            },
        },
    )


def normalized_spec(root: Path, **changes: object):
    configure_project(root, **changes)
    return load_normalized_spec(
        root,
        "M36",
        _contract_root=CONTRACT_ROOT,
    )


def replace_attestation(spec, **changes: object):
    return replace(
        spec,
        semantic_attestation=replace(spec.semantic_attestation, **changes),
    )


class NormalizedSpecAttestationProducerTests(unittest.TestCase):
    def test_producer_generates_canonical_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spec = normalized_spec(Path(directory) / "project")

        attestation = spec.semantic_attestation
        payload = json.loads(attestation.canonical_json)
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.assertEqual("sagekit-normalized-spec-semantic", attestation.schema_id)
        self.assertEqual(1, attestation.version)
        self.assertEqual(canonical, attestation.canonical_json)

    def test_attestation_digest_equals_semantic_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spec = normalized_spec(Path(directory) / "project")

        expected = hashlib.sha256(
            spec.semantic_attestation.canonical_json.encode("utf-8")
        ).hexdigest()
        self.assertEqual(expected, spec.semantic_attestation.digest)
        self.assertEqual(spec.semantic_digest, spec.semantic_attestation.digest)

    def test_source_config_authority_is_in_attested_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spec = normalized_spec(
                Path(directory) / "project",
                project_id="source-config-authority",
            )

        payload = verify_normalized_spec_attestation(spec)
        self.assertEqual(
            {
                "schema_version": 1,
                "project_id": "source-config-authority",
                "adoption_profile": "package-bound",
                "execution_scope": "active-only",
                "package": dict(sorted(package_identity().items())),
                "profiles": [],
            },
            payload["project_authority"],
        )

    def test_relocation_and_provenance_paths_do_not_enter_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            left = normalized_spec(base / "one/project")
            right = normalized_spec(base / "relocated/project")

        self.assertEqual(
            left.semantic_attestation.canonical_json,
            right.semantic_attestation.canonical_json,
        )
        self.assertEqual(left.semantic_digest, right.semantic_digest)
        canonical = left.semantic_attestation.canonical_json
        self.assertNotIn(str(base), canonical)
        self.assertNotIn(left.provenance.target_root, canonical)
        self.assertNotIn(left.provenance.canonical_path, canonical)

    def test_source_config_semantic_change_changes_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            left = normalized_spec(base / "one", project_id="authority-one")
            right = normalized_spec(base / "two", project_id="authority-two")

        self.assertNotEqual(left.semantic_digest, right.semantic_digest)

    def test_gate_order_does_not_change_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            left = normalized_spec(
                base / "one",
                gate_order=("GATE-P2-WRITE", "GATE-P2-SUBMIT"),
            )
            right = normalized_spec(
                base / "two",
                gate_order=("GATE-P2-SUBMIT", "GATE-P2-WRITE"),
            )

        self.assertEqual(left.semantic_digest, right.semantic_digest)

    def test_milestone_phase_gate_permission_and_resource_changes_change_digest(self) -> None:
        cases = (
            {"milestone_change": " changed"},
            {"phase_change": " changed"},
            {"gate_id": "GATE-P2-REPLACED"},
            {"permission": "READ_ONLY_REVIEW"},
            {"resources": ("database:test-state",)},
        )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            baseline = normalized_spec(base / "baseline")
            for index, changes in enumerate(cases):
                with self.subTest(changes=changes):
                    changed = normalized_spec(base / f"changed-{index}", **changes)
                    self.assertNotEqual(
                        baseline.semantic_digest,
                        changed.semantic_digest,
                    )


class NormalizedSpecAttestationVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.spec = normalized_spec(Path(self.temporary.name) / "project")

    def assert_rejected(self, spec, reason: str) -> None:
        with self.assertRaises(NormalizedSpecAttestationError) as caught:
            verify_normalized_spec_attestation(spec)
        self.assertEqual((reason,), caught.exception.reason_codes)
        self.assertNotIn(self.spec.semantic_attestation.canonical_json, str(caught.exception))
        self.assertNotIn(self.spec.provenance.target_root, str(caught.exception))

    def test_canonical_json_corruption_is_rejected(self) -> None:
        corrupted = replace_attestation(
            self.spec,
            canonical_json=self.spec.semantic_attestation.canonical_json.replace(
                '"milestone_id":"M36"',
                '"milestone_id":"M37"',
            ),
        )
        self.assert_rejected(corrupted, "semantic-attestation-digest-mismatch")

    def test_malformed_json_is_controlled(self) -> None:
        malformed = replace_attestation(self.spec, canonical_json='{"project":')
        self.assert_rejected(malformed, "malformed-semantic-attestation-json")

    def test_non_utf8_json_string_is_controlled(self) -> None:
        malformed = replace_attestation(
            self.spec,
            canonical_json='{"value":"\ud800"}',
        )
        self.assert_rejected(malformed, "malformed-semantic-attestation-json")

    def test_attestation_digest_mismatch_is_rejected(self) -> None:
        mismatched = replace_attestation(self.spec, digest="0" * 64)
        self.assert_rejected(mismatched, "semantic-attestation-digest-mismatch")

    def test_normalized_spec_semantic_digest_mismatch_is_rejected(self) -> None:
        mismatched = replace(self.spec, semantic_digest="0" * 64)
        self.assert_rejected(mismatched, "normalized-spec-semantic-digest-mismatch")

    def test_unknown_attestation_version_is_rejected(self) -> None:
        unknown = replace_attestation(self.spec, version=99)
        self.assert_rejected(unknown, "unknown-semantic-attestation-version")

    def test_noncanonical_whitespace_and_key_order_are_rejected(self) -> None:
        payload = json.loads(self.spec.semantic_attestation.canonical_json)
        noncanonical_values = (
            json.dumps(payload, sort_keys=True, indent=2),
            json.dumps(
                dict(reversed(tuple(payload.items()))),
                sort_keys=False,
                separators=(",", ":"),
            ),
        )
        for canonical_json in noncanonical_values:
            with self.subTest(canonical_json=canonical_json[:20]):
                forged_digest = hashlib.sha256(
                    canonical_json.encode("utf-8")
                ).hexdigest()
                noncanonical = replace(
                    self.spec,
                    semantic_digest=forged_digest,
                    semantic_attestation=_SemanticAttestation(
                        schema_id=self.spec.semantic_attestation.schema_id,
                        version=self.spec.semantic_attestation.version,
                        canonical_json=canonical_json,
                        digest=forged_digest,
                    ),
                )
                self.assert_rejected(
                    noncanonical,
                    "noncanonical-semantic-attestation-json",
                )

    def test_verifier_does_not_read_filesystem(self) -> None:
        with patch("pathlib.Path.open", side_effect=AssertionError("filesystem read")), patch(
            "pathlib.Path.read_text", side_effect=AssertionError("filesystem read")
        ), patch("builtins.open", side_effect=AssertionError("filesystem read")):
            payload = verify_normalized_spec_attestation(self.spec)

        self.assertEqual("M36", payload["milestone"]["milestone_id"])

    def test_verifier_does_not_modify_input_and_returns_independent_value(self) -> None:
        before = copy.deepcopy(self.spec)
        payload = verify_normalized_spec_attestation(self.spec)
        payload["milestone"]["milestone_id"] = "MUTATED"

        self.assertEqual(before, self.spec)
        verified_again = verify_normalized_spec_attestation(self.spec)
        self.assertEqual("M36", verified_again["milestone"]["milestone_id"])

    def test_attestation_type_and_verifier_are_not_package_root_exports(self) -> None:
        self.assertFalse(hasattr(sagekit, "SemanticAttestation"))
        self.assertFalse(hasattr(sagekit, "_SemanticAttestation"))
        self.assertFalse(hasattr(sagekit, "verify_normalized_spec_attestation"))


if __name__ == "__main__":
    unittest.main()
