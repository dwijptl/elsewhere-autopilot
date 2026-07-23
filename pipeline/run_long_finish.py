"""Segmented rendering — finish job (Make Long Video workflow).

Concatenates the rendered chunks losslessly (PCM audio = sample-accurate
joins), transcodes audio to AAC into final.mp4, then resumes the pipeline
from the prepare-stage checkpoint: mastering, audits, thumbnails, metadata,
history logs — identical to the single-job path.

Usage: python pipeline/run_long_finish.py <outdir>
"""
import glob
import os
import pickle
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import run  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def concat_chunks(outdir: str) -> str:
    chunks = sorted(glob.glob(os.path.join(outdir, "chunk_*.mkv")))
    if not chunks:
        raise RuntimeError("no chunk_*.mkv files found — did render jobs run?")
    print(f"[concat] {len(chunks)} chunks: "
          + ", ".join(os.path.basename(c) for c in chunks))
    listfile = os.path.join(outdir, "chunks.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(f"file '{os.path.abspath(c)}'\n")
    joined = os.path.join(outdir, "joined.mkv")
    subprocess.run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", listfile, "-c", "copy", "-y", joined],
                   check=True, timeout=1800)
    final = os.path.join(outdir, "final.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-i", joined,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                    "-movflags", "+faststart", "-y", final],
                   check=True, timeout=1800)
    if os.path.getsize(final) < 500_000:
        raise RuntimeError("concat produced a too-small final.mp4")
    for c in chunks + [joined, listfile]:
        try:
            os.remove(c)
        except OSError:
            pass
    print(f"[concat] final.mp4: {os.path.getsize(final) / 1e6:.1f} MB")
    return final


def main() -> None:
    outdir = os.path.abspath(sys.argv[1])
    concat_chunks(outdir)
    with open(os.path.join(outdir, "checkpoint.pkl"), "rb") as f:
        ck = pickle.load(f)
    # restore repo-state files the prepare job wrote in ITS checkout (pace
    # calibration, style rotation, asset ledger) so this job's history
    # commit actually persists them — long run #2 lost all three
    state_dir = os.path.join(outdir, "repo_state")
    if os.path.isdir(state_dir):
        for fn in os.listdir(state_dir):
            shutil.copy2(os.path.join(state_dir, fn),
                         os.path.join(REPO_ROOT, fn))
        print(f"[state] restored {sorted(os.listdir(state_dir))} "
              "from the prepare artifact")
    # paths inside the checkpoint were absolute on the prepare runner —
    # rebase them onto this runner's checkout
    ck["outdir"] = outdir
    ck["workdir"] = os.path.join(outdir, "work")
    ck["manifest_path"] = os.path.join(outdir, "work", "props.json")
    for sc in ck.get("scenes", []):
        for a in sc.get("assets", []):
            if a.get("path"):
                a["path"] = os.path.join(ck["workdir"],
                                         os.path.basename(a["path"]))
    ck["used_engine"] = "remotion-segmented"
    run._finalize_delivery(ck)


if __name__ == "__main__":
    main()
