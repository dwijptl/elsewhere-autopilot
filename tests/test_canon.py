"""The canon tests.

These are the tests that matter most on this channel. Everything else is a
video pipeline; this is the world. If continuity silently breaks, nobody gets
an exception — they just get a channel that slowly stops meaning anything.
"""
import json
import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

import canon as canon_mod  # noqa: E402
import script_gen  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


@pytest.fixture
def cfg():
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def world():
    return canon_mod.load(ROOT)


def _valid_script():
    return {
        "title": "The Underground City That Cooked Itself",
        "verdict": "FAILED",
        "region": "REG-01",
        "series": "stress_test",
        "settlement": {"name": "Corran Shaft"},
        "systems": [{"name": "COOLING"}],
        "stress_event": {"name": "biofouling"},
        "hidden_dependency": "cooling and drinking water share one aquifer",
        "truth_label_spoken": True,
    }


def test_canon_loads_and_brief_carries_the_physics(world):
    brief = canon_mod.brief(world)
    # the constants that every mechanism must obey have to reach the model —
    # a brief that omits them is how you get Earth engineering on an alien world
    assert "K-dwarf" in brief
    assert "0.87 g" in brief
    assert "31.4 hours" in brief
    assert world["planet"]["truth_label"] in brief


def test_unrevealed_regions_stay_secret(world):
    """A teased region must not be describable — the map keeps the secret until
    an episode reveals it. This is the returning-viewer mechanic."""
    brief = canon_mod.brief(world)
    slow_sea = next(r for r in world["atlas"]["regions"] if r["id"] == "REG-02")
    assert slow_sea["status"] == "teased"
    assert "TEASED ONLY" in brief
    assert slow_sea["description"] not in brief


def test_a_clean_script_passes(world, cfg):
    assert canon_mod.validate(_valid_script(), world, cfg) == []


@pytest.mark.parametrize("mutate,rule", [
    (lambda s: s.update({"title": "Kelvara's Buried City"}), "planet_name_in_title"),
    (lambda s: s.update({"verdict": "DESTROYED"}), "verdict_vocabulary"),
    (lambda s: s.update({"region": "REG-02"}), "region_revealed"),
    (lambda s: s.update({"region": "REG-99"}), "region_exists"),
    (lambda s: s.update({"series": "ecology"}), "ecology_locked"),
    (lambda s: s.update({"hidden_dependency": ""}), "stress_test_spine"),
])
def test_canon_violations_are_caught(world, cfg, mutate, rule):
    script = _valid_script()
    mutate(script)
    violations = canon_mod.validate(script, world, cfg)
    assert any(v["rule"] == rule and v["severity"] == "high" for v in violations)


def test_ecology_episode_is_locked_until_the_promise_is_established(world, cfg):
    """Correction 2, approved: the first SIX videos are all stress tests.
    'This Ocean Is One Animal' does not get to jump the queue."""
    script = _valid_script()
    script["series"] = "ecology"
    assert len(world["verdict_record"]["episodes"]) < 6
    assert any(v["rule"] == "ecology_locked"
               for v in canon_mod.validate(script, world, cfg))

    # ...and it unlocks once six episodes exist
    world["verdict_record"]["episodes"] = [
        {"verdict": "FAILED"} for _ in range(6)]
    assert not any(v["rule"] == "ecology_locked"
                   for v in canon_mod.validate(script, world, cfg))


def test_verdict_steering_refuses_collapse_monotony(world, cfg):
    """The format's biggest silent risk: every episode ends in FAILED because
    collapse is the easiest ending to write. The steerer must break the run."""
    world["verdict_record"]["episodes"] = [
        {"verdict": "FAILED"}, {"verdict": "FAILED"}]
    assert canon_mod.steer_verdict(world, cfg) != "FAILED"


def test_verdict_steering_fills_the_biggest_deficit(world, cfg):
    world["verdict_record"]["episodes"] = [
        {"verdict": "FAILED"}, {"verdict": "ADAPTED"}, {"verdict": "FAILED"}]
    # SURVIVED has a 0.3 target and a 0.0 actual — the largest gap
    assert canon_mod.steer_verdict(world, cfg) == "SURVIVED"


def test_pipeline_proposes_canon_but_never_commits_it(world, tmp_path):
    """The pipeline may propose. Only Dwij canonises. If this ever inverts,
    the world starts writing itself and the IP stops being ours."""
    os.makedirs(tmp_path / "canon", exist_ok=True)
    script = _valid_script()
    script["canon_additions"] = {
        "settlements": [{"name": "Corran Shaft"}], "organisms": [], "regions": []}

    before = json.dumps(canon_mod.load(ROOT), sort_keys=True)
    path = canon_mod.propose(script, str(tmp_path))
    after = json.dumps(canon_mod.load(ROOT), sort_keys=True)

    assert before == after, "propose() must never mutate canon.json"
    assert json.load(open(path))["proposed"]["settlements"][0]["name"] == "Corran Shaft"


def test_vocabulary_bridge_maps_new_modes_to_the_renderer_contract():
    """The script speaks channel 2 (schematic/atlas/verdict/motion); the
    renderer still speaks the proven channel-1 contract (glass/map/card).
    If this bridge breaks, panels render empty with no error at all."""
    script = script_gen._normalize({
        "title": "x",
        "scenes": [
            {"narration": "a", "visual_mode": "schematic",
             "schematic": {"headline": "the loop", "value": 340}},
            {"narration": "b", "visual_mode": "atlas",
             "atlas": {"region": "REG-01", "label": "The Cinder Shelf"}},
            {"narration": "c", "visual_mode": "verdict"},
            {"narration": "d", "visual_mode": "motion", "ai_prompt": "a vent"},
        ]}, 4)
    s = script["scenes"]
    assert s[0]["visual_mode"] == "glass"
    assert s[0]["glass"]["value"] == 340 and s[0]["schematic"]["value"] == 340
    assert s[1]["visual_mode"] == "map"
    assert s[1]["map"]["region"] == "REG-01"
    assert s[2]["visual_mode"] == "card" and s[2]["verdict_card"] is True
    assert s[3]["visual_mode"] == "ai_image" and s[3]["hero_motion"] is True


def test_stress_test_spine_survives_the_critique_pass(monkeypatch):
    """A retention editor rewrites words. It does not get to rewrite canon —
    if the critique can drop the verdict or the region, the gate is worthless."""
    original = script_gen._normalize({
        "title": "x", "verdict": "ADAPTED", "region": "REG-01",
        "hidden_dependency": "one aquifer",
        "scenes": [{"narration": "one", "visual_mode": "ai_image"}]}, 1)
    stripped = {"title": "x", "scenes": [{"narration": "sharper", "visual_mode": "ai_image"}]}
    monkeypatch.setattr(script_gen, "_llm", lambda *a: json.dumps(stripped))

    result = script_gen._critique(original, {"llm": {"critique": True},
                                             "channel": {"language": "en-us"}},
                                  "key", "long", 1)
    assert result["verdict"] == "ADAPTED"
    assert result["region"] == "REG-01"
    assert result["hidden_dependency"] == "one aquifer"
