#!/bin/sh
# Renders the banner: 96 frames of an 8-second loop at 1280x448, then encodes animated WebP
# (dark: dissolves into GitHub's dark page; light: the same water as a plate on the white page)
# and a still PNG of frame 0 for prefers-reduced-motion.
# Needs python3 with numpy, scipy and pillow, and img2webp (libwebp).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
out=${1:-"$here/../../banner"}
frames=$(mktemp -d)
cd "$here"
python3 anim.py 1280 448 96 "$frames" 0 2 &
python3 anim.py 1280 448 96 "$frames" 1 2
wait
mkdir -p "$out"
for m in dark plate; do
  img2webp -loop 0 -lossy -q 82 -m 6 -sharp_yuv -d 83 "$frames"/$m*.png -o "$frames/$m.webp"
done
cp "$frames/dark.webp" "$out/scryst-dark.webp"
cp "$frames/plate.webp" "$out/scryst-light.webp"
cp "$frames/dark000.png" "$out/scryst-dark.png"
cp "$frames/plate000.png" "$out/scryst-light.png"
rm -r "$frames"
