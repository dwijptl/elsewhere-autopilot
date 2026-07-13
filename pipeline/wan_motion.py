"""Wan-2.1 i2v hero-motion stage — the channel's most expensive ingredient.

Channel 2's visual economy: almost everything is a seed-locked dossier still
with parallax. But once or twice per episode, behaviour has to be SEEN —
the swarm forming a shape, the cooling vent choking with bloom. The script
marks those scenes `hero_motion`; this stage animates their generated still
with Wan-2.1 on fal (image-to-video), so the motion shot is guaranteed to
match the canon still it grew from — same creature, same light, same frame.

Rules of this stage:
  * HARD CAP at motion.max_per_video (default 2). 720p ≈ 1 billing unit per
    shot (~$0.40-1.15); the cap — not hope — is the budget enforcement.
  * Submit every job to the fal QUEUE first, then poll them together —
    two shots cost one wait, not two.
  * Every failure leaves the still+parallax in place. A run NEVER dies here.
  * The motion shot REPLACES its source still in the scene's asset list
    (in place, keeping beat_index), so visual-beat bindings stay intact and
    the viewer never sees the frozen frame after the living one.
"""
import base64
import os
import subprocess
import time

import requests

import ai_images

QUEUE_BASE = "https://queue.fal.run"

# Motion grammar for the dossier look: survey footage, not showreel.
DOSSIER_MOTION = (
    "subtle documentary field footage, slow natural movement, gentle "
    "handheld drift, dust and heat shimmer in dim amber light, the subject "
    "moves the way an animal moves when nobody is watching")

# The i2v slop tells, negative-prompted on every shot.
NEGATIVE = (
    "fast motion, camera whip, zoom burst, timelapse, morphing, warping, "
    "extra limbs, bright colors, overexposed, lens flare, neon light, "
    "cyan or magenta lighting, text, subtitles, watermark, still picture, "
    "static, painting, cartoon")


def _data_uri(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    with open(path, "rb") as f:
        return f"data:image/{mime};base64," + base64.b64encode(f.read()).decode()


def _probe_duration(path: str, fallback: float) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip())
    except (subprocess.SubprocessError, ValueError, OSError):
        return fallback


def _hero_still(scene: dict) -> dict | None:
    """The scene's generated still — the frame the motion shot grows from."""
    for a in scene.get("assets", []):
        if a.get("kind") == "image" and a.get("ai"):
            return a
    return None


def _build_body(scene: dict, still_path: str, cfg: dict) -> dict:
    mcfg = cfg.get("motion", {})
    fps = int(mcfg.get("fps", 16))
    seconds = float(mcfg.get("seconds", 5))
    # Wan-2.1 accepts 81-100 frames; >81 bills at 1.25x — stay at the floor
    # unless config explicitly asks for longer.
    num_frames = max(81, min(100, int(seconds * fps) + 1))
    prompt = (scene.get("motion_prompt") or scene.get("ai_prompt")
              or scene.get("narration", ""))[:800]
    body = {
        "prompt": f"{prompt.strip()}. {DOSSIER_MOTION}",
        "negative_prompt": NEGATIVE,
        "image_url": _data_uri(still_path),
        "num_frames": num_frames,
        "frames_per_second": fps,
        "resolution": str(mcfg.get("resolution", "720p")),
        "aspect_ratio": "auto",   # inherit the still's aspect — never crop canon
        "enable_safety_checker": True,
        "acceleration": "regular",
    }
    seed = ai_images._canon_seed(prompt, cfg)
    if seed is not None:
        body["seed"] = seed      # a canon creature moves under its own seed too
    return body


def _submit(model: str, body: dict, headers: dict) -> dict | None:
    try:
        r = requests.post(f"{QUEUE_BASE}/{model}", json=body,
                          headers=headers, timeout=120)
        if r.status_code in (401, 403):
            print(f"[motion] fal auth failed — check FAL_KEY: {r.text[:200]}")
            return None
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"[motion] submit failed: {e}")
        return None


def _await_result(model: str, job: dict, headers: dict,
                  timeout_s: float) -> str | None:
    """Poll one queued job; return the video URL or None."""
    rid = job.get("request_id", "")
    status_url = job.get("status_url") or f"{QUEUE_BASE}/{model}/requests/{rid}/status"
    response_url = job.get("response_url") or f"{QUEUE_BASE}/{model}/requests/{rid}"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = requests.get(status_url, headers=headers, timeout=30)
            r.raise_for_status()
            status = r.json().get("status", "")
            if status == "COMPLETED":
                out = requests.get(response_url, headers=headers, timeout=60)
                out.raise_for_status()
                return (out.json().get("video") or {}).get("url")
            if status in ("FAILED", "CANCELLED", "ERROR"):
                print(f"[motion] job {rid[:8]} ended {status}")
                return None
        except (requests.RequestException, ValueError) as e:
            print(f"[motion] poll error ({e}) — retrying")
        time.sleep(6)
    print(f"[motion] job {rid[:8]} timed out after {int(timeout_s)}s")
    return None


def animate_heroes(scenes: list[dict], cfg: dict, outdir: str) -> int:
    """Animate up to motion.max_per_video hero stills. Returns shots landed.

    Fail-open at every step: no key, no flagged scene, no still, submit
    error, poll timeout, bad download — the still+parallax remains and the
    episode ships.
    """
    mcfg = cfg.get("motion", {})
    if not mcfg.get("enabled", True):
        return 0
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        print("[motion] FAL_KEY not set — hero shots stay stills+parallax")
        return 0

    cap = max(0, int(mcfg.get("max_per_video", 2)))
    model = str(mcfg.get("model", "fal-ai/wan-i2v"))
    headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}

    candidates = []
    for sc in scenes:
        if not sc.get("hero_motion"):
            continue
        still = _hero_still(sc)
        if still is None:
            print(f"[motion] scene {sc.get('n')}: hero_motion but no AI still — skipped")
            continue
        candidates.append((sc, still))
        if len(candidates) >= cap:
            break

    if not candidates:
        return 0

    # Submit everything first, then poll — parallel wait, serial money.
    jobs = []
    for sc, still in candidates:
        job = _submit(model, _build_body(sc, still["path"], cfg), headers)
        if job and job.get("request_id"):
            jobs.append((sc, still, job))
            print(f"[motion] scene {sc['n']}: queued wan shot "
                  f"({job['request_id'][:8]})")

    landed = 0
    timeout_s = float(mcfg.get("poll_timeout_seconds", 900))
    fallback_dur = float(mcfg.get("seconds", 5))
    for sc, still, job in jobs:
        url = _await_result(model, job, headers, timeout_s)
        if not url:
            continue
        path = os.path.join(outdir, f"s{sc['n']:02d}_wan.mp4")
        try:
            if not ai_images._download(url, path):
                print(f"[motion] scene {sc['n']}: download too small — kept still")
                continue
        except (requests.RequestException, OSError) as e:
            print(f"[motion] scene {sc['n']}: download failed ({e}) — kept still")
            continue
        # Replace the source still IN PLACE: beat_index (and any other
        # bindings) survive, and the frozen frame never follows the live one.
        still["path"] = path
        still["kind"] = "video"
        still["duration"] = _probe_duration(path, fallback_dur)
        still["motion"] = True
        landed += 1
        print(f"[motion] scene {sc['n']}: wan shot landed "
              f"({still['duration']:.1f}s)")

    est = landed * (0.5 if str(mcfg.get("resolution", "720p")) == "480p" else 1.0)
    print(f"[motion] {landed}/{len(candidates)} hero shots landed "
          f"(~{est:g} billing unit(s))")
    return landed
