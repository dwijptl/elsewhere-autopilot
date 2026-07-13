"""wan_motion — the stage that spends real money, so every rule is tested:
hard cap, fail-open on every step, in-place asset replacement, seed lock."""
import json

import pytest

import wan_motion


def _png(tmp_path, name="still.png"):
    p = tmp_path / name
    p.write_bytes(b"\x89PNG" + b"0" * 100)
    return str(p)


def _scene(n, tmp_path, hero=True):
    return {"n": n, "hero_motion": hero,
            "ai_prompt": f"a vent-crab feeding at dusk {n}",
            "assets": [{"path": _png(tmp_path, f"s{n}.png"), "kind": "image",
                        "ai": True, "beat_index": 0}]}


CFG = {"motion": {"enabled": True, "max_per_video": 2, "seconds": 5,
                  "fps": 16, "model": "fal-ai/wan-i2v"},
       "ai_images": {"seed_lock": False}}


def test_no_fal_key_is_a_noop(monkeypatch, tmp_path):
    monkeypatch.delenv("FAL_KEY", raising=False)
    scenes = [_scene(1, tmp_path)]
    before = json.dumps(scenes[0]["assets"])
    assert wan_motion.animate_heroes(scenes, CFG, str(tmp_path)) == 0
    assert json.dumps(scenes[0]["assets"]) == before


def test_disabled_is_a_noop(monkeypatch, tmp_path):
    monkeypatch.setenv("FAL_KEY", "k")
    cfg = {**CFG, "motion": {**CFG["motion"], "enabled": False}}
    assert wan_motion.animate_heroes([_scene(1, tmp_path)], cfg, str(tmp_path)) == 0


def test_hard_cap_limits_submissions(monkeypatch, tmp_path):
    monkeypatch.setenv("FAL_KEY", "k")
    submitted = []
    monkeypatch.setattr(wan_motion, "_submit",
                        lambda model, body, headers: submitted.append(body) or None)
    scenes = [_scene(n, tmp_path) for n in (1, 2, 3)]  # 3 flagged, cap is 2
    wan_motion.animate_heroes(scenes, CFG, str(tmp_path))
    assert len(submitted) == 2


def test_success_replaces_still_in_place(monkeypatch, tmp_path):
    monkeypatch.setenv("FAL_KEY", "k")
    monkeypatch.setattr(wan_motion, "_submit",
                        lambda *a: {"request_id": "abc12345"})
    monkeypatch.setattr(wan_motion, "_await_result",
                        lambda *a: "https://fal.example/out.mp4")

    def fake_download(url, path):
        with open(path, "wb") as f:
            f.write(b"0" * 30_000)
        return True

    monkeypatch.setattr(wan_motion.ai_images, "_download", fake_download)
    monkeypatch.setattr(wan_motion, "_probe_duration", lambda p, fb: 5.06)
    scenes = [_scene(7, tmp_path)]
    assert wan_motion.animate_heroes(scenes, CFG, str(tmp_path)) == 1
    asset = scenes[0]["assets"][0]
    assert asset["kind"] == "video"
    assert asset["path"].endswith("s07_wan.mp4")
    assert asset["beat_index"] == 0          # beat binding survives the swap
    assert asset["duration"] == pytest.approx(5.06)


def test_poll_failure_keeps_the_still(monkeypatch, tmp_path):
    monkeypatch.setenv("FAL_KEY", "k")
    monkeypatch.setattr(wan_motion, "_submit",
                        lambda *a: {"request_id": "abc12345"})
    monkeypatch.setattr(wan_motion, "_await_result", lambda *a: None)
    scenes = [_scene(3, tmp_path)]
    assert wan_motion.animate_heroes(scenes, CFG, str(tmp_path)) == 0
    assert scenes[0]["assets"][0]["kind"] == "image"  # run never dies here


def test_scene_without_ai_still_is_skipped(monkeypatch, tmp_path):
    monkeypatch.setenv("FAL_KEY", "k")
    called = []
    monkeypatch.setattr(wan_motion, "_submit", lambda *a: called.append(1) or None)
    scenes = [{"n": 1, "hero_motion": True,
               "assets": [{"path": "x.mp4", "kind": "video"}]}]
    assert wan_motion.animate_heroes(scenes, CFG, str(tmp_path)) == 0
    assert not called


def test_canon_seed_flows_into_body(monkeypatch, tmp_path):
    monkeypatch.setattr(wan_motion.ai_images, "_canon_seed",
                        lambda prompt, cfg: 40117)
    body = wan_motion._build_body(_scene(1, tmp_path), _png(tmp_path), CFG)
    assert body["seed"] == 40117
    assert body["num_frames"] == 81          # billing floor, not 1.25x tier
    assert body["image_url"].startswith("data:image/png;base64,")
    assert "documentary" in body["prompt"]
