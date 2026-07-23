#!/bin/bash
# रहस्यलोक Studio — one-time Mac setup.
#   bash gui/setup_mac.sh              (from the elsewhere-autopilot clone)
# Installs system deps via Homebrew, Python deps, and the Remotion renderer.
set -e
cd "$(dirname "$0")/.."

echo "== रहस्यलोक Studio setup =="

if ! command -v brew >/dev/null; then
  echo "Homebrew missing — install it first: https://brew.sh"; exit 1
fi

echo "-- system dependencies (ffmpeg, espeak-ng, node)"
brew list ffmpeg   >/dev/null 2>&1 || brew install ffmpeg
brew list espeak-ng >/dev/null 2>&1 || brew install espeak-ng
command -v node >/dev/null 2>&1 || brew install node@20

echo "-- python dependencies"
python3 -m pip install --quiet -r requirements.txt flask

echo "-- remotion renderer (node_modules, includes headless Chrome)"
(cd remotion && npm install --no-audit --no-fund)

if [ ! -f .env ]; then
  echo "-- creating .env template (fill your keys here or in the GUI)"
  cat > .env <<'EOF'
GEMINI_API_KEY=
PEXELS_API_KEY=
SARVAM_API_KEY=
SARVAM_SPEAKER=
FAL_KEY=
EOF
  chmod 600 .env
fi

echo
echo "Done. Start the app with:  python3 gui/app.py"
echo "…or double-click start-gui.command, then open http://127.0.0.1:8765"
