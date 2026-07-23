"""Narration-pace self-calibration.

Every run measures ground truth (spoken words vs synthesized seconds) and the
next run's word budget uses the measured pace instead of the static
channel.wpm guess. This closes the runtime gap permanently in both directions
(FAILURES.md #6: 6:00 target -> 4:38 delivered; shorts once overran 36%).

Data lives in calibration.json at the repo root and is committed by the
workflow alongside topics_done.txt, so calibration survives across CI runs.
Fail-open: any problem returns None and the configured wpm applies.
"""
import json
import os
import statistics

FILENAME = "calibration.json"
MAX_ENTRIES = 60          # keep the file tiny and diff-friendly
WINDOW = 5                # rolling window per kind
CLAMP = 0.40              # was 0.25 — too tight: Kokoro's REAL Hindi pace
                          # (~177 wpm incl. pauses, long run #2) sits 36%
                          # above the configured 130, so the clamp froze the
                          # word budget short and every Kokoro run came out
                          # ~16 min instead of 22


def _path(repo_root: str) -> str:
    return os.path.join(repo_root, FILENAME)


def _load(repo_root: str) -> list:
    try:
        with open(_path(repo_root), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def record(repo_root: str, kind: str, words: int, seconds: float,
           stamp: str = "", engine: str = "") -> float | None:
    """Append one measured run. Returns the realized wpm (or None)."""
    try:
        words = int(words)
        seconds = float(seconds)
        if words <= 0 or seconds <= 10:
            return None
        wpm = round(words / (seconds / 60.0), 1)
        entries = _load(repo_root)
        entries.append({"stamp": stamp, "kind": str(kind),
                        "words": words, "seconds": round(seconds, 1),
                        "wpm": wpm, "engine": str(engine or "unknown")})
        with open(_path(repo_root), "w", encoding="utf-8") as f:
            json.dump(entries[-MAX_ENTRIES:], f, indent=2, ensure_ascii=False)
        print(f"[calib] recorded {kind} run: {words} words / "
              f"{seconds / 60:.1f} min = {wpm} wpm")
        return wpm
    except Exception as exc:  # never block a render over telemetry
        print(f"[calib] record skipped ({exc})")
        return None


def measured_wpm(repo_root: str, configured_wpm: int,
                 kind: str = "long", engine: str = "") -> int | None:
    """Median realized wpm over the last WINDOW runs of this kind, clamped to
    ±CLAMP of the configured value. None until 2+ measurements exist.

    engine: when given (from tts.preflight's prediction of which voice will
    speak), prefer measurements from that engine — Kokoro runs ~35% faster
    than Sarvam, so mixing their paces produced 16-min "22-min" videos."""
    try:
        entries = [e for e in _load(repo_root)
                   if e.get("kind") == kind
                   and isinstance(e.get("wpm"), (int, float))]
        same = ([e for e in entries if e.get("engine") == engine]
                if engine else [])
        if same:
            # even ONE measurement of the right voice beats a median that
            # mixes Sarvam (~130 wpm) with Kokoro (~177 wpm) paces
            entries = same
        elif len(entries) < 2:
            return None
        runs = [e["wpm"] for e in entries]
        median = statistics.median(runs[-WINDOW:])
        lo = configured_wpm * (1 - CLAMP)
        hi = configured_wpm * (1 + CLAMP)
        return int(round(min(max(median, lo), hi)))
    except Exception:
        return None
