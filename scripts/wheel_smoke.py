from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Mapping, Sequence

from sagekit.managed_execution import ManagedExecutionError, run_managed_command
from sagekit.process_supervisor import ProcessResult
from sagekit.resource_governor import ResourceClass


class SmokeFailure(RuntimeError):
    pass


class SmokeCapabilityFailure(SmokeFailure):
    pass


def preflight_build_backend() -> str:
    try:
        version = importlib.metadata.version("setuptools")
    except importlib.metadata.PackageNotFoundError as exc:
        raise SmokeCapabilityFailure("setuptools>=68 is not installed") from exc
    numeric = tuple(int(part) for part in version.split(".")[:2] if part.isdigit())
    if not numeric or numeric < (68,):
        raise SmokeCapabilityFailure(
            f"setuptools>=68 is required for offline wheel build; found {version}"
        )
    return version


def build_command(python: Path, repository: Path, wheelhouse: Path) -> list[str]:
    return [
        str(python),
        "-I",
        "-B",
        "-m",
        "pip",
        "wheel",
        str(repository),
        "--wheel-dir",
        str(wheelhouse),
        "--no-index",
        "--no-deps",
        "--no-build-isolation",
    ]


def install_command(python: Path, wheel: Path) -> list[str]:
    return [
        str(python),
        "-I",
        "-B",
        "-m",
        "pip",
        "install",
        "--no-index",
        "--no-deps",
        str(wheel),
    ]


def installed_smoke_commands(python: Path) -> list[list[str]]:
    resource_probe = (
        "import importlib.resources; "
        "root=importlib.resources.files('sagekit').joinpath('resources'); "
        "required=('contracts/v0/policy.json','contracts/v1/policy.json',"
        "'contracts/v2/policy.json',"
        "'execution_documents/2026.7.20.1/contract.json',"
        "'execution_documents/2026.7.20.1/project.schema.json',"
        "'execution_documents/2026.7.20.1/milestone.schema.json',"
        "'execution_documents/2026.7.20.1/phase.schema.json',"
         "'execution_documents/2026.7.20.1/profiles/standard-phase-v1.json',"
         "'resource_governance/conservative-host-v1.json',"
         "'docs/agent/HOST_RESOURCE_GOVERNANCE.md'); "
        "missing=[item for item in required if not root.joinpath(item).is_file()]; "
        "assert not missing, f'missing packaged resources: {missing}'"
    )
    prefix = [str(python), "-I", "-B"]
    return [
        [*prefix, "-m", "sagekit", "--help"],
        [*prefix, "-m", "sagekit", "--version"],
        [*prefix, "-m", "sagekit", "check", "--help"],
        [*prefix, "-m", "sagekit", "packet", "compile", "--help"],
        [*prefix, "-m", "sagekit", "workspace", "verify", "--help"],
        [*prefix, "-m", "sagekit", "resource", "status", "--help"],
        [*prefix, "-m", "sagekit", "resource", "run", "--help"],
        [*prefix, "-c", resource_probe],
    ]


def thin_smoke_commands(python: Path, project: Path) -> list[list[str]]:
    prefix = [str(python), "-I", "-B", "-m", "sagekit"]
    return [
        [*prefix, "check", "--target", str(project), "--json"],
        [
            *prefix,
            "packet",
            "compile",
            "--target",
            str(project),
            "--milestone",
            "M36",
            "--phase",
            "P01",
            "--json",
        ],
    ]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_synthetic_thin_project(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    required_docs = {
        "docs/PROJECT_PROFILE.md": "# Project Profile\n\nSynthetic package smoke project.\n",
        "docs/QUALITY_GATES.md": "# Quality Gates\n\nRequire successful focused verification.\n",
        "docs/ACTIVE_CONTEXT.md": "# Active Context\n\nValidate the synthetic thin-v1 project.\n",
        "docs/DOC_ROUTING.md": (
            "# Document Routing\n\nRouting policy: read the active thin manifests.\n"
        ),
    }
    for relative, content in required_docs.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    _write_json(
        root / "SAGE_PROJECT.json",
        {
            "schema_version": 1,
            "sagekit_contract": "2026.7.20.1",
            "execution_document_model": "thin-v1",
            "resource_contract": "conservative-host-v1",
            "effective_from": "M36",
            "legacy_documents": "immutable",
            "profiles": ["standard-milestone@v1", "standard-phase@v1"],
            "overrides": {},
        },
    )
    _write_json(
        root / "docs/M36/MILESTONE_MANIFEST.json",
        {
            "schema_version": 1,
            "sagekit_contract": "2026.7.20.1",
            "document_model": "thin-v1",
            "milestone_id": "M36",
            "objective": "Verify the installed thin execution-document runtime.",
            "capability_outcome": "Installed validation and packet compilation work outside source.",
            "authority_references": ["SAGE_PROJECT.json"],
            "governance_profile": "standard-milestone@v1",
            "dependency_dag": {"P01": []},
            "approval_gates": [
                {
                    "id": "G-M36-WRITE",
                    "applies_to": ["P01"],
                    "status": "approved",
                    "permission_mode": "WRITE_AUTHORIZED",
                    "authority_reference": "SAGE_PROJECT.json",
                }
            ],
            "phase_ids": ["P01"],
            "acceptance_criteria": ["Installed thin-v1 validation succeeds."],
            "invariants": ["The source manifests remain unchanged by compilation."],
            "state": "active",
            "evidence_references": [],
        },
    )
    _write_json(
        root / "docs/M36/phases/P01.json",
        {
            "schema_version": 1,
            "sagekit_contract": "2026.7.20.1",
            "document_model": "thin-v1",
            "phase_id": "P01",
            "objective": "Compile one deterministic standalone packet.",
            "depends_on": [],
            "execution_profile": "standard-phase@v1",
            "resource_profile": "conservative-host-v1",
            "resource_overrides": {},
            "permission_mode": "WRITE_AUTHORIZED",
            "owner": "package-smoke-controller",
            "writable_paths": ["src/synthetic.py"],
            "read_only_references": [
                "SAGE_PROJECT.json",
                "docs/M36/MILESTONE_MANIFEST.json",
            ],
            "forbidden_paths": ["docs/ACTIVE_CONTEXT.md", "docs/DOC_ROUTING.md"],
            "inherit_forbidden": True,
            "acceptance_criteria": ["The compiled packet binds all source digests."],
            "verification_commands": ["python -B -m unittest tests.test_synthetic"],
            "evidence_requirements": ["Record command and exit code."],
            "stop_conditions": ["Stop on authority conflict."],
            "handoff_target": "package-smoke-review",
            "state": "planned",
        },
    )


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def validate_check_payload(payload: object) -> None:
    if not isinstance(payload, dict):
        raise SmokeFailure("installed project check returned a non-object envelope")
    findings = payload.get("findings")
    summary = payload.get("summary")
    if not isinstance(findings, list) or not isinstance(summary, dict):
        raise SmokeFailure("installed project check returned an invalid findings envelope")
    required_summary = {"total", "displayed", "truncated", "by_level"}
    if not required_summary.issubset(summary):
        raise SmokeFailure("installed project check returned an incomplete summary")
    counts = summary.get("by_level")
    integers = [summary.get(key) for key in ("total", "displayed", "truncated")]
    if (
        not isinstance(counts, dict)
        or set(counts) != {"PASS", "WARN", "FAIL"}
        or any(type(value) is not int or value < 0 for value in integers)
        or any(type(value) is not int or value < 0 for value in counts.values())
    ):
        raise SmokeFailure("installed project check returned an invalid summary")
    if (
        summary["displayed"] != len(findings)
        or summary["truncated"] != summary["total"] - summary["displayed"]
        or sum(counts.values()) != summary["total"]
    ):
        raise SmokeFailure("installed project check returned inconsistent summary counts")
    displayed_counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for finding in findings:
        if (
            not isinstance(finding, dict)
            or finding.get("level") not in {"PASS", "WARN", "FAIL"}
            or not isinstance(finding.get("rule"), str)
            or not isinstance(finding.get("message"), str)
        ):
            raise SmokeFailure("installed project check returned an invalid finding")
        displayed_counts[finding["level"]] += 1
    if displayed_counts["FAIL"]:
        raise SmokeFailure("installed project check displayed a FAIL finding")
    if any(displayed_counts[level] > counts[level] for level in displayed_counts):
        raise SmokeFailure("installed project check finding levels exceed summary counts")
    if summary["truncated"] == 0 and displayed_counts != counts:
        raise SmokeFailure("installed project check finding levels differ from summary counts")
    if counts["FAIL"]:
        raise SmokeFailure("installed project check returned a FAIL finding")


def isolated_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    environment = dict(os.environ if source is None else source)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment["PIP_NO_INDEX"] = "1"
    return environment


def venv_python(environment: Path, *, platform_name: str | None = None) -> Path:
    selected = os.name if platform_name is None else platform_name
    if selected == "nt":
        return environment / "Scripts/python.exe"
    return environment / "bin/python"


def run(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    repository: Path | None = None,
    stage: str = "wheel-smoke-command",
    temp_root: Path | None = None,
    timeout: float = 300.0,
) -> ProcessResult:
    try:
        return run_managed_command(
            cwd if repository is None else repository,
            command,
            resource_class=ResourceClass.PACKAGE_BUILD,
            permission_mode="ENVIRONMENT_WRITE_AUTHORIZED",
            controller="sagekit-root-verification-controller",
            stage=stage,
            run_id=f"wheel-smoke-{stage}",
            timeout=timeout,
            max_output_bytes=1024 * 1024,
            environment=environment,
            cwd=cwd,
            temp_root=temp_root,
            wait_timeout=300.0,
        )
    except ManagedExecutionError as exc:
        raise SmokeFailure(str(exc)) from exc


def find_built_wheel(wheelhouse: Path) -> Path:
    wheels = sorted(wheelhouse.glob("sagekit-*.whl"))
    if len(wheels) != 1:
        raise SmokeFailure(
            f"expected exactly one sagekit wheel, found {len(wheels)} in {wheelhouse}"
        )
    return wheels[0]


def run_wheel_smoke(repository: Path) -> None:
    repository = repository.resolve(strict=True)
    if not (repository / "pyproject.toml").is_file():
        raise SmokeFailure(f"repository lacks pyproject.toml: {repository}")
    preflight_build_backend()
    environment = isolated_environment()
    with tempfile.TemporaryDirectory(prefix="sagekit-wheel-smoke-") as temp_name:
        workspace = Path(temp_name)
        wheelhouse = workspace / "wheelhouse"
        fresh_venv = workspace / "fresh-venv"
        outside_source = workspace / "outside-source"
        wheelhouse.mkdir()
        outside_source.mkdir()

        run(
            build_command(Path(sys.executable), repository, wheelhouse),
            cwd=outside_source,
            environment=environment,
            repository=repository,
            stage="wheel-build",
            temp_root=workspace,
        )
        wheel = find_built_wheel(wheelhouse)
        run(
            [sys.executable, "-I", "-B", "-m", "venv", str(fresh_venv)],
            cwd=outside_source,
            environment=environment,
            repository=repository,
            stage="fresh-venv",
            temp_root=workspace,
        )
        python = venv_python(fresh_venv)
        run(
            install_command(python, wheel),
            cwd=outside_source,
            environment=environment,
            repository=repository,
            stage="wheel-install",
            temp_root=workspace,
        )
        for command in installed_smoke_commands(python):
            try:
                run(
                    command,
                    cwd=outside_source,
                    environment=environment,
                    repository=repository,
                    stage="installed-cli-smoke",
                    temp_root=workspace,
                )
            except SmokeFailure as exc:
                if command[-3:] == ["packet", "compile", "--help"]:
                    raise SmokeFailure(
                        "BLOCKED: installed runtime does not expose `sagekit packet compile`"
                    ) from exc
                raise

        synthetic_project = outside_source / "synthetic-project"
        write_synthetic_thin_project(synthetic_project)
        project_before = tree_digest(synthetic_project)
        thin_results = [
            run(
                command,
                cwd=outside_source,
                environment=environment,
                repository=repository,
                stage="installed-thin-smoke",
                temp_root=workspace,
            )
            for command in thin_smoke_commands(python, synthetic_project)
        ]
        try:
            check_payload = json.loads(thin_results[0].stdout)
            packet_payload = json.loads(thin_results[1].stdout)
        except json.JSONDecodeError as exc:
            raise SmokeFailure(f"installed thin-v1 smoke returned invalid JSON: {exc}") from exc
        validate_check_payload(check_payload)
        packet = packet_payload.get("packet")
        if (
            packet_payload.get("ok") is not True
            or not isinstance(packet, dict)
            or packet.get("document_model") != "thin-v1"
            or packet_payload.get("packet_sha256") != packet.get("packet_sha256")
        ):
            raise SmokeFailure("installed packet compile returned an invalid thin-v1 payload")
        if tree_digest(synthetic_project) != project_before:
            raise SmokeFailure("installed packet compile modified the synthetic project")

        bytecode = list(outside_source.rglob("__pycache__")) + list(
            outside_source.rglob("*.pyc")
        )
        if bytecode:
            raise SmokeFailure(
                "outside-source smoke created bytecode: "
                + ", ".join(str(path.relative_to(outside_source)) for path in bytecode)
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and install SAGE-Kit in a fresh isolated environment."
    )
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="SAGE-Kit source repository (defaults to the script's repository).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run_wheel_smoke(args.repository)
    except SmokeCapabilityFailure as exc:
        print(f"WHEEL_SMOKE_CAPABILITY_FAIL: {exc}", file=sys.stderr)
        return 2
    except (OSError, SmokeFailure) as exc:
        print(f"WHEEL_SMOKE_FAIL: {exc}", file=sys.stderr)
        return 1
    print("WHEEL_SMOKE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
