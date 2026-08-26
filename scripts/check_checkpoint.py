#!/usr/bin/env python3
"""Deterministic repository checkpoint validation.

The validator intentionally uses only the Python standard library so it can run
before the development environment exists. Project-specific tools are added as
configuration appears.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
IGNORED_PARTS = {".git", ".nightly", ".venv", "__pycache__"}


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(f"failed: {' '.join(command)}")


def iter_files(suffix: str):
    for path in ROOT.rglob(f"*{suffix}"):
        if not any(part in IGNORED_PARTS for part in path.parts):
            yield path


def validate_json() -> None:
    for path in iter_files(".json"):
        json.loads(path.read_text(encoding="utf-8"))


def validate_toml() -> None:
    for path in iter_files(".toml"):
        tomllib.loads(path.read_text(encoding="utf-8"))


def validate_required_files() -> None:
    required = (
        "AGENTS.md",
        "CONTRIBUTING.md",
        "README.md",
        "docs/NIGHTLY_PLAN.md",
        "docs/PROJECT_STATUS.md",
    )
    missing = [path for path in required if not (ROOT / path).is_file()]
    if missing:
        raise SystemExit(f"missing required files: {', '.join(missing)}")


def main() -> int:
    validate_required_files()
    validate_json()
    validate_toml()
    run(["git", "diff", "--check"])

    pyproject = ROOT / "pyproject.toml"
    if pyproject.exists():
        run(
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "src",
                "tests",
                "custom_components",
            ]
        )
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])

    print("checkpoint validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
