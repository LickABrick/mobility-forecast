"""Fail-closed publication identity checks over GitHub REST snapshots (no writes)."""

import argparse
import json
import re
from pathlib import Path


def validate_candidate(
    *, repository, branch, default_branch, sha, head, version, prs, tags, approved
):
    assert approved, "Explicit publish approval is required"
    assert repository == "LickABrick/mobility-forecast", "Unexpected repository"
    assert branch == default_branch == "main", "Publish only from main"
    assert sha == head, "Default branch moved after validation; dispatch again"
    assert re.fullmatch(r"[0-9a-f]{40}", sha), "Invalid candidate SHA"
    pending = [
        pr
        for pr in prs
        if pr.get("merged_at")
        and pr.get("base", {}).get("ref") == branch
        and any(
            label["name"] == "autorelease: pending" for label in pr.get("labels", [])
        )
    ]
    assert len(pending) == 1, "Expected exactly one pending merged release PR"
    pr = pending[0]
    assert pr["base"]["repo"]["full_name"] == repository
    assert pr["head"]["repo"]["full_name"] == repository
    assert pr["head"]["ref"] == "release-please--branches--main", (
        "Not a Release Please root PR"
    )
    assert pr["merge_commit_sha"] == sha, (
        "Candidate must be release PR merge/squash/rebase tip; later commits require a new release PR"
    )
    assert pr["title"] == f"chore(main): release {version}", (
        "Release PR version mismatch"
    )
    assert f"## {version}" in pr.get("body", ""), "Missing Release Please version body"
    assert f"v{version}" not in {tag["name"] for tag in tags}, (
        "Tag already exists: never overwrite or repeat publication"
    )
    return pr["number"]


def main():
    import os

    from check_release import validate

    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text())
    version = validate(tag=f"v{Path('version.txt').read_text().strip()}")
    number = validate_candidate(
        repository=os.environ["GITHUB_REPOSITORY"],
        branch=os.environ["GITHUB_REF_NAME"],
        default_branch=data["repository"]["default_branch"],
        sha=os.environ["GITHUB_SHA"],
        head=data["head"]["sha"],
        version=version,
        prs=data["prs"],
        tags=data["tags"],
        approved=os.environ.get("PUBLISH_APPROVED") == "true",
    )
    print(
        f"Validated release PR #{number} at {os.environ['GITHUB_SHA']} for v{version}"
    )


if __name__ == "__main__":
    main()
