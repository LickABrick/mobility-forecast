"""Offline asset generation only: pip install cairosvg fonttools.

Uses DejaVu Sans Bold outlines (see FONT-LICENSE.txt), never a runtime font.
"""

from pathlib import Path

import cairosvg
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).parent
MARK = """<path d="M104 392V248c0-80 64-144 144-144h32" fill="none" stroke="#087F8C" stroke-width="48" stroke-linecap="round"/>
<path d="M280 104h128v144" fill="none" stroke="#368BE8" stroke-width="48" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1 68"/>
<circle cx="104" cy="392" r="40" fill="#087F8C"/>
<path d="m350 241 58 59 58-59" fill="none" stroke="#368BE8" stroke-width="32" stroke-linecap="round" stroke-linejoin="round"/>"""


def svg(width, height, content):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img"><title>Mobility Forecast</title>{content}</svg>\n'


def wordmark(color):
    font = TTFont("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    result = []
    for label, y in (("Mobility", 112), ("Forecast", 197)):
        x = 0
        paths = []
        for character in label:
            name = cmap[ord(character)]
            pen = SVGPathPen(glyphs)
            glyphs[name].draw(pen)
            paths.append(
                f'<path transform="translate({x} 0)" d="{pen.getCommands()}"/>'
            )
            x += glyphs[name].width
        result.append(
            f'<g fill="{color}" transform="translate(282 {y}) scale(.039 -.039)">{"".join(paths)}</g>'
        )
    return "".join(result)


def main():
    assets = {"icon": svg(512, 512, MARK)}
    for name, color in (("logo", "#145E69"), ("logo-dark", "#E0F3F6")):
        assets[name] = svg(
            720, 256, f'<g transform="scale(.5)">{MARK}</g>' + wordmark(color)
        )
    for name, content in assets.items():
        (ROOT / f"{name}.svg").write_text(content)
        cairosvg.svg2png(
            bytestring=content.encode(), write_to=str(ROOT / f"{name}.png")
        )

    # HA local assets derive from the same outlined artwork. Trim logo whitespace.
    from io import BytesIO

    from PIL import Image

    target = ROOT.parents[1] / "custom_components/mobility_forecast/brand"
    target.mkdir(exist_ok=True)
    for source, name in (
        ("icon", "icon"),
        ("logo", "logo"),
        ("logo-dark", "dark_logo"),
    ):
        image = Image.open(
            BytesIO(cairosvg.svg2png(bytestring=assets[source].encode()))
        ).convert("RGBA")
        if source != "icon":
            image = image.crop(image.getbbox())
        for scale, suffix in ((1, ""), (2, "@2x")):
            height = 256 * scale
            width = round(image.width * height / image.height)
            image.resize((width, height), Image.Resampling.LANCZOS).save(
                target / f"{name}{suffix}.png", optimize=True
            )


if __name__ == "__main__":
    main()
