from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY / "scripts" / "build_release_assets.py"


def load_release_builder():
    spec = importlib.util.spec_from_file_location("build_release_assets", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("release asset builder is not importable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ReleaseAssetTests(unittest.TestCase):
    def test_direct_script_entrypoint_is_importable(self):
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--help"],
            cwd=REPOSITORY,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("complete SAGE-Kit release asset inventory", completed.stdout)

    def test_release_build_has_a_complete_and_verifiable_asset_inventory(self):
        release = load_release_builder()
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "release"
            assets = release.build_release_assets(REPOSITORY, output)
            release.verify_release_assets(assets)

            self.assertEqual(
                {
                    "sagekit-2026.7.28.4-py3-none-any.whl",
                    "sagekit-2026.7.28.4-py3-none-any.whl.sha256",
                    "sagekit-2026.7.28.4.tar.gz",
                    "sagekit-2026.7.28.4.tar.gz.sha256",
                    "sage-kit-skill-2026.7.28.4.zip",
                    "sage-kit-skill-2026.7.28.4.zip.sha256",
                    "sage-kit-skill-2026.7.28.4.manifest.json",
                },
                {path.name for path in output.iterdir()},
            )

            with tarfile.open(assets.source_archive, "r:gz") as archive:
                names = set(archive.getnames())
            self.assertIn("sagekit-2026.7.28.4/pyproject.toml", names)
            self.assertIn(
                "sagekit-2026.7.28.4/scripts/build_release_assets.py", names
            )

            with zipfile.ZipFile(assets.skill_bundle) as archive:
                embedded = archive.read("sage-kit/manifest.json")
            self.assertEqual(embedded, assets.skill_manifest.read_bytes())
            manifest = json.loads(embedded)
            self.assertEqual("2026.7.28.4", manifest["version"])
            self.assertEqual(
                manifest["aggregate_sha256"],
                release.skill_bundle.aggregate_digest(manifest["files"]),
            )


if __name__ == "__main__":
    unittest.main()
