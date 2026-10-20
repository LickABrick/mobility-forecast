"""Offline documentation checker validates links rather than contacting providers."""

import pytest

from scripts.check_docs import ROOT, anchors, check_link, main


def test_current_documentation():
    main()


def test_anchor_and_missing_path():
    assert anchors("# Heading\n## Heading\n") == {"heading", "heading-1"}
    with pytest.raises(AssertionError):
        check_link(ROOT / "README.md", "docs/does-not-exist.md")
    with pytest.raises(AssertionError):
        check_link(ROOT / "README.md", "docs/index.md#does-not-exist")
