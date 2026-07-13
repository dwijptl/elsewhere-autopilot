"""The hand-written pilot script is a shipped artifact — it must stay legal
against the canon gate and the format's own rules as both evolve. If a canon
edit ever breaks EP-01, this fails BEFORE a workflow burns money on it."""
import json
import os

import yaml

import canon as canon_mod
import script_gen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "ep01_the_underground_city.json")


def _cfg():
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load():
    cfg = _cfg()
    cwd = os.getcwd()
    os.chdir(ROOT)  # canon_mod.load(".") inside the loader path
    try:
        return script_gen.load_script_file(SCRIPT, cfg), cfg
    finally:
        os.chdir(cwd)


def test_pilot_passes_canon_gate():
    script, cfg = _load()
    canon = canon_mod.load(ROOT)
    assert canon_mod.validate(script, canon, cfg) == []


def test_pilot_word_budget():
    script, cfg = _load()
    wc = sum(len(s["narration"].split()) for s in script["scenes"])
    target = cfg["video"]["target_minutes"] * cfg["channel"]["wpm"]
    assert target * 0.92 <= wc <= target * 1.08


def test_pilot_format_spine():
    script, _ = _load()
    modes = [s["visual_mode"] for s in script["scenes"]]
    # post-normalize vocabulary: atlas->map, schematic->glass, verdict->card
    assert modes.count("map") == 1                    # exactly one locator
    assert 1 <= modes.count("glass") <= 2             # the schematic(s)
    assert sum(1 for s in script["scenes"]
               if s.get("verdict_card")) == 1         # one verdict card
    assert 1 <= sum(1 for s in script["scenes"]
                    if s.get("hero_motion")) <= 2     # motion budget
    assert script["verdict"] == "FAILED"              # canon-registered ending
    ms = [s["milestone"]["value"] for s in script["scenes"]]
    assert all(a <= b for a, b in zip(ms, ms[1:]))    # monotonic simulation
    assert "Kelvara" not in script["title"]           # name never in a title


def test_pilot_speaks_truth_label_in_cold_open():
    script, _ = _load()
    first = script["scenes"][0]["narration"].lower()
    assert "fiction" in first and "real" in first
