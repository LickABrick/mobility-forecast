"""Offline relative links/anchors, YAML examples and high-risk documentation drift."""

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]


def anchors(text):
    result = set()
    counts = {}
    for heading in re.findall(r"^#{1,6}\s+(.+)$", text, re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(f"{slug}-{count}" if count else slug)
    return result


def check_link(source, link):
    link = unquote(link)
    parsed = urlsplit(link)
    if parsed.scheme or link.startswith("//"):
        if parsed.netloc == "github.com" and "/blob/" in parsed.path:
            parts = parsed.path.strip("/").split("/")
            # Only this repository's docs are resolved locally; other repositories
            # remain approved external references, unless masquerading as this one.
            if parts[1:2] == ["mobility-forecast"] or parts[:2] == [
                "LickABrick",
                "mobility-forecast",
            ]:
                assert parsed.scheme == "https" and not parsed.query, (
                    f"Malformed documentation URL: {link}"
                )
                assert parts[:4] == [
                    "LickABrick",
                    "mobility-forecast",
                    "blob",
                    "main",
                ], f"Unexpected repository/branch: {link}"
                assert len(parts) > 5 and parts[4] == "docs", (
                    f"Unexpected documentation URL: {link}"
                )
                check_link(
                    ROOT / "README.md",
                    "/".join(parts[4:])
                    + (f"#{parsed.fragment}" if parsed.fragment else ""),
                )
        return
    target = (source.parent / parsed.path).resolve() if parsed.path else source
    assert target.is_relative_to(ROOT) and target.exists(), f"{source}: missing {link}"
    if parsed.fragment and target.suffix == ".md":
        assert parsed.fragment in anchors(target.read_text()), (
            f"{source}: missing anchor {link}"
        )


def main():
    files = [
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "SECURITY.md",
        *sorted((ROOT / "docs").rglob("*.md")),
    ]
    for path in files:
        if "archive" in path.parts:
            continue  # Immutable historical reports retain original link context.
        text = path.read_text()
        for link in re.findall(r"\]\(([^\s)]+)\)", text):
            check_link(path, link)
        for link in re.findall(r'(?:src|srcset)="([^"]+)"', text):
            check_link(path, link)
        for example in re.findall(r"```yaml\n(.*?)```", text, re.S):
            yaml.safe_load(example)
        assert not re.search(
            r"No EV/charging features|Full suite: \d+ passed|HACS validation needs a GitHub token",
            text,
            re.I,
        ), path
    manifest = json.loads(
        (ROOT / "custom_components/mobility_forecast/manifest.json").read_text()
    )
    assert (
        manifest["documentation"] == "https://github.com/LickABrick/mobility-forecast"
    )
    for path in (ROOT / ".github").rglob("*.yml"):
        yaml.safe_load(path.read_text())
    for name in ("strings.json", "translations/en.json", "translations/nl.json"):
        data = json.loads(
            (ROOT / "custom_components/mobility_forecast" / name).read_text()
        )
        for target in re.findall(r"https://[^\s)\"]+", json.dumps(data)):
            check_link(ROOT / "README.md", target)
    import ast

    flow = ast.parse(
        (ROOT / "custom_components/mobility_forecast/config_flow.py").read_text()
    )
    constants = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in flow.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    assert constants["DOCS_REPOSITORY"] == "LickABrick/mobility-forecast"
    assert constants["DOCS_BRANCH"] == "main"
    targets = next(
        ast.literal_eval(node.value)
        for node in flow.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "HELP_TARGETS" for t in node.targets
        )
    )
    for target in targets.values():
        check_link(ROOT / "docs/index.md", target)
    print(
        "Documentation links, anchors, YAML examples, help targets and drift checks passed."
    )


if __name__ == "__main__":
    main()
