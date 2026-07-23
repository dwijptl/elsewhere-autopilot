#!/bin/bash
# Double-click me on macOS to open रहस्यलोक Studio.
cd "$(dirname "$0")"
PY=python3
[ -x "../.venv/bin/python3" ] && PY="../.venv/bin/python3"   # installer venv
"$PY" -c "import flask" 2>/dev/null || "$PY" -m pip install --quiet flask
( sleep 1.5 && open "http://127.0.0.1:8765" ) &
exec "$PY" gui/app.py
