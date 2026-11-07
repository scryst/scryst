#!/bin/sh
# Runs build.sh against stub renderers: a failed render half must fail the build, leave the
# banner untouched, and leave no frames dir behind. Usage: sh scripts/scry/build.test.sh
set -u
src=$(cd "$(dirname "$0")" && pwd)
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
fail=0
mkdir -p "$t/scry" "$t/bin" "$t/tmp" "$t/out"
cp "$src/build.sh" "$t/scry/"
# anim.py stub: args w h n dir half step; STUB_FAIL_HALF names the half that crashes.
cat > "$t/scry/anim.py" <<'PY'
import os, sys
w, h, n, d, half, step = sys.argv[1:7]
crash = half == os.environ.get("STUB_FAIL_HALF")
for i in range(int(half), int(n), int(step)):
    for m in ("dark", "plate"):
        open(os.path.join(d, "%s%03d.png" % (m, i)), "w").close()
    if crash:
        sys.exit(3)  # dies after its first frame, like an OOM kill mid-render
PY
cat > "$t/bin/img2webp" <<'SH'
#!/bin/sh
while [ "$1" != -o ]; do shift; done
echo webp > "$2"
SH
chmod +x "$t/bin/img2webp"
run() { STUB_FAIL_HALF=$1 TMPDIR="$t/tmp" PATH="$t/bin:$PATH" sh "$t/scry/build.sh" "$t/out" >/dev/null 2>&1; }

for half in 0 1; do
  echo old > "$t/out/scryst-dark.webp"
  if run $half; then echo "FAIL: build exits 0 when render half $half crashes"; fail=1; fi
  [ "$(cat "$t/out/scryst-dark.webp")" = old ] || { echo "FAIL: half $half crash overwrote the banner"; fail=1; }
  [ -z "$(ls "$t/tmp")" ] || { echo "FAIL: half $half crash left a frames dir in TMPDIR"; fail=1; rm -rf "$t/tmp"/*; }
done
run none || { echo "FAIL: clean build failed"; fail=1; }
[ "$(cat "$t/out/scryst-dark.webp")" = webp ] || { echo "FAIL: clean build did not write the banner"; fail=1; }
[ -z "$(ls "$t/tmp")" ] || { echo "FAIL: clean build left a frames dir"; fail=1; }
[ $fail = 0 ] && echo "ok build.test.sh"
exit $fail
