#!/usr/bin/env python3
"""Combine glyphs from two fonts into one font.

The inputs are intentionally local files.  Font licenses and the exact files
used for a build should be reviewable and reproducible by the caller.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from functools import lru_cache
import sys
from datetime import datetime
from pathlib import Path



def mapped_codepoints(font) -> set[int]:
    """Return all Unicode codepoints represented by *font*."""

    return {
        codepoint
        for table in font["cmap"].tables
        for codepoint in table.cmap
        if codepoint <= 0x10FFFF
    }


NAMED_RANGE_ALIASES = {
    "cjk": "kanji",
    "digits": "numbers",
    "kana": "kana",
    "latin1": "latin_1",
    "latin-ext": "latin_extended",
}
SUPPORTED_NAMED_RANGES = {
    "ascii", "latin", "latin_1", "latin_extended", "greek", "cyrillic",
    "numbers", "punctuation", "symbols", "emoji", "fullwidth", "halfwidth",
    "math", "arrows", "box_drawing", "dingbats", "currency", "hiragana",
    "katakana", "kana", "japanese", "kanji", "jis_level_1", "jis_level_2",
}


def _ranges(*ranges: tuple[int, int]) -> set[int]:
    return {codepoint for start, end in ranges for codepoint in range(start, end + 1)}


@lru_cache(maxsize=None)
def named_codepoints(name: str) -> set[int]:
    """Return the Unicode codepoints represented by a named character set."""

    name = NAMED_RANGE_ALIASES.get(name, name)
    simple_ranges = {
        "ascii": ((0x0000, 0x007F),),
        "latin": ((0x0000, 0x024F), (0x1E00, 0x1EFF), (0x2C60, 0x2C7F), (0xA720, 0xA7FF)),
        "latin_1": ((0x0000, 0x00FF),),
        "latin_extended": ((0x0100, 0x024F), (0x1E00, 0x1EFF)),
        "greek": ((0x0370, 0x03FF), (0x1F00, 0x1FFF)),
        "cyrillic": ((0x0400, 0x052F), (0x2DE0, 0x2DFF), (0xA640, 0xA69F)),
        "numbers": ((0x0030, 0x0039), (0x0660, 0x0669), (0x06F0, 0x06F9), (0xFF10, 0xFF19)),
        "punctuation": ((0x2000, 0x206F), (0x2E00, 0x2E7F), (0x3000, 0x303F)),
        "symbols": ((0x2000, 0x2BFF), (0xFE00, 0xFE6F)),
        "emoji": ((0x1F000, 0x1FAFF),),
        "fullwidth": ((0xFF01, 0xFFEF),),
        "halfwidth": ((0xFF61, 0xFF9F),),
        "math": ((0x2100, 0x214F), (0x2190, 0x21FF), (0x2200, 0x22FF)),
        "arrows": ((0x2190, 0x21FF), (0x27F0, 0x27FF), (0x2900, 0x297F)),
        "box_drawing": ((0x2500, 0x257F),),
        "dingbats": ((0x2700, 0x27BF),),
        "currency": ((0x20A0, 0x20CF), (0xFFE0, 0xFFE6)),
    }
    if name in simple_ranges:
        return _ranges(*simple_ranges[name])
    if name == "hiragana":
        return _ranges((0x3040, 0x309F))
    if name == "katakana":
        return _ranges((0x30A0, 0x30FF))
    if name == "kana":
        return named_codepoints("hiragana") | named_codepoints("katakana") | _ranges(
            (0x31F0, 0x31FF), (0x1B000, 0x1B0FF)
        )
    if name == "japanese":
        return named_codepoints("kana") | named_codepoints("kanji") | named_codepoints("punctuation")
    if name == "kanji":
        return _ranges(
            (0x3400, 0x4DBF), (0x4E00, 0x9FFF),
            (0xF900, 0xFAFF), (0x20000, 0x2FA1F),
        )
    if name in ("jis_level_1", "jis_level_2"):
        # JIS X 0208 rows 16-47 and 48-84 are the level 1 and level 2
        # kanji respectively. EUC-JP directly encodes a JIS row/cell as
        # 0xA0 + row/cell, so the standard library provides the mapping.
        rows = range(16, 48) if name == "jis_level_1" else range(48, 85)
        result: set[int] = set()
        for row in rows:
            for cell in range(1, 95):
                try:
                    character = bytes((0xA0 + row, 0xA0 + cell)).decode("euc_jp")
                except UnicodeDecodeError:
                    continue
                if len(character) == 1:
                    result.add(ord(character))
        return result
    raise ValueError(
        f"unknown named range: {name}; use --help for supported names or a hexadecimal range"
    )


def parse_ranges(values: list[str] | None) -> set[int] | None:
    """Parse named ranges and repeatable hexadecimal ranges."""

    if not values:
        return None
    result: set[int] = set()
    for value in values:
        for item in value.split(","):
            bounds = item.strip().lower()
            if bounds in NAMED_RANGE_ALIASES or bounds in SUPPORTED_NAMED_RANGES:
                result.update(named_codepoints(bounds))
                continue
            parts = bounds.split("-", 1)
            try:
                def parse_endpoint(endpoint: str) -> int:
                    return int(endpoint.strip().removeprefix("u+").removeprefix("0x"), 16)
                start = parse_endpoint(parts[0])
                end = parse_endpoint(parts[1]) if len(parts) == 2 else start
            except ValueError as error:
                raise ValueError(f"invalid Unicode range: {item}") from error
            if start > end or end > 0x10FFFF:
                raise ValueError(f"invalid Unicode range: {item}")
            result.update(range(start, end + 1))
    return result


def subset_font(font, codepoints: set[int]) -> None:
    """Subset *font* in place while retaining layout tables needed by merging."""

    from fontTools.subset import Options, Subsetter

    options = Options()
    options.layout_features = ["*"]
    options.name_IDs = [1, 2, 3, 4, 5, 6]
    options.name_legacy = True
    options.recalc_average_width = False
    subsetter = Subsetter(options=options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)


def merge_fonts(
    font_a_path: Path,
    font_b_path: Path,
    output_path: Path,
    proportional: bool = False,
    preserve_names: bool = False,
    codepoints: set[int] | None = None,
    family_name: str = "OboroMaru",
) -> None:
    """Create output using B as the base and A for selected codepoints."""

    from fontTools.ttLib import TTFont

    font_a = TTFont(font_a_path)
    font_b = TTFont(font_b_path)
    _require_glyf(font_a, "font A")
    _require_glyf(font_b, "font B")
    a_points = mapped_codepoints(font_a)
    selected = a_points if codepoints is None else a_points & codepoints
    if not selected:
        raise ValueError("font A has no mapped codepoints in the selected ranges")

    a_cmap = font_a["cmap"].getBestCmap()
    b_cmap = font_b["cmap"].getBestCmap()

    # Keep B's glyph IDs, cmap, metrics, hinting and layout tables. Only
    # replace the outline object at each existing selected glyph ID. This is
    # deliberately not a font-table merge: Windows will see the exact same
    # widths and glyph order as the original HackGen font. This also preserves
    # any glyph tables already present in the HackGen parent without attempting
    # to reinterpret them.
    b_glyf = font_b["glyf"]
    a_glyf = font_a["glyf"]
    glyph_names = set(font_b.getGlyphOrder())
    copied: dict[str, str] = {}
    for codepoint in sorted(selected):
        a_name = a_cmap[codepoint]
        if codepoint in b_cmap:
            target = b_cmap[codepoint]
            replacement = deepcopy(a_glyf[a_name])
            if replacement.isComposite():
                for component in replacement.components:
                    component.glyphName = _copy_glyph(
                        component.glyphName, a_glyf, font_a["hmtx"], b_glyf,
                        font_b, glyph_names, copied,
                    )
            b_glyf.glyphs[target] = replacement
        else:
            target = _copy_glyph(a_name, a_glyf, font_a["hmtx"], b_glyf, font_b, glyph_names, copied)
            _add_cmap_mapping(font_b, codepoint, target)
            b_cmap[codepoint] = target

    if not preserve_names:
        _update_name(font_b, proportional=proportional, family=family_name)
    _restore_fixed_width_metadata(font_b)
    if proportional:
        _make_proportional(font_b)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font_b.save(output_path)


def _require_glyf(font, label: str) -> None:
    if "glyf" not in font or "hmtx" not in font:
        raise ValueError(f"{label} must be a TrueType glyf font (CFF/variable fonts are not supported)")


def _copy_glyph(name, source_glyf, source_hmtx, target_glyf, target_font, names, copied):
    if name in copied:
        return copied[name]
    target = name if name not in names else f"A_{name}"
    while target in names:
        target = f"A_{target}"
    copied[name] = target
    glyph = deepcopy(source_glyf[name])
    if glyph.isComposite():
        for component in glyph.components:
            component.glyphName = _copy_glyph(component.glyphName, source_glyf, source_hmtx, target_glyf, target_font, names, copied)
    target_glyf.glyphs[target] = glyph
    target_font.setGlyphOrder(target_font.getGlyphOrder() + [target])
    target_font["hmtx"].metrics[target] = source_hmtx.metrics[name]
    names.add(target)
    return target


def _add_cmap_mapping(font, codepoint, glyph_name):
    for table in font["cmap"].tables:
        if table.isUnicode() and codepoint <= 0xFFFF and table.format in (4, 6, 12, 13):
            table.cmap[codepoint] = glyph_name
        elif table.isUnicode() and table.format in (12, 13):
            table.cmap[codepoint] = glyph_name


def _update_name(font, proportional: bool = False, family: str = "OboroMaru") -> None:
    """Give the generated font a stable, non-upstream family name."""

    subfamily = "Proportional" if proportional else "Regular"
    version = f"Version 1.0.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    name_table = font["name"]
    for name_id, value in (
        (1, family),
        (2, subfamily),
        (4, f"{family} {subfamily}"),
        (5, version),
        (6, "OboroMaru-Proportional" if proportional else "OboroMaru-Regular"),
    ):
        name_table.setName(value, name_id, 3, 1, 0x409)
        name_table.setName(value, name_id, 1, 0, 0)


def _restore_fixed_width_metadata(font) -> None:
    """Preserve the base font's fixed-width behavior after table merging."""

    # Merger combines these fields conservatively and the result otherwise
    # becomes proportional, which can cause size-dependent spacing changes in
    # text renderers. Font B is the base for all non-selected glyphs.
    font["post"].isFixedPitch = 1
    font["head"].flags |= 0x0008  # force ppem to integer values


def _make_proportional(font) -> None:
    """Set advances from outline bounds while retaining a small right margin."""

    glyf = font["glyf"]
    metrics = font["hmtx"].metrics
    margin = round(font["head"].unitsPerEm * 0.05)
    advances = []

    for glyph_name in font.getGlyphOrder():
        glyph = glyf[glyph_name]
        old_advance, left_side_bearing = metrics[glyph_name]
        if glyph.numberOfContours == 0:
            # Keep space, .notdef and other intentionally blank glyphs usable.
            advances.append(old_advance)
            continue
        glyph.recalcBounds(glyf)
        new_advance = max(1, glyph.xMax + margin)
        metrics[glyph_name] = (new_advance, left_side_bearing)
        advances.append(new_advance)

    font["post"].isFixedPitch = 0
    font["head"].flags &= ~0x0008
    font["OS/2"].panose.bProportion = 2
    printable_advances = [advance for advance in advances if advance > 0]
    if printable_advances:
        font["OS/2"].xAvgCharWidth = round(sum(printable_advances) / len(printable_advances))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-a", type=Path, required=True, help="font whose selected glyphs are used")
    parser.add_argument("--font-b", type=Path, required=True, help="base font providing all other glyphs")
    parser.add_argument(
        "--range", dest="ranges", action="append", metavar="START-END",
        help=("Unicode names/ranges taken from font A; comma-separate or repeat "
              f"(names: {', '.join(sorted(SUPPORTED_NAMED_RANGES))}; default: all A cmap)"),
    )
    parser.add_argument("--proportional", action="store_true", help="make glyph advances proportional to their outlines")
    parser.add_argument("--preserve-names", action="store_true", help="keep font B's name table")
    parser.add_argument("--family-name", default="OboroMaru", help="family name written to the generated font")
    parser.add_argument("--output", type=Path, default=None, help="output .ttf path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    font_a = args.font_a
    font_b = args.font_b
    for label, path in (("font A", font_a), ("font B", font_b)):
        if not path.is_file():
            print(f"{label} font not found: {path}", file=sys.stderr)
            return 2
    output = args.output or Path("OboroMaru-Proportional.ttf" if args.proportional else "OboroMaru.ttf")
    try:
        ranges = parse_ranges(args.ranges)
        merge_fonts(
            font_a,
            font_b,
            output,
            proportional=args.proportional,
            preserve_names=args.preserve_names,
            codepoints=ranges,
            family_name=args.family_name,
        )
    except ImportError:
        print("fontTools is required: python3 -m pip install -r requirements.txt", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"font merge failed: {error}", file=sys.stderr)
        return 1
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
