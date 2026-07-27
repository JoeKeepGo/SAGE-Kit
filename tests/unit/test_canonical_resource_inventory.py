import json
import re
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
SKILL_FILES = (
    "skills/sage-kit/SKILL.md",
    "skills/sage-kit/agents/openai.yaml",
    "skills/sage-kit/references/adoption.md",
    "skills/sage-kit/references/claude.md",
    "skills/sage-kit/references/codex.md",
    "skills/sage-kit/references/execution.md",
    "skills/sage-kit/references/kimi-runtime.md",
    "skills/sage-kit/references/opencode.md",
    "skills/sage-kit/references/planning.md",
    "skills/sage-kit/references/review-completion.md",
    "skills/sage-kit/references/claude/agents/sage-coder.md",
    "skills/sage-kit/references/claude/agents/sage-final-review.md",
)
CONTRACT_FAMILIES = (
    "graph",
    "runtime-state",
    "ready-resolution",
    "transition-resolution",
    "evidence-lineage",
    "graph-evolution",
)
PACKAGE_DOC_PATTERN = re.compile(
    r'package-doc\("([A-Za-z0-9_./-]+\.(?:md|json))(?:#[A-Za-z0-9_-]+)?"\)'
)


class CanonicalResourceInventoryTests(unittest.TestCase):
    def test_skill_framework_locators_resolve_to_package_resources(self):
        stale_patterns = (
            re.compile(r"(?<!resources/)sagekit/resources/docs/"),
            re.compile(r'(?<!package-doc\(")docs/agent/'),
            re.compile(r'(?<!package-doc\(")docs/templates/'),
            re.compile(r'(?<!package-doc\(")docs/SAGE_CORE\.md'),
            re.compile(r"\.\./\.\./\.\./docs/"),
        )
        located = set()
        for relative in SKILL_FILES:
            text = (REPOSITORY / relative).read_text(encoding="utf-8")
            for pattern in stale_patterns:
                self.assertIsNone(pattern.search(text), f"{relative}: {pattern.pattern}")
            located.update(PACKAGE_DOC_PATTERN.findall(text))

        self.assertTrue(located)
        missing = sorted(
            path
            for path in located
            if not (REPOSITORY / "sagekit/resources" / path).is_file()
        )
        self.assertEqual([], missing)

    def test_skill_defines_package_doc_as_an_importlib_resource_locator(self):
        skill = (REPOSITORY / "skills/sage-kit/SKILL.md").read_text(encoding="utf-8")
        self.assertIn(
            'importlib.resources.files("sagekit").joinpath("resources/", relative_path)',
            skill,
        )
        self.assertIn("never resolve it relative to the Skill installation", skill)

    def test_source_checkout_package_doc_locators_use_imported_package(self):
        from importlib import resources

        resource = resources.files("sagekit").joinpath(
            "resources/docs/agent/AGENT_HARNESS.md"
        )
        self.assertTrue(resource.is_file())
        self.assertEqual(
            (REPOSITORY / "sagekit/resources/docs/agent/AGENT_HARNESS.md").resolve(),
            Path(str(resource)).resolve(),
        )

    def test_source_package_locator_ignores_external_installed_skill_sibling(self):
        from importlib import resources

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed_skill = root / "installed-skills/sage-kit"
            sibling_decoy = installed_skill / "sagekit/resources/docs/agent/AGENT_HARNESS.md"
            sibling_decoy.parent.mkdir(parents=True)
            sibling_decoy.write_text("sibling-relative decoy", encoding="utf-8")

            resource = resources.files("sagekit").joinpath(
                "resources/docs/agent/AGENT_HARNESS.md"
            )
            self.assertEqual(
                (REPOSITORY / "sagekit/resources/docs/agent/AGENT_HARNESS.md").resolve(),
                Path(str(resource)).resolve(),
            )
            self.assertNotEqual(
                sibling_decoy.read_text(encoding="utf-8"),
                resource.read_text(encoding="utf-8"),
            )

    def test_contract_manifests_name_the_package_resource_owner(self):
        for family in CONTRACT_FAMILIES:
            with self.subTest(family=family):
                directory = Path("sagekit/resources/contracts") / family / "v1"
                contract_path = REPOSITORY / directory / "contract.json"
                contract = json.loads(contract_path.read_text(encoding="utf-8"))
                serialized = json.dumps(contract, sort_keys=True)
                self.assertNotIn("docs/contracts/", serialized)
                owner = contract["packaged_mirror"]
                self.assertEqual(directory.as_posix(), owner["path"])
                self.assertIn("canonical owner", owner["expectation"])

                dependency_paths = {
                    value
                    for item in contract.get("dependencies", {}).values()
                    for key, value in item.items()
                    if key in {"resource", "contract_resource", "schema_resource"}
                }
                missing = sorted(
                    path
                    for path in dependency_paths
                    if path.startswith("sagekit/resources/")
                    and not (REPOSITORY / path).is_file()
                )
                self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
