# Mobility Forecast brand

The original route mark moves from solid measured travel to dotted forecast travel,
ending in a directional chevron. It is not an EV/battery logo and does not use
Home Assistant, HACS or map-provider trademarks.

- `icon.svg` / `icon.png`: transparent square, 512×512.
- `logo.svg` / `logo.png`: teal wordmark for light backgrounds, 720×256.
- `logo-dark.svg` / `logo-dark.png`: pale wordmark for dark backgrounds.
- SVG wordmarks are paths, with no remote resources or required installed fonts.
- Teal `#087F8C`, forecast blue `#368BE8`, ink `#145E69`, pale `#E0F3F6`.

Keep clear space around the mark, preserve proportions, and do not add shadows or
battery symbols. Prefer SVG; use PNG where SVG is not supported. The route artwork
is provided under the repository license. DejaVu Sans Bold letter outlines retain
the notice in `FONT-LICENSE.txt`.

To regenerate offline, install `cairosvg` and `fonttools` in a separate environment
and run `python assets/brand/generate.py` on a machine with DejaVu Sans Bold at the
path in that script. These are **not integration runtime dependencies**.

HACS has no repository-local custom logo field used here; `hacs.json` is unchanged.
These files do not make HA display an official branded integration tile. A future
submission to `home-assistant/brands` must follow its then-current size, naming,
review and licensing requirements; these are editable source assets, not a claim
of submission or acceptance.
