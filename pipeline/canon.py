"""Canon — the world bible as executable infrastructure.

Channel 2's whole bet is that the WORLD is the moat. A world only compounds if
it is consistent, and a weekly AI pipeline will absolutely drift unless the
continuity is mechanical rather than hopeful. So:

  * load()            — read canon/canon.json
  * brief()           — the slice of canon injected into every LLM prompt
  * validate()        — does this script contradict the world? (hard gate)
  * steer_verdict()   — keep the SURVIVED/ADAPTED/FAILED mix honest
  * propose()         — write PROPOSED additions to canon/pending.json

Nothing in this module ever writes to canon.json. New canon lands in
canon/pending.json and Dwij merges it by hand. The pipeline may propose;
only the human may canonise. That is the point.
"""
from __future__ import annotations

import json
import os
import re

CANON_PATH = os.path.join("canon", "canon.json")
PENDING_PATH = os.path.join("canon", "pending.json")

VERDICTS = ("SURVIVED", "ADAPTED", "FAILED")


# ── load ─────────────────────────────────────────────────────────────────
def load(repo_root: str = ".") -> dict:
    with open(os.path.join(repo_root, CANON_PATH), encoding="utf-8") as f:
        return json.load(f)


def art_bible(repo_root: str = ".") -> str:
    path = os.path.join(repo_root, "canon", "art_bible.md")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


# ── prompt injection ─────────────────────────────────────────────────────
def brief(canon: dict, *, include_teased: bool = False) -> str:
    """The canon slice every script prompt sees. Kept tight on purpose — a
    10k-token world bible in the prompt buys drift, not fidelity."""
    p = canon["planet"]
    ph = canon["physics"]
    lines = [
        f"PLANET: {p['name']} — {p['designation']}.",
        f"TRUTH LABEL (spoken in the first 10 seconds, every episode): "
        f"\"{p['truth_label']}\"",
        "",
        "PHYSICS — these are HARD constants. Every mechanism you write must be "
        "consistent with them, and you may not invent new ones:",
        f"- Star: {ph['star']['type']}, {ph['star']['luminosity_solar']} solar "
        f"luminosity. {ph['star']['consequence']}",
        f"- Gravity: {ph['gravity_g']} g. {ph['consequence_gravity']}",
        f"- Day: {ph['day_length_hours']} hours. {ph['consequence_day']}",
        f"- Atmosphere: {ph['atmosphere']['pressure_bar']} bar, "
        f"{ph['atmosphere']['composition']}. {ph['atmosphere']['consequence']}",
        f"- Magnetosphere: {ph['magnetosphere']}",
        f"- Water: {ph['water']}",
        "",
        "ATLAS — regions that EXIST. You may not invent a region; you may not "
        "mention an unrevealed one:",
    ]
    for r in canon["atlas"]["regions"]:
        if r["status"] == "teased" and not include_teased:
            lines.append(
                f"- {r['name']} ({r['id']}): TEASED ONLY. It may be glimpsed in "
                f"a closing shot. It may NOT be the setting of this episode.")
            continue
        lines.append(
            f"- {r['name']} ({r['id']}, {r['type']}): {r['description']} "
            f"KEY FACT: {r['engineering_fact']}")

    if canon.get("settlements"):
        lines += ["", "SETTLEMENTS ALREADY DOCUMENTED (never contradict these; "
                        "a new episode documents a NEW settlement):"]
        for s in canon["settlements"]:
            lines.append(
                f"- {s['name']} ({s['id']}, {s['region']}): {s['premise']} "
                f"Verdict: {s['verdict']} — {s['verdict_reason']}")

    if canon.get("organisms"):
        lines += ["", "ORGANISMS IN CANON (their biology is fixed):"]
        for o in canon["organisms"]:
            lines.append(
                f"- {o['name']} ({o['id']}, {o['region']}): {o['biology']} "
                f"Real-world basis: {o['real_world_basis']}")

    nr = canon["naming_rules"]
    lines += [
        "",
        "NAMING RULES:",
        f"- Settlements: {nr['settlements']}",
        f"- Organisms: {nr['organisms']}",
        f"- Regions: {nr['regions']}",
        f"- Forbidden: {', '.join(nr['forbidden'])}",
        "",
        "HARD RULES:",
    ]
    lines += [f"- {r}" for r in canon["hard_rules"]]
    return "\n".join(lines)


def entity_names(canon: dict) -> set[str]:
    names = set()
    for key in ("settlements", "organisms"):
        for e in canon.get(key, []):
            names.add(e["name"].lower())
            if e.get("common_name"):
                names.add(e["common_name"].lower())
    for r in canon["atlas"]["regions"]:
        names.add(r["name"].lower())
    names.add(canon["planet"]["name"].lower())
    if canon["physics"].get("moon_name"):
        names.add(canon["physics"]["moon_name"].lower())
    return names


# ── verdict steering ─────────────────────────────────────────────────────
def steer_verdict(canon: dict, cfg: dict) -> str:
    """Which verdict does the channel NEED next?

    Left alone, an LLM writing 'stress test' episodes will make everything
    collapse — collapse is the easiest ending to write and the most boring to
    watch six times. So the next episode's verdict is chosen by how far the
    recent record has drifted from the target mix, and handed to the script
    prompt as a constraint rather than a suggestion.
    """
    target = cfg.get("format", {}).get(
        "outcome_ratio_target", {"SURVIVED": 0.3, "ADAPTED": 0.4, "FAILED": 0.3})
    window = int(cfg.get("format", {}).get("outcome_ratio_window", 6))
    recent = [e["verdict"] for e in canon["verdict_record"]["episodes"][-window:]]
    if not recent:
        return "FAILED"  # the pilot is a FAILED — establishing the stakes

    total = len(recent)
    # the verdict whose actual share is furthest BELOW its target share
    deficit = {
        v: float(target.get(v, 0)) - (recent.count(v) / total) for v in VERDICTS
    }
    # never three of the same verdict in a row, whatever the arithmetic says
    if len(recent) >= 2 and recent[-1] == recent[-2]:
        deficit.pop(recent[-1], None)
    return max(deficit, key=deficit.get)


# ── validation ───────────────────────────────────────────────────────────
def validate(script: dict, canon: dict, cfg: dict) -> list[dict]:
    """Structural canon check. Returns a list of violations:
        [{"severity": "high|low", "rule": "...", "detail": "..."}]

    This is the cheap, deterministic half of the gate — it catches the errors
    that don't need an LLM (wrong verdict vocabulary, planet name in the title,
    an episode set in an unrevealed region, a title that leaks the planet).
    The expensive half — 'is this mechanism physically possible' — lives in
    pipeline/canon_check.py, which asks a model with search.
    """
    out: list[dict] = []
    fmt = cfg.get("format", {})
    title = str(script.get("title", ""))
    planet = canon["planet"]["name"]

    # Correction: the planet's name never sells the video.
    if not fmt.get("planet_name_in_title", False):
        if re.search(rf"\b{re.escape(planet)}\b", title, re.I):
            out.append({
                "severity": "high",
                "rule": "planet_name_in_title",
                "detail": f"Title contains the planet name '{planet}'. The title "
                          f"sells the premise; the episode builds the IP.",
            })

    verdict = str(script.get("verdict", "")).upper().strip()
    if verdict not in VERDICTS:
        out.append({
            "severity": "high",
            "rule": "verdict_vocabulary",
            "detail": f"verdict must be one of {VERDICTS}, got '{verdict}'.",
        })

    # The spine: an episode without a stress event is not an episode.
    for field in ("settlement", "systems", "stress_event", "hidden_dependency"):
        if not script.get(field):
            out.append({
                "severity": "high",
                "rule": "stress_test_spine",
                "detail": f"Missing '{field}'. Every episode is: systems -> biome "
                          f"-> one stress event -> verdict. No exceptions.",
            })

    # Region must exist and must be revealed (teased regions are glimpse-only).
    regions = {r["id"]: r for r in canon["atlas"]["regions"]}
    rid = str(script.get("region", "")).strip()
    if rid not in regions:
        out.append({
            "severity": "high",
            "rule": "region_exists",
            "detail": f"region '{rid}' is not in the atlas. Episodes may not "
                      f"invent geography; new regions are revealed by the human.",
        })
    elif regions[rid]["status"] == "teased":
        out.append({
            "severity": "high",
            "rule": "region_revealed",
            "detail": f"region '{rid}' is teased-only and cannot be the setting "
                      f"of an episode yet.",
        })

    # Ecology episodes are locked until the promise is established.
    unlock = int(fmt.get("ecology_episode_unlocks_after", 6))
    done = len(canon["verdict_record"]["episodes"])
    if script.get("series") == "ecology" and done < unlock:
        out.append({
            "severity": "high",
            "rule": "ecology_locked",
            "detail": f"The first {unlock} episodes are ALL stress tests. Ecology "
                      f"appears inside them as threat/resource/solution — not as "
                      f"its own episode. ({done}/{unlock} published.)",
        })

    # A settlement name that already exists is a continuity error, not a
    # callback — UNLESS its canon entry belongs to an episode that has not
    # published yet. Cases are designed in canon first; their debut episode
    # is allowed to name them (e.g. SET-01 Tehlmark Deep debuting in EP-01).
    unpublished = {str(e.get("episode", "")).lower()
                   for e in canon.get("verdict_record", {}).get("episodes", [])
                   if not e.get("published")}
    debuting = {s["name"].lower() for s in canon.get("settlements", [])
                if str(s.get("episode", "")).lower() in unpublished}
    existing = {s["name"].lower() for s in canon.get("settlements", [])}
    new_name = str(script.get("settlement", {}).get("name", "")).lower()
    if (new_name and new_name in existing and new_name not in debuting
            and not script.get("is_return_episode")):
        out.append({
            "severity": "low",
            "rule": "settlement_unique",
            "detail": f"'{new_name}' is already documented. Set is_return_episode "
                      f"if this is a deliberate revisit.",
        })

    if not script.get("truth_label_spoken"):
        out.append({
            "severity": "low",
            "rule": "truth_label",
            "detail": "The fiction disclosure must land in the first 10 seconds.",
        })
    return out


# ── proposals ────────────────────────────────────────────────────────────
def propose(script: dict, repo_root: str = ".") -> str | None:
    """Write the script's canon_additions to canon/pending.json for human
    review. The pipeline proposes; only Dwij canonises."""
    additions = script.get("canon_additions") or {}
    if not any(additions.get(k) for k in ("settlements", "organisms", "regions")):
        return None
    path = os.path.join(repo_root, PENDING_PATH)
    payload = {
        "episode_title": script.get("title"),
        "verdict": script.get("verdict"),
        "proposed": additions,
        "_instructions": "Review, edit, then merge into canon/canon.json by hand. "
                         "Nothing here is canon until you move it.",
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[canon] {sum(len(v) for v in additions.values() if isinstance(v, list))} "
          f"proposed addition(s) written to {PENDING_PATH} — awaiting your review")
    return path
