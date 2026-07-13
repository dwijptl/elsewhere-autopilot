"""Stage 1 — case selection + scene-segmented script.

ELSEWHERE writes one thing: a CIVILIZATION STRESS TEST, set on one persistent
living planet. Every episode is the same four movements —

    the settlement's systems  ->  the biome that shaped them
    ->  one stress event      ->  SURVIVED / ADAPTED / FAILED

— and nothing here may contradict canon/canon.json. The world is the moat, so
the world is enforced in code: every prompt is built on top of a canon brief,
every draft is validated against canon before a single second of voice is paid
for, and the next episode's verdict is STEERED so the channel doesn't decay
into six collapses in a row.

Reads learnings.md (analytics loop) so hooks, pacing and packaging adapt to
what has actually performed.
"""
import json
import math
import os
import re
import time

import requests

import canon as canon_mod
import visual_beats as visual_beats_mod

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


_anthropic_available: list | None = None


def _anthropic_discover(headers: dict) -> list[str]:
    """Ask the API which models this key can actually use (newest first).
    Cached per run; failure just returns [] and we rely on config names."""
    global _anthropic_available
    if _anthropic_available is None:
        try:
            r = requests.get("https://api.anthropic.com/v1/models?limit=100",
                             headers=headers, timeout=30)
            r.raise_for_status()
            _anthropic_available = [m["id"] for m in r.json().get("data", [])]
            print(f"[script] anthropic models available: "
                  f"{_anthropic_available[:6]}")
        except Exception:
            _anthropic_available = []
    return _anthropic_available


def _anthropic(prompt: str, cfg: dict, api_key: str) -> str:
    """Claude for script writing — used when ANTHROPIC_API_KEY is set."""
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01",
               "content-type": "application/json"}
    models = [cfg["llm"].get("anthropic_model", "claude-sonnet-5")] + list(
        cfg["llm"].get("anthropic_fallback_models", ["claude-haiku-4-5-20251001"]))
    # self-heal: append whatever sonnet/haiku this key really has access to
    discovered = _anthropic_discover(headers)
    models += [m for m in discovered if "sonnet" in m]
    models += [m for m in discovered if "haiku" in m]
    seen: set = set()
    models = [m for m in models if not (m in seen or seen.add(m))]

    last_err = None
    for model in models:
        body = {
            "model": model,
            "max_tokens": 8000,
            "temperature": min(float(cfg["llm"].get("temperature", 0.9)), 1.0),
            "system": ("You are a JSON API. Respond with ONLY the requested "
                       "JSON object — no preamble, no markdown fences, no "
                       "commentary after the closing brace."),
            "messages": [{"role": "user", "content": prompt}],
        }
        for attempt in range(3):
            try:
                r = requests.post(ANTHROPIC_URL, json=body, headers=headers,
                                  timeout=180)
                if r.status_code == 404 or (r.status_code == 400
                                            and "model" in r.text.lower()):
                    print(f"[script] anthropic model {model} unavailable, next")
                    last_err = r.text[:200]
                    break
                if r.status_code in (429, 529):
                    wait = 20 * (attempt + 1)
                    print(f"[script] anthropic busy, sleeping {wait}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()["content"][0]["text"]
            except requests.RequestException as e:
                last_err = str(e)
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Anthropic call failed on all models: {last_err}")


def _llm(prompt: str, cfg: dict, gemini_key: str) -> str:
    """Route to Claude when a key exists (better scripts), else Gemini.
    Any Claude failure silently falls back to Gemini — runs never block."""
    ak = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    provider = str(cfg["llm"].get("provider", "auto")).lower()
    if ak and provider in ("auto", "anthropic"):
        try:
            return _anthropic(prompt, cfg, ak)
        except Exception as e:
            print(f"[script] anthropic failed ({e}) -> gemini fallback")
    return _gemini(prompt, cfg, gemini_key)


def _gemini(prompt: str, cfg: dict, api_key: str) -> str:
    models = [cfg["llm"]["model"]] + list(cfg["llm"].get("fallback_models", []))
    last_err = None
    for model in models:
        url = f"{API_BASE}/{model}:generateContent?key={api_key}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": cfg["llm"].get("temperature", 0.9),
            },
        }
        for attempt in range(3):
            try:
                r = requests.post(url, json=body, timeout=120)
                if r.status_code == 404 or (r.status_code == 400 and "model" in r.text.lower()):
                    print(f"[script] model {model} unavailable, trying next")
                    last_err = r.text
                    break
                if r.status_code == 429:
                    wait = 20 * (attempt + 1)
                    print(f"[script] rate limited, sleeping {wait}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except requests.RequestException as e:
                last_err = str(e)
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Gemini call failed on all models. Last error: {last_err}")


def _parse_json(text: str) -> dict:
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # LLMs sometimes add prose around the JSON — extract the first
        # balanced object (string-aware brace scan) and parse that.
        start = text.find("{")
        if start == -1:
            raise
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i + 1])
        raise


def _wpm(cfg: dict) -> int:
    return int(cfg["channel"].get("wpm", 150))


def _lang_rules(cfg: dict) -> str:
    """Channel 2 is English. What used to be a language switch is now the
    NARRATOR CONTRACT — the single hardest thing to keep stable across a
    weekly AI pipeline is voice, so it is spelled out in every prompt."""
    return """
NARRATOR CONTRACT — this is the whole brand, get it wrong and nothing else matters:
- English. A field documentary narrator: measured, warm, precise. An engineer's
  accuracy with a naturalist's affection. Attenborough's restraint, not his
  awe-voice.
- NEVER: "Imagine a world where", "But here's the terrifying part", "What
  happened next will", "Let that sink in", "buckle up", "welcome back",
  rhetorical questions stacked three deep, or ANY sentence that sounds like a
  YouTube essay. If a line could open a hype video, delete it.
- The narrator is not surprised by the planet. They have been here for years.
  They are explaining, patiently, what went wrong and why it was always going
  to. Understatement is the register: "The engineers were not careless. They
  were working from a diagram that was, in one specific way, incomplete."
- Numbers are said plainly, with units, once. Never rounded up for drama.
- Every scene ends on a concrete object, temperature, depth or consequence —
  never on a summary and never on a rhetorical question.
"""


def _style_rules() -> str:
    return """
WRITING STYLE — a filed report, not a video essay:
- Rhythm: alternate short declaratives (4-8 words) with longer explanatory
  sentences. Read it aloud; if a line has no stress pattern, rewrite it.
- Specificity beats breadth: one mechanism per scene, named, with the number
  attached. "The exchanger surfaces dropped from 340 to 160 watts per square
  metre per kelvin" beats "cooling efficiency plummeted".
- Show the engineering DECISION, not just the outcome. Every failure in this
  world was a reasonable choice made with incomplete information — that is
  what makes the format land, and it is why the comments argue.
- The verdict is never gloated over. It is stated, and then the episode stops.
"""


def _canon_rules() -> str:
    return """
THE FORMAT SPINE — non-negotiable, every single episode:
1. SYSTEMS   — what keeps this settlement alive? (heat, water, air, power,
   food) Name the machine and the number it runs at.
2. BIOME     — why is the machine built THAT way? The biome is not scenery;
   it is the reason the engineering exists in the form it does.
3. STRESS    — ONE event tests ONE hidden dependency. Not a disaster montage.
   One thing, followed all the way down.
4. VERDICT   — SURVIVED, ADAPTED or FAILED. Stated once, in near silence.

THE HIDDEN DEPENDENCY is the whole episode. It is the thing two systems shared
that nobody drew on the same diagram. Find it in the systems map, hide it in
plain sight during the first third, and let the stress event reveal it.

FICTION DISCLOSURE: the truth label is spoken inside the first 10 seconds and
appears in the description. We never pretend this is real. The credibility
promise is the inverse: the PLACE is invented, and every MECHANISM is real.
A fabricated mechanism is the one unforgivable error on this channel — if you
cannot name the real-world engineering or biological analogue for something you
have written, you may not write it.
"""


def _ai_max(cfg: dict) -> int:
    """AI-image budget per episode.

    INVERSION vs channel 1: a fictional planet has no stock footage, so AI
    stills are the PRIMARY visual source, not the garnish. A 6-7 minute episode
    is carried by 12-16 stills."""
    aicfg = cfg.get("ai_images", {})
    if os.environ.get("FAL_KEY", "").strip():
        return int(aicfg.get("max_per_video_flux", 16))
    return int(aicfg.get("max_per_video", 8))


# ai_image is the default mode. 'schematic' replaces channel 1's glass panel
# (an engineering dossier diagram, not a liquid-glass HUD), 'atlas' replaces
# the real-world map, and 'verdict' is the SURVIVED/ADAPTED/FAILED card.
VALID_MODES = ("ai_image", "motion", "schematic", "atlas", "kinetic", "stat",
               "card", "verdict", "broll")


def _num_or_none(value):
    """Return a finite float, otherwise None (LLMs sometimes emit NaN/inf)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalize_stat(raw) -> dict:
    """Keep only safe, bounded fields understood by the Remotion stat cards."""
    stat = raw if isinstance(raw, dict) else {}
    value = _num_or_none(stat.get("value"))
    baseline = _num_or_none(stat.get("baseline"))
    maximum = _num_or_none(stat.get("max"))
    bars = []
    if isinstance(stat.get("bars"), list):
        for item in stat["bars"][:5]:
            if not isinstance(item, dict):
                continue
            bar_value = _num_or_none(item.get("value"))
            if bar_value is None:
                continue
            bars.append({"label": str(item.get("label", ""))[:24],
                         "value": bar_value})
    result = {
        "value": value if value is not None else 0,
        "suffix": str(stat.get("suffix", ""))[:12],
        "label": str(stat.get("label", ""))[:100],
    }
    if baseline is not None:
        result["baseline"] = baseline
    if maximum is not None and maximum > 0:
        result["max"] = maximum
    if len(bars) >= 2:
        result["bars"] = bars
    return result


def _normalize_glass(raw) -> dict:
    """Bound the data contract consumed by the liquid-glass renderer."""
    data = raw if isinstance(raw, dict) else {}
    result = {
        "kicker": str(data.get("kicker", ""))[:32],
        "headline": str(data.get("headline", ""))[:90],
        "body": str(data.get("body", ""))[:130],
        "suffix": str(data.get("suffix", ""))[:14],
        "label": str(data.get("label", ""))[:90],
        "location": str(data.get("location", ""))[:60],
        "coordinates": str(data.get("coordinates", ""))[:36],
        "chapter": str(data.get("chapter", ""))[:24],
    }
    value = _num_or_none(data.get("value"))
    delta = _num_or_none(data.get("delta"))
    if value is not None:
        result["value"] = value
    if delta is not None:
        result["delta"] = delta
    direction = str(data.get("delta_direction", data.get("deltaDirection", ""))).lower()
    if direction in ("up", "down", "flat"):
        result["deltaDirection"] = direction
    return result


def _normalize_milestone(raw) -> dict:
    """Bound the per-scene simulation milestone for the story HUD."""
    data = raw if isinstance(raw, dict) else {}
    value = _num_or_none(data.get("value"))
    if value is None:
        return {}
    return {"value": value,
            "label": str(data.get("label", ""))[:18],
            "unit": str(data.get("unit", ""))[:8]}


def _normalize(script: dict, min_scenes: int) -> dict:
    """Validate + default-fill a script dict. Raises on structural problems."""
    assert isinstance(script["scenes"], list) and len(script["scenes"]) >= min_scenes
    for s in script["scenes"]:
        assert s["narration"].strip()
        s.setdefault("visual_mode", "ai_image")
        if s["visual_mode"] not in VALID_MODES:
            s["visual_mode"] = "ai_image"

        # ── vocabulary bridge ────────────────────────────────────────────
        # The SCRIPT speaks channel 2's language (schematic / atlas / verdict /
        # motion). The renderer and asset stages still speak the proven
        # channel-1 contract (glass / map / card). Translating here — once, at
        # the boundary — buys the new format without forking 2,000 lines of
        # working plumbing. The panels look nothing alike; only the data shape
        # is shared.
        mode = s["visual_mode"]
        if mode == "motion":
            s["visual_mode"] = "ai_image"
            s["hero_motion"] = True      # picked up by the Wan/fal motion stage
        elif mode == "schematic":
            s["visual_mode"] = "glass"   # rendered by the dossier schematic
        elif mode == "atlas":
            s["visual_mode"] = "map"     # rendered by the fictional atlas
        elif mode == "verdict":
            s["visual_mode"] = "card"
            s["verdict_card"] = True
        s.setdefault("hero_motion", False)
        s.setdefault("verdict_card", False)

        s.setdefault("search_terms", [])
        s.setdefault("ai_prompt", "")
        s.setdefault("kinetic_text", "")
        s["stat"] = _normalize_stat(s.get("stat"))
        s["glass"] = _normalize_glass(s.get("schematic") or s.get("glass"))
        s["schematic"] = s["glass"]
        s.setdefault("card", {})
        atlas = s.get("atlas") or s.get("map") or {}
        s["atlas"] = atlas
        s["map"] = atlas
        s["milestone"] = _normalize_milestone(s.get("milestone"))
        d = str(s.get("delivery", "calm")).lower().strip()
        s["delivery"] = d if d in ("hook", "calm", "reveal", "urgent") else "calm"
        role = str(s.get("visual_role", "")).lower().strip()
        s["visual_role"] = (role if role in ("experience", "explanation",
                                             "measurement") else "")
        s["must_show"] = [str(t)[:40] for t in (s.get("must_show") or [])
                          if str(t).strip()][:3]
    script["scenes"][0]["delivery"] = "hook"
    assert script["title"].strip()
    script.setdefault("thumb_text", script["title"][:30])
    script.setdefault("thumb_prompt", "")
    script["thumb_headline"] = str(script.get("thumb_headline", ""))[:60]
    script["thumb_question"] = str(script.get("thumb_question", ""))[:40]
    script["premise"] = str(script.get("premise", ""))[:200]
    cv = script.get("changing_variable") or {}
    script["changing_variable"] = {"label": str(cv.get("label", ""))[:18],
                                   "unit": str(cv.get("unit", ""))[:8]}
    script["hero_prompt"] = str(script.get("hero_prompt", ""))[:500]
    script["forbidden_visuals"] = [str(t)[:40] for t in
                                   (script.get("forbidden_visuals") or [])
                                   if str(t).strip()][:6]
    script["next_tease_topic"] = str(script.get("next_tease_topic", ""))[:120]
    script["title_options"] = [str(t)[:90] for t in
                               (script.get("title_options") or [])
                               if str(t).strip()][:5]
    thumbs = []
    for item in (script.get("thumb_options") or [])[:3]:
        if isinstance(item, dict) and str(item.get("text", "")).strip():
            thumbs.append({"text": str(item.get("text", ""))[:30],
                           "concept": str(item.get("concept", ""))[:120]})
    script["thumb_options"] = thumbs

    # ── the stress-test spine (channel 2's reason to exist) ──────────────
    script["verdict"] = str(script.get("verdict", "")).upper().strip()
    script["region"] = str(script.get("region", ""))[:12]
    script["series"] = str(script.get("series", "stress_test"))[:20]
    settlement = script.get("settlement") or {}
    script["settlement"] = {
        "name": str(settlement.get("name", ""))[:40],
        "premise": str(settlement.get("premise", ""))[:240],
        "population": _num_or_none(settlement.get("population")),
    }
    script["systems"] = [
        {"name": str(sy.get("name", ""))[:24],
         "how": str(sy.get("how", ""))[:200],
         "runs_at": str(sy.get("runs_at", ""))[:40],
         # two systems naming the same depends_on IS the hidden dependency.
         # The schematic renders it as one shared node; the audience finds it
         # before the narrator names it.
         "depends_on": str(sy.get("depends_on", ""))[:40]}
        for sy in (script.get("systems") or []) if isinstance(sy, dict)
    ][:5]
    script["hidden_dependency"] = str(script.get("hidden_dependency", ""))[:300]
    stress = script.get("stress_event") or {}
    script["stress_event"] = {
        "name": str(stress.get("name", ""))[:60],
        "trigger": str(stress.get("trigger", ""))[:200],
        "cascade": [str(c)[:120] for c in (stress.get("cascade") or [])][:6],
    }
    script["verdict_reason"] = str(script.get("verdict_reason", ""))[:300]
    script["real_world_basis"] = [str(b)[:160] for b in
                                  (script.get("real_world_basis") or [])][:6]
    script["truth_label_spoken"] = bool(script.get("truth_label_spoken", False))
    script["canon_refs"] = [str(r)[:40] for r in (script.get("canon_refs") or [])][:12]
    additions = script.get("canon_additions") or {}
    script["canon_additions"] = {
        k: (additions.get(k) or []) for k in ("settlements", "organisms", "regions")
    }
    return script


def _critique(script: dict, cfg: dict, api_key: str, kind: str,
              min_scenes: int) -> dict:
    """Second pass — a ruthless retention editor rewrites weak scenes.
    Fail-open: any problem returns the original draft."""
    if not cfg["llm"].get("critique", True):
        return script
    fmt = ("a ~28-second vertical Short (hook <= 12 words; full PAYOFF, then "
           "a loop-friendly final line)" if kind == "short"
           else "a 6-minute documentary (30s hook, mid-video re-hook, payoff ending)")
    prompt = f"""You are a ruthless retention editor for ELSEWHERE, a
speculative-documentary channel. Below is a draft script for {fmt}.

Grade every scene 1-10 on: hook strength, MECHANISM specificity (a named
system, a real number, a consequence you can picture), curiosity pull into
the NEXT scene, and sentence rhythm. Then REWRITE any scene scoring below 8.

The two failure modes you are hunting:
  (a) VIDEO-ESSAY VOICE — hype, rhetorical questions, "here's the crazy part".
      Cut it to the bone. The narrator is calm and has been on this planet for
      years.
  (b) VAGUE ENGINEERING — "the cooling system failed" is not a scene. WHICH
      surface, at WHAT temperature, losing HOW much capacity, over WHAT period.
      The audience is here for the machine.

Keep the same JSON schema, scene count, visual_mode, and every structural field
(settlement, systems, stress_event, hidden_dependency, verdict, region,
canon_refs, canon_additions). You may improve narration, titles, kinetic_text,
delivery and thumbnail text — nothing else.
{_lang_rules(cfg)}
Return ONLY the full revised JSON — no scores, no commentary.

DRAFT:
{json.dumps(script, ensure_ascii=False)}"""
    try:
        revised = _normalize(_parse_json(_llm(prompt, cfg, api_key)), min_scenes)
        # The critique edits words, not factual display payloads. Preserve the
        # first pass's structured visual data so a rewrite cannot silently turn
        # a stat/glass/map scene into an empty overlay.
        for before, after in zip(script["scenes"], revised["scenes"]):
            # both halves of the vocabulary bridge must be preserved: the
            # script speaks 'schematic'/'atlas', the renderer reads
            # 'glass'/'map'. Preserving only one leaves the renderer with an
            # empty panel and no error — the worst kind of failure.
            for field in ("stat", "card", "schematic", "glass", "atlas", "map",
                          "milestone", "must_show", "visual_role",
                          "hero_motion", "verdict_card"):
                after[field] = before.get(field, after.get(field, {}))
        for field in ("premise", "changing_variable", "hero_prompt",
                      "forbidden_visuals", "title_options", "thumb_options",
                      "thumb_headline", "thumb_question", "next_tease_topic",
                      # the spine survives the critique untouched — a retention
                      # editor does not get to rewrite canon
                      "verdict", "verdict_reason", "region", "series",
                      "settlement", "systems", "stress_event",
                      "hidden_dependency", "real_world_basis", "canon_refs",
                      "canon_additions", "truth_label_spoken"):
            if not revised.get(field):
                revised[field] = script.get(field, revised.get(field))
        revised["topic"] = script.get("topic", "")
        print("[script] critique pass applied")
        return revised
    except Exception as e:
        print(f"[script] critique pass skipped ({e}) — keeping draft")
        return script


def load_learnings(repo_root: str) -> str:
    """Analytics learnings + the permanent failure registry — both are
    injected into every topic/script prompt so past mistakes become rules."""
    text = ""
    try:
        with open(os.path.join(repo_root, "learnings.md"), encoding="utf-8") as f:
            text = f.read().strip()[:6000]
    except Exception:
        pass
    try:
        with open(os.path.join(repo_root, "FAILURES.md"), encoding="utf-8") as f:
            failures = f.read().strip()[:3000]
        if failures:
            text += ("\n\nPAST PRODUCTION FAILURES — HARD RULES, never repeat "
                     "any of these:\n" + failures)
    except Exception:
        pass
    return text.strip()


def pick_topic(cfg: dict, api_key: str, done_file: str = "topics_done.txt",
               learnings: str = "") -> str:
    forced = os.environ.get("FORCED_TOPIC", "").strip()
    if forced:
        print(f"[script] using forced topic: {forced}")
        return forced

    done, tease = [], ""
    if os.path.exists(done_file):
        with open(done_file, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith("#"):
                    continue
                if ln.startswith("NEXT:"):
                    tease = ln[5:].strip()  # last marker wins
                else:
                    done.append(ln)
    # honor the previous episode's on-screen tease — the video made a promise
    if tease and tease not in done:
        print(f"[script] honoring previous episode's on-screen tease: {tease}")
        return tease

    learn_block = (f"\nWHAT HAS WORKED ON THIS CHANNEL (analytics digest):\n{learnings}\n"
                   if learnings else "")
    world = canon_mod.load(os.path.dirname(os.path.dirname(
        os.path.abspath(done_file))) if os.path.isabs(done_file) else ".")
    steer = canon_mod.steer_verdict(world, cfg)
    prompt = f"""You are the showrunner of ELSEWHERE — a speculative
documentary channel that stress-tests civilizations on ONE persistent,
original, openly-fictional planet.

{canon_mod.brief(world)}

FORMAT (every episode, no exceptions): a settlement's SYSTEMS -> the BIOME that
shaped them -> ONE STRESS EVENT that tests ONE hidden dependency -> a VERDICT
of SURVIVED, ADAPTED or FAILED.
{_canon_rules()}
AUDIENCE: {cfg['channel']['audience']}
{learn_block}
Cases already documented (NEVER repeat or closely paraphrase these):
{json.dumps(done[-100:], indent=0, ensure_ascii=False)}

VERDICT QUOTA — the next episode must end in: {steer}
This is not a suggestion. Left unchecked, this format decays into six
collapses in a row, and a channel where everything dies is a channel where
nothing is at stake. Invent a case whose HONEST outcome is {steer}.

Invent THREE candidate cases — a new settlement on a REVEALED region of the
atlas, each with a system worth explaining and a dependency worth hiding.

THE STRESS-TEST SCORECARD — score each candidate 1-10 on ALL of:
- machine: is there ONE system a viewer can hold in their head and draw?
- dependency: is the hidden coupling genuinely non-obvious, and genuinely fair
  (visible in hindsight, invisible in foresight)? THIS IS THE MOST IMPORTANT
  SCORE. A dependency the audience guesses at minute two is a dead episode.
- escalation: does the stress produce 5+ measurable, monotonic steps
  (a temperature, a pressure, a population, a reserve, falling or rising)?
- biome_lock: could this case ONLY happen on this planet, given its physics?
  A case that would work identically on Earth is a rejected case.
- reality: does every mechanism have a REAL, citable Earth analogue
  (engineering, chemistry, biology, materials)? Name it.
- debate: will the comments argue about whether the engineers were stupid or
  unlucky? (If everyone agrees, the episode has no comment section.)
- thumbnail: can it be drawn as ONE image that promises the premise?
- canon: does it deepen the world without contradicting a single line above?
- honest_verdict: does the case genuinely end in {steer} without cheating?

REJECT any candidate that needs a mechanism you cannot ground in real science
(reality <= 5), that would work unchanged on Earth (biome_lock <= 5), or whose
verdict has to be forced (honest_verdict <= 5).

Return JSON exactly:
{{"candidates": [{{"topic": "the episode's working title — a premise, never the
planet's name", "settlement": "...", "region": "REG-0X", "machine": "one line",
"hidden_dependency": "one line", "verdict": "{steer}",
"scores": {{"machine": 0, "dependency": 0, "escalation": 0, "biome_lock": 0,
"reality": 0, "debate": 0, "thumbnail": 0, "canon": 0, "honest_verdict": 0}},
"total": 0}}],
"topic": "<the candidate with the highest total>"}}"""
    last_err = None
    for attempt in range(3):
        try:
            parsed = _parse_json(_llm(prompt, cfg, api_key))
            topic = str(parsed.get("topic") or "").strip()
            if not topic:
                cands = parsed.get("candidates") or []
                cands = sorted(cands, key=lambda c: -float(c.get("total", 0)))
                topic = str(cands[0]["topic"]).strip()
            print(f"[script] auto-picked topic (journey-tested): {topic}")
            return topic
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            last_err = e
            print(f"[script] bad topic JSON (attempt {attempt + 1}): {e}")
    raise RuntimeError(f"Could not pick a topic after 3 attempts: {last_err}")


def _plan_visual_beats(script: dict, cfg: dict, api_key: str) -> dict:
    """Add sentence-level stock intentions using one free Gemini request.

    This intentionally bypasses the optional paid script provider.  The task
    is constrained visual indexing, not creative writing, and Gemini's free
    tier is sufficient.  Any API/schema failure falls back to deterministic
    coverage based on the scene's existing search terms.
    """
    settings = cfg.get("longform_quality", {}).get("visual_beats", {})
    if not settings.get("enabled", True):
        return script
    payload = visual_beats_mod.planner_payload(script, cfg)
    forbidden = script.get("forbidden_visuals") or []
    contract = ""
    if forbidden or script.get("hero_prompt"):
        contract = f"""
CONTINUITY CONTRACT (breaking it ruins the episode):
- FORBIDDEN VISUALS: {json.dumps(forbidden)} — never write a query that could
  return any of these; they contradict the premise.
- The episode has ONE recurring hero ({str(script.get('hero_prompt', ''))[:120]}).
  Beats about the protagonist are carried by that hero image — write those
  beats' queries for the surrounding ENVIRONMENT, never for stock humans.
"""
    prompt = f"""You are the visual editor of a premium science documentary.
Turn the FINAL Hindi narration below into a sentence-level visual beat sheet.
{contract}

Return ONLY JSON:
{{"scenes":[{{"n":1,"visual_beats":[{{
  "cue":"an EXACT 3-8 word verbatim phrase from the Hindi narration where this visual starts",
  "search_terms":["one exact concrete ENGLISH Pexels query","one fallback query"],
  "purpose":"what the viewer must understand from this visual"
}}]}}]}}

Rules:
- Return exactly target_beats for each scene and preserve scene order.
- Beat 1 starts at the beginning of its scene; all cues proceed in narration order.
- Each query must depict the nouns in its cue, not the scene's general mood.
- Named landmarks, animals, machines, planets and anatomy require the exact subject.
- Prefer real documentary footage: aerials, macro, natural habitat, physical processes.
- Never use metaphorical offices, typing, food, drinks, products or captive wildlife.
- Vary scale and camera language across consecutive beats.
- Do not request generated art, text, logos or copyrighted characters.

SCENES:
{json.dumps(payload, ensure_ascii=False)}"""
    try:
        raw = _parse_json(_gemini(prompt, cfg, api_key))
        script = visual_beats_mod.normalize_plan(script, raw, cfg)
        total = sum(len(s.get("visual_beats", [])) for s in script["scenes"])
        print(f"[script] semantic visual plan: {total} beats (free Gemini pass)")
        return script
    except Exception as exc:
        print(f"[script] visual beat planner skipped ({exc}) — deterministic fallback")
        return visual_beats_mod.normalize_plan(script, None, cfg)


def generate_script(cfg: dict, topic: str, api_key: str, learnings: str = "",
                    script_hint: dict | None = None) -> dict:
    script_hint = script_hint or {}
    v = cfg["video"]
    wpm = _wpm(cfg)
    words = int(v["target_minutes"] * wpm)
    ai_max = _ai_max(cfg)
    motion_max = int(cfg.get("motion", {}).get("max_per_video", 2))
    learn_block = (f"\nCHANNEL LEARNINGS — apply these to hook style, pacing, and "
                   f"thumbnail text:\n{learnings}\n" if learnings else "")
    world = canon_mod.load(".")
    steer = str(script_hint.get("verdict") or canon_mod.steer_verdict(world, cfg)).upper()
    prompt = f"""You are the writer of ELSEWHERE — a speculative documentary
channel (voiceover + AI-generated field photography + dossier graphics, no
on-camera host). You are writing one CIVILIZATION STRESS TEST.

CASE: {topic}
TARGET: ~{words} spoken words (about {v['target_minutes']} minutes at {wpm} wpm)
HARD RANGE: {int(words * 0.92)}-{int(words * 1.08)} spoken words across all
scenes. Count before returning; expand thin scenes with mechanism, never filler.

{canon_mod.brief(world)}
{_canon_rules()}
THIS EPISODE'S VERDICT IS: {steer}
Write the case honestly toward that ending. Do not cheat it, do not soften it,
and do not reveal it early — the verdict lands in the final 40 seconds.

TONE: {cfg['channel']['tone']}
AUDIENCE: {cfg['channel']['audience']}
{learn_block}{_lang_rules(cfg)}{_style_rules()}
Return ONLY valid JSON with this exact shape:
{{
  "title": "the premise, honestly, <= 70 chars. NEVER contains the planet's name. Model: 'The Underground City That Cooked Itself'",
  "title_options": ["5 alternatives, strongest first: one plain, one mechanism-led, one number-led"],
  "thumb_text": "2-4 bold words, Latin caps (e.g. 'IT COOKED ITSELF')",
  "thumb_headline": "4-7 word dramatic line — high intensity, 100% delivered by the episode; never a fabricated claim",
  "thumb_question": "3-5 word curiosity annotation, or empty string",
  "thumb_prompt": "ENGLISH text-to-image prompt for the thumbnail, obeying the art bible: ONE subject filling 50-70% of frame, warm K-dwarf light, basalt/ochre palette, rim-lit against a mid-dark background with real depth (never near-black — it must read at 160px), bottom third kept clear for text. Documentary photograph, not concept art.",
  "thumb_options": [{{"text": "2-4 caps words", "concept": "alternative visual idea"}}, {{"text": "...", "concept": "..."}}, {{"text": "...", "concept": "..."}}],
  "region": "the atlas region ID this episode is set in (e.g. REG-01) — must already be REVEALED",
  "series": "stress_test",
  "settlement": {{"name": "obeys the naming rules", "premise": "ONE sentence: what this place is and why it exists here", "population": 0}},
  "systems": [{{"name": "COOLING", "how": "one sentence: the actual mechanism", "runs_at": "the number it normally holds (e.g. '31 C at level 9')", "depends_on": "the ONE resource or structure this system ultimately rests on (e.g. 'the aquifer'). CRITICAL: at least TWO systems must name the SAME depends_on — that shared node IS the hidden dependency, and the schematic draws it as one node with two lines running into it. Name it plainly, as an engineer would on a diagram, with no hint that it matters."}}],
  "hidden_dependency": "ONE sentence: the coupling two systems shared that nobody drew on the same diagram. This is the episode.",
  "stress_event": {{"name": "short name for the event", "trigger": "what starts it — small, plausible, unglamorous", "cascade": ["4-6 steps, each a measurable consequence of the last"]}},
  "verdict": "{steer}",
  "verdict_reason": "one sentence, stated plainly, no gloating",
  "real_world_basis": ["3-6 REAL Earth analogues that ground the mechanisms — name the actual phenomenon, material or engineering failure mode a viewer could go and look up. If you cannot fill this, you have invented a fake mechanism and must rewrite."],
  "truth_label_spoken": true,
  "canon_refs": ["IDs from canon this episode uses, e.g. REG-01, ORG-01"],
  "canon_additions": {{"settlements": [{{"name": "...", "region": "REG-0X", "premise": "...", "systems": {{}}, "hidden_dependency": "...", "verdict": "{steer}", "verdict_reason": "..."}}], "organisms": [{{"name": "...", "region": "REG-0X", "biology": "...", "real_world_basis": "...", "visual_signature": "...", "no_fixed_anatomy": true}}], "regions": []}},
  "premise": "ONE sentence: the machine, and the thing it did not know about itself",
  "changing_variable": {{"label": "the ONE metric the viewer watches move (CORE TEMP, RESERVE, PRESSURE)", "unit": "C"}},
  "hero_prompt": "ENGLISH image prompt for the recurring HERO subject the episode returns to as conditions worsen — a place, a machine or a surface, NOT a named character: subject + setting + light + camera angle, per the art bible",
  "forbidden_visuals": ["3-6 short ENGLISH phrases naming imagery that would BREAK this world: e.g. 'blue-white sunlight', 'Earth vegetation', 'glossy sci-fi chrome', 'glowing holograms', 'creature with a face'"],
  "next_tease_topic": "the EXACT case teased in the final scene, as a working title — the pipeline WILL make it the next episode, so it must be producible and canon-legal",
  "description": "2-3 sentences. MUST open with the truth label. Ends with 3 hashtags.",
  "tags": ["8-12 tags"],
  "scenes": [
    {{
      "n": 1,
      "title": "3-6 word scene title",
      "narration": "60-150 words of spoken narration",
      "visual_mode": "ai_image | motion | schematic | atlas | kinetic | stat | card | verdict",
      "visual_role": "experience | explanation | measurement",
      "delivery": "hook | calm | reveal | urgent",
      "must_show": ["1-2 short ENGLISH phrases naming what MUST be visible for this narration to be true"],
      "milestone": {{"value": 0, "label": "optional metric label", "unit": "C"}},
      "ai_prompt": "the art-bible-obedient image prompt (required when visual_mode is ai_image or motion)",
      "search_terms": ["ONLY for abstract texture beats (dust, water, rock) — leave empty otherwise; there is no stock footage of a planet that does not exist"],
      "kinetic_text": "3-6 word punch phrase (kinetic only)",
      "stat": {{"value": 0, "suffix": "", "label": "", "max": null, "baseline": null, "bars": [{{"label": "short", "value": 0}}]}},
      "card": {{"kicker": "short category", "headline": "5-10 words", "body": "one sentence, under 18 words"}},
      "schematic": {{"kicker": "SYSTEM", "headline": "what the diagram shows", "body": "one support line", "value": null, "suffix": "", "label": "", "delta": null, "delta_direction": "up | down | flat", "location": "", "coordinates": "", "chapter": ""}},
      "atlas": {{"region": "REG-01", "label": "locator caption"}}
    }}
  ]
}}

VISUAL MODES — this planet has no stock footage, so AI stills carry the film:
- MOST scenes are "ai_image". Every ai_prompt obeys the art bible: dim amber
  K-dwarf light, basalt and ochre, documentary lenses, a human or a doorway for
  scale, film grain, matte contrast. Banned: neon rim light, chrome, lens flare,
  god-rays, creatures looking at camera, text inside the image.
- EXACTLY 1-{motion_max} scenes are "motion": the single moment that must MOVE (the
  cascade's turning point, or the stress event arriving). These are expensive —
  spend them on the hook or the collapse, never on an establishing shot.
- EXACTLY 1 scene is "atlas" — the locator, early. The map of the world is the
  returning-viewer glue; every episode plants its case on it.
- EXACTLY 1-2 scenes are "schematic": the dossier diagram of the machine. This
  is where the hidden dependency hides IN PLAIN SIGHT — draw the two systems
  that share the thing, and do not comment on it.
- EXACTLY 1 scene is "verdict": the final card. SURVIVED / ADAPTED / FAILED.
  Near-silence. No music swell. State it and stop.
- 0-2 "stat" scenes when narration centres on ONE number that is MOVING.
- 0-1 "kinetic" scene for the single hardest line in the script.
- 0-1 "card" for a definition or a timeline beat.
- "broll" is allowed ONLY for abstract texture with no world-specific content
  (dust in light, water surface, rock). If a stock clip could show Earth, it is
  banned.

Script rules:
- THE MACHINE FIRST. By 90 seconds the viewer must be able to draw the
  settlement's life-support system on a napkin. You cannot break something the
  audience does not understand.
- THE HIDDEN DEPENDENCY is stated OUT LOUD exactly once, in the schematic scene,
  as a neutral fact — and its significance is not explained until the cascade.
  The pleasure of this format is the viewer seeing it half a second before the
  narrator says it.
- ONE STRESS EVENT. Not a montage of disasters. One trigger, followed all the
  way down through 4-6 measurable steps. Each step is caused by the previous
  step — if you can reorder them, they are not a cascade.
- SIMULATION ENGINE: changing_variable is the ONE number the viewer watches.
  EVERY scene carries a milestone.value on it, escalating monotonically, and the
  narration must SAY that number. A viewer must be able to answer "how bad is it
  now?" at any second.
- THE ENGINEERS WERE NOT STUPID. Every decision that led here was defensible
  with the information they had. Write at least one scene that makes the
  audience agree with the choice that kills the city. This is the difference
  between a stress test and a disaster video.
- SCALE ANCHORING: every large number gets exactly ONE physical comparison a
  viewer can feel — a body, a room, a season, a walk. Never three.
- {v['scenes_min']} to {v['scenes_max']} scenes. Scene 1 is a 20-25 second COLD OPEN that
  states the premise and speaks the truth label. First concrete mechanism by
  0:45. Re-hooks near 25%, 50%, 75%. Final scene is the verdict plus a 15-second
  glimpse of the next case.
- THE TEASE IS A CONTRACT: the final glimpse must describe next_tease_topic
  exactly, must be canon-legal, and the pipeline WILL produce it next week.
- REALITY CHECK before you return: for every mechanism you wrote, can you name
  the real Earth phenomenon it is built on? If not, delete the mechanism. The
  place is fictional; the principles are real. That sentence is the channel.
- Narration is written for the EAR. Every scene advances exactly one idea."""

    def _word_count(s: dict) -> int:
        return sum(len(str(sc.get("narration", "")).split()) for sc in s["scenes"])

    for attempt in range(3):
        try:
            script = _normalize(_parse_json(_llm(prompt, cfg, api_key)), 4)
            script["topic"] = topic
            script = _critique(script, cfg, api_key, "long", 4)
            # enforce the word budget BEFORE TTS — a short script is a short
            # video, and expanding here is free (no wasted voice credits)
            wc = _word_count(script)
            if wc < int(words * 0.88):
                print(f"[script] undershoot ({wc}/{words} words) — expansion pass")
                exp = f"""The draft below runs {wc} spoken words but must run
{int(words * 0.95)}-{int(words * 1.05)} words. Expand the THINNEST scenes with
concrete, specific material — mechanisms, named places, numbers, consequences
— never filler, never repetition. Keep the same JSON schema, scene count,
visual modes and every non-narration field unchanged.
{_lang_rules(cfg)}
Return ONLY the full revised JSON.

DRAFT:
{json.dumps(script, ensure_ascii=False)}"""
                try:
                    expanded = _normalize(_parse_json(_llm(exp, cfg, api_key)), 4)
                    for before, after in zip(script["scenes"], expanded["scenes"]):
                        for field in ("stat", "card", "glass", "map", "milestone"):
                            after[field] = before.get(field, {})
                    for field in ("premise", "changing_variable", "hero_prompt",
                                  "forbidden_visuals", "title_options",
                                  "thumb_options", "thumb_headline",
                                  "thumb_question", "next_tease_topic"):
                        if not expanded.get(field):
                            expanded[field] = script.get(field)
                    expanded["topic"] = topic
                    if _word_count(expanded) > wc:
                        script = expanded
                        print(f"[script] expanded to {_word_count(script)} words")
                except Exception as exc:
                    print(f"[script] expansion skipped ({exc})")
            script = _plan_visual_beats(script, cfg, api_key)
            modes = [s["visual_mode"] for s in script["scenes"]]
            print(f"[script] '{script['title']}' — {len(modes)} scenes, modes: {modes}")
            return script
        except (KeyError, AssertionError, json.JSONDecodeError) as e:
            print(f"[script] invalid script JSON (attempt {attempt + 1}): {e}")
    raise RuntimeError("Could not obtain a valid script after 3 attempts")


def generate_short_script(cfg: dict, topic: str, api_key: str,
                          learnings: str = "") -> dict:
    """Script for a vertical Short/Reel: one idea, ~25s, loop-friendly."""
    scfg = cfg.get("short", {})
    seconds = int(scfg.get("target_seconds", 25))
    # shorts word budget calibrates to the REAL spoken pace (Sarvam Hindi with
    # pauses runs ~95-105 wpm, well below the long-form planning rate)
    wpm = int(scfg.get("wpm", min(_wpm(cfg), 105)))
    words = int(seconds / 60 * wpm)
    short_ai_max = min(_ai_max(cfg), 2)
    learn_block = (f"\nCHANNEL LEARNINGS — apply to hook and pacing:\n{learnings}\n"
                   if learnings else "")
    prompt = f"""You are writing a YouTube SHORT / Instagram REEL script for a
faceless channel (vertical video: voiceover + b-roll + big captions).

TOPIC: {topic}
TARGET: ~{words} spoken words TOTAL (~{seconds} seconds — shorts are ruthless)
HARD RANGE: {int(words * 0.9)}-{int(words * 1.15)} words. Under {int(words * 0.9)}
feels incomplete and cheap; over {int(words * 1.15)} kills completion rate.
Count your words before returning.
TONE: {cfg['channel']['tone']}, but faster and punchier than long-form
{learn_block}{_lang_rules(cfg)}{_style_rules()}
Return ONLY valid JSON:
{{
  "title": "<= 80 chars, curiosity gap, no clickbait lies",
  "thumb_text": "2-4 bold ENGLISH/Hinglish punch words (Latin script)",
  "delivery-note": "each scene also gets \"delivery\": hook | calm | reveal | urgent (scene 1 = hook; the twist scene = reveal); and may use visual_mode \"map\" with \"map\": {{\"lat\": 0.0, \"lon\": 0.0, \"label\": \"हिन्दी\"}} when one specific place is the star (0-1 map scenes)",
  "description": "1-2 lines, end with hashtags including #shorts",
  "tags": ["6-10 tags"],
  "scenes": [
    {{
      "n": 1,
      "title": "2-4 word label",
      "narration": "8-30 words",
      "visual_mode": "broll | ai_image | kinetic | stat | card | map | glass",
      "search_terms": ["concrete visual term", "alternative", "broader fallback"],
      "ai_prompt": "text-to-image prompt (only for ai_image, else empty)",
      "kinetic_text": "3-6 word punch phrase (only for kinetic, else empty)",
      "forbidden_visuals-note": "also return a top-level \"forbidden_visuals\" array: 3-6 ENGLISH phrases of footage that would break this premise (e.g. 'scuba diver', 'oxygen tank')",
      "stat": {{"value": 0, "suffix": "", "label": "", "max": null, "baseline": null, "bars": [{{"label": "short label", "value": 0}}]}},
      "card": {{"kicker": "category", "headline": "short headline", "body": "under 12 words"}},
      "glass": {{"kicker": "category", "headline": "short Hindi line", "body": "under 10 words", "value": null, "suffix": "", "label": "", "delta": null, "delta_direction": "up | down | flat", "location": "", "coordinates": "", "chapter": ""}}
    }}
  ]
}}

Shorts rules:
- SCENARIO LOCK (scientific integrity — highest priority): if the topic is a
  hypothetical with multiple interpretations (e.g. "oxygen disappears" could
  mean atmospheric O₂ gas vanishing OR every oxygen atom vanishing from water,
  rock and concrete), CHOOSE EXACTLY ONE interpretation in scene 1 and derive
  every consequence from that one scenario only. Never mix consequences across
  interpretations (atmospheric-O₂ loss does NOT turn concrete to dust). When
  it sharpens the hook, state the boundary explicitly ("सिर्फ हवा की ऑक्सीजन —
  10 सेकंड के लिए"). Honest consequences of the chosen scenario are dramatic
  enough.
- VISUAL VARIETY: each scene's search_terms must name a DIFFERENT concrete
  subject — no two consecutive scenes may depict the same subject (never two
  scenes of the same distressed person). The viewer sees a new image every
  ~3 seconds.
- {scfg.get('scenes_min', 4)}-{scfg.get('scenes_max', 6)} micro-scenes. ONE idea total.
  HARD CAP: ~{words} spoken words across the whole script — if over, cut
  adjectives and merge scenes. Shorter beats complete.
- Scene 1 = the hook: <= 12 words, the single most jolting fact/question.
  No greetings, no context, no "did you know".
- PAYOFF + LOOP (critical): the middle scenes must FULLY deliver what the
  hook promises — never withhold the core answer; a viewer who watches once
  must feel they got the complete story. THEN the final scene (8-15 words)
  opens a NEW, related tension instead of concluding. Banned: "...prove
  that", "so next time", "that's why" (and their Hindi equivalents:
  "...साबित करते हैं", "तो अगली बार", "इसीलिए"). Best version: the last line
  is a complete thought that ALSO ends on a connective ("जानने के लिए...",
  "और अगर...") which grammatically flows into the hook line on replay, so
  the loop reads as one continuous sentence — but it must never feel like
  the video was cut off mid-sentence.
- Exactly 1-2 "kinetic" scenes, 0-1 "stat", 0-{short_ai_max} "ai_image"
  (put an ai_image on the hook when the topic's strongest visual doesn't
  exist as stock), rest "broll".
- A stat may add max (ring gauge), baseline (before/after) or 2-4 bars. Keep a
  bare value/suffix/label for the original punchy big-number treatment.
- 0-1 "card" scene may replace a broll scene when a definition, warning or
  comparison communicates the idea faster. Keep all card text extremely short.
- 0-1 "glass" scene may replace a stat/card beat for the hook or payoff. Use
  only one focal number or one short fact; never stack multiple facts in it.
- SEARCH TERM DISCIPLINE (footage relevance depends on this):
  * Every term must belong to the TOPIC'S OWN VISUAL WORLD. If the topic is
    polar, terms are "glacier calving aerial", "arctic tundra", "ice sheet
    drone" — never generic ice cubes or drinks.
  * NEVER metaphorical, studio, or commercial-looking imagery: no beverages,
    food, offices, hands, product shots.
  * Wildlife must look WILD: add "wild"/"aerial"/"natural habitat" to animal
    terms; zoo or enclosure footage is forbidden.
  * Prefer vertical-friendly subjects (waterfalls, cliffs, towers, canyons,
    aurora, drone descents).
  * If narration names a real landmark, machine, animal or anatomical part,
    search_terms[0] MUST name that exact subject. If exact footage is unlikely,
    rewrite the narration generically instead of showing a misleading substitute.
- Every sentence must earn its half-second. Cut every filler word."""

    for attempt in range(3):
        try:
            script = _normalize(_parse_json(_llm(prompt, cfg, api_key)), 3)
            script["topic"] = topic
            script = _critique(script, cfg, api_key, "short", 3)
            print(f"[script] SHORT '{script['title']}' — "
                  f"{[s['visual_mode'] for s in script['scenes']]}")
            return script
        except (KeyError, AssertionError, json.JSONDecodeError) as e:
            print(f"[script] invalid short JSON (attempt {attempt + 1}): {e}")
    raise RuntimeError("Could not obtain a valid short script after 3 attempts")


def log_topic_done(topic: str, done_file: str = "topics_done.txt") -> None:
    with open(done_file, "a", encoding="utf-8") as f:
        f.write(topic + "\n")
