"""The render guard: missing files never reach the renderer."""
import os

import run


def test_missing_and_corrupt_assets_are_dropped_and_borrowed(tmp_path):
    good = tmp_path / "s01_ok.mp4"
    good.write_bytes(b"x" * 2048)
    tiny = tmp_path / "s02_tiny.mp4"
    tiny.write_bytes(b"x")  # sub-1KB = corrupt
    scenes = [
        {"n": 1, "visual_mode": "broll",
         "assets": [{"path": str(good), "kind": "video"},
                    {"path": str(tmp_path / "gone.mp4"), "kind": "video"}],
         "visual_beats": [{"assets": [{"path": str(tmp_path / "gone2.mp4"),
                                       "kind": "image"}]}]},
        {"n": 2, "visual_mode": "broll",
         "assets": [{"path": str(tiny), "kind": "video"}]},
        {"n": 3, "visual_mode": "map", "assets": []},
    ]
    run._validate_scene_assets(scenes)
    assert [a["path"] for a in scenes[0]["assets"]] == [str(good)]
    assert scenes[0]["visual_beats"][0]["assets"] == []
    assert scenes[1]["assets"] == [{"path": str(good), "kind": "video"}]  # borrowed
    assert scenes[2]["assets"] == []  # map scenes may be empty


# ── Sarvam circuit breaker (Make Long Video run #1 postmortem) ───────────
def test_sarvam_breaker_opens_after_consecutive_failures(monkeypatch):
    import numpy as np
    import tts

    tts.reset_run_state()
    calls = {"sarvam": 0}

    def dead_sarvam(text, cfg, dlv):
        calls["sarvam"] += 1
        raise RuntimeError("simulated slow-failing API")

    monkeypatch.setattr(tts, "_synth_sarvam", dead_sarvam)
    monkeypatch.setattr(tts, "_synth_kokoro",
                        lambda text, cfg: np.zeros(2400, dtype=np.float32))
    cfg = {"tts": {"engine": "sarvam"}, "video": {}}
    for i in range(4):
        tts.synth_scene("नमस्ते", f"/tmp/breaker_{i}.wav", cfg)
    # scenes 1+2 try Sarvam and fail; breaker opens; scenes 3+4 skip it
    assert calls["sarvam"] == tts.SARVAM_BREAKER_LIMIT
    assert tts.fallback_used()
    tts.reset_run_state()
    assert tts._sarvam_fail_streak == 0


# ── engine-aware pace calibration (16-min "22-min" video postmortem) ─────
def test_calibration_prefers_matching_engine(tmp_path):
    import calibration
    calibration.record(str(tmp_path), "long", 1094, 496.0, "a", engine="mixed")
    calibration.record(str(tmp_path), "long", 2860, 971.5, "b", engine="kokoro")
    # planned voice kokoro -> its own single measurement (177), not the
    # cross-engine median (154) that undershot run #2 by six minutes
    assert calibration.measured_wpm(str(tmp_path), 130, "long",
                                    engine="kokoro") == 177
    # unknown-engine hint falls back to the all-entries median
    assert calibration.measured_wpm(str(tmp_path), 130, "long",
                                    engine="sarvam") == 154
    # no hint (single-job legacy path) keeps the old behavior
    assert calibration.measured_wpm(str(tmp_path), 130, "long") == 154
