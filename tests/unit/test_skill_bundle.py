from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY / "scripts" / "build_skill_bundle.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_skill_bundle", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("skill bundle builder is not importable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SkillBundleTests(unittest.TestCase):
    def test_bundle_is_complete_and_independent_of_repository_cwd(self):
        builder = load_builder()
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            artifact = builder.build_skill_bundle(REPOSITORY, root / "release")
            expanded = root / "outside-repository" / "host-skills"
            builder.extract_and_verify_skill_bundle(artifact.archive, expanded)

            skill = expanded / "sage-kit"
            manifest = json.loads((skill / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("sage-kit", manifest["skill_name"])
            self.assertEqual("2026.7.28.4", manifest["version"])
            self.assertTrue(manifest["aggregate_sha256"])
            self.assertTrue((skill / "SKILL.md").read_text(encoding="utf-8").startswith("---\n"))
            self.assertTrue((skill / "agents/openai.yaml").is_file())
            self.assertTrue((skill / "references/codex.md").is_file())
            self.assertFalse((skill / "sagekit").exists())

            locators = builder.package_doc_locators(skill)
            self.assertTrue(locators)
            for relative in locators:
                self.assertTrue(
                    (REPOSITORY / "sagekit/resources" / relative).is_file(),
                    relative,
                )

            # A bundle is merely a release artifact. It never writes a host's
            # existing Installed Skill without an explicit extraction request.
            untouched = root / "installed-skill" / "sentinel.txt"
            untouched.parent.mkdir(parents=True)
            untouched.write_text("unchanged", encoding="utf-8")
            self.assertEqual("unchanged", untouched.read_text(encoding="utf-8"))

    def test_manifest_covers_exact_zip_payload_and_checksum_asset(self):
        builder = load_builder()
        with tempfile.TemporaryDirectory() as temp_name:
            artifact = builder.build_skill_bundle(REPOSITORY, Path(temp_name))
            self.assertEqual(
                artifact.archive.name,
                "sage-kit-skill-2026.7.28.4.zip",
            )
            self.assertEqual(
                artifact.checksum.name,
                "sage-kit-skill-2026.7.28.4.zip.sha256",
            )
            self.assertTrue(artifact.checksum.read_text(encoding="utf-8").startswith(artifact.sha256))

            with zipfile.ZipFile(artifact.archive) as archive:
                manifest = json.loads(archive.read("sage-kit/manifest.json"))
                names = set(archive.namelist())

            payload_names = {f"sage-kit/{item['path']}" for item in manifest["files"]}
            self.assertEqual(payload_names | {"sage-kit/manifest.json"}, names)
            self.assertEqual(
                manifest["aggregate_sha256"],
                builder.aggregate_digest(manifest["files"]),
            )
            self.assertNotIn(str(REPOSITORY), json.dumps(manifest, sort_keys=True))

    def test_bundle_paths_fail_closed_for_windows_and_posix_escapes(self):
        builder = load_builder()
        for path in ("../SKILL.md", "/SKILL.md", "C:/SKILL.md", "..\\SKILL.md"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                builder._safe_relative(path)


if __name__ == "__main__":
    unittest.main()
