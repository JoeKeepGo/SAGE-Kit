"""Build the complete, explicit release asset set for SAGE-Kit."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


_BUNDLE_SCRIPT = Path(__file__).with_name("build_skill_bundle.py")
_BUNDLE_SPEC = importlib.util.spec_from_file_location("build_skill_bundle", _BUNDLE_SCRIPT)
if _BUNDLE_SPEC is None or _BUNDLE_SPEC.loader is None:
    raise RuntimeError("skill bundle builder is not importable")
skill_bundle = importlib.util.module_from_spec(_BUNDLE_SPEC)
sys.modules[_BUNDLE_SPEC.name] = skill_bundle
_BUNDLE_SPEC.loader.exec_module(skill_bundle)


SOURCE_EXCLUDED_PARTS = frozenset(
    {
        ".git",
        ".worktrees",
        ".pytest_cache",
        "__pycache__",
        "build",
        "dist",
        "sagekit.egg-info",
    }
)


@dataclass(frozen=True)
class ReleaseAssets:
    version: str
    wheel: Path
    wheel_checksum: Path
    source_archive: Path
    source_checksum: Path
    skill_bundle: Path
    skill_checksum: Path
    skill_manifest: Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksum(path: Path) -> Path:
    checksum = path.with_name(f"{path.name}.sha256")
    checksum.write_text(f"{sha256_file(path)}  {path.name}\n", encoding="ascii")
    return checksum


def asset_names(version: str) -> frozenset[str]:
    wheel = f"sagekit-{version}-py3-none-any.whl"
    source = f"sagekit-{version}.tar.gz"
    skill = f"sage-kit-skill-{version}.zip"
    return frozenset(
        {
            wheel,
            f"{wheel}.sha256",
            source,
            f"{source}.sha256",
            skill,
            f"{skill}.sha256",
            f"sage-kit-skill-{version}.manifest.json",
        }
    )


def _source_files(repository: Path, output_directory: Path) -> tuple[Path, ...]:
    ignored_output = output_directory.resolve()
    files: list[Path] = []
    for path in repository.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(repository)
        if any(part in SOURCE_EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix == ".pyc":
            continue
        try:
            path.resolve().relative_to(ignored_output)
        except ValueError:
            files.append(path)
    return tuple(sorted(files, key=lambda path: path.relative_to(repository).as_posix()))


def build_source_archive(repository: Path, output_directory: Path, version: str) -> Path:
    archive = output_directory / f"sagekit-{version}.tar.gz"
    prefix = f"sagekit-{version}"
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for path in _source_files(repository, output_directory):
                    relative = path.relative_to(repository).as_posix()
                    info = tar.gettarinfo(str(path), arcname=f"{prefix}/{relative}")
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    with path.open("rb") as source:
                        tar.addfile(info, source)
    return archive


def build_wheel(repository: Path, output_directory: Path, version: str) -> Path:
    command = [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "pip",
        "wheel",
        str(repository),
        "--wheel-dir",
        str(output_directory),
        "--no-index",
        "--no-deps",
        "--no-build-isolation",
    ]
    completed = subprocess.run(
        command,
        cwd=repository,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            "wheel build failed: " + (completed.stderr or completed.stdout).strip()
        )
    wheel = output_directory / f"sagekit-{version}-py3-none-any.whl"
    if not wheel.is_file():
        raise RuntimeError(f"release wheel is missing: {wheel.name}")
    return wheel


def _verify_checksum(path: Path, checksum: Path) -> None:
    expected = f"{sha256_file(path)}  {path.name}\n"
    if checksum.read_text(encoding="ascii") != expected:
        raise ValueError(f"invalid checksum asset: {checksum.name}")


def verify_release_assets(assets: ReleaseAssets) -> None:
    output = assets.wheel.parent
    version = assets.version
    if {path.name for path in output.iterdir()} != asset_names(version):
        raise ValueError("release asset inventory is incomplete or contains unexpected files")
    _verify_checksum(assets.wheel, assets.wheel_checksum)
    _verify_checksum(assets.source_archive, assets.source_checksum)
    _verify_checksum(assets.skill_bundle, assets.skill_checksum)
    with tarfile.open(assets.source_archive, "r:gz") as source:
        names = source.getnames()
        prefix = f"sagekit-{version}/"
        if not names or any(not name.startswith(prefix) or ".." in Path(name).parts for name in names):
            raise ValueError("source archive has unsafe paths")
        if f"{prefix}pyproject.toml" not in names:
            raise ValueError("source archive lacks pyproject.toml")
    with zipfile.ZipFile(assets.skill_bundle) as bundle:
        embedded_manifest = bundle.read("sage-kit/manifest.json")
    if embedded_manifest != assets.skill_manifest.read_bytes():
        raise ValueError("Skill bundle manifest sidecar differs from embedded manifest")
    manifest = json.loads(embedded_manifest)
    if manifest.get("version") != version:
        raise ValueError("Skill bundle manifest version differs from release version")
    if manifest.get("aggregate_sha256") != skill_bundle.aggregate_digest(manifest.get("files", [])):
        raise ValueError("Skill bundle manifest aggregate digest is invalid")


def build_release_assets(repository: Path, output_directory: Path) -> ReleaseAssets:
    repository = repository.resolve(strict=True)
    output_directory.mkdir(parents=True, exist_ok=True)
    if any(output_directory.iterdir()):
        raise ValueError("release output directory must be empty")
    version = skill_bundle.package_version(repository)
    wheel = build_wheel(repository, output_directory, version)
    source_archive = build_source_archive(repository, output_directory, version)
    bundle = skill_bundle.build_skill_bundle(repository, output_directory)
    assets = ReleaseAssets(
        version=version,
        wheel=wheel,
        wheel_checksum=write_checksum(wheel),
        source_archive=source_archive,
        source_checksum=write_checksum(source_archive),
        skill_bundle=bundle.archive,
        skill_checksum=bundle.checksum,
        skill_manifest=bundle.manifest_path,
    )
    verify_release_assets(assets)
    return assets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the complete SAGE-Kit release asset inventory."
    )
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    assets = build_release_assets(args.repository, args.output_dir)
    print(
        json.dumps(
            {name: str(getattr(assets, name)) for name in assets.__dataclass_fields__},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
