#!/bin/sh
# Draws the profile banner: the hand, then iron filings over a magnet cut in its shape.
# Needs Python 3 with numpy, scipy and Pillow. Writes ../../banner/filings-*.png.
set -e
cd "$(dirname "$0")"
out=../../banner
python3 hand.py
python3 filings.py $out/filings-light.png light &
python3 filings.py $out/filings-dark.png dark &
CANVAS=1240x800 python3 filings.py $out/filings-phone-light.png light --scale 2.1 --cx 0.5 --cy 0.5 &
CANVAS=1240x800 python3 filings.py $out/filings-phone-dark.png dark --scale 2.1 --cx 0.5 --cy 0.5 &
wait
