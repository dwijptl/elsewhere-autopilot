"""Segmented rendering — chunk job (Make Long Video workflow).

Renders ONE frame-range of the Main composition to chunk_<i>.mkv
(h264 + PCM audio: PCM concatenates sample-accurately later, no AAC
frame-boundary pops). Frame math mirrors remotion/src/Root.tsx
mainDuration() exactly.

Usage: python pipeline/render_chunk.py <outdir> <chunk_index> <total_chunks>
"""
import json
import math
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTION_DIR = os.path.join(REPO_ROOT, "remotion")


def total_frames(m: dict) -> int:
    fps = int(m["fps"])
    scene_total = sum(round(sc["audioDuration"] * fps) for sc in m["scenes"])
    outro = max(round(float(m.get("outroSeconds", 4)) * fps), fps)
    overlaps = len(m["scenes"]) * int(m["xfadeFrames"])
    return max(fps, scene_total + outro - overlaps)


def chunk_range(total: int, index: int, chunks: int) -> tuple[int, int]:
    size = math.ceil(total / chunks)
    start = index * size
    end = min(start + size - 1, total - 1)
    return start, end


def main() -> None:
    outdir, index, chunks = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    workdir = os.path.join(outdir, "work")
    manifest_path = os.path.join(workdir, "props.json")
    with open(manifest_path, encoding="utf-8") as f:
        m = json.load(f)["manifest"]
    total = total_frames(m)
    start, end = chunk_range(total, index, chunks)
    if start > end:
        print(f"[chunk {index}] empty range — nothing to render")
        return
    out = os.path.join(outdir, f"chunk_{index:02d}.mkv")
    cmd = ["npx", "remotion", "render", "src/index.ts", "Main",
           os.path.abspath(out),
           "--props", os.path.abspath(manifest_path),
           "--public-dir", os.path.abspath(workdir),
           "--frames", f"{start}-{end}",
           "--audio-codec", "pcm-16",
           "--concurrency", "3", "--log", "warn"]
    print(f"[chunk {index}] frames {start}-{end} of {total}:", " ".join(cmd))
    subprocess.run(cmd, cwd=REMOTION_DIR, check=True, timeout=3.0 * 3600)
    if not os.path.exists(out) or os.path.getsize(out) < 100_000:
        raise RuntimeError(f"chunk {index} produced no/too-small output")
    print(f"[chunk {index}] done: {os.path.getsize(out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
