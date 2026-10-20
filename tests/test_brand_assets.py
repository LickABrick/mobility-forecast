"""Offline structural checks; rendering was also inspected during authoring."""

from pathlib import Path
from xml.etree import ElementTree

from PIL import Image

ROOT = Path(__file__).parents[1]


def test_brand_assets_are_local_transparent_and_bounded():
    for name in ("icon", "logo", "logo-dark"):
        path = ROOT / "assets" / "brand" / f"{name}.svg"
        content = path.read_text()
        tree = ElementTree.fromstring(content)
        assert tree.tag.endswith("svg")
        assert "<text" not in content
        assert "href=" not in content
        assert path.stat().st_size < 100_000
        png = path.with_suffix(".png")
        with Image.open(png) as image:
            assert image.mode == "RGBA"
            assert image.size == ((512, 512) if name == "icon" else (720, 256))
            assert image.getpixel((0, 0))[3] == 0
            assert image.getbbox() is not None
        assert png.stat().st_size < 100_000


def test_ha_local_brand_dimensions():
    root = ROOT / "custom_components/mobility_forecast/brand"
    for name in ("icon", "logo", "dark_logo"):
        for scale, suffix in ((1, ""), (2, "@2x")):
            path = root / f"{name}{suffix}.png"
            with Image.open(path) as image:
                assert image.height == 256 * scale
                assert image.width >= image.height
                if name == "icon":
                    assert image.width == image.height
                assert image.mode == "RGBA"
                assert image.getextrema()[3][0] == 0
                assert image.getextrema()[3][1] == 255
                image.verify()
            assert path.stat().st_size < 150_000


def test_readme_brand_links_exist():
    import re

    content = (ROOT / "README.md").read_text()
    paths = re.findall(r'(?:src|srcset)="(assets/brand/[^\"]+)"', content)
    assert len(paths) == 2
    assert all((ROOT / path).is_file() for path in paths)
