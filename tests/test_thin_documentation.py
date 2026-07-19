from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_VERSION = "2026.7.19.3"
SOURCE_CONTRACT_ROOT = (
    REPO_ROOT / "docs/contracts/execution-documents" / CONTRACT_VERSION
)
RUNTIME_CONTRACT_ROOT = (
    REPO_ROOT / "sagekit/resources/execution_documents" / CONTRACT_VERSION
)
PACKAGED_DOC_CONTRACT_ROOT = (
    REPO_ROOT / "sagekit/resources/docs/contracts/execution-documents" / CONTRACT_VERSION
)

CONTRACT_FILES = (
    "contract.json",
    "project.schema.json",
    "milestone.schema.json",
    "phase.schema.json",
    "profiles/standard-milestone-v1.json",
    "profiles/standard-phase-v1.json",
)

PROJECT_KEYS = {
    "schema_version",
    "sagekit_contract",
    "execution_document_model",
    "effective_from",
    "legacy_documents",
    "profiles",
    "overrides",
}
MILESTONE_KEYS = {
    "schema_version",
    "sagekit_contract",
    "document_model",
    "milestone_id",
    "objective",
    "capability_outcome",
    "authority_references",
    "governance_profile",
    "dependency_dag",
    "approval_gates",
    "phase_ids",
    "acceptance_criteria",
    "invariants",
    "state",
    "evidence_references",
}
PHASE_KEYS = {
    "schema_version",
    "sagekit_contract",
    "document_model",
    "phase_id",
    "objective",
    "depends_on",
    "execution_profile",
    "permission_mode",
    "owner",
    "writable_paths",
    "read_only_references",
    "forbidden_paths",
    "inherit_forbidden",
    "acceptance_criteria",
    "verification_commands",
    "evidence_requirements",
    "stop_conditions",
    "handoff_target",
    "state",
}


def load_json(path: Path) -> object:
    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise AssertionError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


class ThinExecutionContractResourceTests(unittest.TestCase):
    def test_contract_sources_runtime_resources_and_packaged_docs_are_byte_identical(self):
        for relative in CONTRACT_FILES:
            with self.subTest(relative=relative):
                source = SOURCE_CONTRACT_ROOT / relative
                runtime = RUNTIME_CONTRACT_ROOT / relative
                packaged_doc = PACKAGED_DOC_CONTRACT_ROOT / relative
                self.assertTrue(source.is_file(), source)
                self.assertTrue(runtime.is_file(), runtime)
                self.assertTrue(packaged_doc.is_file(), packaged_doc)
                self.assertEqual(source.read_bytes(), runtime.read_bytes())
                self.assertEqual(source.read_bytes(), packaged_doc.read_bytes())

    def test_contract_indexes_strict_schemas_and_versioned_profiles(self):
        contract = load_json(SOURCE_CONTRACT_ROOT / "contract.json")
        self.assertEqual(
            set(contract),
            {
                "schema_version",
                "contract_id",
                "execution_document_model",
                "project_schema",
                "milestone_schema",
                "phase_schema",
                "runtime_defaults",
                "overrideable_policy_keys",
                "profiles",
            },
        )
        self.assertEqual(contract["schema_version"], 1)
        self.assertEqual(contract["contract_id"], CONTRACT_VERSION)
        self.assertEqual(contract["execution_document_model"], "thin-v1")
        self.assertEqual(
            contract["profiles"],
            {
                "standard-milestone@v1": "profiles/standard-milestone-v1.json",
                "standard-phase@v1": "profiles/standard-phase-v1.json",
            },
        )
        self.assertNotIn(
            "approval_required_for_write", contract["overrideable_policy_keys"]
        )

        expected = {
            "project.schema.json": PROJECT_KEYS,
            "milestone.schema.json": MILESTONE_KEYS,
            "phase.schema.json": PHASE_KEYS,
        }
        for filename, keys in expected.items():
            with self.subTest(schema=filename):
                schema = load_json(SOURCE_CONTRACT_ROOT / filename)
                self.assertEqual(schema["type"], "object")
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(set(schema["properties"]), keys)
                self.assertEqual(set(schema["required"]), keys)

        project_schema = load_json(SOURCE_CONTRACT_ROOT / "project.schema.json")
        overrides = project_schema["properties"]["overrides"]
        self.assertFalse(overrides["additionalProperties"])
        self.assertEqual(
            set(overrides["properties"]),
            {"standard-milestone@v1", "standard-phase@v1"},
        )
        self.assertNotIn(
            "approval_required_for_write",
            project_schema["$defs"]["policy_override"]["properties"],
        )

        milestone_schema = load_json(SOURCE_CONTRACT_ROOT / "milestone.schema.json")
        gate = milestone_schema["$defs"]["approval_gate"]
        self.assertFalse(gate["additionalProperties"])
        self.assertEqual(
            set(gate["required"]),
            {"id", "applies_to", "status", "permission_mode", "authority_reference"},
        )
        self.assertEqual(gate["properties"]["applies_to"]["type"], "array")
        self.assertEqual(
            gate["properties"]["status"]["enum"],
            ["pending", "approved", "rejected"],
        )
        self.assertEqual(
            milestone_schema["properties"]["state"]["enum"],
            ["planned", "active", "blocked", "accepted", "closed"],
        )

        phase_schema = load_json(SOURCE_CONTRACT_ROOT / "phase.schema.json")
        self.assertEqual(
            phase_schema["properties"]["state"]["enum"],
            ["planned", "ready", "active", "blocked", "complete"],
        )

    def test_profiles_hold_generic_governance_outside_project_manifests(self):
        required_policy = {
            "verification_economy",
            "worktree_policy",
            "corrective_policy",
            "review_policy",
            "completion_semantics",
            "approval_required_for_write",
        }
        for name, profile_id in (
            ("standard-milestone-v1.json", "standard-milestone@v1"),
            ("standard-phase-v1.json", "standard-phase@v1"),
        ):
            with self.subTest(profile=name):
                profile = load_json(SOURCE_CONTRACT_ROOT / "profiles" / name)
                self.assertEqual(
                    set(profile), {"schema_version", "id", "generic_rules", "policy"}
                )
                self.assertEqual(profile["schema_version"], 1)
                self.assertEqual(profile["id"], profile_id)
                self.assertGreaterEqual(len(profile["generic_rules"]), 5)
                self.assertEqual(set(profile["policy"]), required_policy)
                self.assertIs(profile["policy"]["approval_required_for_write"], True)


class ThinTemplateTests(unittest.TestCase):
    TEMPLATE_CASES = (
        ("SAGE_PROJECT_TEMPLATE.json", PROJECT_KEYS),
        ("THIN_MILESTONE_TEMPLATE.json", MILESTONE_KEYS),
        ("THIN_PHASE_TEMPLATE.json", PHASE_KEYS),
    )

    def test_templates_are_byte_identical_packaged_resources_with_exact_fields(self):
        for filename, expected_keys in self.TEMPLATE_CASES:
            with self.subTest(template=filename):
                source = REPO_ROOT / "docs/templates" / filename
                packaged = REPO_ROOT / "sagekit/resources/docs/templates" / filename
                self.assertTrue(source.is_file(), source)
                self.assertTrue(packaged.is_file(), packaged)
                self.assertEqual(source.read_bytes(), packaged.read_bytes())
                payload = load_json(source)
                self.assertEqual(set(payload), expected_keys)

    def test_thin_templates_retain_project_facts_not_generic_governance_prose(self):
        generic_prose = (
            "verification economy",
            "worktree policy",
            "generic corrective",
            "generic review",
            "completion semantics",
            "what is standard",
            "what is heavy",
        )
        for filename, _ in self.TEMPLATE_CASES:
            with self.subTest(template=filename):
                text = (REPO_ROOT / "docs/templates" / filename).read_text(
                    encoding="utf-8"
                ).casefold()
                for phrase in generic_prose:
                    self.assertNotIn(phrase, text)

        milestone = load_json(REPO_ROOT / "docs/templates/THIN_MILESTONE_TEMPLATE.json")
        phase = load_json(REPO_ROOT / "docs/templates/THIN_PHASE_TEMPLATE.json")
        self.assertEqual(milestone["governance_profile"], "standard-milestone@v1")
        self.assertEqual(milestone["approval_gates"][0]["applies_to"], ["P1"])
        self.assertEqual(phase["execution_profile"], "standard-phase@v1")
        self.assertTrue(milestone["authority_references"])
        self.assertTrue(phase["acceptance_criteria"])
        self.assertTrue(phase["verification_commands"])
        self.assertTrue(phase["stop_conditions"])


class ThinDocumentationTests(unittest.TestCase):
    def test_readmes_explain_thick_kit_thin_project_and_migration_boundary(self):
        for filename in ("README.md", "README.zh-CN.md"):
            with self.subTest(readme=filename):
                text = (REPO_ROOT / filename).read_text(encoding="utf-8")
                folded = text.casefold()
                self.assertIn("sagekit packet compile", folded)
                self.assertIn("sage_project.json", folded)
                self.assertIn("thin-v1", folded)
                self.assertIn("legacy-markdown", folded)
                self.assertIn("installed skill", folded)
                self.assertLess(len(text.splitlines()), 340)

    def test_skill_and_core_define_authority_without_requiring_expanded_project_rules(self):
        skill = (REPO_ROOT / "skills/sage-kit/SKILL.md").read_text(encoding="utf-8")
        core = (REPO_ROOT / "docs/SAGE_CORE.md").read_text(encoding="utf-8")
        combined = (skill + "\n" + core).casefold()
        for phrase in (
            "governance interpreter",
            "generic governance",
            "installed skill is not project authority",
            "standalone compiled packet",
            "legacy-markdown",
            "thin-v1",
        ):
            self.assertIn(phrase, combined)

    def test_agent_docs_and_skill_references_route_thin_documents_without_retroactive_migration(self):
        paths = (
            "docs/agent/AGENT_HARNESS.md",
            "docs/agent/MILESTONE_PLANNING.md",
            "docs/agent/PHASE_EXECUTION.md",
            "docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md",
            "docs/DOC_ROUTING_TEMPLATE.md",
            "skills/sage-kit/references/adoption.md",
            "skills/sage-kit/references/planning.md",
            "skills/sage-kit/references/execution.md",
            "skills/sage-kit/references/review-completion.md",
        )
        combined = "\n".join(
            (REPO_ROOT / path).read_text(encoding="utf-8") for path in paths
        ).casefold()
        for phrase in (
            "sage_project.json",
            "milestone_manifest.json",
            "execution_document_model",
            "accepted historical",
            "must not fall back",
        ):
            self.assertIn(phrase, combined)


if __name__ == "__main__":
    unittest.main()
