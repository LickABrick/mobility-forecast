#!/usr/bin/env python3
"""Run bounded autonomous phase-1 checkpoints with an OpenAI usage guard.

This controller is intentionally deterministic. Each Hermes invocation receives
one checkpoint, is supervised for time and quota, and must leave verification
and git evidence. The controller never redeems banked resets and never pushes.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".nightly"
LOG = RUNTIME / "controller.log"
HERMES = pathlib.Path("/home/guus/.local/bin/hermes")
HERMES_PYTHON = pathlib.Path("/home/guus/.hermes/hermes-agent/venv/bin/python")
DEADLINE = dt.datetime.fromisoformat(
    os.environ.get("MOBILITY_NIGHTLY_DEADLINE", "2026-08-26T03:01:16+02:00")
)
SAFETY_FLOOR = float(os.environ.get("MOBILITY_USAGE_FLOOR", "15"))
POLL_SECONDS = 60
MAX_RUN_SECONDS = 35 * 60

PROMPT = """Work on exactly one coherent checkpoint in the Mobility Forecast repository.

Mandatory workflow:
1. Read AGENTS.md, CONTRIBUTING.md, docs/NIGHTLY_PLAN.md and docs/PROJECT_STATUS.md fully.
2. Inspect git status and recent commits. Preserve and finish or safely repair any partial work left by an interrupted prior run.
3. Select the highest-priority ready unchecked checkpoint. Do only that checkpoint or one clearly documented sub-slice if it is too large.
4. Use TDD for executable behavior. Keep domain logic pure and typed. Never access production Home Assistant, real route APIs, vehicle services, notifications, credentials or personal data.
5. Review every applicable configuration file and schema at this checkpoint. Update configuration/docs only when justified; never silently change defaults.
6. Run python scripts/check_checkpoint.py plus relevant tests/linters. Independently inspect the diff for secrets, privacy leaks and scope creep.
7. Update docs/NIGHTLY_PLAN.md and docs/PROJECT_STATUS.md with exact evidence, remaining risks and the next checkpoint.
8. Make one logical Conventional Commit (two only if an independently reviewable foundation is strictly required). Never amend/rebase/reset existing commits. Never push or create a remote.
9. Verify git status and the new commit, then exit. Do not continue to another checkpoint; the controller must measure quota first.

If all checkpoints are complete, perform one bounded audit/fix checkpoint rather than inventing scope. If blocked, document the exact blocker and leave the worktree clean or clearly explained.
"""


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def log(message: str) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    line = f"{now().isoformat(timespec='seconds')} {message}"
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def usage() -> dict[str, Any] | None:
    result = subprocess.run(
        [str(HERMES_PYTHON), str(ROOT / "scripts/codex_usage.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    try:
        payload = json.loads(result.stdout.strip())
    except (json.JSONDecodeError, TypeError):
        log(f"usage unavailable rc={result.returncode}")
        return None
    if not payload.get("available"):
        log(f"usage unavailable reason={payload.get('unavailable_reason')}")
        return None
    return payload


def windows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("label", "")).lower(): item for item in payload.get("windows", [])}


def remaining(item: dict[str, Any] | None) -> float | None:
    if not item:
        return None
    value = item.get("remaining_percent")
    return float(value) if isinstance(value, (int, float)) else None


def reset_time(item: dict[str, Any] | None) -> dt.datetime | None:
    raw = item.get("reset_at") if item else None
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(str(raw)).astimezone()
    except ValueError:
        return None


def quota_action(payload: dict[str, Any] | None) -> tuple[str, dt.datetime | None]:
    if payload is None:
        return "stop-unmeasurable", None
    by_label = windows(payload)
    session = by_label.get("session")
    weekly = by_label.get("weekly")
    session_left = remaining(session)
    weekly_left = remaining(weekly)
    log(f"usage session={session_left}% weekly={weekly_left}% floor={SAFETY_FLOOR}%")
    if weekly_left is None or weekly_left <= SAFETY_FLOOR:
        return "stop-weekly", None
    if session_left is None:
        return "stop-unmeasurable", None
    if session_left <= SAFETY_FLOOR:
        reset = reset_time(session)
        if reset and reset < DEADLINE:
            return "pause-session", reset
        return "stop-session", reset
    return "continue", None


def stop_process(process: subprocess.Popen[str], reason: str) -> None:
    if process.poll() is not None:
        return
    log(f"terminating agent pid={process.pid} reason={reason}")
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=30)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=10)


def run_checkpoint(index: int) -> str:
    output_path = RUNTIME / f"agent-{index:02d}.log"
    command = [
        str(HERMES),
        "chat",
        "-Q",
        "--provider",
        "openai-codex",
        "-m",
        "gpt-5.6-sol",
        "-t",
        "terminal,file,web,skills",
        "--max-turns",
        "40",
        "--source",
        "tool",
        "-q",
        PROMPT,
    ]
    log(f"starting checkpoint agent={index}")
    started = time.monotonic()
    with output_path.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            text=True,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        while process.poll() is None:
            elapsed = time.monotonic() - started
            if now() >= DEADLINE:
                stop_process(process, "deadline")
                return "deadline"
            if elapsed >= MAX_RUN_SECONDS:
                stop_process(process, "per-run-timeout")
                return "timeout"
            action, reset = quota_action(usage())
            if action != "continue":
                stop_process(process, action)
                if action == "pause-session" and reset:
                    return f"pause:{reset.isoformat()}"
                return action
            time.sleep(POLL_SECONDS)
        log(f"agent={index} exited rc={process.returncode}")
        return f"exit:{process.returncode}"


def validate() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_checkpoint.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    log(f"post-run validation rc={result.returncode} output={(result.stdout + result.stderr).strip()[-500:]}")
    status = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    log("git status: " + status.stdout.strip().replace("\n", " | "))


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    log(f"controller started deadline={DEADLINE.isoformat()} floor={SAFETY_FLOOR}%")
    index = 1
    while now() < DEADLINE:
        action, reset = quota_action(usage())
        if action == "pause-session" and reset:
            wake = min(reset + dt.timedelta(minutes=2), DEADLINE)
            seconds = max(0.0, (wake - now()).total_seconds())
            log(f"pausing until normal session reset wake={wake.isoformat()}")
            time.sleep(seconds)
            continue
        if action != "continue":
            log(f"controller stopped before run reason={action}")
            break

        result = run_checkpoint(index)
        validate()
        if result.startswith("pause:"):
            reset = dt.datetime.fromisoformat(result.split(":", 1)[1]).astimezone()
            wake = min(reset + dt.timedelta(minutes=2), DEADLINE)
            log(f"run hit session floor; pausing until {wake.isoformat()}")
            time.sleep(max(0.0, (wake - now()).total_seconds()))
        elif result in {"stop-weekly", "stop-session", "stop-unmeasurable", "deadline"}:
            log(f"controller stopping after run result={result}")
            break
        else:
            index += 1
            time.sleep(90)

    validate()
    final = usage()
    if final:
        quota_action(final)
    log("controller finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
