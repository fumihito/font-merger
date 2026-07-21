#!/bin/sh

# Build a merged font in one command.  FONT_A supplies selected glyphs;
# FONT_B is the base for every other glyph.

set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT_DIR"

if [ -z "${PYTHON:-}" ]; then
    if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
        PYTHON="$ROOT_DIR/.venv/bin/python"
    else
        PYTHON=python3
    fi
fi

OUTPUT=${OUTPUT:-OboroMaru.ttf}
PROPORTIONAL_OUTPUT=${PROPORTIONAL_OUTPUT:-OboroMaru-Proportional.ttf}

if [ -z "${FONT_A:-}" ] || [ -z "${FONT_B:-}" ]; then
    echo "Set both FONT_A and FONT_B." >&2
    exit 2
fi
RANGE_ARGS=
if [ -n "${UNICODE_RANGES:-}" ]; then
    RANGE_ARGS="--range=$UNICODE_RANGES"
fi
FAMILY_NAME=${FAMILY_NAME:-OboroMaru}

if ! "$PYTHON" -c 'import fontTools' >/dev/null 2>&1; then
    echo "fontTools is not installed for: $PYTHON" >&2
    echo "Run: $PYTHON -m pip install -r requirements.txt" >&2
    exit 2
fi

"$PYTHON" scripts/merge_fonts.py \
    --font-a "$FONT_A" \
    --font-b "$FONT_B" \
    $RANGE_ARGS \
    --family-name "$FAMILY_NAME" \
    --output "$OUTPUT"

exec "$PYTHON" scripts/merge_fonts.py \
    --font-a "$FONT_A" \
    --font-b "$FONT_B" \
    $RANGE_ARGS \
    --family-name "$FAMILY_NAME" \
    --proportional \
    --output "$PROPORTIONAL_OUTPUT"
