#!/bin/bash
# Double-click me on macOS to open रहस्यलोक Studio.
cd "$(dirname "$0")"
python3 -c "import flask" 2>/dev/null || python3 -m pip install --quiet flask
( sleep 1.5 && open "http://127.0.0.1:8765" ) &
exec python3 gui/app.py
