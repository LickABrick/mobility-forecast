"""Publication fails closed on ambiguous identity, repeats and missing approval."""

from copy import deepcopy

import pytest

from scripts.check_release_candidate import validate_candidate


def candidate():
    repo = {"full_name": "LickABrick/mobility-forecast"}
    return dict(
        repository=repo["full_name"],
        branch="main",
        default_branch="main",
        sha="a" * 40,
        head="a" * 40,
        version="1.0.0",
        approved=True,
        tags=[],
        prs=[
            dict(
                number=12,
                merged_at="2026-10-20",
                base={"ref": "main", "repo": repo},
                head={"ref": "release-please--branches--main", "repo": repo},
                merge_commit_sha="a" * 40,
                title="chore(main): release 1.0.0",
                body="## 1.0.0\n\nFeatures",
                labels=[{"name": "autorelease: pending"}],
            )
        ],
    )


def test_candidate():
    assert validate_candidate(**candidate()) == 12


@pytest.mark.parametrize(
    "field,value",
    [
        ("branch", "other"),
        ("default_branch", "master"),
        ("head", "b" * 40),
        ("approved", False),
        ("repository", "fork/repo"),
        ("version", "1.0.1"),
        ("tags", [{"name": "v1.0.0"}]),
    ],
)
def test_invalid_context(field, value):
    data = candidate()
    data[field] = value
    with pytest.raises(AssertionError):
        validate_candidate(**data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("merge_commit_sha", "b" * 40),
        ("title", "fix: ordinary PR"),
        ("body", "not a release"),
        ("merged_at", None),
        ("labels", []),
    ],
)
def test_not_release_merge(field, value):
    data = candidate()
    data["prs"][0][field] = value
    with pytest.raises(AssertionError):
        validate_candidate(**data)


def test_multiple_candidates():
    data = candidate()
    data["prs"].append(deepcopy(data["prs"][0]))
    with pytest.raises(AssertionError):
        validate_candidate(**data)
