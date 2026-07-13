"""Stage 2.5 — the canon gate. Channel 1's factcheck, inverted.

Channel 1 asked: "is this claim TRUE?"
Channel 2 cannot ask that — the place is invented. So it asks the two questions
that actually protect this channel:

  1. CANON     — does this script contradict the world? (deterministic, free:
                 pipeline/canon.py)
  2. SCIENCE   — is every MECHANISM real? A fictional setting is the promise;
                 a fabricated mechanism is a lie. "The place is fictional; the
                 principles are real" is either true in every episode or the
                 channel is worthless.

This runs BEFORE TTS, so a canon break costs nothing but a retry, and a
DRAFT-DO-NOT-PUBLISH release never reaches the channel by accident.
"""
from __future__ import annotations

import json
import os

import requests

import canon as canon_mod

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _gemini_search(prompt: str, cfg: dict, api_key: str) -> str:
    """Gemini with Google Search grounding — the same free-tier call channel 1
    uses to verify claims, pointed at mechanisms instead of facts."""
    models = [cfg["llm"]["model"]] + list(cfg["llm"].get("fallback_models", []))
    last = None
    for model in models:
        url = f"{API_BASE}/{model}:generateContent?key={api_key}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.2},
        }
        try:
            r = requests.post(url, json=body, timeout=120)
            if r.status_code >= 400:
                last = r.text[:200]
                continue
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except requests.RequestException as e:
            last = str(e)
    raise RuntimeError(f"canon_check: search call failed ({last})")


def _science_review(script: dict, canon: dict, cfg: dict, api_key: str) -> list[dict]:
    """Ask a searching model whether each mechanism has a real Earth analogue.

    Fail-open by design: this stage NEVER kills a run on its own error. It
    either produces findings or it produces nothing.
    """
    ph = canon["physics"]
    mechanisms = {
        "systems": script.get("systems", []),
        "hidden_dependency": script.get("hidden_dependency", ""),
        "stress_event": script.get("stress_event", {}),
        "verdict_reason": script.get("verdict_reason", ""),
        "claimed_real_world_basis": script.get("real_world_basis", []),
    }
    prompt = f"""You are the science reviewer for a speculative documentary.

The SETTING is openly fictional and is NOT under review. Do not flag the planet,
the settlement or the organisms for being invented — that is the premise, and
the audience is told so in the first ten seconds.

What IS under review: every MECHANISM must be physically real. The channel's
promise is "the place is fictional; the principles are real". A mechanism with
no real-world analogue is the one unforgivable error here.

THE PLANET'S FIXED PHYSICS (treat as given, check consistency AGAINST them):
- Star: {ph['star']['type']}, {ph['star']['luminosity_solar']} solar luminosity
- Gravity: {ph['gravity_g']} g
- Day: {ph['day_length_hours']} hours
- Atmosphere: {ph['atmosphere']['pressure_bar']} bar, {ph['atmosphere']['composition']}

THE EPISODE'S MECHANISMS:
{json.dumps(mechanisms, indent=2)}

FULL NARRATION:
{json.dumps([s['narration'] for s in script['scenes']], indent=2)}

For each mechanism, search and decide:
- "grounded"    — a real Earth phenomenon, material behaviour or engineering
                  failure mode supports it. NAME it and cite a source.
- "unsupported" — plausible-sounding but you can find nothing real behind it.
- "wrong"       — it contradicts physics, chemistry, biology, or this planet's
                  own constants (e.g. convective cooling numbers that assume
                  1 bar; an organism metabolising something unavailable here;
                  a thermal budget that ignores a 31-hour day).

Severity: "high" if the episode's CENTRAL mechanism (the hidden dependency, the
cascade, or the verdict) is unsupported or wrong — that breaks the whole
episode. "low" if it is decorative colour.

Return ONLY JSON:
{{"findings": [{{"mechanism": "...", "status": "grounded|unsupported|wrong",
"severity": "high|low", "real_analogue": "the actual Earth phenomenon, or empty",
"source": "url or publication", "fix": "one-line correction if not grounded"}}]}}"""
    try:
        raw = _gemini_search(prompt, cfg, api_key)
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        start = raw.find("{")
        parsed = json.loads(raw[start:raw.rfind("}") + 1])
        return parsed.get("findings", [])[:int(
            cfg.get("canon_check", {}).get("max_claims", 12))]
    except Exception as e:
        print(f"[canon_check] science review skipped ({e}) — advisory only")
        return []


def check_script(script: dict, cfg: dict, api_key: str,
                 repo_root: str = ".") -> dict:
    """Returns a report dict; run.py gates the release on report['status']."""
    ccfg = cfg.get("canon_check", {})
    report = {"status": "OK", "canon": [], "science": [], "checked": 0}
    if not ccfg.get("enabled", True):
        report["status"] = "SKIPPED"
        return report

    world = canon_mod.load(repo_root)

    # 1. canon — deterministic, free, and the one that catches drift
    if ccfg.get("check_canon", True):
        report["canon"] = canon_mod.validate(script, world, cfg)

    # 2. science — the credibility promise
    if ccfg.get("check_science", True) and api_key:
        report["science"] = _science_review(script, world, cfg, api_key)

    report["checked"] = len(report["canon"]) + len(report["science"])

    high_canon = [v for v in report["canon"] if v["severity"] == "high"]
    bad_science = [f for f in report["science"]
                   if f.get("status") in ("unsupported", "wrong")
                   and f.get("severity") == "high"]

    gate = ccfg.get("gate", "high_risk")
    blocking = bool(high_canon or bad_science)
    if gate is True and (report["canon"] or bad_science):
        report["status"] = "DRAFT-DO-NOT-PUBLISH"
    elif gate == "high_risk" and blocking:
        report["status"] = "DRAFT-DO-NOT-PUBLISH"

    for v in high_canon:
        print(f"[canon_check] CANON BREAK ({v['rule']}): {v['detail']}")
    for f in bad_science:
        print(f"[canon_check] MECHANISM {f['status'].upper()}: "
              f"{f['mechanism']} — {f.get('fix', '')}")
    print(f"[canon_check] {report['checked']} checks · {report['status']}")
    return report


def markdown(report: dict) -> str:
    """Release-notes block — what Dwij reads before pressing publish."""
    if report.get("status") == "SKIPPED":
        return "_Canon check skipped._"
    lines = [f"**Canon check: {report['status']}**", ""]
    if report.get("canon"):
        lines.append("Canon:")
        for v in report["canon"]:
            mark = "❌" if v["severity"] == "high" else "⚠️"
            lines.append(f"- {mark} `{v['rule']}` — {v['detail']}")
    if report.get("science"):
        lines.append("")
        lines.append("Mechanisms:")
        for f in report["science"]:
            mark = {"grounded": "✅", "unsupported": "⚠️",
                    "wrong": "❌"}.get(f.get("status"), "•")
            basis = f.get("real_analogue") or f.get("fix", "")
            src = f" ({f['source']})" if f.get("source") else ""
            lines.append(f"- {mark} {f['mechanism']} — {basis}{src}")
    if not report.get("canon") and not report.get("science"):
        lines.append("_No findings._")
    return "\n".join(lines)
