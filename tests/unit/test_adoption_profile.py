from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sagekit.check import run_check
from sagekit.init import init_files_for_mode, package_resource_root, run_init
from sagekit.doctor import run_doctor
from sagekit.spec_sources import package_identity
from sagekit.modes import LEGACY_REQUIRED_DOCS


class AdoptionProfileTests(unittest.TestCase):
    def test_legacy_docs_without_equivalent_authority_are_not_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in LEGACY_REQUIRED_DOCS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"# {path.stem}\n", encoding="utf-8")

            diagnosed = run_doctor(root)

        self.assertTrue(
            any(item.level == "PASS" and item.rule == "adopted-project" for item in diagnosed),
            diagnosed,
        )
        self.assertTrue(
            any(item.level == "WARN" and item.rule == "project-authority" for item in diagnosed),
            diagnosed,
        )

    def test_package_bound_is_the_small_default_without_framework_tree(self) -> None:
        files = init_files_for_mode(
            "heavy", package_resource_root(), profile="package-bound"
        )
        destinations = {item.destination for item in files}

        self.assertEqual(
            {"SAGEKIT_CONFIG.json", "docs/ACTIVE_CONTEXT.md", "docs/DOC_ROUTING.md"},
            destinations,
        )
        self.assertFalse(any(path.startswith("docs/agent/") for path in destinations))
        self.assertFalse(any(path.startswith("docs/templates/") for path in destinations))
        self.assertNotIn("docs/SAGE_CORE.md", destinations)

    def test_vendored_legacy_remains_an_explicit_compatibility_profile(self) -> None:
        files = init_files_for_mode(
            "heavy", package_resource_root(), profile="vendored-legacy"
        )
        destinations = {item.destination for item in files}

        self.assertIn("docs/SAGE_CORE.md", destinations)
        self.assertIn("docs/agent/GOVERNANCE_LEVELS.md", destinations)
        self.assertTrue(any(path.startswith("docs/templates/") for path in destinations))

    def test_default_init_creates_executable_empty_active_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            findings = run_init(root, mode="heavy", exact_root=True)
            config = json.loads((root / "SAGEKIT_CONFIG.json").read_text(encoding="utf-8"))
            checked = run_check(root)
            diagnosed = run_doctor(root)

        self.assertFalse(any(item.level == "FAIL" for item in findings), findings)
        self.assertEqual(package_identity(), config["package"])
        self.assertEqual("project", config["project_id"])
        self.assertEqual({}, config["sources"])
        self.assertFalse((root / "docs/SAGE_CORE.md").exists())
        self.assertFalse((root / "docs/agent").exists())
        self.assertFalse(any(item.level == "FAIL" for item in checked), checked)
        self.assertFalse(
            any(item.rule == "adoption-required-docs" and item.level != "PASS" for item in diagnosed),
            diagnosed,
        )

    def test_doctor_fails_when_configured_active_context_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            run_init(root, mode="heavy", exact_root=True)
            (root / "docs/ACTIVE_CONTEXT.md").unlink()

            diagnosed = run_doctor(root)

        self.assertTrue(
            any(item.level == "FAIL" and item.rule == "active-context" for item in diagnosed),
            diagnosed,
        )
        self.assertFalse(
            any(item.level == "PASS" and item.rule == "adoption-required-docs" for item in diagnosed),
            diagnosed,
        )

    def test_doctor_reports_vendored_profile_without_package_bound_false_label(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            run_init(root, mode="heavy", exact_root=True)
            config_path = root / "SAGEKIT_CONFIG.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["adoption_profile"] = "vendored-legacy"
            config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            for relative in LEGACY_REQUIRED_DOCS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_text(f"# {path.stem}\n", encoding="utf-8")

            diagnosed = run_doctor(root)

        adopted = [item for item in diagnosed if item.rule == "adopted-project"]
        self.assertTrue(adopted, diagnosed)
        self.assertTrue(any("vendored-legacy" in item.message for item in adopted), adopted)
        self.assertFalse(any("package-bound" in item.message for item in adopted), adopted)


if __name__ == "__main__":
    unittest.main()
