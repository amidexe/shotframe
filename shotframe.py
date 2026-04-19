#!/usr/bin/env python3
"""shotframe — wrap phone screenshots in a polished canvas for app-store listings.

Usage:
    shotframe.py                       # scan current dir, prompt for captions
    shotframe.py path/to/folder        # scan that folder, prompt for captions
    shotframe.py path/to/config.yaml   # render from a config
    shotframe.py --init                # scaffold shotframe.yaml in current dir
"""
import argparse
import base64
import glob
import os
import struct
import subprocess
import sys

import yaml


MAX_CAPTION_CHARS = 28


DEFAULT_CONFIG = {
    "input_dir": ".",
    "output_dir": "processed",
    "layout_mode": "portrait",
    "background": {
        "top": "#F5F5F7",
        "bottom": "#E8E8EB",
    },
    "layout": {
        # All ratios are relative to the input PNG's width.
        "side_padding": 0.118,
        "caption_height": 0.370,
        "bottom_padding": 0.222,
        "corner_radius": 0.044,
    },
    "caption": {
        "font_family": "'Inter Display', Inter, sans-serif",
        "font_size": 0.082,
        "font_weight": 800,
        "letter_spacing": -2.5,
        "color": "#14141A",
        "line1_y": 0.194,
        "line2_y": 0.282,
    },
    "landscape": {
        # 16:9 landscape canvas: phone on the right, caption on the left.
        "canvas_width": 1920,
        "canvas_height": 1080,
        "phone_margin_v": 60,
        "phone_margin_right": 140,
        "text_margin_left": 140,
        "font_family": "'Inter Display', Inter, sans-serif",
        "font_size": 72,
        "font_weight": 800,
        "letter_spacing": -2.5,
        "line_height": 1.15,
        "color": "#14141A",
        "corner_radius": 48,
    },
    "shadow": {
        "blur": 0.031,
        "offset_y": 0.013,
        "opacity": 0.16,
    },
    "frame_color": "#FFFFFF",
    "screenshots": [],
}


SVG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{BG_TOP}"/>
      <stop offset="100%" stop-color="{BG_BOTTOM}"/>
    </linearGradient>
    <filter id="ds" x="-15%" y="-15%" width="130%" height="130%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="{SHADOW_BLUR}"/>
      <feOffset dx="0" dy="{SHADOW_DY}" result="offsetblur"/>
      <feComponentTransfer>
        <feFuncA type="linear" slope="{SHADOW_OPACITY}"/>
      </feComponentTransfer>
      <feMerge>
        <feMergeNode/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <clipPath id="rounded">
      <rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" rx="{R}" ry="{R}"/>
    </clipPath>
  </defs>

  <rect width="{W}" height="{H}" fill="url(#bg)"/>

  <text text-anchor="middle"
        font-family="{FONT_FAMILY}"
        font-size="{FONT_SIZE}" font-weight="{FONT_WEIGHT}"
        letter-spacing="{LETTER_SPACING}"
        fill="{TEXT_COLOR}">
    <tspan x="{W_HALF}" y="{L1Y}">{L1}</tspan>
    <tspan x="{W_HALF}" y="{L2Y}">{L2}</tspan>
  </text>

  <rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" rx="{R}" ry="{R}"
        fill="{FRAME_COLOR}" filter="url(#ds)"/>
  <image xlink:href="data:image/png;base64,{B64}"
         x="{SX}" y="{SY}" width="{SW}" height="{SH}"
         clip-path="url(#rounded)"
         preserveAspectRatio="xMidYMid slice"/>
</svg>
"""


LANDSCAPE_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{BG_TOP}"/>
      <stop offset="100%" stop-color="{BG_BOTTOM}"/>
    </linearGradient>
    <filter id="ds" x="-15%" y="-15%" width="130%" height="130%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="{SHADOW_BLUR}"/>
      <feOffset dx="0" dy="{SHADOW_DY}" result="offsetblur"/>
      <feComponentTransfer>
        <feFuncA type="linear" slope="{SHADOW_OPACITY}"/>
      </feComponentTransfer>
      <feMerge>
        <feMergeNode/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <clipPath id="rounded">
      <rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" rx="{R}" ry="{R}"/>
    </clipPath>
  </defs>

  <rect width="{W}" height="{H}" fill="url(#bg)"/>

  <text text-anchor="start"
        font-family="{FONT_FAMILY}"
        font-size="{FONT_SIZE}" font-weight="{FONT_WEIGHT}"
        letter-spacing="{LETTER_SPACING}"
        fill="{TEXT_COLOR}">
    <tspan x="{TEXT_X}" y="{L1Y}">{L1}</tspan>
    <tspan x="{TEXT_X}" y="{L2Y}">{L2}</tspan>
  </text>

  <rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" rx="{R}" ry="{R}"
        fill="{FRAME_COLOR}" filter="url(#ds)"/>
  <image xlink:href="data:image/png;base64,{B64}"
         x="{SX}" y="{SY}" width="{SW}" height="{SH}"
         clip-path="url(#rounded)"
         preserveAspectRatio="xMidYMid slice"/>
</svg>
"""


def png_dimensions(path):
    """Read width/height from a PNG header without decoding the image."""
    with open(path, "rb") as f:
        header = f.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    w, h = struct.unpack(">II", header[16:24])
    return w, h


def normalize_caption(caption):
    if isinstance(caption, str):
        caption = [caption]
    return [str(line) for line in caption[:2]]


def render(cfg, entries, base_dir):
    if cfg.get("layout_mode", "portrait") == "landscape_16_9":
        render_landscape(cfg, entries, base_dir)
        return
    render_portrait(cfg, entries, base_dir)


def render_portrait(cfg, entries, base_dir):
    in_dir = os.path.join(base_dir, cfg["input_dir"])
    out_dir = os.path.join(base_dir, cfg["output_dir"])
    os.makedirs(out_dir, exist_ok=True)

    bg = cfg["background"]
    L = cfg["layout"]
    T = cfg["caption"]
    SH = cfg["shadow"]

    for entry in entries:
        fname = entry["file"]
        caption = normalize_caption(entry.get("caption", []))

        too_long = [(i + 1, len(c)) for i, c in enumerate(caption)
                    if len(c) > MAX_CAPTION_CHARS]
        if too_long:
            for ln, length in too_long:
                print(f"skip {fname}: line {ln} is {length} chars, "
                      f"max is {MAX_CAPTION_CHARS}", file=sys.stderr)
            continue

        l1 = caption[0] if len(caption) > 0 else ""
        l2 = caption[1] if len(caption) > 1 else ""

        src = os.path.join(in_dir, fname)
        if not os.path.exists(src):
            print(f"skip missing: {fname}", file=sys.stderr)
            continue

        in_w, in_h = png_dimensions(src)

        side = round(in_w * L["side_padding"])
        cap_h = round(in_w * L["caption_height"])
        bot = round(in_w * L["bottom_padding"])
        canvas_w = in_w + 2 * side
        canvas_h = cap_h + in_h + bot
        shot_x = side
        shot_y = cap_h
        radius = round(in_w * L["corner_radius"])

        font_size = round(in_w * T["font_size"])
        l1y = round(in_w * T["line1_y"])
        l2y = round(in_w * T["line2_y"])

        shadow_blur = round(in_w * SH["blur"])
        shadow_dy = round(in_w * SH["offset_y"])

        with open(src, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")

        svg = SVG_TEMPLATE.format(
            W=canvas_w, H=canvas_h, W_HALF=canvas_w // 2,
            BG_TOP=bg["top"], BG_BOTTOM=bg["bottom"],
            SX=shot_x, SY=shot_y, SW=in_w, SH=in_h,
            R=radius, FRAME_COLOR=cfg["frame_color"],
            SHADOW_BLUR=shadow_blur, SHADOW_DY=shadow_dy,
            SHADOW_OPACITY=SH["opacity"],
            FONT_FAMILY=T["font_family"], FONT_SIZE=font_size,
            FONT_WEIGHT=T["font_weight"], LETTER_SPACING=T["letter_spacing"],
            TEXT_COLOR=T["color"], L1Y=l1y, L2Y=l2y,
            B64=b64, L1=l1, L2=l2,
        )

        svg_tmp = os.path.join(out_dir, fname.replace(".png", ".svg"))
        out_png = os.path.join(out_dir, fname)
        with open(svg_tmp, "w") as f:
            f.write(svg)

        subprocess.run(["rsvg-convert", "-o", out_png, svg_tmp], check=True)
        os.remove(svg_tmp)
        print(f"ok: {fname} ({in_w}x{in_h} -> {canvas_w}x{canvas_h})")


def render_landscape(cfg, entries, base_dir):
    in_dir = os.path.join(base_dir, cfg["input_dir"])
    out_dir = os.path.join(base_dir, cfg["output_dir"])
    os.makedirs(out_dir, exist_ok=True)

    bg = cfg["background"]
    L = cfg["landscape"]
    SH = cfg["shadow"]

    W = L["canvas_width"]
    H = L["canvas_height"]

    # Relative ratios for the shadow reuse the portrait shadow scale —
    # drop shadow looks good at the same visual weight as the portrait one,
    # so we scale by canvas width similarly.
    shadow_blur = round(W * SH["blur"] * 0.4)
    shadow_dy = round(W * SH["offset_y"] * 0.4)

    for entry in entries:
        fname = entry["file"]
        caption = normalize_caption(entry.get("caption", []))

        too_long = [(i + 1, len(c)) for i, c in enumerate(caption)
                    if len(c) > MAX_CAPTION_CHARS]
        if too_long:
            for ln, length in too_long:
                print(f"skip {fname}: line {ln} is {length} chars, "
                      f"max is {MAX_CAPTION_CHARS}", file=sys.stderr)
            continue

        src = os.path.join(in_dir, fname)
        if not os.path.exists(src):
            print(f"skip missing: {fname}", file=sys.stderr)
            continue

        in_w, in_h = png_dimensions(src)

        phone_h = H - 2 * L["phone_margin_v"]
        phone_w = round(phone_h * in_w / in_h)
        shot_x = W - L["phone_margin_right"] - phone_w
        shot_y = L["phone_margin_v"]

        font_size = L["font_size"]
        line_spacing = L["line_height"] * font_size
        n_lines = len([c for c in caption if c]) or 1
        block_h = n_lines * line_spacing
        start_y = (H - block_h) / 2
        l1y = round(start_y + font_size * 0.8)
        l2y = round(l1y + line_spacing)

        l1 = caption[0] if len(caption) > 0 else ""
        l2 = caption[1] if len(caption) > 1 else ""

        with open(src, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")

        svg = LANDSCAPE_SVG.format(
            W=W, H=H,
            BG_TOP=bg["top"], BG_BOTTOM=bg["bottom"],
            SX=shot_x, SY=shot_y, SW=phone_w, SH=phone_h,
            R=L["corner_radius"], FRAME_COLOR=cfg["frame_color"],
            SHADOW_BLUR=shadow_blur, SHADOW_DY=shadow_dy,
            SHADOW_OPACITY=SH["opacity"],
            FONT_FAMILY=L["font_family"], FONT_SIZE=font_size,
            FONT_WEIGHT=L["font_weight"], LETTER_SPACING=L["letter_spacing"],
            TEXT_COLOR=L["color"],
            TEXT_X=L["text_margin_left"], L1Y=l1y, L2Y=l2y,
            B64=b64, L1=l1, L2=l2,
        )

        svg_tmp = os.path.join(out_dir, fname.replace(".png", ".svg"))
        out_png = os.path.join(out_dir, fname)
        with open(svg_tmp, "w") as f:
            f.write(svg)

        subprocess.run(["rsvg-convert", "-o", out_png, svg_tmp], check=True)
        os.remove(svg_tmp)
        print(f"ok: {fname} ({in_w}x{in_h} -> {W}x{H})")


def interactive_collect(cfg, base_dir):
    in_dir = os.path.join(base_dir, cfg["input_dir"])
    pngs = sorted(glob.glob(os.path.join(in_dir, "*.png")))
    if not pngs:
        print(f"no PNGs in {in_dir}", file=sys.stderr)
        return []

    entries = []
    for path in pngs:
        fname = os.path.basename(path)
        print(f"\n{fname}")
        print(f"  Caption — up to 2 lines, max {MAX_CAPTION_CHARS} chars each.")
        print("  Empty line to finish, 'skip' to drop this screenshot.")
        lines = []
        while len(lines) < 2:
            line = input(f"  {len(lines) + 1}> ").strip()
            if line.lower() == "skip":
                lines = None
                break
            if not line:
                break
            if len(line) > MAX_CAPTION_CHARS:
                print(f"  too long ({len(line)} chars, max {MAX_CAPTION_CHARS}) "
                      f"— try again")
                continue
            lines.append(line)
        if lines is None:
            continue
        entries.append({"file": fname, "caption": lines})
    return entries


def write_default_config(path):
    if os.path.exists(path):
        print(f"refuse to overwrite existing {path}", file=sys.stderr)
        sys.exit(1)
    sample = {k: dict(v) if isinstance(v, dict) else v
              for k, v in DEFAULT_CONFIG.items()}
    sample["screenshots"] = [
        {"file": "01-welcome.png", "caption": ["Line one", "Line two"]},
        {"file": "02-feature.png", "caption": "Single-line caption"},
    ]
    with open(path, "w") as f:
        yaml.safe_dump(sample, f, allow_unicode=True, sort_keys=False)
    print(f"wrote {path}")


def merge_config(user_cfg):
    merged = {k: dict(v) if isinstance(v, dict) else v
              for k, v in DEFAULT_CONFIG.items()}
    for k, v in user_cfg.items():
        if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged


def run_folder(folder):
    cfg = merge_config({})
    cfg["input_dir"] = "."
    base_dir = os.path.abspath(folder)
    entries = interactive_collect(cfg, base_dir)
    if entries:
        render(cfg, entries, base_dir)


def run_config(config_path):
    with open(config_path) as f:
        user_cfg = yaml.safe_load(f) or {}
    cfg = merge_config(user_cfg)
    base_dir = os.path.dirname(os.path.abspath(config_path)) or "."
    entries = cfg.get("screenshots", [])
    if not entries:
        entries = interactive_collect(cfg, base_dir)
        if not entries:
            return
    render(cfg, entries, base_dir)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("path", nargs="?", default=".",
                   help="folder with PNGs, or path to a config YAML (default: .)")
    p.add_argument("--init", action="store_true",
                   help="write a starter shotframe.yaml in the current dir")
    args = p.parse_args()

    if args.init:
        write_default_config("shotframe.yaml")
        return

    if not os.path.exists(args.path):
        print(f"no such path: {args.path}", file=sys.stderr)
        sys.exit(1)

    if os.path.isdir(args.path):
        auto_yaml = os.path.join(args.path, "shotframe.yaml")
        if os.path.exists(auto_yaml):
            run_config(auto_yaml)
        else:
            run_folder(args.path)
    else:
        run_config(args.path)


if __name__ == "__main__":
    main()
