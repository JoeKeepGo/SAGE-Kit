import json
import re
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
    r"sagekit/resources/docs/[A-Za-z0-9_./-]+\.(?:md|json)"
)


class CanonicalResourceInventoryTests(unittest.TestCase):
    def test_skill_framework_locators_resolve_to_package_resources(self):
        stale_patterns = (
            re.compile(r"(?<!resources/)docs/agent/"),
            re.compile(r"(?<!resources/)docs/templates/"),
            re.compile(r"(?<!resources/)docs/SAGE_CORE\.md"),
            re.compile(r"\.\./\.\./\.\./docs/"),
        )
        located = set()
        for relative in SKILL_FILES:
            text = (REPOSITORY / relative).read_text(encoding="utf-8")
            for pattern in stale_patterns:
                self.assertIsNone(pattern.search(text), f"{relative}: {pattern.pattern}")
            located.update(PACKAGE_DOC_PATTERN.findall(text))

        self.assertTrue(located)
        missing = sorted(path for path in located if not (REPOSITORY / path).is_file())
        self.assertEqual([], missing)

    def test_codex_markdown_links_resolve_inside_repository(self):
        reference = REPOSITORY / "skills/sage-kit/references/codex.md"
        text = reference.read_text(encoding="utf-8")
        links = re.findall(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)", text)
        repository_links = [link for link in links if "://" not in link]
        self.assertTrue(repository_links)
        missing = sorted(
            link
            for link in repository_links
            if not (reference.parent / link).resolve().is_file()
        )
        self.assertEqual([], missing)

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
