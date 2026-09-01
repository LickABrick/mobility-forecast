#!/usr/bin/env python3
"""Build and verify the deterministic Mobility Forecast manual-test ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = PurePosixPath("custom_components/mobility_forecast")
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FILE_MODE = stat.S_IFREG | 0o644
FORBIDDEN_PARTS = {
    "__pycache__",
    ".storage",
    ".env",
    "secrets.yaml",
}
REQUIRED_FILES = {
    COMPONENT / "manifest.json",
    COMPONENT / "strings.json",
    COMPONENT / "translations/en.json",
}


class PackageError(RuntimeError):
    """Raised when the package cannot be proven safe and reproducible."""


def _tracked_component_files() -> tuple[PurePosixPath, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", str(COMPONENT)],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    paths = tuple(
        sorted(
            PurePosixPath(raw.decode("utf-8"))
            for raw in result.stdout.split(b"\0")
            if raw
        )
    )
    if not paths:
        raise PackageError("no tracked integration files found")
    if not set(paths) >= REQUIRED_FILES:
        missing = ", ".join(str(path) for path in sorted(REQUIRED_FILES - set(paths)))
        raise PackageError(f"required package files missing: {missing}")

    for path in paths:
        if not path.is_relative_to(COMPONENT) or path == COMPONENT:
            raise PackageError(f"file is outside integration package: {path}")
        if FORBIDDEN_PARTS.intersection(path.parts):
            raise PackageError(f"forbidden runtime or private path: {path}")
        source = ROOT.joinpath(*path.parts)
        if source.is_symlink() or not source.is_file():
            raise PackageError(f"package source must be a regular file: {path}")
    return paths


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checksum_path(archive: Path) -> Path:
    return archive.with_suffix(archive.suffix + ".sha256")


def _write_checksum(archive: Path) -> str:
    digest = _sha256(archive)
    _checksum_path(archive).write_text(
        f"{digest}  {archive.name}\n",
        encoding="ascii",
        newline="\n",
    )
    return digest


def _read_expected_checksum(archive: Path) -> str:
    sidecar = _checksum_path(archive)
    try:
        line = sidecar.read_text(encoding="ascii")
    except FileNotFoundError as error:
        raise PackageError(f"checksum sidecar missing: {sidecar.name}") from error
    expected_line_suffix = f"  {archive.name}\n"
    if not line.endswith(expected_line_suffix):
        raise PackageError("checksum sidecar has an invalid filename or format")
    digest = line[: -len(expected_line_suffix)]
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise PackageError("checksum sidecar has an invalid SHA-256 digest")
    return digest


def check_package(archive: Path) -> str:
    """Verify checksum, exact tracked scope, metadata, and source bytes."""

    archive = archive.resolve()
    if not archive.is_file():
        raise PackageError(f"archive missing: {archive}")
    expected_digest = _read_expected_checksum(archive)
    actual_digest = _sha256(archive)
    if actual_digest != expected_digest:
        raise PackageError("checksum mismatch")

    expected_paths = _tracked_component_files()
    expected_names = [str(path) for path in expected_paths]
    try:
        with zipfile.ZipFile(archive) as package:
            infos = package.infolist()
            names = [info.filename for info in infos]
            if names != expected_names:
                raise PackageError(
                    "archive contents differ from tracked integration files"
                )
            for path, info in zip(expected_paths, infos, strict=True):
                if info.date_time != FIXED_TIMESTAMP:
                    raise PackageError(f"non-deterministic timestamp: {path}")
                if info.compress_type != zipfile.ZIP_STORED:
                    raise PackageError(f"unexpected compression method: {path}")
                if info.create_system != 3 or info.external_attr >> 16 != FILE_MODE:
                    raise PackageError(f"unexpected file mode: {path}")
                source = ROOT.joinpath(*path.parts).read_bytes()
                if package.read(info) != source:
                    raise PackageError(f"archive file differs from checkout: {path}")
            corrupt = package.testzip()
            if corrupt is not None:
                raise PackageError(f"corrupt archive member: {corrupt}")
    except zipfile.BadZipFile as error:
        raise PackageError("invalid ZIP archive") from error
    return actual_digest


def build_package(output_dir: Path) -> Path:
    """Create the archive from only tracked integration files, then verify it."""

    paths = _tracked_component_files()
    manifest_path = ROOT.joinpath(*COMPONENT.parts, "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = manifest.get("version")
    if not isinstance(version, str) or not version.strip():
        raise PackageError("manifest version must be a non-empty string")

    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"mobility_forecast-{version}.zip"
    temporary = archive.with_suffix(archive.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as package:
            for path in paths:
                info = zipfile.ZipInfo(str(path), date_time=FIXED_TIMESTAMP)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = FILE_MODE << 16
                package.writestr(info, ROOT.joinpath(*path.parts).read_bytes())
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)

    digest = _write_checksum(archive)
    if check_package(archive) != digest:
        raise PackageError("post-build digest changed unexpectedly")
    return archive


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument(
        "--check",
        type=Path,
        metavar="ARCHIVE",
        help="verify an existing archive and its .sha256 sidecar",
    )
    operation.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "dist",
        help="build output directory (default: dist)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        if args.check is not None:
            archive = args.check
            digest = check_package(archive)
            print(f"package check: PASS ({digest})")
        else:
            archive = build_package(args.output_dir)
            print(f"built: {archive}")
            print(f"checksum: {_checksum_path(archive)}")
            print("package check: PASS")
    except (
        OSError,
        PackageError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as error:
        print(f"package check: FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
