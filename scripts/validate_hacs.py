"""Validate repository metadata with the schemas bundled in HACS Action."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "mobility_forecast"


class Schema(Protocol):
    """Minimal callable boundary exposed by the pinned HACS image."""

    def __call__(self, value: object) -> object: ...


def _schema(name: str) -> Schema:
    module = import_module("custom_components.hacs.utils.validate")
    return cast(Schema, getattr(module, name))


def _read_object(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path.relative_to(ROOT)} must contain a JSON object")
    mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in mapping):
        raise TypeError(f"{path.relative_to(ROOT)} keys must be strings")
    return cast(dict[str, object], mapping)


def main() -> None:
    """Fail when either current HACS metadata schema rejects the repository."""
    _schema("HACS_MANIFEST_JSON_SCHEMA")(_read_object(ROOT / "hacs.json"))
    _schema("INTEGRATION_MANIFEST_JSON_SCHEMA")(
        _read_object(INTEGRATION / "manifest.json")
    )
    print("HACS local metadata schemas: PASS")


if __name__ == "__main__":
    main()
