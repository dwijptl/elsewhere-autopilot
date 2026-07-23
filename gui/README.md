# रहस्यलोक Studio — the GUI

A local control room for both channels (रहस्यलोक + Terra Incognita).
Runs entirely on your Mac; nothing is hosted anywhere.

## First time (5 minutes)

```bash
git clone https://github.com/dwijptl/elsewhere-autopilot.git
cd elsewhere-autopilot
bash gui/setup_mac.sh        # brew deps + python deps + remotion
```

Optional, for the Terra Incognita tab:

```bash
cd .. && git clone https://github.com/dwijptl/faceless-autopilot.git
cd faceless-autopilot && pip3 install -r requirements.txt && (cd remotion && npm install)
```

## Every time

Double-click **start-gui.command** (or `python3 gui/app.py`) → the dashboard
opens at http://127.0.0.1:8765.

## What it does

- **New run — this Mac**: type a topic (or leave empty for auto), set the
  minutes, Start. Live stage stepper (research → script → … → render) and a
  streaming log. No 6-hour CI cap — long videos render in one pass. The app
  wraps runs in `caffeinate -i`, so the Mac won't sleep mid-render (just
  keep the lid open).
- **GitHub cloud**: paste a classic token (repo + workflow) once, dispatch
  any workflow, watch recent runs, and download release files
  (final.mp4 / thumbnails / captions.srt) straight into
  `~/Downloads/rahasyalok-studio/<release>/`.
- **Local outputs**: every finished local run appears with a playable video
  and links to all its files (metadata.md has the ready-to-paste YouTube
  description).
- **Setup**: API keys live in the repo's `.env` (chmod 600, gitignored) —
  paste them once in the Setup card.

## Security notes

- The app binds to 127.0.0.1 only — nothing on your network can reach it.
- The GitHub token is kept in memory; "remember" writes it to
  `~/.rahasyalok_studio.json` (chmod 600). It is only ever sent to
  api.github.com over HTTPS.
- After a local run, commit the history files (`topics_done.txt`,
  `styles_used.txt`, `assets_used.json`, `calibration.json`) so the cloud
  autopilot and your Mac don't drift apart:
  `git add -A && git commit -m "log local run" && git push`
