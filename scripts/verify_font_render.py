#!/usr/bin/env python3
"""Render ASCII alphanumerics and perform basic raster sanity checks."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
CELL_WIDTH = 220
CELL_HEIGHT = 230
GLYPH_TOP = 36
INK_THRESHOLD = 128


def render_and_check(font_path: Path, output_path: Path, size: int) -> list[str]:
    font = ImageFont.truetype(str(font_path), size)
    columns = 6
    rows = (len(ALNUM) + columns - 1) // columns
    image = Image.new("RGB", (columns * CELL_WIDTH, rows * CELL_HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    failures: list[str] = []

    for index, character in enumerate(ALNUM):
        row, column = divmod(index, columns)
        x = column * CELL_WIDTH
        y = row * CELL_HEIGHT
        draw.rectangle((x, y, x + CELL_WIDTH - 1, y + CELL_HEIGHT - 1), outline="#dddddd")
        draw.text((x + 8, y + 8), character, font=ImageFont.truetype(str(font_path), 24), fill="#777777")

        bbox = draw.textbbox((0, 0), character, font=font)
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if width <= 0 or height <= 0:
            failures.append(f"{character}: empty metrics")
            continue

        text_x = x + (CELL_WIDTH - width) // 2 - bbox[0]
        text_y = y + GLYPH_TOP - bbox[1]
        draw.text((text_x, text_y), character, font=font, fill="black")

        gray = image.crop((x + 2, y + 28, x + CELL_WIDTH - 2, y + CELL_HEIGHT - 2)).convert("L")
        ink_mask = gray.point(lambda pixel: 255 if pixel < INK_THRESHOLD else 0)
        ink_count = gray.width * gray.height - ink_mask.histogram()[0]
        if ink_count == 0:
            failures.append(f"{character}: no rendered pixels")
            continue

        ink_bbox = ink_mask.getbbox()
        if ink_bbox is None:
            failures.append(f"{character}: no ink bounding box")
            continue
        ink_width = ink_bbox[2] - ink_bbox[0]
        ink_height = ink_bbox[3] - ink_bbox[1]
        ink_ratio = ink_count / (gray.width * gray.height)
        if ink_width >= gray.width - 4 or ink_height >= gray.height - 4:
            failures.append(f"{character}: ink reaches cell boundary ({ink_width}x{ink_height})")
        if ink_ratio > 0.65:
            failures.append(f"{character}: excessive ink area ({ink_ratio:.1%})")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True, help="font to render")
    parser.add_argument("--output", type=Path, required=True, help="specimen PNG to write")
    parser.add_argument("--size", type=int, default=160, help="glyph pixel size (default: 160)")
    args = parser.parse_args()
    if not args.font.is_file():
        parser.error(f"font not found: {args.font}")
    if args.size < 16:
        parser.error("--size must be at least 16")

    failures = render_and_check(args.font, args.output, args.size)
    print(f"wrote {args.output} ({len(ALNUM)} glyphs)")
    if failures:
        print("render verification failed:")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print("render verification passed: no blank, overflowing, or excessively filled glyphs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
