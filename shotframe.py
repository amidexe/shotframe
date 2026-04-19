#!/usr/bin/env python3
"""shotframe — wrap phone screenshots in a polished canvas for app-store listings.

Usage:
    shotframe.py                       # read ./shotframe.yaml
    shotframe.py path/to/config.yaml
    shotframe.py --init                # scaffold shotframe.yaml
    shotframe.py --interactive         # prompt for a caption per PNG in input_dir
"""
import argparse
import base64
import glob
import os
import subprocess
import sys

import yaml


DEFAULT_CONFIG = {
    "input_dir": ".",
    "output_dir": "processed",
    "canvas": {
        "width": 1200,
        "height": 2500,
        "bg_top": "#F5F5F7",
        "bg_bottom": "#E8E8EB",
    },
    "screenshot": {
        "width": 918,
        "height": 2060,
        "y": 360,
        "radius": 48,
        "frame_color": "#FFFFFF",
    },
    "caption": {
        "font_family": "'Inter Display', Inter, sans-serif",
        "font_size": 88,
        "font_weight": 800,
        "letter_spacing": -2.5,
        "color": "#14141A",
        "line1_y": 210,
        "line2_y": 305,
    },
    "shadow": {
        "blur": 34,
        "offset_y": 14,
        "opacity": 0.16,
    },
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


def render(cfg, entries, base_dir):
    in_dir = os.path.join(base_dir, cfg["input_dir"])
    out_dir = os.path.join(base_dir, cfg["output_dir"])
    os.makedirs(out_dir, exist_ok=True)

    c = cfg["canvas"]
    s = cfg["screenshot"]
    t = cfg["caption"]
    sh = cfg["shadow"]

    shot_x = (c["width"] - s["width"]) // 2

    for entry in entries:
        fname = entry["file"]
        caption = entry.get("caption", [])
        if isinstance(caption, str):
            caption = [caption]
        l1 = caption[0] if len(caption) > 0 else ""
        l2 = caption[1] if len(caption) > 1 else ""

        src = os.path.join(in_dir, fname)
        if not os.path.exists(src):
            print(f"skip missing: {fname}", file=sys.stderr)
            continue

        with open(src, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")

        svg = SVG_TEMPLATE.format(
            W=c["width"], H=c["height"], W_HALF=c["width"] // 2,
            BG_TOP=c["bg_top"], BG_BOTTOM=c["bg_bottom"],
            SX=shot_x, SY=s["y"], SW=s["width"], SH=s["height"],
            R=s["radius"], FRAME_COLOR=s["frame_color"],
            SHADOW_BLUR=sh["blur"], SHADOW_DY=sh["offset_y"],
            SHADOW_OPACITY=sh["opacity"],
            FONT_FAMILY=t["font_family"], FONT_SIZE=t["font_size"],
            FONT_WEIGHT=t["font_weight"], LETTER_SPACING=t["letter_spacing"],
            TEXT_COLOR=t["color"], L1Y=t["line1_y"], L2Y=t["line2_y"],
            B64=b64, L1=l1, L2=l2,
        )

        svg_tmp = os.path.join(out_dir, fname.replace(".png", ".svg"))
        out_png = os.path.join(out_dir, fname)
        with open(svg_tmp, "w") as f:
            f.write(svg)

        subprocess.run(["rsvg-convert", "-o", out_png, svg_tmp], check=True)
        os.remove(svg_tmp)
        print(f"ok: {fname}")


def interactive_collect(cfg, base_dir):
    in_dir = os.path.join(base_dir, cfg["input_dir"])
    pngs = sorted(glob.glob(os.path.join(in_dir, "*.png")))
    if not pngs:
        print(f"no PNGs in {in_dir}", file=sys.stderr)
        return []

    entries = []
    for path in pngs:
        fname = os.path.basename(path)
        print(f"\n📸 {fname}")
        print("  Caption — up to 2 lines, empty line to finish, 'skip' to skip:")
        lines = []
        while len(lines) < 2:
            line = input(f"  {len(lines) + 1}> ").strip()
            if line.lower() == "skip":
                lines = None
                break
            if not line:
                break
            lines.append(line)
        if lines is None:
            continue
        entries.append({"file": fname, "caption": lines})
    return entries


def write_default_config(path):
    if os.path.exists(path):
        print(f"refuse to overwrite existing {path}", file=sys.stderr)
        sys.exit(1)
    sample = dict(DEFAULT_CONFIG)
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


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("config", nargs="?", default="shotframe.yaml",
                   help="path to config (default: shotframe.yaml)")
    p.add_argument("--init", action="store_true",
                   help="write a starter shotframe.yaml in the current dir")
    p.add_argument("--interactive", action="store_true",
                   help="prompt for captions instead of reading the config list")
    args = p.parse_args()

    if args.init:
        write_default_config("shotframe.yaml")
        return

    if not os.path.exists(args.config):
        print(f"no config: {args.config} (try --init)", file=sys.stderr)
        sys.exit(1)

    with open(args.config) as f:
        user_cfg = yaml.safe_load(f) or {}

    cfg = merge_config(user_cfg)
    base_dir = os.path.dirname(os.path.abspath(args.config)) or "."

    if args.interactive:
        entries = interactive_collect(cfg, base_dir)
    else:
        entries = cfg.get("screenshots", [])
        if not entries:
            print("config has no 'screenshots:' list; use --interactive",
                  file=sys.stderr)
            sys.exit(1)

    render(cfg, entries, base_dir)


if __name__ == "__main__":
    main()
