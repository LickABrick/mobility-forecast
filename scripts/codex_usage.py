#!/usr/bin/env python3
"""Print a secret-free OpenAI Codex account-usage snapshot as JSON."""

from __future__ import annotations

import json
import pathlib
import sys

HERMES_SOURCE = pathlib.Path("/home/guus/.hermes/hermes-agent")
sys.path.insert(0, str(HERMES_SOURCE))

from agent.account_usage import fetch_account_usage  # noqa: E402


def main() -> int:
    snapshot = fetch_account_usage("openai-codex")
    if snapshot is None:
        print(json.dumps({"available": False, "reason": "no snapshot"}))
        return 2

    windows = []
    for window in snapshot.windows:
        used = window.used_percent
        windows.append(
            {
                "label": window.label,
                "used_percent": used,
                "remaining_percent": None if used is None else max(0.0, 100.0 - used),
                "reset_at": None if window.reset_at is None else window.reset_at.isoformat(),
            }
        )

    print(
        json.dumps(
            {
                "available": not bool(snapshot.unavailable_reason),
                "provider": snapshot.provider,
                "plan": snapshot.plan,
                "fetched_at": snapshot.fetched_at.isoformat(),
                "windows": windows,
                "details": list(snapshot.details),
                "unavailable_reason": snapshot.unavailable_reason,
            },
            sort_keys=True,
        )
    )
    return 0 if not snapshot.unavailable_reason else 2


if __name__ == "__main__":
    raise SystemExit(main())
