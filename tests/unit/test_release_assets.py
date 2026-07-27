from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


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


def write_prebuilt_wheel(repository: Path, output: Path, version: str) -> Path:
    wheel = output / f"sagekit-{version}-py3-none-any.whl"
    wheel.write_bytes(b"prebuilt deterministic unit fixture\n")
    return wheel


class ReleaseAssetTests(unittest.TestCase):
    def init_git_repository(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "baseline",
            ],
            check=True,
        )

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
            with patch.object(release, "verify_tracked_worktree_clean") as clean, patch.object(
                release, "build_wheel", side_effect=write_prebuilt_wheel
            ) as build_wheel:
                assets = release.build_release_assets(REPOSITORY, output)
            clean.assert_called_once_with(REPOSITORY.resolve())
            build_wheel.assert_called_once_with(
                REPOSITORY.resolve(), output, "2026.7.28.4"
            )
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

    def test_source_archive_uses_only_the_frozen_tracked_manifest(self):
        release = load_release_builder()
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "repository"
            root.mkdir()
            tracked = root / "tracked.txt"
            tracked.write_text("tracked\n", encoding="utf-8")
            self.init_git_repository(root)
            (root / ".env").write_text("secret=value\n", encoding="utf-8")
            (root / ".sagekit").mkdir()
            (root / ".sagekit" / "runtime.json").write_text("{}\n", encoding="utf-8")
            (root / "secret-fixture.txt").write_text("secret\n", encoding="utf-8")

            archive = release.build_source_archive(root, Path(temp_name), "test")
            with tarfile.open(archive, "r:gz") as source:
                names = set(source.getnames())
            self.assertEqual({"sagekit-test/tracked.txt"}, names)

    def test_source_archive_rejects_unstaged_and_staged_tracked_changes(self):
        release = load_release_builder()
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "repository"
            root.mkdir()
            tracked = root / "tracked.txt"
            tracked.write_text("baseline\n", encoding="utf-8")
            self.init_git_repository(root)

            tracked.write_text("unstaged\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no unstaged tracked changes"):
                release.build_source_archive(root, Path(temp_name), "test")

            subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
            with self.assertRaisesRegex(ValueError, "no staged tracked changes"):
                release.build_source_archive(root, Path(temp_name), "test")

    def test_source_archive_normalizes_tar_metadata_across_host_modes(self):
        release = load_release_builder()
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "payload.txt"
            source.write_text("stable payload\n", encoding="utf-8")
            entry = release.TrackedSourceEntry(
                source, release.PurePosixPath("payload.txt"), 0o100644
            )
            first = release.write_source_archive(root / "first.tar.gz", (entry,), "test")
            original_mode = source.stat().st_mode
            try:
                os.chmod(source, 0o600)
                second = release.write_source_archive(root / "second.tar.gz", (entry,), "test")
            finally:
                os.chmod(source, original_mode)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first, "r:gz") as archive:
                member = archive.getmember("sagekit-test/payload.txt")
            self.assertEqual(0, member.mtime)
            self.assertEqual(0, member.uid)
            self.assertEqual(0, member.gid)
            self.assertEqual("", member.uname)
            self.assertEqual("", member.gname)
            self.assertEqual(0o644, member.mode)

    def test_tampered_skill_payload_fails_even_when_outer_checksum_is_regenerated(self):
        release = load_release_builder()
        with tempfile.TemporaryDirectory() as temp_name:
            with patch.object(release, "verify_tracked_worktree_clean"), patch.object(
                release, "build_wheel", side_effect=write_prebuilt_wheel
            ) as build_wheel:
                assets = release.build_release_assets(REPOSITORY, Path(temp_name))
            build_wheel.assert_called_once_with(
                REPOSITORY.resolve(), Path(temp_name), "2026.7.28.4"
            )
            with zipfile.ZipFile(assets.skill_bundle) as original:
                payloads = {
                    name: original.read(name)
                    for name in original.namelist()
                }
            payloads["sage-kit/SKILL.md"] += b"\nchanged\n"
            with zipfile.ZipFile(assets.skill_bundle, "w", zipfile.ZIP_DEFLATED) as mutated:
                for name, payload in payloads.items():
                    mutated.writestr(name, payload)
            release.write_checksum(assets.skill_bundle)

            with self.assertRaises(ValueError):
                release.verify_release_assets(assets)


if __name__ == "__main__":
    unittest.main()
