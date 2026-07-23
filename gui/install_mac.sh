#!/bin/bash
# रहस्यलोक Studio — one-command Mac installer.
# Run this in Terminal on the Mac:
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/dwijptl/elsewhere-autopilot/main/gui/install_mac.sh)"
#
# It sets up EVERYTHING under ~/rahasyalok :
#   ~/rahasyalok/elsewhere-autopilot   (रहस्यलोक channel)
#   ~/rahasyalok/faceless-autopilot    (Terra Incognita channel)
#   ~/rahasyalok/.venv                 (python 3.11 + all pipeline deps)
# then launches the Studio at http://127.0.0.1:8765
set -e
BASE="$HOME/rahasyalok"
mkdir -p "$BASE"
cd "$BASE"
echo "== रहस्यलोक Studio installer =="

# 1) Homebrew --------------------------------------------------------------
if ! command -v brew >/dev/null 2>&1; then
  if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  else
    echo "-- installing Homebrew (it may ask for your Mac password)"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
fi

# 2) system tools ----------------------------------------------------------
echo "-- system tools (ffmpeg, espeak-ng, git, node, python 3.11)"
for pkg in ffmpeg espeak-ng git; do
  brew list "$pkg" >/dev/null 2>&1 || brew install "$pkg"
done
command -v node >/dev/null 2>&1 || brew install node
brew list python@3.11 >/dev/null 2>&1 || brew install python@3.11

# 3) the two channel repos -------------------------------------------------
clone_or_update() {
  if [ -d "$1/.git" ]; then
    echo "-- updating $1"; git -C "$1" pull --ff-only || true
  else
    echo "-- cloning $1"; git clone "https://github.com/dwijptl/$1.git"
  fi
}
clone_or_update elsewhere-autopilot
clone_or_update faceless-autopilot

# 4) python env ------------------------------------------------------------
echo "-- python environment (~/rahasyalok/.venv)"
PY="$(brew --prefix python@3.11)/bin/python3.11"
[ -d .venv ] || "$PY" -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r elsewhere-autopilot/requirements.txt flask
./.venv/bin/pip install --quiet -r faceless-autopilot/requirements.txt

# 5) remotion renderer (downloads its own headless Chrome once) ------------
echo "-- remotion renderer (first npm install takes a few minutes)"
(cd elsewhere-autopilot/remotion && npm install --no-audit --no-fund)
(cd faceless-autopilot/remotion && npm install --no-audit --no-fund)

# 6) key templates ---------------------------------------------------------
for repo in elsewhere-autopilot faceless-autopilot; do
  if [ ! -f "$repo/.env" ]; then
    printf 'GEMINI_API_KEY=\nPEXELS_API_KEY=\nSARVAM_API_KEY=\nSARVAM_SPEAKER=\nFAL_KEY=\n' > "$repo/.env"
    chmod 600 "$repo/.env"
  fi
done

echo
echo "== done. Launching रहस्यलोक Studio =="
echo "   next time: double-click elsewhere-autopilot/start-gui.command"
cd elsewhere-autopilot
( sleep 2 && open "http://127.0.0.1:8765" ) &
exec "$BASE/.venv/bin/python3" gui/app.py
