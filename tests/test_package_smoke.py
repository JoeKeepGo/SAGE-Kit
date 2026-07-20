import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/wheel_smoke.py"


def load_wheel_smoke():
    spec = importlib.util.spec_from_file_location("wheel_smoke", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("wheel smoke script is not importable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WheelSmokeScriptTests(unittest.TestCase):
    def test_build_and_install_commands_are_offline_and_dependency_free(self):
        wheel_smoke = load_wheel_smoke()
        python = Path("python")
        repository = Path("repository")
        wheelhouse = Path("wheelhouse")
        wheel = wheelhouse / "sagekit-test.whl"

        build = wheel_smoke.build_command(python, repository, wheelhouse)
        install = wheel_smoke.install_command(python, wheel)

        self.assertIn("--no-index", build)
        self.assertIn("--no-deps", build)
        self.assertIn("--no-build-isolation", build)
        self.assertIn("--no-index", install)
        self.assertIn("--no-deps", install)

    def test_offline_build_backend_has_a_deterministic_preflight(self):
        wheel_smoke = load_wheel_smoke()

        with patch.object(wheel_smoke.importlib.metadata, "version", return_value="68.0"):
            self.assertEqual("68.0", wheel_smoke.preflight_build_backend())
        with patch.object(wheel_smoke.importlib.metadata, "version", return_value="80.1"):
            self.assertEqual("80.1", wheel_smoke.preflight_build_backend())
        with patch.object(wheel_smoke.importlib.metadata, "version", return_value="67.9"):
            with self.assertRaises(wheel_smoke.SmokeCapabilityFailure):
                wheel_smoke.preflight_build_backend()

    def test_installed_smoke_uses_isolated_no_bytecode_python(self):
        wheel_smoke = load_wheel_smoke()
        python = Path("venv-python")

        commands = wheel_smoke.installed_smoke_commands(python)

        self.assertTrue(commands)
        for command in commands:
            self.assertEqual([str(python), "-I", "-B"], command[:3])
        flattened = "\n".join(" ".join(command) for command in commands)
        self.assertIn("-m sagekit --help", flattened)
        self.assertIn("-m sagekit packet compile --help", flattened)
        self.assertIn("-m sagekit workspace verify --help", flattened)
        self.assertIn("-m sagekit resource status --help", flattened)
        self.assertIn("-m sagekit resource run --help", flattened)
        self.assertIn("importlib.resources", flattened)
        self.assertIn("execution_documents/2026.7.20.1/phase.schema.json", flattened)
        self.assertIn("resource_governance/conservative-host-v1.json", flattened)
        self.assertIn("docs/agent/HOST_RESOURCE_GOVERNANCE.md", flattened)

    def test_subprocess_environment_removes_source_import_overrides(self):
        wheel_smoke = load_wheel_smoke()
        original = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": "source-tree",
            "PYTHONHOME": "source-runtime",
        }

        isolated = wheel_smoke.isolated_environment(original)

        self.assertNotIn("PYTHONPATH", isolated)
        self.assertNotIn("PYTHONHOME", isolated)
        self.assertEqual("1", isolated["PYTHONDONTWRITEBYTECODE"])

    def test_cross_platform_venv_python_location(self):
        wheel_smoke = load_wheel_smoke()
        environment = Path("fresh-venv")

        self.assertEqual(
            environment / "Scripts/python.exe",
            wheel_smoke.venv_python(environment, platform_name="nt"),
        )
        self.assertEqual(
            environment / "bin/python",
            wheel_smoke.venv_python(environment, platform_name="posix"),
        )

    def test_synthetic_thin_project_commands_check_and_compile_outside_source(self):
        wheel_smoke = load_wheel_smoke()
        python = Path("fresh-venv/bin/python")
        project = Path("outside-source/synthetic-project")

        with self.subTest("fixture"):
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "synthetic-project"
                wheel_smoke.write_synthetic_thin_project(root)
                lock = json.loads((root / "SAGE_PROJECT.json").read_text(encoding="utf-8"))
                milestone = json.loads(
                    (root / "docs/M36/MILESTONE_MANIFEST.json").read_text(
                        encoding="utf-8"
                    )
                )
                phase = json.loads(
                    (root / "docs/M36/phases/P01.json").read_text(encoding="utf-8")
                )
                self.assertEqual("thin-v1", lock["execution_document_model"])
                self.assertEqual("conservative-host-v1", lock["resource_contract"])
                self.assertEqual("M36", milestone["milestone_id"])
                self.assertEqual("P01", phase["phase_id"])
                self.assertEqual("conservative-host-v1", phase["resource_profile"])

        commands = wheel_smoke.thin_smoke_commands(python, project)
        flattened = "\n".join(" ".join(command) for command in commands)
        self.assertIn("sagekit check --target", flattened)
        self.assertIn("sagekit packet compile --target", flattened)
        self.assertIn("--milestone M36 --phase P01 --json", flattened)
        for command in commands:
            self.assertEqual([str(python), "-I", "-B"], command[:3])

    def test_installed_check_envelope_validation_rejects_malformed_shapes(self):
        wheel_smoke = load_wheel_smoke()
        valid = {
            "findings": [
                {"level": "PASS", "rule": "project-contract", "message": "valid"}
            ],
            "summary": {
                "total": 1,
                "displayed": 1,
                "truncated": 0,
                "by_level": {"PASS": 1, "WARN": 0, "FAIL": 0},
            },
        }
        wheel_smoke.validate_check_payload(valid)

        malformed = (
            {"findings": ["FAIL"], "summary": valid["summary"]},
            {"findings": [], "summary": {"total": 0, "by_level": {}}},
            {
                "findings": [],
                "summary": {
                    "total": 1,
                    "displayed": 0,
                    "truncated": 0,
                    "by_level": {"PASS": 1, "WARN": 0, "FAIL": 0},
                },
            },
            {
                "findings": [],
                "summary": {
                    "total": 1,
                    "displayed": 0,
                    "truncated": 1,
                    "by_level": {"PASS": 0, "WARN": 0, "FAIL": 1},
                },
            },
            {
                "findings": [
                    {"level": "FAIL", "rule": "false-green", "message": "hidden"}
                ],
                "summary": {
                    "total": 1,
                    "displayed": 1,
                    "truncated": 0,
                    "by_level": {"PASS": 1, "WARN": 0, "FAIL": 0},
                },
            },
            {
                "findings": [
                    {"level": "WARN", "rule": "mismatch", "message": "wrong count"}
                ],
                "summary": {
                    "total": 1,
                    "displayed": 1,
                    "truncated": 0,
                    "by_level": {"PASS": 1, "WARN": 0, "FAIL": 0},
                },
            },
        )
        for payload in malformed:
            with self.subTest(payload=payload), self.assertRaises(wheel_smoke.SmokeFailure):
                wheel_smoke.validate_check_payload(payload)


if __name__ == "__main__":
    unittest.main()
