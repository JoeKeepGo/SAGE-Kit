"""Build and verify the explicit host-installable SAGE-Kit Skill bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


SKILL_NAME = "sage-kit"
SKILL_ROOT = Path("skills") / SKILL_NAME
MANIFEST_NAME = "manifest.json"
PACKAGE_DOC_PATTERN = re.compile(
    r'package-doc\("([A-Za-z0-9_./-]+\.(?:md|json))(?:#[A-Za-z0-9_-]+)?"\)'
)
VERSION_PATTERN = re.compile(r'^__version__\s*=\s*"([^"]+)"$', re.MULTILINE)
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class SkillBundleArtifact:
    archive: Path
    checksum: Path
    sha256: str
    manifest: dict[str, object]


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def package_version(repository: Path) -> str:
    source = (repository / "sagekit" / "__init__.py").read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(source)
    if match is None:
        raise ValueError("sagekit.__version__ is missing")
    return match.group(1)


def _safe_relative(path: str) -> PurePosixPath:
    candidate = PurePosixPath(path)
    if (
        candidate.is_absolute()
        or "\\" in path
        or not candidate.parts
        or any(
            part in {"", ".", ".."} or ":" in part or "\x00" in part
            for part in candidate.parts
        )
    ):
        raise ValueError(f"unsafe bundle path: {path!r}")
    return candidate


def skill_files(repository: Path) -> tuple[Path, ...]:
    root = repository / SKILL_ROOT
    if not root.is_dir():
        raise FileNotFoundError(root)
    files = tuple(
        sorted(
            (
                path
                for path in root.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.name != MANIFEST_NAME
                and path.suffix != ".pyc"
            ),
            key=lambda path: path.relative_to(root).as_posix(),
        )
    )
    if not files or not (root / "SKILL.md").is_file():
        raise ValueError("Skill bundle requires skills/sage-kit/SKILL.md")
    return files


def bundle_records(repository: Path) -> list[dict[str, object]]:
    root = repository / SKILL_ROOT
    records: list[dict[str, object]] = []
    for path in skill_files(repository):
        content = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        _safe_relative(relative)
        records.append(
            {
                "path": relative,
                "sha256": sha256_bytes(content),
                "size_bytes": len(content),
            }
        )
    return records


def aggregate_digest(records: Iterable[dict[str, object]]) -> str:
    ordered = sorted(
        (
            {
                "path": str(record["path"]),
                "sha256": str(record["sha256"]),
                "size_bytes": int(record["size_bytes"]),
            }
            for record in records
        ),
        key=lambda record: record["path"],
    )
    canonical = json.dumps(
        ordered, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(canonical)


def build_manifest(repository: Path) -> dict[str, object]:
    records = bundle_records(repository)
    return {
        "schema_version": 1,
        "kind": "sage-kit-skill-bundle",
        "skill_name": SKILL_NAME,
        "version": package_version(repository),
        "files": records,
        "aggregate_sha256": aggregate_digest(records),
    }


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def build_skill_bundle(repository: Path, output_directory: Path) -> SkillBundleArtifact:
    repository = repository.resolve(strict=True)
    output_directory.mkdir(parents=True, exist_ok=True)
    version = package_version(repository)
    archive = output_directory / f"{SKILL_NAME}-skill-v{version}.zip"
    checksum = output_directory / f"{archive.name}.sha256"
    manifest = build_manifest(repository)
    root = repository / SKILL_ROOT

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for record in manifest["files"]:
            relative = _safe_relative(str(record["path"]))
            bundle.writestr(
                _zip_info(f"{SKILL_NAME}/{relative.as_posix()}"),
                (root.joinpath(*relative.parts)).read_bytes(),
            )
        manifest_bytes = (
            json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        bundle.writestr(_zip_info(f"{SKILL_NAME}/{MANIFEST_NAME}"), manifest_bytes)

    digest = sha256_bytes(archive.read_bytes())
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    return SkillBundleArtifact(archive, checksum, digest, manifest)


def _read_manifest(bundle: zipfile.ZipFile) -> dict[str, object]:
    try:
        payload = json.loads(bundle.read(f"{SKILL_NAME}/{MANIFEST_NAME}"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("bundle has no valid manifest") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("kind") != "sage-kit-skill-bundle"
        or payload.get("skill_name") != SKILL_NAME
        or not isinstance(payload.get("version"), str)
        or not isinstance(payload.get("files"), list)
        or not isinstance(payload.get("aggregate_sha256"), str)
    ):
        raise ValueError("bundle manifest has an invalid shape")
    return payload


def extract_and_verify_skill_bundle(archive: Path, destination: Path) -> dict[str, object]:
    archive = archive.resolve(strict=True)
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        manifest = _read_manifest(bundle)
        records = manifest["files"]
        expected_names = {f"{SKILL_NAME}/{MANIFEST_NAME}"}
        validated: list[tuple[PurePosixPath, bytes]] = []
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("bundle manifest contains an invalid file record")
            relative = _safe_relative(str(record.get("path", "")))
            relative_text = relative.as_posix()
            if relative_text in seen:
                raise ValueError(f"bundle manifest duplicates {relative_text!r}")
            seen.add(relative_text)
            content = bundle.read(f"{SKILL_NAME}/{relative_text}")
            if record.get("size_bytes") != len(content) or record.get("sha256") != sha256_bytes(content):
                raise ValueError(f"bundle file digest mismatch: {relative_text}")
            expected_names.add(f"{SKILL_NAME}/{relative_text}")
            validated.append((relative, content))
        if set(bundle.namelist()) != expected_names:
            raise ValueError("bundle archive and manifest disagree")
        if manifest["aggregate_sha256"] != aggregate_digest(records):
            raise ValueError("bundle aggregate digest mismatch")

        target = destination / SKILL_NAME
        if target.exists():
            raise FileExistsError(f"explicit destination already exists: {target}")
        target.mkdir(parents=True)
        try:
            for relative, content in validated:
                output = target.joinpath(*relative.parts)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(content)
            (target / MANIFEST_NAME).write_bytes(
                bundle.read(f"{SKILL_NAME}/{MANIFEST_NAME}")
            )
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise
    return manifest


def package_doc_locators(skill_root: Path) -> set[str]:
    return {
        locator
        for path in skill_root.rglob("*")
        if path.is_file() and path.suffix in {".md", ".yaml", ".yml"}
        for locator in PACKAGE_DOC_PATTERN.findall(path.read_text(encoding="utf-8"))
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build an explicit, host-installable SAGE-Kit Skill bundle."
    )
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    artifact = build_skill_bundle(args.repository, args.output_dir)
    print(
        json.dumps(
            {
                "archive": str(artifact.archive),
                "checksum": str(artifact.checksum),
                "sha256": artifact.sha256,
                "version": artifact.manifest["version"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
