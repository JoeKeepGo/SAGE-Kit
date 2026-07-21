from __future__ import annotations

import json
import unittest
from pathlib import Path

from sagekit import __version__


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_VERSION = "2026.7.20.1"
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
    "resource_contract",
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
    "resource_profile",
    "resource_overrides",
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
    def test_frozen_execution_contract_is_independent_of_package_release(self):
        self.assertEqual(__version__, "2026.7.20.2")
        self.assertEqual(CONTRACT_VERSION, "2026.7.20.1")
        self.assertNotEqual(CONTRACT_VERSION, __version__)

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
                "resource_contract",
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
        self.assertEqual(contract["resource_contract"], "conservative-host-v1")
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
        project = load_json(REPO_ROOT / "docs/templates/SAGE_PROJECT_TEMPLATE.json")
        self.assertEqual(project["resource_contract"], "conservative-host-v1")
        self.assertEqual(milestone["governance_profile"], "standard-milestone@v1")
        self.assertEqual(milestone["approval_gates"][0]["applies_to"], ["P1"])
        self.assertEqual(phase["execution_profile"], "standard-phase@v1")
        self.assertEqual(phase["resource_profile"], "conservative-host-v1")
        self.assertEqual(phase["resource_overrides"], {})
        self.assertTrue(milestone["authority_references"])
        self.assertTrue(phase["acceptance_criteria"])
        self.assertTrue(phase["verification_commands"])
        self.assertTrue(phase["stop_conditions"])


class ThinDocumentationTests(unittest.TestCase):
    def test_readmes_describe_embedded_harness_without_public_cli_guidance(self):
        for filename in ("README.md", "README.zh-CN.md"):
            with self.subTest(readme=filename):
                text = (REPO_ROOT / filename).read_text(encoding="utf-8")
                folded = text.casefold()
                self.assertIn("harness", folded)
                self.assertNotIn("pipx install", folded)
                self.assertNotIn("sagekit init", folded)
                self.assertNotIn("python -m sagekit", folded)
                self.assertNotIn("source candidate", text.casefold())

    def test_readmes_keep_authority_in_project_spec_not_fixed_documents(self):
        english = " ".join(
            (REPO_ROOT / "README.md").read_text(encoding="utf-8").casefold().split()
        )
        chinese = " ".join(
            (REPO_ROOT / "README.zh-CN.md").read_text(encoding="utf-8").casefold().split()
        )

        self.assertIn("project-owned spec and configuration", english)
        self.assertIn("optional legacy layout", english)
        self.assertIn("does not own project policy", english)
        self.assertNotIn("project documents remain the source of truth", english)
        self.assertNotIn("harness core is embeddable and project-owned", english)
        self.assertIn("项目自有的 spec 与配置是权威来源", chinese)
        self.assertIn("可选传统布局", chinese)

    def test_readmes_core_and_repository_skill_route_resource_governance(self):
        readmes = "\n".join(
            (REPO_ROOT / filename).read_text(encoding="utf-8")
            for filename in ("README.md", "README.zh-CN.md")
        ).casefold()
        core = (REPO_ROOT / "docs/SAGE_CORE.md").read_text(encoding="utf-8").casefold()
        skill = (REPO_ROOT / "skills/sage-kit/SKILL.md").read_text(
            encoding="utf-8"
        ).casefold()
        self.assertIn("embeddable", readmes)
        self.assertIn("project", readmes)
        for text in (core, skill):
            self.assertIn("conservative-host-v1", text)
            self.assertIn("workspace", text)
            self.assertIn("managed", text)
            self.assertIn("soft", text)
        self.assertIn("resource governance", skill)
        self.assertIn("workspace verification", skill)

    def test_governance_authority_and_fail_closed_rules_are_packaged(self):
        pairs = {
            "core": (
                "docs/SAGE_CORE.md",
                "sagekit/resources/docs/SAGE_CORE.md",
            ),
            "quality": (
                "docs/QUALITY_GATES_TEMPLATE.md",
                "sagekit/resources/docs/QUALITY_GATES_TEMPLATE.md",
            ),
            "strict": (
                "docs/agent/STRICT_MODE.md",
                "sagekit/resources/docs/agent/STRICT_MODE.md",
            ),
            "entry": (
                "docs/agent/PROJECT_OWNER_ENTRY.md",
                "sagekit/resources/docs/agent/PROJECT_OWNER_ENTRY.md",
            ),
            "assurance": (
                "docs/agent/MODEL_ASSURANCE_POLICY.md",
                "sagekit/resources/docs/agent/MODEL_ASSURANCE_POLICY.md",
            ),
            "adapters": (
                "docs/agent/CAPABILITY_ADAPTERS.md",
                "sagekit/resources/docs/agent/CAPABILITY_ADAPTERS.md",
            ),
        }
        documents = {}
        for name, (source_path, packaged_path) in pairs.items():
            source = REPO_ROOT / source_path
            packaged = REPO_ROOT / packaged_path
            self.assertEqual(source.read_bytes(), packaged.read_bytes(), name)
            documents[name] = " ".join(
                source.read_text(encoding="utf-8").split()
            )

        self.assertIn("retained active SPEC, phase, or task authority", documents["core"])
        self.assertIn("Markdown location is provenance, not authority by itself", documents["core"])
        self.assertIn("Active execution authority gate", documents["quality"])
        self.assertNotIn("Phase documentation gate", documents["quality"])
        self.assertIn("No fallback gate", documents["quality"])
        self.assertIn("hidden success, unauthorized fallback, or silent downgrade", documents["quality"])
        self.assertIn("Do not mark work `BLOCKED` merely because a fixed round count was reached", documents["quality"])
        self.assertIn("deterministic failure must not be retried speculatively", documents["quality"])
        self.assertIn("choose or change architecture", documents["strict"])
        self.assertIn("Do not add fallback behavior unless", documents["strict"])
        self.assertIn("advisory prompts, not product requirements", documents["entry"])
        self.assertIn("must not invent a product threat model", documents["entry"])
        self.assertIn("versioned project or runtime classification", documents["assurance"])
        self.assertIn("passes its identifier and version to descendants", documents["assurance"])
        self.assertIn("advisory routing inputs, not product requirements", documents["adapters"])
        self.assertIn("Only the active project SPEC or its named owner", documents["adapters"])

    def test_resource_governance_document_is_packaged_and_states_containment_levels(self):
        source = REPO_ROOT / "docs/agent/HOST_RESOURCE_GOVERNANCE.md"
        packaged = REPO_ROOT / "sagekit/resources/docs/agent/HOST_RESOURCE_GOVERNANCE.md"
        self.assertTrue(source.is_file(), source)
        self.assertTrue(packaged.is_file(), packaged)
        self.assertEqual(source.read_bytes(), packaged.read_bytes())
        text = " ".join(source.read_text(encoding="utf-8").casefold().split())
        for phrase in (
            "conservative-host-v1",
            "sagekit.verify_project_workspace",
            "sagekit.check_project",
            "sagekit.run_managed_command",
            "waiting_for_resource",
            "soft guarantee",
            "`hard`",
            "`managed`",
            "containment_level",
            "containment_complete",
            "cleanup_complete",
            "orphan_check",
            "platform_adapter",
            "limitations",
            "windows-job-object-gated-v1",
            "posix-session-process-group-v1",
            "job object",
            "process group",
        ):
            self.assertIn(phrase, text)
        self.assertIn("does not intercept", text)

    def test_readmes_explain_thick_kit_thin_project_and_migration_boundary(self):
        for filename in ("README.md", "README.zh-CN.md"):
            with self.subTest(readme=filename):
                text = (REPO_ROOT / filename).read_text(encoding="utf-8")
                folded = text.casefold()
                self.assertIn("harness", folded)
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

    def test_lane_f_profiles_use_embedded_authority_and_soft_unknown_runtime_guarantees(self):
        harness = (REPO_ROOT / "docs/agent/AGENT_HARNESS.md").read_text(
            encoding="utf-8"
        )
        economy = (REPO_ROOT / "docs/agent/EXECUTION_ECONOMY.md").read_text(
            encoding="utf-8"
        )
        packet = (
            REPO_ROOT / "docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md"
        ).read_text(encoding="utf-8")
        claude = (REPO_ROOT / "skills/sage-kit/references/claude.md").read_text(
            encoding="utf-8"
        )
        kimi = (
            REPO_ROOT / "skills/sage-kit/references/kimi-runtime.md"
        ).read_text(encoding="utf-8")
        opencode = (
            REPO_ROOT / "skills/sage-kit/references/opencode.md"
        ).read_text(encoding="utf-8")
        combined = "\n".join((harness, economy, packet, claude, kimi, opencode))

        self.assertNotIn("explicit CLI selection", combined)
        self.assertNotIn("CLI help/version", combined)
        self.assertNotIn("--snapshot-authority", combined)
        self.assertNotIn("--allow-dirty", combined)
        self.assertIn("explicit embedded API source", harness)
        self.assertIn("`snapshot_authority` field", economy)
        self.assertIn("`snapshot_authority` API/config field", packet)
        self.assertIn("Invoke explicitly with `/sage-kit`", claude)
        self.assertIn("Other clients that describe themselves as compatible", kimi)
        self.assertIn("treat unknown behavior as a soft capability", kimi)
        self.assertIn("normalized `ACTIVE_SPEC` or execution packet", claude)
        self.assertIn("normalized active SPEC", kimi)
        self.assertIn("normalized active SPEC", opencode)
        self.assertIn("Persist a packet only when", claude)
        self.assertIn("Persist a packet only when", opencode)
        self.assertIn("Persist a lane packet", " ".join(kimi.split()))

        for path in (
            "docs/agent/MILESTONE_PLANNING.md",
            "docs/agent/PHASE_EXECUTION.md",
            "docs/DOC_ROUTING_TEMPLATE.md",
            "skills/sage-kit/references/planning.md",
        ):
            with self.subTest(location_independent_source=path):
                text = " ".join(
                    (REPO_ROOT / path)
                    .read_text(encoding="utf-8")
                    .casefold()
                    .split()
                )
                self.assertIn("explicit", text)
                self.assertIn("configured", text)
                self.assertIn("provenance, not authority", text)


if __name__ == "__main__":
    unittest.main()
