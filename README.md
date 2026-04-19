# shotframe

Wrap raw phone screenshots in a polished canvas for app-store listings.
One YAML config, one Python script, one command — no design tool required.

![before and after](https://raw.githubusercontent.com/amidexe/shotframe/main/examples/after/welcome.png)

## What it does

Takes a folder of phone screenshots, adds a neutral-grey backdrop, a bold
two-line headline on top, soft drop shadow and rounded corners around the
device screen, and renders polished PNGs ready for RuStore, Google Play,
or App Store listings. All text is rendered via SVG and `rsvg-convert`,
so Cyrillic (and anything else `fontconfig` can find) is first-class.

## Requirements

- Python 3.9+
- [PyYAML](https://pypi.org/project/PyYAML/)
- `rsvg-convert` (Debian/Ubuntu: `apt install librsvg2-bin`; macOS: `brew install librsvg`)
- A display sans font with the glyphs you need. The default template uses
  Inter Display — install on Debian/Ubuntu with `apt install fonts-inter`,
  or override `caption.font_family` in the config.

## Install

```bash
git clone https://github.com/amidexe/shotframe.git
cd shotframe
pip install -r requirements.txt   # just PyYAML
```

There is no package yet — call `shotframe.py` directly.

## Quick start

```bash
cd examples
python ../shotframe.py shotframe.yaml
# polished PNGs appear in ./after/
```

## Your own project

Put your phone screenshots in a folder, then:

```bash
python shotframe.py --init              # writes shotframe.yaml next to your config
# edit shotframe.yaml — set input_dir / output_dir / screenshots
python shotframe.py shotframe.yaml
```

## Interactive mode

Don't want to hand-edit YAML? Point `input_dir` at your screenshots and run:

```bash
python shotframe.py shotframe.yaml --interactive
```

The script walks through every PNG in `input_dir` and prompts you for a
caption (up to two lines; empty line ends the caption; `skip` drops the
screenshot). Rendering happens right after.

## Config

```yaml
input_dir: before        # folder with raw screenshots
output_dir: after        # where polished PNGs go

canvas:
  width: 1200
  height: 2500
  bg_top: "#F5F5F7"
  bg_bottom: "#E8E8EB"

screenshot:
  width: 918             # rendered size of the device screen inside the canvas
  height: 2060
  y: 360                 # vertical offset from the top of the canvas
  radius: 48             # corner radius
  frame_color: "#FFFFFF" # visible only around fully-transparent screenshots

caption:
  font_family: "'Inter Display', Inter, sans-serif"
  font_size: 88
  font_weight: 800
  letter_spacing: -2.5
  color: "#14141A"
  line1_y: 210           # y of the first caption line (SVG baseline)
  line2_y: 305

shadow:
  blur: 34
  offset_y: 14
  opacity: 0.16

screenshots:
  - file: 01-welcome.png
    caption:
      - Line one
      - Line two
  - file: 02-feature.png
    caption: Single-line caption
```

Every top-level section is optional — missing keys fall back to sensible
defaults matching the example above.

## Why

Most store-listing tools are heavy (Figma templates, paid mockup generators,
proprietary SaaS). `shotframe` is ~250 lines of Python that you read in one
sitting, keep in your repo, and wire into CI if you feel like it.

## License

MIT. See [LICENSE](LICENSE).
