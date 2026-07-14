"""Deterministic flat-frame detector — the last line of defence.

Every other gate in this pipeline checks INTENTIONS: that assets were
generated, that scenes were assigned visuals, that components typecheck.
Twice (pilot runs #2 and #3) the intentions were fine and the SCREEN was
still an empty gradient. This module checks the finished pixels instead.

No LLM, no API, no quota, no skipping: ffmpeg + PIL, runs on every render.
Calibrated on real output (2026-07-14): genuine scenes measure detail
stddev 20-30 with edge energy 3.6-5.6; broken gradient scenes measure 1-5
with 0.15-0.9. Thresholds sit in the gulf between (10 / 2.0).

The centre band (14-70%% height) is measured, so captions, chips and the
metric readout can't mask an empty canvas.
"""
import io
import subprocess

from PIL import Image, ImageFilter, ImageStat

STD_THRESH = 10.0     # spatial detail below this is a colour field
EDGE_THRESH = 2.0     # edge energy below this means no structure at all
SAMPLE_SECONDS = 3.0  # one probe every N seconds
MIN_RUN_SECONDS = 6.0  # tolerate brief transitions; flag sustained emptiness


def _duration(path: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path], capture_output=True, text=True, timeout=60)
        return float(out.stdout.strip())
    except (subprocess.SubprocessError, ValueError, OSError):
        return 0.0


def _frame_metrics(path: str, t: float) -> tuple[float, float] | None:
    try:
        p = subprocess.run(
            ["ffmpeg", "-v", "quiet", "-ss", str(t), "-i", path,
             "-frames:v", "1", "-vf", "scale=480:270",
             "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, timeout=60)
        img = Image.open(io.BytesIO(p.stdout)).convert("L")
    except Exception:
        return None
    w, h = img.size
    band = img.crop((int(w * .06), int(h * .14), int(w * .94), int(h * .70)))
    std = ImageStat.Stat(band).stddev[0]
    edges = ImageStat.Stat(band.filter(ImageFilter.FIND_EDGES)).mean[0]
    return std, edges


def check(final_path: str) -> dict:
    """Scan the finished video. Returns {passed, flat_ranges, samples}.

    flat_ranges: [(start_s, end_s), ...] — sustained stretches where the
    centre of the frame is effectively a solid colour. Fail-open on probe
    errors (a broken probe must not block a release; it just can't verify).
    """
    duration = _duration(final_path)
    if duration <= 0:
        return {"passed": True, "flat_ranges": [], "samples": 0,
                "note": "unprobeable — not verified"}
    flats, samples = [], 0
    t = SAMPLE_SECONDS / 2
    while t < duration:
        m = _frame_metrics(final_path, t)
        samples += 1
        if m is not None:
            std, edges = m
            flats.append((t, std < STD_THRESH and edges < EDGE_THRESH))
        t += SAMPLE_SECONDS

    ranges, run_start = [], None
    for t, is_flat in flats:
        if is_flat and run_start is None:
            run_start = t
        elif not is_flat and run_start is not None:
            if t - run_start >= MIN_RUN_SECONDS:
                ranges.append((round(run_start - SAMPLE_SECONDS / 2, 1),
                               round(t, 1)))
            run_start = None
    if run_start is not None and duration - run_start >= MIN_RUN_SECONDS:
        ranges.append((round(run_start - SAMPLE_SECONDS / 2, 1),
                       round(duration, 1)))

    return {"passed": not ranges, "flat_ranges": ranges, "samples": samples}


def describe(report: dict) -> str:
    if report.get("passed"):
        return "OK — no flat stretches"
    def mmss(s: float) -> str:
        return f"{int(s // 60)}:{int(s % 60):02d}"
    spans = ", ".join(f"{mmss(a)}-{mmss(b)}" for a, b in report["flat_ranges"])
    return f"⚠️ FLAT FRAMES at {spans} — DO NOT PUBLISH"
