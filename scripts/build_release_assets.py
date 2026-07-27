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
from pathlib import Path, PurePosixPath


_BUNDLE_SCRIPT = Path(__file__).with_name("build_skill_bundle.py")
_BUNDLE_SPEC = importlib.util.spec_from_file_location("build_skill_bundle", _BUNDLE_SCRIPT)
if _BUNDLE_SPEC is None or _BUNDLE_SPEC.loader is None:
    raise RuntimeError("skill bundle builder is not importable")
skill_bundle = importlib.util.module_from_spec(_BUNDLE_SPEC)
sys.modules[_BUNDLE_SPEC.name] = skill_bundle
_BUNDLE_SPEC.loader.exec_module(skill_bundle)


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


@dataclass(frozen=True)
class TrackedSourceEntry:
    path: Path
    relative: PurePosixPath
    git_mode: int


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


def verify_tracked_worktree_clean(repository: Path) -> None:
    checks = (
        ("unstaged tracked changes", ("diff", "--quiet", "--exit-code")),
        ("staged tracked changes", ("diff", "--cached", "--quiet", "--exit-code")),
    )
    for label, arguments in checks:
        completed = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 1:
            raise ValueError(
                f"release source archive requires no {label}; commit or revert them first"
            )
        if completed.returncode:
            raise RuntimeError(f"could not verify {label} before source archive build")


def _safe_tracked_path(value: bytes) -> PurePosixPath:
    try:
        text = value.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise ValueError("tracked source path is not valid UTF-8") from exc
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or "\\" in text
        or not path.parts
        or any(part in {"", ".", ".."} or ":" in part or "\x00" in part for part in path.parts)
    ):
        raise ValueError(f"unsafe tracked source path: {text!r}")
    return path


def tracked_source_entries(repository: Path) -> tuple[TrackedSourceEntry, ...]:
    completed = subprocess.run(
        ["git", "-C", str(repository), "ls-files", "-s", "-z"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError("could not read frozen Git tracked manifest")
    root = repository.resolve(strict=True)
    entries: list[TrackedSourceEntry] = []
    seen: set[PurePosixPath] = set()
    for record in completed.stdout.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode_text, _object_id, stage_text = metadata.split(b" ")
            git_mode = int(mode_text, 8)
        except (ValueError, TypeError) as exc:
            raise ValueError("malformed Git tracked manifest entry") from exc
        if stage_text != b"0" or git_mode not in {0o100644, 0o100755}:
            raise ValueError("tracked manifest contains an unsupported Git entry")
        relative = _safe_tracked_path(raw_path)
        if relative in seen:
            raise ValueError(f"tracked manifest duplicates {relative.as_posix()!r}")
        seen.add(relative)
        path = root.joinpath(*relative.parts)
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise ValueError(f"tracked source path escapes repository: {relative}") from exc
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"tracked source is not a regular file: {relative}")
        entries.append(TrackedSourceEntry(path, relative, git_mode))
    if not entries:
        raise ValueError("frozen Git tracked manifest is empty")
    return tuple(sorted(entries, key=lambda entry: entry.relative.as_posix()))


def write_source_archive(
    archive: Path, entries: tuple[TrackedSourceEntry, ...], version: str
) -> Path:
    prefix = f"sagekit-{version}"
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.GNU_FORMAT) as tar:
                for entry in entries:
                    info = tar.gettarinfo(
                        str(entry.path), arcname=f"{prefix}/{entry.relative.as_posix()}"
                    )
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    info.mode = 0o755 if entry.git_mode == 0o100755 else 0o644
                    info.pax_headers = {}
                    with entry.path.open("rb") as source:
                        tar.addfile(info, source)
    return archive


def build_source_archive(repository: Path, output_directory: Path, version: str) -> Path:
    verify_tracked_worktree_clean(repository)
    archive = output_directory / f"sagekit-{version}.tar.gz"
    return write_source_archive(archive, tracked_source_entries(repository), version)


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
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Skill bundle contains duplicate archive names")
        embedded_manifest = bundle.read("sage-kit/manifest.json")
        if embedded_manifest != assets.skill_manifest.read_bytes():
            raise ValueError("Skill bundle manifest sidecar differs from embedded manifest")
        manifest = json.loads(embedded_manifest)
        if manifest.get("version") != version:
            raise ValueError("Skill bundle manifest version differs from release version")
        records = manifest.get("files")
        if not isinstance(records, list):
            raise ValueError("Skill bundle manifest has no file records")
        expected_names = {"sage-kit/manifest.json"}
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Skill bundle manifest has an invalid file record")
            relative = skill_bundle._safe_relative(str(record.get("path", "")))
            relative_text = relative.as_posix()
            if relative_text in seen:
                raise ValueError("Skill bundle manifest duplicates a file record")
            seen.add(relative_text)
            name = f"sage-kit/{relative_text}"
            expected_names.add(name)
            payload = bundle.read(name)
            if record.get("size_bytes") != len(payload) or record.get("sha256") != skill_bundle.sha256_bytes(payload):
                raise ValueError(f"Skill bundle payload digest mismatch: {relative_text}")
        if set(names) != expected_names:
            raise ValueError("Skill bundle archive names do not match its manifest")
        if manifest.get("aggregate_sha256") != skill_bundle.aggregate_digest(records):
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
