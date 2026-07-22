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
